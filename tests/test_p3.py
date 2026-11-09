"""P3 验收测试：访达界面（离屏）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config import Config
from src.core.models import SlideFile
from src.ui.finder_view import BreadcrumbBar, FinderView


def _mk_tree(root: Path) -> None:
    (root / "2026年" / "一季度").mkdir(parents=True)
    (root / "2026年" / "二季度").mkdir(parents=True)
    for rel in ("2026年/一季度/奇异恩典.pptx", "2026年/一季度/你真伟大.pps", "2026年/二季度/主在圣殿中.odp"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"demo")


@pytest.fixture()
def config(tmp_path):
    tree = tmp_path / "主目录"
    tree.mkdir()
    _mk_tree(tree)
    cfg = Config(settings_path=tmp_path / "config.ini")
    cfg.set_main_dir(tree)
    cfg.sync()
    return cfg


@pytest.fixture()
def window(qapp, config, tmp_path):
    from src.ui.main_window import MainWindow

    win = MainWindow(config=config, db_path=tmp_path / "idx.db")
    yield win
    win.close()


# ---------- 基础装配 ----------

def test_main_window_builds(qapp, window):
    assert window.windowTitle().startswith("诗歌投影")
    assert window.finder.count() > 0
    assert window.sidebar is not None
    assert window.search_edit.placeholderText() != ""


def test_content_counts_in_statusbar(qapp, window):
    # 顶层：仅“2026年”1 个文件夹、0 个文件
    window.refresh_content()  # 扫描线程可能已覆盖状态栏，重新刷一次再断言
    assert "1 个文件夹" in window.statusBar().currentMessage()
    assert "0 个诗歌文件" in window.statusBar().currentMessage()
    # 一季度：2 个诗歌文件
    window.navigate(window.config.main_dir / "2026年" / "一季度")
    assert "0 个文件夹" in window.statusBar().currentMessage()
    assert "2 个诗歌文件" in window.statusBar().currentMessage()


def test_navigate_and_history(qapp, window):
    sub = window.config.main_dir / "2026年" / "一季度"
    window.navigate(sub)
    assert window._current_dir == sub
    assert window.btn_back.isEnabled() and not window.btn_forward.isEnabled()

    window.go_back()
    assert window._current_dir == window.config.main_dir
    assert not window.btn_back.isEnabled() and window.btn_forward.isEnabled()

    window.go_forward()
    assert window._current_dir == sub


def test_navigate_missing_dir_noop(qapp, window):
    before = window._current_dir
    window.navigate(window.config.main_dir / "不存在的目录")
    assert window._current_dir == before


def test_view_toggle(qapp, window):
    from PySide6.QtWidgets import QListWidget

    window._set_list_mode()
    assert window.finder.viewMode() == QListWidget.ViewMode.ListMode
    assert window.btn_list_view.isChecked() and not window.btn_icon_view.isChecked()
    window._set_icon_mode()
    assert window.finder.viewMode() == QListWidget.ViewMode.IconMode


# ---------- FinderView ----------

def test_finder_populate(qapp, tmp_path):
    dirs = [tmp_path / "目录A", tmp_path / "目录B"]
    files = [
        SlideFile(path=tmp_path / "诗歌.pptx", size=10, mtime=1.0, name="诗歌.pptx", rel_path="诗歌.pptx")
    ]
    view = FinderView()
    view.populate(dirs, files)
    assert view.count() == 3

    # 目录项与文件项角色数据
    from src.ui.finder_view import ROLE_IS_DIR, ROLE_PATH

    item = view.item(0)
    assert item.data(ROLE_IS_DIR) is True
    assert item.data(ROLE_PATH) == str(tmp_path / "目录A")
    assert view.item(2).data(ROLE_IS_DIR) is False


def test_finder_thumb_update(qapp, tmp_path):
    view = FinderView()
    files = [SlideFile(path=tmp_path / "诗歌.pptx", size=10, mtime=1.0, name="诗歌.pptx", rel_path="诗歌.pptx")]
    view.populate([], files)
    png = tmp_path / "thumb.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    view.set_thumb(str(tmp_path / "诗歌.pptx"), str(png))
    assert not view.item(0).icon().isNull()
    view.mark_failed(str(tmp_path / "诗歌.pptx"))
    assert not view.item(0).icon().isNull()


# ---------- BreadcrumbBar ----------

def test_breadcrumb_segments(qapp, config):
    bar = BreadcrumbBar(config.main_dir)
    deep = config.main_dir / "2026年" / "一季度"
    bar.rebuild(deep)
    labels = [bar._layout.itemAt(i).widget() for i in range(bar._layout.count())]
    texts = [w.text() for w in labels if hasattr(w, "text") and w.text() != "› "]
    assert "主目录" in texts and "一季度" in texts


# ---------- 设置对话框 ----------

def test_settings_dialog_save(qapp, config, tmp_path):
    from src.ui.settings_dialog import SettingsDialog

    new_dir = tmp_path / "新主目录"
    new_dir.mkdir()
    dlg = SettingsDialog(config)
    dlg.main_dir_edit.setText(str(new_dir))
    dlg.soffice_edit.setText("/opt/lo/soffice")
    dlg.cache_spin.setValue(512)
    dlg.confirm_box.setChecked(False)
    dlg._save()
    assert dlg.result() == SettingsDialog.DialogCode.Accepted
    assert config.main_dir == new_dir
    assert config.soffice_path == "/opt/lo/soffice"
    assert config.cache_limit_mb == 512
    assert config.single_screen_confirm is False


# ---------- 扫描线程（真实后台线程） ----------

def test_scan_worker(qapp, config, tmp_path, qtbot_skip=None):
    from src.ui.workers import ScanWorker

    results = {}
    w = ScanWorker(config.main_dir, db_path=tmp_path / "idx2.db")
    w.done.connect(lambda files, stats: results.update(files=files, stats=stats))
    w.failed.connect(lambda msg: results.update(err=msg))
    w.start()
    deadline_timeout_ms = 5000
    import time

    t0 = time.time()
    while "files" not in results and time.time() - t0 < 5:
        qapp.processEvents()
        time.sleep(0.02)
    w.wait(2000)
    assert "files" in results
    assert results["stats"].scanned == 3
    assert len(results["files"]) == 3
