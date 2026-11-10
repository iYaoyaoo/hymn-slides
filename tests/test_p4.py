"""R2/R3 验收测试（v4 搜索）：防抖 → 引擎文字索引 → 树过滤定位。"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.core.config import Config
from src.core.indexer import Indexer
from src.core.models import SearchResult
from src.core.search import search_all


@pytest.fixture()
def window(qapp, tmp_path):
    from src.ui.main_window import MainWindow

    tree = tmp_path / "主目录" / "2026年"
    tree.mkdir(parents=True)
    for name in ("奇异恩典.pptx", "你真伟大.pps"):
        (tree / name).write_bytes(b"demo")
    cfg = Config(settings_path=tmp_path / "config.ini")
    cfg.set_main_dir(tree.parent)
    cfg.sync()

    db = tmp_path / "idx.db"
    with Indexer(db) as idx:
        idx.sync_scan(tree.parent)
        fid = idx.file_id_by_path(str(tree / "奇异恩典.pptx"))
        idx.upsert_slide_texts(fid, [(1, "何等奇妙的救主"), (2, "我罪已得赦免")])
        idx.set_page_count(fid, 2)
        fid2 = idx.file_id_by_path(str(tree / "你真伟大.pps"))
        idx.upsert_slide_texts(fid2, [(1, "主啊我赞美你")])
        idx.set_page_count(fid2, 1)

    win = MainWindow(config=cfg, db_path=db, scan_fulltext=False)
    yield win
    win.close()


def _wait_tree_loaded(qapp, window, timeout=8):
    t0 = time.time()
    while time.time() - t0 < timeout:
        qapp.processEvents()
        if window.tree.topLevelItemCount() > 0:
            return True
        time.sleep(0.05)
    return False


def test_search_filters_tree_to_matches(qapp, window):
    assert _wait_tree_loaded(qapp, window)
    assert window.tree.visible_file_count() == 2

    # 全文命中 1 个文件
    window.search_edit.setText("赦免")
    window._do_search()
    assert window.tree.visible_file_count() == 1
    assert window.tree.selected_file() == str(
        window.config.main_dir / "2026年" / "奇异恩典.pptx"
    )
    assert "命中 1" in window.statusBar().currentMessage()

    # 文件名命中
    window.search_edit.setText("伟大")
    window._do_search()
    assert window.tree.visible_file_count() == 1
    assert window.tree.selected_file() == str(
        window.config.main_dir / "2026年" / "你真伟大.pps"
    )

    # 无命中 → 全隐藏
    window.search_edit.setText("不存在的关键词xyz")
    window._do_search()
    assert window.tree.visible_file_count() == 0
    assert "无命中" in window.statusBar().currentMessage()

    # 清空 → 恢复全树
    window.search_edit.setText("")
    window._do_search()
    assert window.tree.visible_file_count() == 2


def test_search_debounce_single_fire(qapp, window):
    assert _wait_tree_loaded(qapp, window)
    fired: list[str] = []
    window.search_edit.textChanged.disconnect()
    window.search_edit.textChanged.connect(lambda: fired.append(window.search_edit.text()))
    # 重新接防抖（模拟主窗口接线）
    window.search_edit.textChanged.connect(lambda: window._search_timer.start())
    window.search_edit.setText("奇")
    window.search_edit.setText("奇异")
    t0 = time.time()
    while time.time() - t0 < 1.5:
        qapp.processEvents()
        time.sleep(0.02)
    # 防抖后应只触发一次搜索（树过滤结果正确）
    assert window.tree.visible_file_count() == 1


def test_escape_clears_search(qapp, window):
    assert _wait_tree_loaded(qapp, window)
    window.search_edit.setText("赦免")
    window._do_search()
    assert window.tree.visible_file_count() == 1
    window._on_escape()
    qapp.processEvents()
    assert window.search_edit.text() == ""
    # 等防抖触发恢复全树
    t0 = time.time()
    while window.tree.visible_file_count() != 2 and time.time() - t0 < 2:
        qapp.processEvents()
        time.sleep(0.02)
    assert window.tree.visible_file_count() == 2


def test_search_via_index_fulltext_page(qapp, tmp_path):
    """全文命中页码与片段（引擎无关，索引层既有能力）。"""
    tree = tmp_path / "主目录"
    tree.mkdir()
    (tree / "诗歌.pptx").write_bytes(b"demo")
    with Indexer(tmp_path / "idx.db") as idx:
        idx.sync_scan(tree)
        fid = idx.file_id_by_path(str(tree / "诗歌.pptx"))
        idx.upsert_slide_texts(fid, [(1, "何等奇妙的救主"), (2, "我罪已得赦免")])
        rs = search_all(idx._conn, "赦免")
        assert len(rs) == 1 and rs[0].page == 2 and "【赦免】" in rs[0].snippet
