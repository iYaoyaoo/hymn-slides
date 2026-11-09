"""左侧目录树（QFileSystemModel 目录过滤，根=主目录）。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir, Signal
from PySide6.QtWidgets import QFileSystemModel, QTreeView


class SidebarTree(QTreeView):
    dir_clicked = Signal(str)

    def __init__(self, root: Path, parent=None):
        super().__init__(parent)
        self._model = QFileSystemModel(self)
        self._model.setFilter(
            QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.NoSymLinks | ~QDir.Filter.Hidden
        )
        self.setModel(self._model)
        for col in range(1, 4):
            self.hideColumn(col)
        self.setHeaderHidden(True)
        self.clicked.connect(self._on_clicked)
        self.setRoot(root)

    def setRoot(self, root: Path) -> None:
        self._root = Path(root)
        idx = self._model.setRootPath(str(root))
        self.setRootIndex(idx)

    def _on_clicked(self, index) -> None:
        path = self._model.filePath(index)
        if path:
            self.dir_clicked.emit(path)
