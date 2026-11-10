"""搜索：文件名模糊 + 幻灯片全文（LIKE，最简方案见 docs/schema.md）。

v4 F3：命中仅用于过滤树（命中文件+祖先链），无结果面板，故只返回文件
标识（file_id/path/name），不生成命中片段。
"""
from __future__ import annotations

from src.core.models import SearchResult
from src.utils.logger import get_logger

logger = get_logger("search")


def _escape_like(kw: str) -> str:
    return kw.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def search_filename(conn, keyword: str, limit: int = 200) -> list[SearchResult]:
    """文件名模糊搜索。"""
    if not keyword.strip():
        return []
    pattern = f"%{_escape_like(keyword.strip())}%"
    cur = conn.execute(
        r"SELECT id, path, name FROM files WHERE name LIKE ? ESCAPE '\' ORDER BY name LIMIT ?",
        (pattern, limit),
    )
    return [SearchResult(file_id=r[0], path=r[1], name=r[2]) for r in cur.fetchall()]


def search_fulltext(conn, keyword: str, limit: int = 200) -> list[SearchResult]:
    """全文搜索：同一文件多页命中合并为一条（树过滤按文件粒度）。"""
    if not keyword.strip():
        return []
    pattern = f"%{_escape_like(keyword.strip())}%"
    cur = conn.execute(
        r"SELECT DISTINCT f.id, f.path, f.name "
        r"FROM slide_texts t JOIN files f ON f.id = t.file_id "
        r"WHERE t.text LIKE ? ESCAPE '\' "
        r"ORDER BY f.name LIMIT ?",
        (pattern, limit),
    )
    return [SearchResult(file_id=r[0], path=r[1], name=r[2]) for r in cur.fetchall()]


def search_all(conn, keyword: str, limit: int = 200) -> list[SearchResult]:
    """文件名 + 全文合并搜索；文件名命中排前，全文按文件名排序。"""
    by_name = search_filename(conn, keyword, limit)
    by_text = search_fulltext(conn, keyword, limit)
    seen: set[int] = set()
    out: list[SearchResult] = []
    for r in by_name:
        out.append(r)
        seen.add(r.file_id)
    for r in by_text:
        if r.file_id not in seen:
            out.append(r)
    logger.info("搜索“%s”：文件名 %d 条，全文 %d 条", keyword, len(by_name), len(by_text))
    return out[:limit]
