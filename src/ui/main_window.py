"""主窗口（v4 F2/F3）：上方大搜索区（主视觉居中）+ 下方全高诗歌树 + 状态栏。

主流程：搜索 → 树过滤定位（命中文件+祖先链）→ 选中 → F5/双击放映。
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.config import Config
from src.core.indexer import Indexer
from src.core.models import SUPPORTED_EXTS
from src.core.search import search_all
from src.render.engine_detect import detect_from_config
from src.ui.hymn_tree import HymnTree, reveal_in_file_manager
from src.ui.settings_dialog import SettingsDialog
from src.ui.workers import PageRenderWorker, ScanWorker
from src.utils.logger import get_logger

logger = get_logger("main_window")

SEARCH_DEBOUNCE_MS = 300


class MainWindow(QMainWindow):
    def __init__(self, config: Config | None = None, db_path: Path | None = None, scan_fulltext: bool = True):
        super().__init__()
        self.config = config or Config()
        self.db_path = db_path
        self._scan_fulltext = scan_fulltext
        self.setWindowTitle("诗歌投影 HymnSlides")
        self.resize(1100, 760)

        self._search_idx: Indexer | None = None

        self._build_ui()

        # 后台线程：放映页渲染（LO 投影窗用）与扫描
        self.page_worker = PageRenderWorker(parent=self)
        self.page_worker.start()

        # 放映控制器（F4/F6；引擎链在 R3 接入）
        from src.show.show_controller import ShowController

        self.show_controller = ShowController(self.page_worker, self.config, parent=self)
        self.show_controller.state_changed.connect(self._on_show_state_changed)

        self._warn_if_no_engine()
        self.start_scan()

    # ---------- UI 构建 ----------

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 6)
        layout.setSpacing(8)

        # 上方搜索区（主视觉居中）
        top = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索诗歌文件名或内容…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedHeight(42)
        font = self.search_edit.font()
        font.setPointSizeF(15)
        self.search_edit.setFont(font)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.btn_expand = QPushButton("展开全部")
        self.btn_expand.clicked.connect(lambda: self.tree.expandAll())
        self.btn_collapse = QPushButton("收起")
        self.btn_collapse.clicked.connect(lambda: self.tree.collapseAll())
        self.btn_settings = QPushButton("设置")
        self.btn_settings.clicked.connect(self.open_settings)

        top.addWidget(self.search_edit, 4)
        top.addWidget(self.btn_expand)
        top.addWidget(self.btn_collapse)
        top.addWidget(self.btn_settings)
        layout.addLayout(top)

        # 下方全高树
        self.tree = HymnTree()
        self.tree.file_double_clicked.connect(lambda p: self.start_show(Path(p)))
        self.tree.reveal_requested.connect(lambda p: reveal_in_file_manager(Path(p)))
        layout.addWidget(self.tree, 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage("就绪")

        # 搜索防抖（v4 F3）
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._do_search)
        self.search_edit.textChanged.connect(lambda: self._search_timer.start())

        # 快捷键（v4 F7）
        from PySide6.QtGui import QKeySequence, QShortcut
        from PySide6.QtCore import Qt

        QShortcut(QKeySequence(QKeySequence.StandardKey.Find), self).activated.connect(self._focus_search)
        QShortcut(QKeySequence(Qt.Key.Key_F5), self).activated.connect(self.start_show_from_selection)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self._on_escape)

    # ---------- 搜索（v4 F3：过滤树） ----------

    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _on_escape(self) -> None:
        """Esc：清空搜索并恢复全树（放映中的 Esc 由放映窗/演示者窗处理）。"""
        if self.search_edit.text():
            self.search_edit.clear()
            self.tree.setFocus()

    def _search_index(self) -> Indexer:
        if self._search_idx is None:
            self._search_idx = Indexer(self.db_path)
        return self._search_idx

    def _do_search(self) -> None:
        kw = self.search_edit.text().strip()
        if not kw:
            self.tree.apply_filter(None)
            self.statusBar().showMessage("就绪")
            return
        results = search_all(self._search_index()._conn, kw)
        keep = {r.path for r in results}
        visible = self.tree.apply_filter(keep)
        if results:
            self.tree.select_file(results[0].path)
            self.statusBar().showMessage(f"“{kw}”命中 {len(results)} 个文件")
        else:
            self.statusBar().showMessage(f"“{kw}”无命中")

    # ---------- 放映（v4 F4） ----------

    def start_show_from_selection(self) -> None:
        path = self.tree.selected_file()
        if path is None or Path(path).suffix.lower() not in SUPPORTED_EXTS:
            self.statusBar().showMessage("请先在树中选择一个诗歌文件", 4000)
            return
        self.start_show(Path(path))

    def start_show(self, ppt: Path) -> None:
        from src.show.display_manager import enumerate_screens

        screens = enumerate_screens()
        self.show_controller.start(ppt, screens)

    def _on_show_state_changed(self, state: str) -> None:
        if state == "showing":
            self.statusBar().showMessage("放映中…（Esc 结束）")

    # ---------- 扫描（树构建源） ----------

    def start_scan(self) -> None:
        self.statusBar().showMessage("扫描中…")
        self._scan_worker = ScanWorker(
            self.config.main_dir, db_path=self.db_path, fulltext=self._scan_fulltext, parent=self
        )
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.tree_ready.connect(self._on_tree_ready)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    def _on_scan_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.statusBar().showMessage(f"后台建立全文索引 {done}/{total}（可正常使用）")

    def _on_tree_ready(self, files, stats) -> None:
        """元数据就绪：树立即可用（全文索引继续在后台并行，v4.1 修复首扫空白/卡顿）。"""
        self.tree.load_files(self.config.main_dir, files)
        if self.search_edit.text().strip():
            self._do_search()
        self.statusBar().showMessage(f"已加载 {stats.scanned} 个诗歌文件，正在后台建立全文索引…")

    def _on_scan_done(self, files, stats) -> None:
        self.tree.load_files(self.config.main_dir, files)
        self.statusBar().showMessage(f"索引完成：共 {stats.scanned} 个诗歌文件", 5000)
        # 搜索态下刷新过滤结果
        if self.search_edit.text().strip():
            self._do_search()

    def _on_scan_failed(self, msg: str) -> None:
        self.statusBar().showMessage(f"扫描失败：{msg}", 8000)

    # ---------- 设置（F1） ----------

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            if dlg.main_dir_changed:
                self._search_idx = None
                self.tree.clear()
                self.start_scan()
            else:
                # 引擎路径变化 → 提示重启后生效（探测链在启动时缓存）
                self.statusBar().showMessage("引擎设置已保存，重启后生效", 6000)

    # ---------- 启动提示 ----------

    def _warn_if_no_engine(self) -> None:
        cands = detect_from_config(self.config)
        if cands.any_available():
            show = cands.first_show()
            if show is not None:
                self.statusBar().showMessage(f"放映引擎：{show.name}")
            return
        logger.error("启动提示：未检测到任何放映引擎")
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        QMessageBox.warning(
            self,
            "需要放映引擎",
            "未检测到 PowerPoint / WPS / LibreOffice。\n\n"
            "诗歌放映与内容索引依赖以上三者之一（任选安装）：\n"
            "· Microsoft PowerPoint（推荐，放映保真最高）\n"
            "· WPS Office\n"
            "· LibreOffice（免费开源：https://www.libreoffice.org）\n\n"
            "安装后重启本程序，或在“设置”中手动指定路径。",
        )

    def closeEvent(self, event) -> None:
        self.page_worker.request_stop()
        self.page_worker.wait(8000)
        sw = getattr(self, "_scan_worker", None)
        if sw is not None and sw.isRunning():
            sw.wait(15000)
        if self._search_idx is not None:
            self._search_idx.close()
            self._search_idx = None
        super().closeEvent(event)
