"""macOS PowerPoint 引擎（AppleScript，v4 规范 F5）。

Mac 版 PowerPoint 提供 AppleScript 放映控制；无导出图片接口（render 能力缺失，
出图/全文回落 LibreOffice）。放映窗口的位置由 PowerPoint 自身的
"演示者显示/放映于"偏好决定，AppleScript 无法精确指定屏幕（已知限制，README 标注）。

v4.2 真机发现（GUI 验收日志）：启动放映失败时错误信息为空（违反可诊断性）。
加固：①启动拆为"打开文稿"与"启动放映"两步，放映命令重试等待冷启动就绪；
②错误信息始终包含 rc 与原始输出（stdout/stderr 分记日志）。
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from src.render.engine import BaseEngine, ShowSession
from src.utils.logger import get_logger

logger = get_logger("as_engine")

MAC_PPT_BIN = Path("/Applications/Microsoft PowerPoint.app/Contents/MacOS/Microsoft PowerPoint")

OPEN_WAIT_SECONDS = 30   # 打开文稿后等待 active presentation 就绪的上限
RUN_RETRY_TIMES = 15     # 启动放映命令重试次数（每次间隔 1s）


def _run_osascript(script: str, timeout: int = 60) -> tuple[int, str]:
    """执行 AppleScript，返回 (returncode, 诊断输出)。输出为空时给占位文本避免空错误。"""
    proc = subprocess.run(  # noqa: S603（参数列表调用）
        ["osascript", "-e", script], capture_output=True, text=True, timeout=timeout, check=False
    )
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if proc.returncode != 0:
        logger.error("AppleScript 失败：rc=%d stdout=%r stderr=%r", proc.returncode, out, err)
    return proc.returncode, (err or out or "（osascript 无输出）")


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
        # ①打开文稿（activate 触发冷启动时本步耗时较长）
        open_rc, open_out = _run_osascript(
            'tell application "Microsoft PowerPoint"\n'
            "activate\n"
            f'open POSIX file "{ppt}"\n'
            "end tell",
            timeout=90,
        )
        if open_rc != 0:
            raise RuntimeError(f"AppleScript 打开演示文稿失败（rc={open_rc}）：{open_out}")

        # ②等待 active presentation 就绪后启动放映（冷启动后立即执行会因文稿未就绪失败）
        run_cmd = (
            'tell application "Microsoft PowerPoint" to '
            "run slide show slide show of active presentation"
        )
        last_out = ""
        deadline = time.time() + OPEN_WAIT_SECONDS
        for _ in range(RUN_RETRY_TIMES):
            rc, last_out = _run_osascript(run_cmd)
            if rc == 0:
                logger.info("AppleScript 放映已启动（屏幕定位由 PowerPoint 偏好决定，rect=%s 忽略）", screen_rect)
                return MacPptShowSession(ppt)
            if time.time() >= deadline:
                break
            time.sleep(1)
        raise RuntimeError(
            f"AppleScript 启动 PowerPoint 放映失败（重试 {RUN_RETRY_TIMES} 次，rc={rc}）：{last_out}"
        )
