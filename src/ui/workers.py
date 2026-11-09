"""后台线程：扫描索引与缩略图渲染（规范 §3-2：耗时操作禁止阻塞 UI 主线程）。"""
from __future__ import annotations

import queue
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from src.core.indexer import Indexer
from src.core.models import SlideFile
from src.render.thumbnail import RenderCache, RenderError
from src.utils.logger import get_logger

logger = get_logger("workers")


class ScanWorker(QThread):
    """递归扫描+增量索引（独立 SQLite 连接，避免跨线程使用）。"""

    done = Signal(object, object)  # (list[SlideFile], ScanStats)
    failed = Signal(str)

    def __init__(self, root: Path, db_path: Path | None = None, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.db_path = db_path

    def run(self) -> None:
        try:
            with Indexer(self.db_path) as idx:
                stats = idx.sync_scan(self.root)
                files = idx.get_all_files()
            self.done.emit(files, stats)
        except Exception as e:  # noqa: BLE001（后台线程兜底，禁止静默崩溃）
            logger.error("扫描线程失败：%s", e)
            self.failed.emit(str(e))


class ThumbWorker(QThread):
    """逐文件渲染 256px 缩略图；主线程通过队列投递任务，信号回传结果。"""

    thumb_ready = Signal(str, str)  # (ppt 绝对路径, png 路径)
    thumb_failed = Signal(str)  # (ppt 绝对路径) —— UI 侧显示“转换失败”角标

    def __init__(self, cache_root: Path | None = None, cache_limit_mb: int = 2048, parent=None):
        super().__init__(parent)
        self._queue: queue.Queue[Path] = queue.Queue()
        self._stop = False
        self._cache_root = cache_root
        self._cache_limit_mb = cache_limit_mb
        self._cache: RenderCache | None = None

    def enqueue(self, ppt_path: Path) -> None:
        self._queue.put(Path(ppt_path))

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        self._cache = RenderCache(root=self._cache_root)
        while not self._stop:
            try:
                ppt = self._queue.get(timeout=0.3)
            except queue.Empty:
                continue
            try:
                png = self._cache.thumb(ppt, 0)
                self.thumb_ready.emit(str(ppt), str(png))
            except RenderError as e:
                logger.warning("缩略图失败（角标）：%s，%s", ppt.name, e)
                self.thumb_failed.emit(str(ppt))
            except Exception as e:  # noqa: BLE001（单文件失败不影响其他）
                logger.error("缩略图异常：%s，%s", ppt.name, e)
                self.thumb_failed.emit(str(ppt))
            try:
                self._cache.enforce_limit(self._cache_limit_mb)
            except OSError:
                pass
