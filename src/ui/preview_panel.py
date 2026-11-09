"""预览：右侧逐页缩略图面板（懒加载）+ 全屏预览（←→翻页，Esc 退出，F11）。

懒加载策略：先探测页数；每次只渲染已滚入视野附近的页（可见窗口 + 前后 5 页）。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

LAZY_WINDOW = 5  # 当前视野前后各加载的页数


class PreviewPanel(QWidget):
    """右侧面板：给定 PPT，逐页 256px 缩略图（懒加载）。"""

    page_double_clicked = Signal(str, int)  # (ppt, 页码) —— 双击某页 → 全屏预览该页

    def __init__(self, worker=None, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._ppt: Path | None = None
        self._page_count = 0
        self._loaded_pages: set[int] = set()
        self._enqueued_pages: set[int] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status_label = QLabel("选择文件查看预览")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setGridSize(QSize(120, 110))
        self.list.setIconSize(QSize(100, 75))
        self.list.setWordWrap(False)
        self.list.itemDoubleClicked.connect(self._on_double_clicked)
        self.list.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self.status_label)
        layout.addWidget(self.list)

        if worker is not None:
            self.set_worker(worker)

    def set_worker(self, worker) -> None:
        self._worker = worker
        worker.count_ready.connect(self._on_count_ready)
        worker.page_ready.connect(self._on_page_ready)

    # ---------- 公共 ----------

    def set_file(self, ppt: Path | None) -> None:
        if ppt is None:
            self._ppt = None
            self._page_count = 0
            self._loaded_pages.clear()
            self._enqueued_pages.clear()
            self.list.clear()
            self.status_label.setText("选择文件查看预览")
            return
        if Path(ppt) == self._ppt:
            return
        self._ppt = Path(ppt)
        self._page_count = 0
        self._loaded_pages.clear()
        self._enqueued_pages.clear()
        self.list.clear()
        self.status_label.setText("转换中…")
        self._worker.request_count(self._ppt)

    # ---------- worker 回调 ----------

    def _on_count_ready(self, ppt: str, count: int) -> None:
        if self._ppt is None or str(self._ppt) != ppt:
            return
        self._page_count = count
        self.status_label.setText(f"{self._ppt.name}（{count} 页）")
        for i in range(count):
            item = QListWidgetItem(f"第 {i + 1} 页")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(item)
        self._enqueue_visible()

    def _on_page_ready(self, ppt: str, page: int, png: str) -> None:
        if self._ppt is None or str(self._ppt) != ppt:
            return
        self._loaded_pages.add(page)
        if 0 <= page < self.list.count():
            self.list.item(page).setIcon(QPixmap(png))

    # ---------- 懒加载 ----------

    def _visible_range(self) -> tuple[int, int]:
        if self._page_count == 0:
            return (0, -1)
        bar = self.list.verticalScrollBar()
        per_row = max(1, self.list.width() // max(1, self.list.gridSize().width()))
        top = bar.value()
        height_pages = max(1, self.list.viewport().height() // max(1, self.list.gridSize().height()))
        start = max(0, int(top / max(1, self.list.gridSize().height())) * per_row - LAZY_WINDOW)
        end = min(self._page_count - 1, (int(top / max(1, self.list.gridSize().height())) + height_pages) * per_row + LAZY_WINDOW)
        return (start, end)

    def _enqueue_visible(self) -> None:
        if self._ppt is None or self._page_count == 0:
            return
        start, end = self._visible_range()
        for p in range(start, end + 1):
            if p not in self._loaded_pages and p not in self._enqueued_pages:
                self._enqueued_pages.add(p)
                self._worker.request_page(self._ppt, p)

    def _on_scroll(self, _value: int) -> None:
        self._enqueue_visible()

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        if self._ppt is not None:
            self.page_double_clicked.emit(str(self._ppt), int(item.data(Qt.ItemDataRole.UserRole)))


class FullscreenPreview(QDialog):
    """全屏预览：←→/Space/PgUp/PgDn 翻页，Esc 退出。"""

    def __init__(self, worker, ppt: Path, page: int = 0, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._ppt = Path(ppt)
        self._page = 0
        self._requested_page = -1
        self._total = 0
        self._navigating = True  # 有多页才启用翻页

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.image_label = QLabel("加载中…")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: black; color: white;")
        layout.addWidget(self.image_label)

        worker.show_ready.connect(self._on_show_ready)
        worker.count_ready.connect(self._on_count_ready)
        worker.request_count(self._ppt)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.showFullScreen()
        self._load_page(self._page)

    def _on_count_ready(self, ppt: str, count: int) -> None:
        if str(self._ppt) == ppt:
            self._total = count
            self._navigating = count > 1

    def _load_page(self, page: int) -> None:
        if self._total and not (0 <= page < self._total):
            return
        self._requested_page = page
        self.image_label.setText(f"加载中…（第 {page + 1} 页）")
        self._worker.request_show(self._ppt, page)

    def _on_show_ready(self, ppt: str, page: int, png: str) -> None:
        if str(self._ppt) != ppt or page != self._requested_page:
            return
        self._page = page
        pm = QPixmap(png)
        screen = self.screen() if self.screen() is not None else None
        if screen is not None:
            pm = pm.scaled(screen.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(pm)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp, Qt.Key.Key_Space):
            if self._navigating and self._page > 0:
                self._load_page(self._page - 1)
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            if self._navigating and (self._total == 0 or self._page < self._total - 1):
                self._load_page(self._page + 1)
        elif key == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
