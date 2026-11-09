"""soffice 探测：①配置手动指定 ②捆绑目录 ③系统安装（规范 §3-7）。

结果逐候选写日志；全部失败返回 None，由调用方给出引导提示。
不做平台专属 API 以外的假设；Windows 注册表探测属系统安装来源的一部分。
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from src.utils import paths
from src.utils.logger import get_logger

logger = get_logger("lo_detect")


@dataclass
class SofficeInfo:
    path: Path | None
    source: str  # "config" | "bundled" | "system" | ""
    candidates: list[str]  # 探测轨迹（每项含结果说明）

    @property
    def found(self) -> bool:
        return self.path is not None


def _bundled_candidates() -> list[Path]:
    """捆绑目录候选（发布包内 libreoffice/）。"""
    bundle = paths.app_bundle_dir()
    if sys.platform == "darwin" and bundle is not None:
        # <.app>/Contents/Resources/libreoffice/LibreOffice.app/Contents/MacOS/soffice
        return [
            bundle
            / "Contents"
            / "Resources"
            / "libreoffice"
            / "LibreOffice.app"
            / "Contents"
            / "MacOS"
            / "soffice"
        ]
    # Windows / 开发态：<exe目录>/libreoffice/program/soffice(.exe)
    exe_dir = paths.exe_dir()
    names = ["soffice.exe", "soffice"] if os.name == "nt" else ["soffice"]
    return [exe_dir / "libreoffice" / "program" / n for n in names]


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
    """按 配置→捆绑→系统 顺序探测 soffice，写日志并返回结果。

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

    # ② 捆绑目录
    for p in _bundled_candidates():
        if _is_executable(p):
            candidates.append(f"bundled: {p}（命中）")
            logger.info("soffice 探测：捆绑目录命中 %s", p)
            return SofficeInfo(p, "bundled", candidates)
        candidates.append(f"bundled: {p}（不存在）")

    # ③ 系统安装
    for p in _system_candidates():
        if _is_executable(p):
            candidates.append(f"system: {p}（命中）")
            logger.info("soffice 探测：系统安装命中 %s", p)
            return SofficeInfo(p, "system", candidates)
        candidates.append(f"system: {p}（不存在）")

    logger.error("soffice 探测：三个来源均未找到 LibreOffice")
    return SofficeInfo(None, "", candidates)
