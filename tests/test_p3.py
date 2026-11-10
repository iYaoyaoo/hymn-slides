"""R2 验收测试（v4 UI）：诗歌树构建/过滤/定位 + 主窗口装配 + 扫描线程。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config import Config
from src.core.indexer import Indexer
from src.core.models import SlideFile
from src.ui.hymn_tree import HymnTree, reveal_in_file_manager


def _mk_tree(root: Path) -> None:
    (root / "2026年" / "一季度").mkdir(parents=True)
    (root / "2026年" / "二季度").mkdir(parents=True)
    for rel in ("2026年/一季度/奇异恩典.pptx", "2026年/一季度/你真伟大.pps", "2026年/二季度/主在圣殿中.odp"):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"demo")


def _files(root: Path) -> list[SlideFile]:
    _mk_tree(root)
    return [SlideFile.from_path(root / rel, root) for rel in (
        "2026年/一季度/奇异恩典.pptx",
        "2026年/一季度/你真伟大.pps",
        "2026年/二季度/主在圣殿中.odp",
    )]


# ---------- HymnTree ----------

def test_tree_build(qapp, tmp_path):
    tree = HymnTree()
    tree.load_files(tmp_path, _files(tmp_path))
    root = tree.topLevelItem(0)
    assert root.text(0) == tmp_path.name
    assert tree.visible_file_count() == 3
    # 目录层级：根 > 2026年 > 一季度 > 文件（子项按 rel_path 排序）
    y = root.child(0)
    assert y.text(0) == "2026年"
    q1 = y.child(0)
    assert q1.childCount() == 2
    assert {q1.child(i).text(0) for i in range(2)} == {"奇异恩典.pptx", "你真伟大.pps"}


def test_tree_filter_keep_ancestors(qapp, tmp_path):
    tree = HymnTree()
    tree.load_files(tmp_path, _files(tmp_path))
    keep = {str(tmp_path / "2026年" / "二季度" / "主在圣殿中.odp")}
    visible = tree.apply_filter(keep)
    assert visible == 1
    # 命中文件可见
    hit = tree._find_by_text("主在圣殿中.odp")
    assert hit is not None and not hit.isHidden()
    # 未命中的文件隐藏
    miss = tree._find_by_text("奇异恩典.pptx")
    assert miss is not None and miss.isHidden()
    # 祖先目录可见且展开
    assert not hit.parent().isHidden() and hit.parent().isExpanded()

    # 清空 → 恢复全树
    assert tree.apply_filter(None) == 3


def test_tree_select_and_expand(qapp, tmp_path):
    tree = HymnTree()
    tree.load_files(tmp_path, _files(tmp_path))
    target = str(tmp_path / "2026年" / "二季度" / "主在圣殿中.odp")
    assert tree.select_file(target) is True
    assert tree.selected_file() == target
    # 祖先已展开
    item = tree.currentItem()
    anc = item.parent()
    assert anc is not None and anc.isExpanded()

    # 不存在的文件
    assert tree.select_file("/no/such.pptx") is False


def test_tree_double_click_file_signal(qapp, tmp_path):
    tree = HymnTree()
    tree.load_files(tmp_path, _files(tmp_path))
    target = str(tmp_path / "2026年" / "一季度" / "奇异恩典.pptx")
    tree.select_file(target)
    got: list[str] = []
    tree.file_double_clicked.connect(got.append)
    tree._on_double_clicked(tree.currentItem(), 0)
    assert got == [target]
    # 目录双击不触发
    tree._on_double_clicked(tree.topLevelItem(0), 0)
    assert got == [target]


def test_tree_selection_signal(qapp, tmp_path):
    tree = HymnTree()
    tree.load_files(tmp_path, _files(tmp_path))
    got: list = []
    tree.file_selection_changed.connect(got.append)
    tree.select_file(str(tmp_path / "2026年" / "一季度" / "奇异恩典.pptx"))
    assert got and got[-1] == str(tmp_path / "2026年" / "一季度" / "奇异恩典.pptx")


def test_tree_expand_collapse_buttons_exist(qapp, tmp_path):
    """展开/收起按钮作用于全树（main_window 装配测试中覆盖操作）。"""
    from src.ui.main_window import MainWindow

    cfg = Config(settings_path=tmp_path / "cfg.ini")
    tree = tmp_path / "主目录"
    tree.mkdir()
    cfg.set_main_dir(tree)
    cfg.sync()
    win = MainWindow(config=cfg, db_path=tmp_path / "idx.db", scan_fulltext=False)
    assert win.btn_expand.text() == "展开全部"
    assert win.btn_collapse.text() == "收起"
    win.close()


def test_reveal_platform_command(monkeypatch, tmp_path):
    """在文件管理器中显示：平台分支命令（macOS=open -R）。"""
    import sys

    if sys.platform != "darwin":
        pytest.skip("仅 macOS")
    target = tmp_path / "诗歌.pptx"
    target.write_bytes(b"x")
    calls: list = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

    import src.ui.hymn_tree as ht

    monkeypatch.setattr(ht.subprocess, "run", fake_run)
    reveal_in_file_manager(target)
    assert calls and calls[0][:2] == ["open", "-R"]


# ---------- MainWindow（v4 装配） ----------

@pytest.fixture()
def window(qapp, tmp_path):
    from src.ui.main_window import MainWindow

    tree = tmp_path / "主目录"
    (tree / "2026年" / "一季度").mkdir(parents=True)
    (tree / "2026年" / "一季度" / "奇异恩典.pptx").write_bytes(b"demo")
    cfg = Config(settings_path=tmp_path / "config.ini")
    cfg.set_main_dir(tree)
    cfg.sync()
    win = MainWindow(config=cfg, db_path=tmp_path / "idx.db", scan_fulltext=False)
    yield win
    win.close()


def test_main_window_layout(qapp, window):
    assert window.windowTitle().startswith("诗歌投影")
    assert window.search_edit.placeholderText()
    assert window.search_edit.height() >= 40  # 大搜索区（主视觉）
    assert window.tree is not None and window.tree.topLevelItemCount() >= 0


def test_main_window_scan_loads_tree(qapp, window, tmp_path):
    import time

    deadline = time.time() + 8
    while time.time() < deadline:
        window.statusBar() and None
        if window.tree.topLevelItemCount() > 0:
            break
        qapp.processEvents()
        time.sleep(0.05)
    assert window.tree.visible_file_count() == 1
    assert window.index_files and window.index_files[0].name == "奇异恩典.pptx"


# ---------- 扫描线程 ----------

def test_scan_worker(qapp, tmp_path):
    """tree_ready 立即发（树秒出）；done 随后。"""
    from src.ui.workers import ScanWorker

    tree = tmp_path / "主目录"
    _mk_tree(tree)
    results: dict = {}
    w = ScanWorker(tree, db_path=tmp_path / "idx2.db", fulltext=False)
    w.tree_ready.connect(lambda files, stats: results.update(tree_files=files, tree_stats=stats))
    w.done.connect(lambda files, stats: results.update(files=files, stats=stats))
    w.failed.connect(lambda msg: results.update(err=msg))
    w.start()
    import time

    t0 = time.time()
    while "tree_files" not in results and time.time() - t0 < 8:
        qapp.processEvents()
        time.sleep(0.02)
    assert "tree_files" in results  # 元数据就绪信号先到
    while "files" not in results and time.time() - t0 < 8:
        qapp.processEvents()
        time.sleep(0.02)
    w.wait(2000)
    assert "files" in results
    assert results["stats"].scanned == 3
    assert len(results["files"]) == 3


def test_scan_worker_fulltext_parallel_and_resilient(qapp, tmp_path, monkeypatch):
    """全文回填：并行提取、单文件失败不中断、只处理主目录下文件。"""
    import threading

    from src.ui import workers as workers_mod
    from src.ui.workers import ScanWorker

    tree = tmp_path / "主目录"
    (tree / "诗歌").mkdir(parents=True)
    for name in ("a.pptx", "b.pptx", "c.pptx"):
        (tree / "诗歌" / name).write_bytes(b"demo")

    # 预置"主目录之外"的陈旧行（文件真实存在于磁盘，不会被 sync_scan 清理；
    # page_count 为 NULL，且不应被本次回填触碰——root 过滤）
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "旧文件.pptx"
    outside_file.write_bytes(b"demo")
    outside_path = str(outside_file)
    db = tmp_path / "idx.db"
    with Indexer(db) as idx0:
        idx0._conn.execute(
            "INSERT INTO files(path, rel_path, name, ext, size, mtime, page_count, indexed_at) "
            "VALUES(?,?,?,?,?,?,NULL,?)",
            (outside_path, "旧文件.pptx", "旧文件.pptx", ".pptx", 1, 1000.0, 1000.0),
        )
        idx0._conn.commit()

    used_threads: set[int] = set()

    class _StubCache:
        def slide_texts(self, ppt: Path):
            used_threads.add(threading.get_ident())
            if ppt.name == "b.pptx":
                raise RuntimeError("模拟单文件转换失败")
            return [(1, f"{ppt.stem} 的歌词")]

    monkeypatch.setattr(workers_mod, "_thread_cache", lambda: _StubCache())

    results: dict = {}
    w = ScanWorker(tree, db_path=db, fulltext=True)
    w.done.connect(lambda files, stats: results.update(files=files, stats=stats))
    w.failed.connect(lambda msg: results.update(err=msg))
    progress: list[tuple] = []
    w.progress.connect(lambda d, t: progress.append((d, t)))
    w.start()
    import time

    t0 = time.time()
    while "files" not in results and time.time() - t0 < 15:
        qapp.processEvents()
        time.sleep(0.05)
    w.wait(3000)
    assert "files" in results and "err" not in results
    # 提取发生在多个线程（并行）
    assert len(used_threads) >= 2
    # 进度覆盖全部 3 个文件
    assert progress and progress[-1] == (3, 3)
    # 成功的 2 个文件全文已入库，失败的 page_count 仍为 NULL；陈旧行未被触碰
    with Indexer(db) as idx:
        fid_a = idx.file_id_by_path(str(tree / "诗歌" / "a.pptx"))
        fid_b = idx.file_id_by_path(str(tree / "诗歌" / "b.pptx"))
        cur = idx._conn.execute("SELECT page_count FROM files WHERE id=?", (fid_a,))
        assert cur.fetchone()[0] == 1
        cur = idx._conn.execute("SELECT page_count FROM files WHERE id=?", (fid_b,))
        assert cur.fetchone()[0] is None
        cur = idx._conn.execute("SELECT page_count FROM files WHERE path=?", (outside_path,))
        assert cur.fetchone()[0] is None
