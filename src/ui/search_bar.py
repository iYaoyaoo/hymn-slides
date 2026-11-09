"""搜索：300ms 防抖 + 文件名/全文结果面板（规范 F4）。

SearchBar 持有 QLineEdit 与防抖 QTimer；SearchResultsPanel 双击定位并选中。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget

from src.core.models import SearchResult

DEBOUNCE_MS = 300


class SearchBar(QWidget):
    """防抖搜索逻辑：textChanged → 300ms 后触发搜索回调。"""

    def __init__(self, edit, on_search, parent=None):
        super().__init__(parent)
        self._edit = edit
        self._on_search = on_search
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(self._fire)
        edit.textChanged.connect(self._restart)

    def _restart(self) -> None:
        self._timer.start()

    def _fire(self) -> None:
        self._on_search(self._edit.text())

    def trigger_now(self) -> None:
        """立即触发（测试/程序化调用）。"""
        self._timer.stop()
        self._on_search(self._edit.text())


class SearchResultsPanel(QListWidget):
    """搜索结果面板：双击 → locate_requested(path, page)。"""

    locate_requested = Signal(str, int)  # (ppt 绝对路径, 页码或 -1)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.itemDoubleClicked.connect(self._on_double_clicked)

    def show_results(self, results: list[SearchResult], keyword: str) -> None:
        self.clear()
        for r in results:
            label = r.name if r.page is None else f"{r.name} · 第 {r.page} 页"
            item = QListWidgetItem(label)
            item.setToolTip(r.snippet or r.path)
            item.setData(0x0100, r.path)       # Qt.UserRole+0
            item.setData(0x0101, r.page if r.page is not None else -1)
            self.addItem(item)
        self.setVisible(len(results) > 0)

    def hide_panel(self) -> None:
        self.clear()
        self.setVisible(False)

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        self.locate_requested.emit(item.data(0x0100), int(item.data(0x0101)))
