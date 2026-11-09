"""搜索：文件名模糊 + 幻灯片全文（LIKE，最简方案见 docs/schema.md）。"""
from __future__ import annotations

from src.core.models import SearchResult
from src.utils.logger import get_logger

logger = get_logger("search")

_SNIPPET_CONTEXT = 20  # 全文命中片段：关键词前后各取字符数


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
    """全文搜索：返回 file+页码+片段。同一文件多页命中各为一条。"""
    if not keyword.strip():
        return []
    kw = keyword.strip()
    pattern = f"%{_escape_like(kw)}%"
    cur = conn.execute(
        r"SELECT f.id, f.path, f.name, t.page, t.text "
        r"FROM slide_texts t JOIN files f ON f.id = t.file_id "
        r"WHERE t.text LIKE ? ESCAPE '\' "
        r"ORDER BY f.name, t.page LIMIT ?",
        (pattern, limit),
    )
    results: list[SearchResult] = []
    for fid, path, name, page, text in cur.fetchall():
        snippet = _make_snippet(text, kw)
        results.append(SearchResult(file_id=fid, path=path, name=name, page=page, snippet=snippet))
    return results


def _make_snippet(text: str, kw: str) -> str:
    """取关键词前后各 _SNIPPET_CONTEXT 字符，关键词部分用【】标出。"""
    pos = text.find(kw)
    if pos < 0:
        return text[: _SNIPPET_CONTEXT * 2]
    start = max(0, pos - _SNIPPET_CONTEXT)
    end = min(len(text), pos + len(kw) + _SNIPPET_CONTEXT)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:pos]}【{kw}】{text[pos + len(kw):end]}{suffix}"


def search_all(conn, keyword: str, limit: int = 200) -> list[SearchResult]:
    """文件名 + 全文合并搜索；文件名命中排前，全文按文件名/页码排序。"""
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
