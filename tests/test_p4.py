"""P4 验收测试：搜索（防抖/结果面板/定位）与预览（面板懒加载/全屏翻页）。"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.core.config import Config
from src.core.indexer import Indexer
from src.core.models import SearchResult
from src.core.search import search_all
from src.ui.search_bar import DEBOUNCE_MS, SearchBar, SearchResultsPanel


# ---------- SearchBar 防抖 ----------

def test_search_bar_debounce(qapp, tmp_path):
    from PySide6.QtWidgets import QLineEdit

    edit = QLineEdit()
    calls: list[str] = []
    bar = SearchBar(edit, lambda kw: calls.append(kw))
    edit.setText("奇")
    edit.setText("奇异恩")  # 两次输入应合并为一次
    t0 = time.time()
    while len(calls) == 0 and time.time() - t0 < 2:
        qapp.processEvents()
        time.sleep(0.02)
    assert calls == ["奇异恩"]

    bar.trigger_now()
    assert calls == ["奇异恩", "奇异恩"]  # trigger_now 不受防抖影响


# ---------- SearchResultsPanel ----------

def test_results_panel_show_and_locate(qapp):
    panel = SearchResultsPanel()
    results = [
        SearchResult(file_id=1, path="/a/奇异恩典.pptx", name="奇异恩典.pptx"),
        SearchResult(file_id=2, path="/a/你真伟大.pptx", name="你真伟大.pptx", page=3, snippet="…【伟大】…"),
    ]
    panel.show_results(results, "恩")
    assert panel.isVisible() and panel.count() == 2
    assert "第 3 页" in panel.item(1).text()

    got: list[tuple] = []
    panel.locate_requested.connect(lambda p, page: got.append((p, page)))
    panel._on_double_clicked(panel.item(1))
    assert got == [("/a/你真伟大.pptx", 3)]

    panel.hide_panel()
    assert not panel.isVisible() and panel.count() == 0


# ---------- 全文搜索（真实 SQLite，模拟已回填的 slide_texts） ----------

@pytest.fixture()
def search_db(tmp_path):
    tree = tmp_path / "主目录"
    _dir = tree / "2026年"
    _dir.mkdir(parents=True)
    for name in ("奇异恩典.pptx", "你真伟大.pps"):
        (tree / "2026年" / name).write_bytes(b"demo")
    with Indexer(tmp_path / "idx.db") as idx:
        idx.sync_scan(tree)
        fid = idx.file_id_by_path(str(_dir / "奇异恩典.pptx"))
        idx.upsert_slide_texts(fid, [(1, "何等奇妙的救主"), (2, "我罪已得赦免")])
        idx.set_page_count(fid, 2)
    return tmp_path / "idx.db", tree


def test_search_fulltext_via_ui_index(search_db):
    db, _tree = search_db
    with Indexer(db) as idx:
        rs = search_all(idx._conn, "赦免")
        assert len(rs) == 1 and rs[0].page == 2 and "赦免" in rs[0].snippet


# ---------- MainWindow 搜索集成 ----------

@pytest.fixture()
def window(qapp, tmp_path):
    from src.ui.main_window import MainWindow

    tree = tmp_path / "主目录" / "2026年"
    tree.mkdir(parents=True)
    (tree / "奇异恩典.pptx").write_bytes(b"demo")
    (tree / "你真伟大.pps").write_bytes(b"demo")
    cfg = Config(settings_path=tmp_path / "config.ini")
    cfg.set_main_dir(tree.parent)
    cfg.sync()

    db = tmp_path / "idx.db"
    with Indexer(db) as idx:
        idx.sync_scan(tree.parent)
        fid = idx.file_id_by_path(str(tree / "奇异恩典.pptx"))
        idx.upsert_slide_texts(fid, [(1, "何等奇妙的救主"), (2, "我罪已得赦免")])
        idx.set_page_count(fid, 2)

    win = MainWindow(config=cfg, db_path=db, scan_fulltext=False)
    yield win
    win.close()


def test_window_do_search_and_locate(qapp, window):
    window.show()
    qapp.processEvents()
    window._do_search("赦免")
    assert window.search_results.count() == 1
    assert not window.search_results.isHidden()
    assert "奇异恩典" in window.search_results.item(0).text()

    # 定位：应导航到所在目录并选中文件
    window._locate_search_result(
        str(window.config.main_dir / "2026年" / "奇异恩典.pptx"), 2
    )
    sel = window.finder.current_path()
    assert sel == str(window.config.main_dir / "2026年" / "奇异恩典.pptx")

    # 清空关键词 → 面板隐藏
    window._do_search("")
    assert window.search_results.isHidden()


def test_window_focus_search(qapp, window):
    window.show()
    qapp.processEvents()
    window._focus_search()
    qapp.processEvents()
    assert window.search_edit.hasFocus() or window.search_edit.hasSelectedText()


# ---------- PreviewPanel 懒加载 ----------

class FakePageWorker:
    """模拟 PageRenderWorker 信号协议（QObject 信号）。"""

    def __init__(self):
        from PySide6.QtCore import QObject, Signal

        class _Sig(QObject):
            count_ready = Signal(str, int)
            page_ready = Signal(str, int, str)
            show_ready = Signal(str, int, str)
            page_failed = Signal(str, int)

        self._obj = _Sig()
        self.count_ready = self._obj.count_ready
        self.page_ready = self._obj.page_ready
        self.show_ready = self._obj.show_ready
        self.page_failed = self._obj.page_failed
        self.requests: list[tuple] = []

    def request_count(self, ppt):
        self.requests.append(("count", str(ppt)))

    def request_page(self, ppt, page):
        self.requests.append(("page", str(ppt), page))

    def request_show(self, ppt, page):
        self.requests.append(("show", str(ppt), page))


def _make_png(tmp_path, name="p.png"):
    from PIL import Image

    p = tmp_path / name
    Image.new("RGB", (16, 12), "red").save(p)
    return str(p)


def test_preview_panel_lazy(qapp, tmp_path):
    from src.ui.preview_panel import PreviewPanel

    worker = FakePageWorker()
    panel = PreviewPanel(worker)
    ppt = tmp_path / "诗歌.pptx"
    ppt.write_bytes(b"demo")

    panel.set_file(ppt)
    assert ("count", str(ppt)) in worker.requests

    worker.count_ready.emit(str(ppt), 30)
    assert panel.list.count() == 30
    assert panel.status_label.text().startswith("诗歌.pptx")
    # 首批懒加载（可见窗口 ± LAZY_WINDOW）
    page_reqs = [r for r in worker.requests if r[0] == "page"]
    assert 0 < len(page_reqs) <= 30

    png = _make_png(tmp_path)
    worker.page_ready.emit(str(ppt), 0, png)
    assert not panel.list.item(0).icon().isNull()

    # 切换文件 → 清空重载
    ppt2 = tmp_path / "另首诗歌.pptx"
    ppt2.write_bytes(b"demo")
    worker.requests.clear()
    panel.set_file(ppt2)
    assert panel.list.count() == 0
    assert ("count", str(ppt2)) in worker.requests

    # None → 清空
    panel.set_file(None)
    assert panel.list.count() == 0 and "选择文件查看预览" in panel.status_label.text()


def test_preview_panel_double_click_page(qapp, tmp_path):
    from src.ui.preview_panel import PreviewPanel

    worker = FakePageWorker()
    panel = PreviewPanel(worker)
    ppt = tmp_path / "诗歌.pptx"
    ppt.write_bytes(b"demo")
    panel.set_file(ppt)
    worker.count_ready.emit(str(ppt), 3)

    got: list[tuple] = []
    panel.page_double_clicked.connect(lambda p, page: got.append((p, page)))
    panel._on_double_clicked(panel.list.item(2))
    assert got == [(str(ppt), 2)]


# ---------- 全屏预览：翻页与退出 ----------

def test_fullscreen_preview_navigation(qapp, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QDialog

    from src.ui.preview_panel import FullscreenPreview

    worker = FakePageWorker()
    dlg = FullscreenPreview(worker, tmp_path / "诗歌.pptx")
    assert ("count", str(tmp_path / "诗歌.pptx")) in worker.requests
    worker.count_ready.emit(str(tmp_path / "诗歌.pptx"), 5)
    dlg._load_page(0)
    assert ("show", str(tmp_path / "诗歌.pptx"), 0) in worker.requests

    png = _make_png(tmp_path)
    worker.show_ready.emit(str(tmp_path / "诗歌.pptx"), 0, png)
    assert not dlg.image_label.pixmap().isNull()

    # → 翻到第 1 页
    dlg.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier))
    assert ("show", str(tmp_path / "诗歌.pptx"), 1) in worker.requests

    # ← 回到第 0 页
    dlg.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier))
    assert ("show", str(tmp_path / "诗歌.pptx"), 0) in worker.requests

    # Esc 退出
    dlg.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    qapp.processEvents()
    assert not dlg.isVisible()
