"""主窗口（访达风格）：工具栏（面包屑+视图切换+搜索框）、左侧目录树、
图标/列表内容区、底部状态栏（文件数/扫描状态）（规范 F2/F3）。"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QDir, Qt
from PySide6.QtWidgets import (
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QToolButton,
    QWidget,
)

from src.core.config import Config
from src.core.indexer import Indexer
from src.core.models import SUPPORTED_EXTS, SlideFile
from src.core.scanner import is_hidden
from src.core.search import search_all
from src.render.lo_detect import detect_soffice
from src.ui.finder_view import BreadcrumbBar, FinderView, ROLE_PATH
from src.ui.preview_panel import FullscreenPreview, PreviewPanel
from src.ui.search_bar import SearchBar, SearchResultsPanel
from src.ui.settings_dialog import SettingsDialog
from src.ui.sidebar import SidebarTree
from src.ui.workers import PageRenderWorker, ScanWorker, ThumbWorker
from src.utils.logger import get_logger

logger = get_logger("main_window")


class MainWindow(QMainWindow):
    def __init__(self, config: Config | None = None, db_path: Path | None = None, scan_fulltext: bool = True):
        super().__init__()
        self.config = config or Config()
        self.db_path = db_path
        self._scan_fulltext = scan_fulltext
        self.setWindowTitle("诗歌投影 HymnSlides")
        self.resize(1280, 800)

        self.index_files: list[SlideFile] = []  # 扫描结果（搜索/统计用）
        self._search_idx: Indexer | None = None
        self._history: list[Path] = []
        self._hist_pos = -1
        self._current_dir: Path = self.config.main_dir

        self._build_toolbar()
        self._build_central()
        self.statusBar().showMessage("就绪")

        # 后台线程
        self.thumb_worker = ThumbWorker(cache_limit_mb=self.config.cache_limit_mb, parent=self)
        self.thumb_worker.thumb_ready.connect(self._on_thumb_ready)
        self.thumb_worker.thumb_failed.connect(self._on_thumb_failed)
        self.thumb_worker.start()

        self.page_worker = PageRenderWorker(parent=self)
        self.page_worker.start()
        self.preview_panel.set_worker(self.page_worker)
        self.preview_panel.page_double_clicked.connect(
            lambda ppt, page: self._open_fullscreen_preview(Path(ppt), page)
        )

        # 搜索：防抖 + 结果面板（F4）
        self.search_bar = SearchBar(self.search_edit, self._do_search, self)
        self.search_results = SearchResultsPanel()
        self.content_splitter.addWidget(self.search_results)  # 初始隐藏
        self.search_results.locate_requested.connect(self._locate_search_result)

        # 快捷键（F8）
        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence(QKeySequence.StandardKey.Find), self).activated.connect(self._focus_search)
        QShortcut(QKeySequence(Qt.Key.Key_F11), self).activated.connect(
            lambda: self._open_fullscreen_preview_from_finder()
        )
        QShortcut(QKeySequence(Qt.Key.Key_F5), self).activated.connect(self.start_show)

        # 放映控制器（F6；双屏编排 P6 扩展）
        from src.show.show_controller import ShowController

        self.show_controller = ShowController(self.page_worker, self.config, parent=self)
        self.show_controller.state_changed.connect(self._on_show_state_changed)

        self._warn_if_no_libreoffice()
        self.navigate(self.config.main_dir, push_history=True)
        self.start_scan()

    # ---------- UI 构建 ----------

    def _build_toolbar(self) -> None:
        tb = QToolBar("工具栏")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.btn_back = QToolButton()
        self.btn_back.setText("‹")
        self.btn_back.setToolTip("后退")
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self.go_back)
        tb.addWidget(self.btn_back)

        self.btn_forward = QToolButton()
        self.btn_forward.setText("›")
        self.btn_forward.setToolTip("前进")
        self.btn_forward.setEnabled(False)
        self.btn_forward.clicked.connect(self.go_forward)
        tb.addWidget(self.btn_forward)

        self.breadcrumb = BreadcrumbBar(self.config.main_dir)
        self.breadcrumb.segment_clicked.connect(lambda p: self.navigate(Path(p)))
        tb.addWidget(self.breadcrumb)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        tb.addWidget(spacer)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索文件名或内容…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(240)
        tb.addWidget(self.search_edit)  # 行为接线在 P4（搜索与预览）

        self.btn_icon_view = QToolButton()
        self.btn_icon_view.setText("图标")
        self.btn_icon_view.setCheckable(True)
        self.btn_icon_view.setChecked(True)
        self.btn_icon_view.clicked.connect(self._set_icon_mode)
        tb.addWidget(self.btn_icon_view)

        self.btn_list_view = QToolButton()
        self.btn_list_view.setText("列表")
        self.btn_list_view.setCheckable(True)
        self.btn_list_view.clicked.connect(self._set_list_mode)
        tb.addWidget(self.btn_list_view)

        btn_settings = QPushButton("设置")
        btn_settings.clicked.connect(self.open_settings)
        tb.addWidget(btn_settings)

    def _build_central(self) -> None:
        self.sidebar = SidebarTree(self.config.main_dir)
        self.sidebar.dir_clicked.connect(lambda p: self.navigate(Path(p)))

        self.finder = FinderView()
        self.finder.open_dir_requested.connect(lambda p: self.navigate(Path(p)))
        self.finder.open_file_requested.connect(self._on_file_double_clicked)
        self.finder.itemSelectionChanged.connect(self._on_finder_selection_changed)

        self.preview_panel = PreviewPanel()

        self.content_splitter = QSplitter()
        self.content_splitter.setOrientation(Qt.Orientation.Vertical)
        self.content_splitter.addWidget(self.finder)

        self.central_splitter = QSplitter()
        self.central_splitter.addWidget(self.sidebar)
        self.central_splitter.addWidget(self.content_splitter)
        self.central_splitter.addWidget(self.preview_panel)
        self.central_splitter.setSizes([220, 820, 240])
        self.setCentralWidget(self.central_splitter)

    # ---------- 导航（F2：后退/前进） ----------

    def navigate(self, path: Path, push_history: bool = True) -> None:
        path = Path(path)
        if not path.is_dir():
            logger.warning("导航目标不是目录：%s", path)
            return
        self._current_dir = path
        if push_history:
            del self._history[self._hist_pos + 1:]
            self._history.append(path)
            self._hist_pos = len(self._history) - 1
        self.breadcrumb.rebuild(path)
        self._update_nav_buttons()
        self.refresh_content()

    def go_back(self) -> None:
        if self._hist_pos > 0:
            self._hist_pos -= 1
            self.navigate(self._history[self._hist_pos], push_history=False)

    def go_forward(self) -> None:
        if self._hist_pos < len(self._history) - 1:
            self._hist_pos += 1
            self.navigate(self._history[self._hist_pos], push_history=False)

    def _update_nav_buttons(self) -> None:
        self.btn_back.setEnabled(self._hist_pos > 0)
        self.btn_forward.setEnabled(self._hist_pos < len(self._history) - 1)

    # ---------- 内容区 ----------

    def refresh_content(self) -> None:
        d = QDir(str(self._current_dir))
        d.setFilter(QDir.Filter.Dirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot | ~QDir.Filter.Hidden)
        d.setSorting(QDir.SortFlag.DirsFirst | QDir.SortFlag.Name)
        entries = d.entryInfoList()

        dirs: list[Path] = []
        files: list[SlideFile] = []
        for e in entries:
            p = Path(e.absoluteFilePath())
            if e.isDir():
                if not is_hidden(p):
                    dirs.append(p)
            elif p.suffix.lower() in SUPPORTED_EXTS and not is_hidden(p):
                files.append(SlideFile.from_path(p, self.config.main_dir))

        self.finder.populate(dirs, files)
        for sf in files:
            self.thumb_worker.enqueue(sf.path)

        self.statusBar().showMessage(f"{len(dirs)} 个文件夹 · {len(files)} 个诗歌文件")

    def _on_thumb_ready(self, ppt_path: str, png_path: str) -> None:
        self.finder.set_thumb(ppt_path, png_path)

    def _on_thumb_failed(self, ppt_path: str) -> None:
        self.finder.mark_failed(ppt_path)

    def _on_file_double_clicked(self, path: str) -> None:
        """双击/Enter 文件 → 全屏预览（F5/F8）。"""
        self._open_fullscreen_preview(Path(path))

    def _on_finder_selection_changed(self) -> None:
        """选中变化 → 右侧预览面板（F5）。"""
        p = self.finder.current_path()
        if p is None:
            self.preview_panel.set_file(None)
            return
        path = Path(p)
        self.preview_panel.set_file(path if path.suffix.lower() in SUPPORTED_EXTS else None)

    def _open_fullscreen_preview(self, ppt: Path, page: int = 0) -> None:
        dlg = FullscreenPreview(self.page_worker, ppt, page, parent=self)
        dlg.exec()

    def _open_fullscreen_preview_from_finder(self) -> None:
        """F11：对当前选中文件全屏预览。"""
        p = self.finder.current_path()
        if p is not None and Path(p).suffix.lower() in SUPPORTED_EXTS:
            self._open_fullscreen_preview(Path(p))

    # ---------- 放映（F6/F7） ----------

    def start_show(self) -> None:
        """F5：放映当前选中文件。"""
        p = self.finder.current_path()
        if p is None or Path(p).suffix.lower() not in SUPPORTED_EXTS:
            self.statusBar().showMessage("请先选择一个诗歌文件再放映", 4000)
            return
        from src.show.display_manager import enumerate_screens

        screens = enumerate_screens()
        self.show_controller.start(Path(p), screens, dual_allowed=True)

    def _on_show_state_changed(self, state: str) -> None:
        if state == "showing":
            self.statusBar().showMessage("放映中…（Esc 结束）")

    # ---------- 搜索（F4） ----------

    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _search_index(self) -> Indexer:
        if self._search_idx is None:
            self._search_idx = Indexer(self.db_path)
        return self._search_idx

    def _do_search(self, keyword: str) -> None:
        kw = keyword.strip()
        if not kw:
            self.search_results.hide_panel()
            return
        results = search_all(self._search_index()._conn, kw)
        self.search_results.show_results(results, kw)

    def _locate_search_result(self, path: str, page: int) -> None:
        """双击搜索结果 → 定位到所在目录并选中文件。"""
        p = Path(path)
        if not p.is_file():
            self.statusBar().showMessage("文件已不存在，可能已被移动或删除", 5000)
            return
        self.navigate(p.parent)
        for i in range(self.finder.count()):
            item = self.finder.item(i)
            if item.data(ROLE_PATH) == path:
                self.finder.setCurrentItem(item)
                self.finder.scrollToItem(item)
                break

    # ---------- 视图切换（F3） ----------

    def _set_icon_mode(self) -> None:
        self.finder.set_icon_mode()
        self.btn_icon_view.setChecked(True)
        self.btn_list_view.setChecked(False)

    def _set_list_mode(self) -> None:
        self.finder.set_list_mode()
        self.btn_icon_view.setChecked(False)
        self.btn_list_view.setChecked(True)

    # ---------- 扫描（F2 穿透递归） ----------

    def start_scan(self) -> None:
        self.statusBar().showMessage("扫描中…")
        self._scan_worker = ScanWorker(
            self.config.main_dir, db_path=self.db_path, fulltext=self._scan_fulltext, parent=self
        )
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    def _on_scan_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.statusBar().showMessage(f"索引中（转换 PDF 提取文字）{done}/{total}")

    def _on_scan_done(self, files, stats) -> None:
        self.index_files = files
        total = stats.scanned
        self.statusBar().showMessage(f"索引完成：共 {total} 个诗歌文件", 5000)
        logger.info("UI 扫描完成：%s", self.statusBar().currentMessage())

    def _on_scan_failed(self, msg: str) -> None:
        self.statusBar().showMessage(f"扫描失败：{msg}", 8000)

    # ---------- 设置（F1） ----------

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            if dlg.main_dir_changed:
                new_main = self.config.main_dir
                self._history.clear()
                self._hist_pos = -1
                self.sidebar.setRoot(new_main)
                self.breadcrumb._root = new_main
                self.navigate(new_main, push_history=True)
            self.thumb_worker._cache_limit_mb = self.config.cache_limit_mb
            self.start_scan()

    # ---------- 启动提示 ----------

    def _warn_if_no_libreoffice(self) -> None:
        info = detect_soffice(self.config.soffice_path)
        if not info.found:
            logger.error("启动提示：未找到 LibreOffice")
            if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
                return  # 离屏环境（CI/测试）不弹模态框
            QMessageBox.warning(
                self,
                "需要 LibreOffice",
                "未检测到 LibreOffice。\n\n"
                "诗歌缩略图与放映依赖 LibreOffice（免费开源）。\n"
                "请安装后重启本程序，或在“设置”中手动指定 soffice 路径。",
            )

    def closeEvent(self, event) -> None:
        self.thumb_worker.request_stop()
        self.thumb_worker.wait(8000)
        self.page_worker.request_stop()
        self.page_worker.wait(8000)
        sw = getattr(self, "_scan_worker", None)
        if sw is not None and sw.isRunning():
            sw.wait(5000)
        if self._search_idx is not None:
            self._search_idx.close()
            self._search_idx = None
        super().closeEvent(event)
