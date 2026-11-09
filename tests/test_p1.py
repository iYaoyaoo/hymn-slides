"""P1 验收测试：递归扫描、mtime 增量索引、文件名+全文搜索（tmp_path 夹具）。"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from src.core.indexer import Indexer
from src.core.models import SUPPORTED_EXTS
from src.core.scanner import is_hidden, scan_directory
from src.core.search import search_all, search_filename, search_fulltext


def _mk(root: Path, rel: str, content: str = "x", mtime: float | None = None) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


# ---------- scanner ----------

def test_scan_finds_supported_and_chinese_names(tmp_path):
    _mk(tmp_path, "2026主日/感恩诗歌/奇异恩典.pptx")
    _mk(tmp_path, "2026主日/感恩诗歌/你真伟大.pps")
    _mk(tmp_path, "普通/聚会.odp")
    _mk(tmp_path, "忽略我.txt")  # 不支持的扩展名
    files = scan_directory(tmp_path)
    assert len(files) == 3
    assert {f.name for f in files} == {"奇异恩典.pptx", "你真伟大.pps", "聚会.odp"}


def test_scan_three_levels_and_skips_hidden(tmp_path):
    _mk(tmp_path, "年/月/日/深处.ppt")
    _mk(tmp_path, ".隐藏/机密.pptx")          # 隐藏目录
    _mk(tmp_path, "正常/.隐藏文件.pptx")       # 隐藏文件
    _mk(tmp_path, "$RECYCLE.BIN/回收.pptx")   # 系统目录
    _mk(tmp_path, "正常/~$锁文件.pptx")       # Office 临时文件
    files = scan_directory(tmp_path)
    assert len(files) == 1
    assert files[0].name == "深处.ppt"
    assert files[0].rel_path == str(Path("年") / "月" / "日" / "深处.ppt")


def test_is_hidden_rules():
    assert is_hidden(Path(".abc"))
    assert is_hidden(Path("~$xyz.pptx"))
    assert is_hidden(Path("a.tmp"))
    assert not is_hidden(Path("正常.pptx"))
    assert not is_hidden(Path("诗歌 2026.pptx"))


def test_scan_missing_root(tmp_path):
    assert scan_directory(tmp_path / "不存在") == []


# ---------- indexer：增量 ----------

def test_indexer_incremental_flow(tmp_path):
    _mk(tmp_path, "a.pptx", "1", mtime=1000.0)
    _mk(tmp_path, "d/b.pptx", "22", mtime=1000.0)
    with Indexer(tmp_path / "idx.db") as idx:
        s1 = idx.sync_scan(tmp_path)
        assert (s1.scanned, s1.added, s1.unchanged, s1.removed) == (2, 2, 0, 0)

        # 再扫：全部跳过
        s2 = idx.sync_scan(tmp_path)
        assert (s2.added, s2.updated, s2.unchanged, s2.removed) == (0, 0, 2, 0)

        # 新增文件
        _mk(tmp_path, "c.pptx", "333", mtime=2000.0)
        # 修改 b.pptx（size 变化）
        b = tmp_path / "d" / "b.pptx"
        b.write_text("changed-longer", encoding="utf-8")
        os.utime(b, (2000.0, 2000.0))
        # 删除 a.pptx
        (tmp_path / "a.pptx").unlink()

        s3 = idx.sync_scan(tmp_path)
        assert (s3.scanned, s3.added, s3.updated, s3.removed) == (2, 1, 1, 1)
        assert len(idx.get_all_files()) == 2


def test_indexer_update_clears_texts(tmp_path):
    _mk(tmp_path, "a.pptx", "1", mtime=1000.0)
    with Indexer(tmp_path / "idx.db") as idx:
        idx.sync_scan(tmp_path)
        fid = idx.file_id_by_path(str(tmp_path / "a.pptx"))
        assert fid is not None
        idx.upsert_slide_texts(fid, [(1, "旧内容")])
        idx.set_page_count(fid, 5)
        # 文件变化 → 更新 → 全文应被清空、页数置 NULL
        p = tmp_path / "a.pptx"
        p.write_text("changed", encoding="utf-8")
        os.utime(p, (2000.0, 2000.0))
        idx.sync_scan(tmp_path)
        cur = idx._conn.execute("SELECT COUNT(*) FROM slide_texts")
        assert cur.fetchone()[0] == 0
        cur = idx._conn.execute("SELECT page_count FROM files WHERE id=?", (fid,))
        assert cur.fetchone()[0] is None


def test_indexer_remove_cascades_texts(tmp_path):
    _mk(tmp_path, "a.pptx", "1", mtime=1000.0)
    with Indexer(tmp_path / "idx.db") as idx:
        idx.sync_scan(tmp_path)
        fid = idx.file_id_by_path(str(tmp_path / "a.pptx"))
        idx.upsert_slide_texts(fid, [(1, "文字")])
        (tmp_path / "a.pptx").unlink()
        idx.sync_scan(tmp_path)
        cur = idx._conn.execute("SELECT COUNT(*) FROM slide_texts")
        assert cur.fetchone()[0] == 0


def test_supported_exts_complete():
    assert SUPPORTED_EXTS == {".ppt", ".pptx", ".pps", ".ppsx", ".pot", ".potx", ".odp"}


# ---------- search ----------

def _index_with_texts(tmp_path):
    _mk(tmp_path, "奇异恩典.pptx", "1", mtime=1000.0)
    _mk(tmp_path, "你真伟大.pptx", "2", mtime=1000.0)
    idx = Indexer(tmp_path / "idx.db")
    idx.sync_scan(tmp_path)
    fid1 = idx.file_id_by_path(str(tmp_path / "奇异恩典.pptx"))
    fid2 = idx.file_id_by_path(str(tmp_path / "你真伟大.pptx"))
    idx.upsert_slide_texts(fid1, [(1, "何等奇妙的救主"), (2, "我罪已得赦免")])
    idx.upsert_slide_texts(fid2, [(1, "主啊我赞美你"), (2, "你真伟大配得尊贵")])
    return idx


def test_search_filename_chinese(tmp_path):
    with _index_with_texts(tmp_path) as idx:
        rs = search_filename(idx._conn, "恩典")
        assert len(rs) == 1 and rs[0].name == "奇异恩典.pptx"
        rs = search_filename(idx._conn, "不存在关键词")
        assert rs == []


def test_search_fulltext_page_and_snippet(tmp_path):
    with _index_with_texts(tmp_path) as idx:
        rs = search_fulltext(idx._conn, "赦免")
        assert len(rs) == 1
        assert rs[0].page == 2
        assert "【赦免】" in rs[0].snippet


def test_search_all_dedup_order(tmp_path):
    with _index_with_texts(tmp_path) as idx:
        rs = search_all(idx._conn, "伟大")
        # “你真伟大.pptx”文件名命中；其余“伟大”全文命中共 1 条 → 同文件已去重
        assert len(rs) == 1
        rs2 = search_all(idx._conn, "真伟大")
        assert rs2[0].name == "你真伟大.pptx" and rs2[0].page is None  # 文件名命中优先（无页码）


def test_search_like_escape(tmp_path):
    with _index_with_texts(tmp_path) as idx:
        assert search_filename(idx._conn, "100%") == []
        assert search_filename(idx._conn, "_") == []
        assert search_fulltext(idx._conn, "%") == []


def test_search_empty_keyword(tmp_path):
    with _index_with_texts(tmp_path) as idx:
        assert search_all(idx._conn, "") == []
        assert search_all(idx._conn, "   ") == []


# ---------- CLI --scan 端到端 ----------

def test_cli_scan_end_to_end(tmp_path, capsys):
    import main as main_mod

    _mk(tmp_path, "诗歌/奇异恩典.pptx", "1", mtime=1000.0)
    _mk(tmp_path, "诗歌/你真伟大.pps", "22", mtime=1000.0)
    rc = main_mod.main(["--scan", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "文件总数: 2" in out
    assert "新增 2" in out
    # 再扫一次：全部跳过
    rc2 = main_mod.main(["--scan", str(tmp_path)])
    out2 = capsys.readouterr().out
    assert rc2 == 0 and "跳过 2" in out2
