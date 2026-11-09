"""--selftest：双平台环境探测（OS / Python / LibreOffice 三候选来源），结果写日志（规范 P0）。"""
from __future__ import annotations

import platform
import sys

from src.render import lo_detect
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


def _lo_section(soffice: lo_detect.SofficeInfo) -> list[str]:
    lines = []
    for c in soffice.candidates:
        lines.append(f"LibreOffice 候选: {c}")
        logger.info("selftest: %s", c)
    if soffice.found:
        lines.append(f"LibreOffice: 命中 {soffice.path}（来源={soffice.source}）")
        logger.info("LibreOffice 探测命中：%s（来源=%s）", soffice.path, soffice.source)
    else:
        lines.append("LibreOffice: 未找到 —— 请安装 LibreOffice 或在设置中手动指定 soffice 路径")
        logger.error("selftest：LibreOffice 未找到")
    return lines


def run_selftest() -> tuple[bool, str]:
    """执行环境自检，返回（是否全部通过, 报告文本）。"""
    lines: list[str] = []
    os_lines = _os_section()
    py_lines = _python_section()

    from src.core.config import Config

    cfg = Config()
    info = lo_detect.detect_soffice(cfg.soffice_path)
    lo_lines = _lo_section(info)

    os_ok = not any("不在支持平台内" in x for x in os_lines)
    py_ok = not any("需要 3.11+" in x for x in py_lines)

    ok = os_ok and py_ok and info.found
    lines.extend(os_lines)
    lines.extend(py_lines)
    lines.extend(lo_lines)
    lines.append(f"SELFTEST RESULT: {'PASS' if ok else 'FAIL'}")
    logger.info("selftest 完成：%s", "PASS" if ok else "FAIL")
    return ok, "\n".join(lines)
