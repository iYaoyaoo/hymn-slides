"""放映窗：无边框全屏、1920px 放映页、键盘翻页（F6）。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.utils.logger import get_logger

logger = get_logger("projection")


class ProjectionWindow(QWidget):
    """无边框全屏放映窗（置于指定屏幕）。

    页面图片经 PageRenderWorker.request_show 异步渲染（1920px，缓存）。
    """

    page_changed = Signal(int)   # 翻页后当前页（0 起）
    show_ended = Signal()        # 放映结束（Esc 或拔屏）

    def __init__(self, worker, ppt: Path, page: int = 0, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._ppt = Path(ppt)
        self._page = 0
        self._requested_page = -1
        self._total = 0
        self._target_screen = None

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)

        worker.show_ready.connect(self._on_show_ready)
        worker.count_ready.connect(self._on_count_ready)
        worker.request_count(self._ppt)

    # ---------- 屏幕 ----------

    def show_on_screen(self, screen) -> None:
        """全屏置于指定 QScreen（仅按几何，不假设身份）。"""
        self._target_screen = screen
        if screen is not None:
            self.setGeometry(screen.geometry())
            from PySide6.QtGui import QScreen

            if isinstance(screen, QScreen):
                self.setScreen(screen)
        self.showFullScreen()
        self.activateWindow()
        self._load_page(self._page)

    def current_screen(self):
        return self._target_screen

    # ---------- 页面 ----------

    def _on_count_ready(self, ppt: str, count: int) -> None:
        if str(self._ppt) == ppt:
            self._total = count

    def _load_page(self, page: int) -> None:
        if self._total and not (0 <= page < self._total):
            return
        self._requested_page = page
        self.image_label.setText(f"加载中…（第 {page + 1} 页）")
        self._worker.request_show(self._ppt, page)

    def go_to(self, page: int) -> None:
        """外部（演示者窗）请求跳页。"""
        self._load_page(page)

    def next_page(self) -> None:
        self._load_page(self._page + 1)

    def prev_page(self) -> None:
        self._load_page(self._page - 1)

    def _on_show_ready(self, ppt: str, page: int, png: str) -> None:
        if str(self._ppt) != ppt or page != self._requested_page:
            return
        self._page = page
        pm = QPixmap(png)
        pm = pm.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(pm)
        self.page_changed.emit(page)

    # ---------- 键盘（F8） ----------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp, Qt.Key.Key_Space):
            if self._page > 0:
                self._load_page(self._page - 1)
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            if self._total == 0 or self._page < self._total - 1:
                self._load_page(self._page + 1)
        elif key == Qt.Key.Key_Escape:
            self.end_show()
        else:
            super().keyPressEvent(event)

    def end_show(self) -> None:
        """结束放映（Esc / 拔屏）。"""
        logger.info("放映结束：%s", self._ppt.name)
        self.show_ended.emit()
        self.close()
