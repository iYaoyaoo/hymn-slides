"""引擎探测（v4 规范 §3-7）：PowerPoint → WPS → LibreOffice 三级链。

探测只做注册表/文件存在性检查（不启动 Office 应用），结果逐候选写日志。
手动指定（QSettings）：libreoffice=soffice 路径；powerpoint=PowerPoint 程序路径；
wps=WPS 程序路径。手动指定优先于自动探测。
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger("engine_detect")

ENGINE_POWERPOINT = "powerpoint"
ENGINE_WPS = "wps"
ENGINE_LIBREOFFICE = "libreoffice"

# 优先级顺序（v4 规范）
PRIORITY = [ENGINE_POWERPOINT, ENGINE_WPS, ENGINE_LIBREOFFICE]

MAC_PPT_DEFAULT = Path("/Applications/Microsoft PowerPoint.app")


@dataclass
class EngineInfo:
    name: str
    available: bool
    supports_render: bool  # 页面图片导出 + 全文文字
    supports_show: bool    # 原生放映控制
    detail: str = ""
    manual: bool = False    # 是否来自手动指定


@dataclass
class EngineCandidates:
    """一次探测的完整结果（写日志/selftest 用）。"""

    infos: list[EngineInfo] = field(default_factory=list)

    def first_show(self) -> EngineInfo | None:
        for i in self.infos:
            if i.available and i.supports_show:
                return i
        return None

    def first_render(self) -> EngineInfo | None:
        for i in self.infos:
            if i.available and i.supports_render:
                return i
        return None

    def any_available(self) -> bool:
        return any(i.available for i in self.infos)


def _registry_has(prog_id: str) -> bool:
    """Windows 注册表 ProgID 检查（不启动应用）。"""
    if os.name != "nt":
        return False
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id):
            return True
    except OSError:
        return False
    except ImportError:
        return False


def _detect_powerpoint(manual_path: str = "") -> EngineInfo:
    if manual_path:
        p = Path(manual_path).expanduser()
        if sys.platform == "darwin":
            ok = p.is_dir() and (p / "Contents" / "MacOS" / "Microsoft PowerPoint").is_file()
        else:
            ok = p.is_file()
        return EngineInfo(
            ENGINE_POWERPOINT, ok,
            supports_render=(os.name == "nt" and ok),  # Mac 版无导出图片接口
            supports_show=ok,
            detail=f"手动指定：{p}",
            manual=True,
        )
    if sys.platform == "darwin":
        ok = (MAC_PPT_DEFAULT / "Contents" / "MacOS" / "Microsoft PowerPoint").is_file()
        return EngineInfo(ENGINE_POWERPOINT, ok, supports_render=False, supports_show=ok,
                          detail=f"{MAC_PPT_DEFAULT}（{'存在' if ok else '未安装'}）")
    if os.name == "nt":
        ok = _registry_has("PowerPoint.Application")
        return EngineInfo(ENGINE_POWERPOINT, ok, supports_render=ok, supports_show=ok,
                          detail=f"注册表 ProgID PowerPoint.Application（{'命中' if ok else '未安装'}）")
    return EngineInfo(ENGINE_POWERPOINT, False, False, False, detail="不支持的平台")


def _detect_wps(manual_path: str = "") -> EngineInfo:
    # macOS WPS 无自动化接口：即使安装也不可用（v4 规范）
    if sys.platform == "darwin":
        return EngineInfo(ENGINE_WPS, False, False, False, detail="macOS 无自动化接口，跳过")
    if manual_path and Path(manual_path).is_file():
        return EngineInfo(ENGINE_WPS, True, True, True, detail=f"手动指定：{manual_path}", manual=True)
    if os.name == "nt":
        for prog_id in ("Kwpp.Application", "wpp.Application", "KWPP.Application"):
            if _registry_has(prog_id):
                return EngineInfo(ENGINE_WPS, True, True, True,
                                  detail=f"注册表 ProgID {prog_id}（命中）")
        return EngineInfo(ENGINE_WPS, False, False, False, detail="注册表未找到 Kwpp/wpp ProgID（未安装）")
    return EngineInfo(ENGINE_WPS, False, False, False, detail="不支持的平台")


def _detect_libreoffice(manual_path: str = "") -> EngineInfo:
    from src.render.lo_detect import detect_soffice

    info = detect_soffice(manual_path)
    return EngineInfo(
        ENGINE_LIBREOFFICE, info.found, supports_render=info.found, supports_show=info.found,
        detail=str(info.path) if info.found else "系统未安装 LibreOffice",
        manual=bool(manual_path) and info.found and info.source == "config",
    )


def detect_engines(
    ppt_path: str = "",
    wps_path: str = "",
    lo_path: str = "",
) -> EngineCandidates:
    """按优先级探测三级引擎，逐候选写日志。"""
    cands = EngineCandidates()
    detectors = (
        (ENGINE_POWERPOINT, lambda: _detect_powerpoint(ppt_path)),
        (ENGINE_WPS, lambda: _detect_wps(wps_path)),
        (ENGINE_LIBREOFFICE, lambda: _detect_libreoffice(lo_path)),
    )
    for name, det in detectors:
        info = det()
        cands.infos.append(info)
        logger.info(
            "引擎探测 %s：%s（渲染=%s 放映=%s）",
            name,
            info.detail,
            "可用" if info.supports_render and info.available else "不可用",
            "可用" if info.supports_show and info.available else "不可用",
        )
    return cands


def detect_from_config(config) -> EngineCandidates:
    """从 Config 读手动路径并探测。"""
    return detect_engines(
        ppt_path=str(getattr(config, "ppt_path", "") or ""),
        wps_path=str(getattr(config, "wps_path", "") or ""),
        lo_path=str(getattr(config, "soffice_path", "") or ""),
    )
