"""SQLite 索引：mtime+size 增量同步（schema 见 docs/schema.md）。"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from src.core.models import ScanStats, SlideFile
from src.core.scanner import iter_slide_files
from src.utils import paths
from src.utils.logger import get_logger

logger = get_logger("indexer")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    rel_path TEXT NOT NULL,
    name TEXT NOT NULL,
    ext TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    page_count INTEGER,
    indexed_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_name ON files(name);
CREATE TABLE IF NOT EXISTS slide_texts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    page INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_texts_file ON slide_texts(file_id);
CREATE INDEX IF NOT EXISTS idx_texts_text ON slide_texts(text);
"""


class Indexer:
    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = paths.cache_dir() / "index.db"
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ---------- 基础 ----------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Indexer":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------- 增量同步 ----------

    def sync_scan(self, root: Path) -> ScanStats:
        """扫描 root 并增量同步索引（新增/更新/删除），返回统计。"""
        start = time.time()
        root = Path(root)
        stats = ScanStats()
        on_disk: dict[str, SlideFile] = {}
        for sf in iter_slide_files(root):
            stats.scanned += 1
            on_disk[str(sf.path)] = sf

        cur = self._conn.execute("SELECT id, path, size, mtime FROM files")
        existing = {row[1]: (row[0], row[2], row[3]) for row in cur.fetchall()}

        for path_str, sf in on_disk.items():
            if path_str not in existing:
                self._insert(sf)
                stats.added += 1
            else:
                fid, size, mtime = existing[path_str]
                if size != sf.size or mtime != sf.mtime:
                    self._update(fid, sf)
                    stats.updated += 1
                else:
                    stats.unchanged += 1

        for path_str, (fid, _, _) in existing.items():
            if path_str not in on_disk:
                self._conn.execute("DELETE FROM files WHERE id=?", (fid,))
                stats.removed += 1

        self._conn.commit()
        stats.elapsed = time.time() - start
        logger.info(
            "索引同步完成：磁盘 %d（新增 %d / 更新 %d / 跳过 %d / 删除 %d），耗时 %.2fs",
            stats.scanned, stats.added, stats.updated, stats.unchanged, stats.removed, stats.elapsed,
        )
        return stats

    def _insert(self, sf: SlideFile) -> int:
        cur = self._conn.execute(
            "INSERT INTO files(path, rel_path, name, ext, size, mtime, page_count, indexed_at) "
            "VALUES(?,?,?,?,?,?,NULL,?)",
            (str(sf.path), sf.rel_path, sf.name, sf.ext, sf.size, sf.mtime, time.time()),
        )
        return int(cur.lastrowid or 0)

    def _update(self, file_id: int, sf: SlideFile) -> None:
        # 内容变化 → 旧全文失效（P2 重新提取）
        self._conn.execute("DELETE FROM slide_texts WHERE file_id=?", (file_id,))
        self._conn.execute(
            "UPDATE files SET rel_path=?, name=?, ext=?, size=?, mtime=?, indexed_at=?, page_count=NULL "
            "WHERE id=?",
            (sf.rel_path, sf.name, sf.ext, sf.size, sf.mtime, time.time(), file_id),
        )

    # ---------- 查询 ----------

    def get_all_files(self) -> list[SlideFile]:
        cur = self._conn.execute(
            "SELECT path, size, mtime, name, rel_path FROM files ORDER BY rel_path"
        )
        return [SlideFile(path=Path(r[0]), size=r[1], mtime=r[2], name=r[3], rel_path=r[4]) for r in cur.fetchall()]

    def file_id_by_path(self, path: str) -> int | None:
        cur = self._conn.execute("SELECT id FROM files WHERE path=?", (path,))
        row = cur.fetchone()
        return int(row[0]) if row else None

    # ---------- 全文回填（P2 渲染管线调用） ----------

    def set_page_count(self, file_id: int, page_count: int) -> None:
        self._conn.execute("UPDATE files SET page_count=? WHERE id=?", (page_count, file_id))

    def upsert_slide_texts(self, file_id: int, texts: list[tuple[int, str]]) -> None:
        """texts: [(页码(1起), 该页文字), ...]；先清空旧记录再写入。"""
        self._conn.execute("DELETE FROM slide_texts WHERE file_id=?", (file_id,))
        self._conn.executemany(
            "INSERT INTO slide_texts(file_id, page, text) VALUES(?,?,?)",
            [(file_id, page, text) for page, text in texts],
        )
        self._conn.commit()
