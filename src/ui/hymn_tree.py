"""诗歌树视图（v4 F2）：类 Mac 访达列表样式，目录+诗歌文件。

能力：扫描结果全量构建；搜索过滤（命中文件+祖先目录链）；一键展开/收起；
文件右键"在文件管理器中显示"（平台分支）；双击文件=放映。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem

from src.core.models import SlideFile

ROLE_PATH = Qt.ItemDataRole.UserRole + 1
ROLE_IS_DIR = Qt.ItemDataRole.UserRole + 2


def reveal_in_file_manager(path: Path) -> None:
    """在文件管理器中显示（F8 平台分支：Windows=explorer /select；macOS=open -R）。"""
    path = Path(path)
    if not path.exists():
        return
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)], check=False)  # noqa: S603
        elif os.name == "nt":
            subprocess.run(["explorer", "/select,", str(path)], check=False)  # noqa: S603
        else:
            subprocess.run(["xdg-open", str(path.parent)], check=False)  # noqa: S603
    except OSError as e:
        from src.utils.logger import get_logger

        get_logger("hymn_tree").warning("在文件管理器中显示失败：%s，%s", path, e)


class HymnTree(QTreeWidget):
    """主界面核心树：目录+诗歌文件。"""

    file_double_clicked = Signal(str)        # 双击文件（=放映，v4 F4）
    reveal_requested = Signal(str)           # 右键菜单：在文件管理器中显示

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(20)
        self.setUniformRowHeights(True)
        self.setExpandsOnDoubleClick(False)  # 双击目录不折叠，双击文件触发放映
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.itemDoubleClicked.connect(self._on_double_clicked)
        self._root_name = "诗歌目录"
        self._root_path = ""
        self._dir_items: dict[str, QTreeWidgetItem] = {}

    # ---------- 构建 ----------

    def load_files(self, root: Path, files: list[SlideFile]) -> None:
        """按扫描结果全量重建树（目录随文件路径创建；仅含诗歌文件的目录显示）。"""
        selected = self.selected_file()
        expanded_dirs = {
            self._path_of(self.topLevelItem(i)) for i in range(self.topLevelItemCount())
        }
        self.clear()

        self._root_path = str(root)
        self._root_name = root.name or "诗歌目录"
        root_item = QTreeWidgetItem([self._root_name])
        root_item.setData(0, ROLE_PATH, str(root))
        root_item.setData(0, ROLE_IS_DIR, True)
        self.addTopLevelItem(root_item)

        self._dir_items: dict[str, QTreeWidgetItem] = {str(root): root_item}

        def ensure_dir(d: Path) -> QTreeWidgetItem:
            key = str(d)
            if key in self._dir_items:
                return self._dir_items[key]
            # 构建顺序自根向下：父级目录必然已注册
            parent_item = self._dir_items.get(str(d.parent), root_item)
            item = QTreeWidgetItem([d.name])
            item.setData(0, ROLE_PATH, key)
            item.setData(0, ROLE_IS_DIR, True)
            parent_item.addChild(item)
            self._dir_items[key] = item
            return item

        for sf in sorted(files, key=lambda f: f.rel_path):
            parts = Path(sf.rel_path).parts[:-1]
            parent_item = root_item
            acc = root
            for part in parts:
                acc = acc / part
                parent_item = ensure_dir(acc)
            file_item = QTreeWidgetItem([sf.name])
            file_item.setData(0, ROLE_PATH, str(sf.path))
            file_item.setData(0, ROLE_IS_DIR, False)
            parent_item.addChild(file_item)

        # 恢复展开/选中
        for d in expanded_dirs:
            item = self._dir_items.get(d)
            if item is not None:
                item.setExpanded(True)
        if selected:
            self.select_file(selected)

    # ---------- 过滤（v4 F3：命中文件+祖先链） ----------

    def apply_filter(self, keep_paths: set[str] | None) -> int:
        """None=显示全部；否则仅保留命中文件及其祖先目录链。返回可见文件数。"""
        if keep_paths is None:
            for i in range(self.topLevelItemCount()):
                self._set_subtree_hidden(self.topLevelItem(i), False)
            return self.visible_file_count()

        visible_files: set[str] = set()
        for i in range(self.topLevelItemCount()):
            visible_files |= self._filter_subtree(self.topLevelItem(i), keep_paths)
        return len(visible_files)

    def _filter_subtree(self, item: QTreeWidgetItem, keep: set[str]) -> set[str]:
        """递归过滤：返回该子树保留下来的文件路径集合。"""
        path = item.data(0, ROLE_PATH)
        is_dir = bool(item.data(0, ROLE_IS_DIR))
        if not is_dir:
            keep_it = path in keep
            item.setHidden(not keep_it)
            return {path} if keep_it else set()
        kept: set[str] = set()
        for i in range(item.childCount()):
            kept |= self._filter_subtree(item.child(i), keep)
        item.setHidden(not kept)
        item.setExpanded(bool(kept))  # 命中时自动展开祖先链
        return kept

    def _set_subtree_hidden(self, item: QTreeWidgetItem, hidden: bool) -> None:
        item.setHidden(hidden)
        for i in range(item.childCount()):
            self._set_subtree_hidden(item.child(i), hidden)

    def visible_file_count(self) -> int:
        count = 0

        def visit(item):
            nonlocal count
            if not bool(item.data(0, ROLE_IS_DIR)) and not item.isHidden():
                count += 1

        self._walk(visit)
        return count

    def _walk(self, visit) -> None:
        def rec(item):
            visit(item)
            for i in range(item.childCount()):
                rec(item.child(i))
        for i in range(self.topLevelItemCount()):
            rec(self.topLevelItem(i))

    # ---------- 选中与定位 ----------

    def selected_file(self) -> str | None:
        item = self.currentItem()
        if item is not None and not bool(item.data(0, ROLE_IS_DIR)):
            return item.data(0, ROLE_PATH)
        return None

    def select_file(self, path: str) -> bool:
        item = self._find_by_path(path)
        if item is None:
            return False
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent.setHidden(False)
            parent = parent.parent()
        item.setHidden(False)
        self.setCurrentItem(item)
        self.scrollToItem(item)
        return True

    def _find_by_path(self, path: str) -> QTreeWidgetItem | None:
        found: list[QTreeWidgetItem] = []

        def visit(item):
            if item.data(0, ROLE_PATH) == path:
                found.append(item)

        self._walk(visit)
        return found[0] if found else None

    # ---------- 右键菜单 ----------

    def _on_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None or bool(item.data(0, ROLE_IS_DIR)):
            return
        menu = QMenu(self)
        act = QAction("在文件管理器中显示", menu)
        act.triggered.connect(lambda: self.reveal_requested.emit(item.data(0, ROLE_PATH)))
        menu.addAction(act)
        menu.exec(self.viewport().mapToGlobal(pos))

    # ---------- 双击 ----------

    def _on_double_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        if not bool(item.data(0, ROLE_IS_DIR)):
            self.file_double_clicked.emit(item.data(0, ROLE_PATH))

    @staticmethod
    def _path_of(item) -> str:
        if item is None:
            return ""
        return item.data(0, ROLE_PATH) or ""
