"""LibreOffice 探测（v4 规范 §3-7）：①配置手动指定 ②系统安装。

v4 起 LibreOffice 不再便携捆绑（bundle_lo 移除），探测仅两步。
结果逐候选写日志；全部失败返回 None，由调用方给出引导提示。
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger("lo_detect")


@dataclass
class SofficeInfo:
    path: Path | None
    source: str  # "config" | "system" | ""
    candidates: list[str]  # 探测轨迹（每项含结果说明）

    @property
    def found(self) -> bool:
        return self.path is not None


def _system_candidates() -> list[Path]:
    """系统安装候选。"""
    if sys.platform == "darwin":
        return [
            Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        ]
    if os.name == "nt":
        cands: list[Path] = []
        # 注册表探测
        try:
            import winreg  # type: ignore

            for root in (winreg.HKEY_LOCAL_MACHINE,):
                for sub in (
                    r"SOFTWARE\LibreOffice\UNO\InstallPath",
                    r"SOFTWARE\WOW6432Node\LibreOffice\UNO\InstallPath",
                ):
                    try:
                        with winreg.OpenKey(root, sub) as key:
                            val, _ = winreg.QueryValueEx(key, "")
                            cands.append(Path(val) / "soffice.exe")
                    except OSError:
                        continue
        except ImportError:
            pass
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        cands.extend(
            [
                Path(pf) / "LibreOffice" / "program" / "soffice.exe",
                Path(pf86) / "LibreOffice" / "program" / "soffice.exe",
            ]
        )
        return cands
    return []


def _is_executable(p: Path) -> bool:
    return p.is_file() and (os.access(p, os.X_OK) or os.name == "nt")


def detect_soffice(config_value: str = "") -> SofficeInfo:
    """按 配置→系统安装 顺序探测 soffice，写日志并返回结果。

    config_value: QSettings 中用户手动指定的路径（可为空）。
    """
    candidates: list[str] = []

    # ① 配置手动指定
    if config_value:
        p = Path(config_value).expanduser()
        if _is_executable(p):
            candidates.append(f"config: {p}（命中）")
            logger.info("soffice 探测：配置指定命中 %s", p)
            return SofficeInfo(p, "config", candidates)
        candidates.append(f"config: {p}（不存在或不可执行）")
        logger.warning("soffice 探测：配置指定路径无效：%s", p)

    # ② 系统安装
    for p in _system_candidates():
        if _is_executable(p):
            candidates.append(f"system: {p}（命中）")
            logger.info("soffice 探测：系统安装命中 %s", p)
            return SofficeInfo(p, "system", candidates)
        candidates.append(f"system: {p}（不存在）")

    logger.error("soffice 探测：未找到 LibreOffice")
    return SofficeInfo(None, "", candidates)
