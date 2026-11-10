"""后台线程：扫描索引与页面渲染（规范 §3-2：耗时操作禁止阻塞 UI 主线程）。

v4.1 修复（大目录首扫）：元数据同步完成立即发 tree_ready（树秒出），
全文提取降为后台任务并行执行（FULLTEXT_WORKERS 路，每线程独立 LO profile），
单文件失败仅记录不中断；只处理主目录下的文件。
"""
from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from src.core.indexer import Indexer
from src.core.models import SlideFile
from src.render.engine import EngineChain
from src.render.thumbnail import RenderCache, RenderError
from src.utils.logger import get_logger

logger = get_logger("workers")

FULLTEXT_WORKERS = 3  # 并行 LibreOffice 实例数（每线程独立 profile）

_TLS = threading.local()


def _thread_cache() -> RenderCache:
    """线程本地 RenderCache（各自独立引擎链与 LO profile，支持并行转换）。"""
    if not hasattr(_TLS, "cache"):
        _TLS.cache = RenderCache()
    return _TLS.cache


class ScanWorker(QThread):
    """递归扫描+增量索引；全文回填为后台并行任务（不阻塞树展示）。"""

    tree_ready = Signal(object, object)  # (list[SlideFile], ScanStats) —— 元数据就绪，树立即可用
    done = Signal(object, object)  # 全文回填完成后的最终文件列表
    progress = Signal(int, int)  # (已回填, 需回填)
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
                files = idx.get_all_files()
            # 元数据就绪：立即让树可用（修复"首次打开树空白"）
            self.tree_ready.emit(files, stats)
            if self.fulltext:
                self._fulltext_pass()
                with Indexer(self.db_path) as idx2:
                    files = idx2.get_all_files()
            self.done.emit(files, stats)
        except Exception as e:  # noqa: BLE001（后台线程兜底，禁止静默崩溃）
            logger.error("扫描线程失败：%s", e)
            self.failed.emit(str(e))

    # ---------- 全文回填（并行） ----------

    def _pending_rows(self, idx: Indexer) -> list[tuple[int, str]]:
        """主目录下尚未提取文字的文件。"""
        rows = idx._conn.execute(
            "SELECT id, path FROM files WHERE page_count IS NULL"
        ).fetchall()
        return [(fid, p) for fid, p in rows if self._under_root(p)]

    def _under_root(self, path_str: str) -> bool:
        try:
            return Path(path_str).is_relative_to(self.root)
        except (ValueError, OSError):
            return False

    def _fulltext_pass(self) -> None:
        with Indexer(self.db_path) as idx:
            rows = self._pending_rows(idx)
            total = len(rows)
            if total == 0:
                return
            logger.info("全文回填开始：%d 个文件，%d 路并行", total, FULLTEXT_WORKERS)

            def extract(path_str: str):
                """转换+提取（线程内，独立 LO profile）；返回 (texts, error)。"""
                try:
                    return _thread_cache().slide_texts(Path(path_str)), None
                except Exception as e:  # noqa: BLE001（单文件失败仅记录，不中断整体）
                    return None, str(e)

            done_count = 0
            with ThreadPoolExecutor(max_workers=FULLTEXT_WORKERS) as pool:
                futures = {pool.submit(extract, p): (fid, p) for fid, p in rows}
                for fut in as_completed(futures):
                    fid, path_str = futures[fut]
                    texts, err = fut.result()
                    if err is not None:
                        logger.warning("全文提取失败（跳过）：%s，%s", path_str, err)
                    else:
                        try:
                            idx.upsert_slide_texts(fid, texts)
                            idx.set_page_count(fid, len(texts))
                        except Exception as e:  # noqa: BLE001
                            logger.error("全文入库失败：%s，%s", path_str, e)
                    done_count += 1
                    self.progress.emit(done_count, total)
            logger.info("全文回填完成：%d 个文件", total)


class PageRenderWorker(QThread):
    """按需渲染：页数探测 / 1920px 放映页（LO 投影窗路径）。主线程以队列投递。

    v4.2 取消预览：256px 缩略图通道（page_ready/request_page）已移除，
    演示者窗为纯文字视图。
    """

    count_ready = Signal(str, int)  # (ppt, 页数)
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
                elif kind == "show":
                    png = self._cache.show_page(ppt, req[2])
                    self.show_ready.emit(str(ppt), req[2], str(png))
            except RenderError as e:
                logger.warning("页面渲染失败：%s 第 %s 页，%s", ppt.name, req[2] if len(req) > 2 else "?", e)
                self.page_failed.emit(str(ppt), req[2] if len(req) > 2 else -1)
            except Exception as e:  # noqa: BLE001
                logger.error("页面渲染异常：%s，%s", ppt.name, e)
                self.page_failed.emit(str(ppt), req[2] if len(req) > 2 else -1)
