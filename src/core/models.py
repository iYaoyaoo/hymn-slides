"""数据模型：支持格式、文件条目、扫描统计。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# 支持格式（规范 §4）
SUPPORTED_EXTS = frozenset({".ppt", ".pptx", ".pps", ".ppsx", ".pot", ".potx", ".odp"})


@dataclass
class SlideFile:
    """一个 PPT 文件条目。"""
    path: Path
    size: int
    mtime: float  # Unix 秒（round 4 位）
    name: str
    rel_path: str = ""

    @property
    def ext(self) -> str:
        return self.path.suffix.lower()

    @classmethod
    def from_path(cls, path: Path, root: Path) -> "SlideFile":
        st = path.stat()
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
        return cls(
            path=path,
            size=st.st_size,
            mtime=round(st.st_mtime, 4),
            name=path.name,
            rel_path=rel,
        )


@dataclass
class ScanStats:
    """一次扫描+索引的统计。"""
    scanned: int = 0          # 磁盘上发现的文件数
    added: int = 0            # 新入库
    updated: int = 0          # size/mtime 变化后更新
    unchanged: int = 0        # 跳过
    removed: int = 0          # 磁盘已不存在，从库中删除
    errors: list[str] = field(default_factory=list)
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class SearchResult:
    """搜索结果条目（v4 F3：树过滤按文件粒度，只含文件标识）。"""
    file_id: int
    path: str
    name: str
