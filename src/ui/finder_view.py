"""内容区：图标视图（缩略图网格）/ 列表视图 + 面包屑。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QWidget

from src.core.models import SlideFile

ROLE_PATH = Qt.ItemDataRole.UserRole + 1
ROLE_IS_DIR = Qt.ItemDataRole.UserRole + 2

_FAILED_PNG: QPixmap | None = None


def failed_badge_icon() -> QIcon:
    """“转换失败”角标图标（红底白字，懒生成一次）。"""
    global _FAILED_PNG
    if _FAILED_PNG is None:
        pm = QPixmap(128, 128)
        pm.fill(QColor("#b91c1c"))
        painter = QPainter(pm)
        painter.setPen(QColor("white"))
        font = QFont()
        font.setPixelSize(20)
        painter.setFont(font)
        painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "转换失败")
        painter.end()
        _FAILED_PNG = pm
    return QIcon(pm)


class BreadcrumbBar(QWidget):
    """面包屑：主目录段可点击逐级导航。"""

    segment_clicked = Signal(str)  # 点击段对应的绝对路径

    def __init__(self, root: Path, parent=None):
        super().__init__(parent)
        self._root = root
        self._layout = None
        self.rebuild(root)

    def rebuild(self, path: Path) -> None:
        from PySide6.QtWidgets import QHBoxLayout

        if self._layout is not None:
            while self._layout.count():
                item = self._layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            self._layout = QHBoxLayout(self)
            self._layout.setContentsMargins(4, 0, 4, 0)
            self._layout.setSpacing(0)

        path = Path(path).resolve()
        root = Path(self._root).resolve()
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            rel_parts = ()
        segments = [(root.name, str(root))]
        current = root
        for part in rel_parts:
            current = current / part
            segments.append((part, str(current)))

        for i, (name, seg_path) in enumerate(segments):
            if i > 0:
                sep = QLabel(" › ")
                self._layout.addWidget(sep)
            btn = QLabel(name)
            btn.setStyleSheet("QLabel { padding: 2px 4px; border-radius: 4px; }")
            btn.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            def _make_click(p: str):
                def onClick(_event=None, p=p):
                    self.segment_clicked.emit(p)
                return onClick

            btn.mousePressEvent = _make_click(seg_path)  # type: ignore[method-assign]
            self._layout.addWidget(btn)
            if i == len(segments) - 1:
                btn.setStyleSheet("QLabel { padding: 2px 4px; font-weight: bold; }")
        self._layout.addStretch(1)


class FinderView(QListWidget):
    """图标/列表双视图内容区。"""

    open_dir_requested = Signal(str)      # 双击目录
    open_file_requested = Signal(str)    # 双击文件（P4 接预览）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setWordWrap(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setIconSize(self.sizeHintForIconMode())
        self.itemDoubleClicked.connect(self._on_double_clicked)
        # Enter 键（itemActivated 含双击与回车）→ 双击处理器（F8：Enter=预览）
        self.itemActivated.connect(self._on_double_clicked)

    @staticmethod
    def sizeHintForIconMode() -> object:
        from PySide6.QtCore import QSize

        return QSize(128, 128)

    # ---------- 视图切换 ----------

    def set_icon_mode(self) -> None:
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setGridSize(self._grid_for_mode())

    def set_list_mode(self) -> None:
        self.setViewMode(QListWidget.ViewMode.ListMode)
        self.setGridSize(self._grid_for_mode())

    def _grid_for_mode(self):
        from PySide6.QtCore import QSize

        if self.viewMode() == QListWidget.ViewMode.IconMode:
            return QSize(140, 150)
        return QSize(160, 30)

    # ---------- 填充 ----------

    def populate(self, dirs: list[Path], files: list[SlideFile]) -> None:
        self.clear()
        style = self.style()
        folder_icon = style.standardIcon(style.StandardPixmap.SP_DirIcon)
        for d in dirs:
            item = QListWidgetItem(folder_icon, d.name)
            item.setData(ROLE_PATH, str(d))
            item.setData(ROLE_IS_DIR, True)
            self.addItem(item)
        for sf in files:
            item = QListWidgetItem(sf.name)
            item.setData(ROLE_PATH, str(sf.path))
            item.setData(ROLE_IS_DIR, False)
            self.addItem(item)

    def set_thumb(self, ppt_path: str, png_path: str) -> None:
        for i in range(self.count()):
            item = self.item(i)
            if item.data(ROLE_PATH) == ppt_path and not item.data(ROLE_IS_DIR):
                item.setIcon(QIcon(png_path))
                return

    def mark_failed(self, ppt_path: str) -> None:
        for i in range(self.count()):
            item = self.item(i)
            if item.data(ROLE_PATH) == ppt_path and not item.data(ROLE_IS_DIR):
                item.setIcon(failed_badge_icon())
                return

    def current_path(self) -> str | None:
        item = self.currentItem()
        return item.data(ROLE_PATH) if item else None

    # ---------- 内部 ----------

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(ROLE_PATH)
        if item.data(ROLE_IS_DIR):
            self.open_dir_requested.emit(path)
        else:
            self.open_file_requested.emit(path)
