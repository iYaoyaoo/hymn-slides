"""递归扫描：跳过隐藏/系统目录，收集支持的 PPT 格式（规范 F2）。"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from src.core.models import SUPPORTED_EXTS, SlideFile
from src.utils.logger import get_logger

logger = get_logger("scanner")

# 跳过的目录名（隐藏目录由 is_hidden 统一处理）
SYSTEM_DIRS = frozenset({
    "System Volume Information",
    "$RECYCLE.BIN",
    "$RECYCLE",
    "__MACOSX",
    "lo_profile",
    "lost+found",
})


def is_hidden(entry: Path) -> bool:
    name = entry.name
    if name.startswith("."):
        return True
    if name.endswith(".tmp") or name.startswith("~$"):  # Office 临时锁文件
        return True
    return False


def iter_slide_files(root: Path) -> Iterator[SlideFile]:
    """递归产出 root 下所有支持的 PPT 文件（已跳过隐藏/系统目录）。

    单个文件 stat 失败记日志跳过，不中断扫描。
    """
    root = Path(root)
    if not root.is_dir():
        logger.error("扫描根目录不存在或不是目录：%s", root)
        return
    for dirpath, dirnames, filenames in root.walk(follow_symlinks=False):
        # walk(top_down=True 默认)：原地修改 dirnames 即可剪枝
        dirnames[:] = [d for d in dirnames if not is_hidden(Path(d)) and d not in SYSTEM_DIRS]
        for fn in filenames:
            if is_hidden(Path(fn)):
                continue
            p = Path(dirpath) / fn
            if p.suffix.lower() not in SUPPORTED_EXTS:
                continue
            try:
                yield SlideFile.from_path(p, root)
            except OSError as e:
                logger.warning("扫描文件失败 %s: %s", p, e)


def scan_directory(root: Path) -> list[SlideFile]:
    return list(iter_slide_files(root))
