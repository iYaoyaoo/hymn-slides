"""后台线程：扫描索引与页面渲染（规范 §3-2：耗时操作禁止阻塞 UI 主线程）。"""
from __future__ import annotations

import queue
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from src.core.indexer import Indexer
from src.core.models import SlideFile
from src.render.engine import EngineChain
from src.render.thumbnail import RenderCache, RenderError
from src.utils.logger import get_logger

logger = get_logger("workers")


class ScanWorker(QThread):
    """递归扫描+增量索引+全文回填（未提取过文字的文件转换 PDF 并提取）。"""

    done = Signal(object, object)  # (list[SlideFile], ScanStats)
    progress = Signal(int, int)  # (已回填, 需回填) —— 全文转换进度
    failed = Signal(str)

    def __init__(self, root: Path, db_path: Path | None = None, fulltext: bool = True, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.db_path = db_path
        self.fulltext = fulltext

    def run(self) -> None:
        try:
            with Indexer(self.db_path) as idx:
                stats = idx.sync_scan(self.root)
                if self.fulltext:
                    cache = RenderCache()
                    rows = idx._conn.execute(
                        "SELECT id, path FROM files WHERE page_count IS NULL"
                    ).fetchall()
                    total = len(rows)
                    for i, (fid, path_str) in enumerate(rows):
                        try:
                            from src.render.thumbnail import refresh_index_fulltext

                            refresh_index_fulltext(Path(path_str), idx, cache)
                        except RenderError as e:
                            logger.warning("全文回填失败（跳过）：%s，%s", path_str, e)
                        self.progress.emit(i + 1, total)
                files = idx.get_all_files()
            self.done.emit(files, stats)
        except Exception as e:  # noqa: BLE001（后台线程兜底，禁止静默崩溃）
            logger.error("扫描线程失败：%s", e)
            self.failed.emit(str(e))


class PageRenderWorker(QThread):
    """按需渲染：页数探测 / 256px 页缩略 / 1920px 放映页。主线程以队列投递。"""

    count_ready = Signal(str, int)  # (ppt, 页数)
    page_ready = Signal(str, int, str)  # (ppt, 页码, png)
    show_ready = Signal(str, int, str)  # (ppt, 页码, png)
    page_failed = Signal(str, int)  # (ppt, 页码)

    def __init__(self, cache_root: Path | None = None, parent=None):
        super().__init__(parent)
        self._queue: queue.Queue[tuple] = queue.Queue()
        self._stop = False
        self._cache_root = cache_root
        self._cache: RenderCache | None = None

    def request_count(self, ppt_path: Path) -> None:
        self._queue.put(("count", Path(ppt_path)))

    def request_page(self, ppt_path: Path, page: int) -> None:
        self._queue.put(("page", Path(ppt_path), page))

    def request_show(self, ppt_path: Path, page: int) -> None:
        self._queue.put(("show", Path(ppt_path), page))

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        self._cache = RenderCache(root=self._cache_root)
        while not self._stop:
            try:
                req = self._queue.get(timeout=0.3)
            except queue.Empty:
                continue
            kind = req[0]
            ppt = req[1]
            try:
                if kind == "count":
                    self.count_ready.emit(str(ppt), self._cache.page_count(ppt))
                elif kind == "page":
                    png = self._cache.thumb(ppt, req[2])
                    self.page_ready.emit(str(ppt), req[2], str(png))
                elif kind == "show":
                    png = self._cache.show_page(ppt, req[2])
                    self.show_ready.emit(str(ppt), req[2], str(png))
            except RenderError as e:
                logger.warning("页面渲染失败：%s 第 %s 页，%s", ppt.name, req[2] if len(req) > 2 else "?", e)
                self.page_failed.emit(str(ppt), req[2] if len(req) > 2 else -1)
            except Exception as e:  # noqa: BLE001
                logger.error("页面渲染异常：%s，%s", ppt.name, e)
                self.page_failed.emit(str(ppt), req[2] if len(req) > 2 else -1)
