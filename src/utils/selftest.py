"""--selftest：环境探测（OS / Python / 引擎三级链 PowerPoint→WPS→LibreOffice），结果写日志（v4 规范）。"""
from __future__ import annotations

import platform
import sys

from src.render.engine_detect import detect_engines
from src.utils.logger import get_logger

logger = get_logger("selftest")


def _os_section() -> list[str]:
    system = platform.system()
    release = platform.release()
    machine = platform.machine()
    ok = system in ("Darwin", "Windows")
    line = f"OS: {system} {release} ({machine})"
    if not ok:
        line += " —— 不在支持平台内（仅支持 Windows / macOS）"
    logger.info("%s", line)
    return [line]


def _python_section() -> list[str]:
    version = sys.version_info
    ok = version >= (3, 11)
    line = (
        f"Python: {sys.version.split()[0]} ({sys.executable}) "
        f"frozen={bool(getattr(sys, 'frozen', False))}"
    )
    if not ok:
        line += " —— 需要 3.11+"
    logger.info("%s", line)
    return [line]


def _engine_section(cands) -> list[str]:
    from src.render.engine import EngineChain

    lines = []
    for line in EngineChain([], cands).summary():
        lines.append(line)
        logger.info("selftest: %s", line)
    render = cands.first_render()
    show = cands.first_show()
    lines.append(f"当前渲染引擎: {render.name if render else '无（需安装 PowerPoint/WPS/LibreOffice 之一）'}")
    lines.append(f"当前放映引擎: {show.name if show else '无（需安装 PowerPoint/WPS/LibreOffice 之一）'}")
    if render is None or show is None:
        lines.append("引导：请安装 PowerPoint / WPS / LibreOffice 之一，或访问官网下载")
        logger.error("selftest：未检测到任何可用引擎")
    return lines


def run_selftest() -> tuple[bool, str]:
    """执行环境自检，返回（是否全部通过, 报告文本）。"""
    lines: list[str] = []
    os_lines = _os_section()
    py_lines = _python_section()

    from src.core.config import Config

    cfg = Config()
    cands = detect_engines(
        ppt_path=cfg.ppt_path,
        wps_path=cfg.wps_path,
        lo_path=cfg.soffice_path,
    )
    engine_lines = _engine_section(cands)

    os_ok = not any("不在支持平台内" in x for x in os_lines)
    py_ok = not any("需要 3.11+" in x for x in py_lines)
    engines_ok = cands.any_available()

    ok = os_ok and py_ok and engines_ok
    lines.extend(os_lines)
    lines.extend(py_lines)
    lines.extend(engine_lines)
    lines.append(f"SELFTEST RESULT: {'PASS' if ok else 'FAIL'}")
    logger.info("selftest 完成：%s", "PASS" if ok else "FAIL")
    return ok, "\n".join(lines)
