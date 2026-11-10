"""macOS PowerPoint 引擎（AppleScript，v4 规范 F5）。

Mac 版 PowerPoint 提供 AppleScript 放映控制；无导出图片接口（render 能力缺失，
出图/全文回落 LibreOffice）。放映窗口的位置由 PowerPoint 自身的
"演示者显示/放映于"偏好决定，AppleScript 无法精确指定屏幕（已知限制，README 标注）。

AppleScript 语法依据 Microsoft Office for Mac 字典实现；本开发机无 PowerPoint，
实际效果列入人工复核清单（决策规则 §8）。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from src.render.engine import BaseEngine, ShowSession
from src.utils.logger import get_logger

logger = get_logger("as_engine")

MAC_PPT_BIN = Path("/Applications/Microsoft PowerPoint.app/Contents/MacOS/Microsoft PowerPoint")


def _run_osascript(script: str) -> tuple[int, str]:
    proc = subprocess.run(  # noqa: S603（参数列表调用）
        ["osascript", "-e", script], capture_output=True, text=True, timeout=60, check=False
    )
    return proc.returncode, proc.stdout.strip() + (("\n" + proc.stderr.strip()) if proc.stderr.strip() else "")


class MacPptShowSession(ShowSession):
    def __init__(self, ppt: Path):
        self._ppt = ppt
        self._active = True

    def current_page(self) -> int:
        rc, out = _run_osascript(
            'tell application "Microsoft PowerPoint"\n'
            "try\n"
            "	return slide index of slide of slide show view of active presentation\n"
            "on error\n"
            "	return 0\n"
            "end try\n"
            "end tell"
        )
        if rc != 0:
            return 0
        try:
            return int(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return 0

    def next_page(self) -> None:
        _run_osascript(
            'tell application "Microsoft PowerPoint" to advance slide show of slide show view of active presentation'
        )

    def prev_page(self) -> None:
        _run_osascript(
            'tell application "Microsoft PowerPoint" to go to previous slide of slide show view of active presentation'
        )

    def end(self) -> None:
        _run_osascript(
            'tell application "Microsoft PowerPoint" to exit slide show of slide show view of active presentation'
        )
        self._active = False


class MacPptEngine(BaseEngine):
    name = "powerpoint"
    supports_render = False  # Mac 版无导出图片接口
    supports_show = True

    def start_show(self, ppt: Path, screen_rect: tuple[int, int, int, int]) -> ShowSession:
        rc, out = _run_osascript(
            'tell application "Microsoft PowerPoint"\n'
            "activate\n"
            f'open POSIX file "{ppt}"\n'
            "delay 1\n"
            "run slide show slide show of active presentation\n"
            "end tell"
        )
        if rc != 0:
            raise RuntimeError(f"AppleScript 启动 PowerPoint 放映失败：{out}")
        logger.info("AppleScript 放映已启动（屏幕定位由 PowerPoint 偏好决定，rect=%s 忽略）", screen_rect)
        return MacPptShowSession(ppt)
