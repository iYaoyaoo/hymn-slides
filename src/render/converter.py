"""PPT→PDF 转换：LibreOffice 无头，独立 profile，超时 120s，失败重试 1 次（规范 §3-8、P2）。"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from src.utils import paths
from src.utils.logger import get_logger

logger = get_logger("converter")

TIMEOUT_SECONDS = 120

_PROFILE_READY = False
_STALE_SECONDS = 24 * 3600


def profile_dir() -> Path:
    """soffice 独立临时 profile（规范 §3-8）：数据目录 lo_profile/ 下每线程子目录。

    v4.1：不同线程各自独立 profile → 支持多路并行无头转换（互不顶掉）；
    不同进程（用户双开）亦天然隔离。退出时删除自身目录；清理超 24h 遗留目录。
    """
    global _PROFILE_READY
    base = paths.lo_profile_dir()
    mine = base / f"p{os.getpid()}_{threading.get_ident()}"
    if not _PROFILE_READY:
        _PROFILE_READY = True
        now = time.time()
        for d in base.glob("p*"):
            try:
                if d != mine and (now - d.stat().st_mtime) > _STALE_SECONDS:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass
        atexit.register(lambda: shutil.rmtree(mine, ignore_errors=True))
    mine.mkdir(parents=True, exist_ok=True)
    return mine


@dataclass
class ConvertResult:
    ok: bool
    pdf_path: Path | None = None
    error: str = ""
    elapsed: float = 0.0


def convert_to_pdf(
    ppt_path: Path,
    out_dir: Path,
    soffice: Path,
    timeout: int = TIMEOUT_SECONDS,
) -> ConvertResult:
    """将 ppt_path 转换为 PDF 至 out_dir（同名 .pdf）。

    子进程一律参数列表调用；独立临时 profile 避免与用户打开的 LibreOffice 冲突。
    失败（含超时）重试 1 次；再失败记日志返回 ok=False（调用方给 UI 角标，不崩溃）。
    """
    ppt_path = Path(ppt_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    expected_pdf = out_dir / (ppt_path.stem + ".pdf")
    if expected_pdf.is_file() and expected_pdf.stat().st_size > 0:
        return ConvertResult(ok=True, pdf_path=expected_pdf, elapsed=0.0)

    profile = profile_dir()
    cmd = [
        str(soffice),
        "--headless",
        "--norestore",
        "--nolockcheck",
        f"-env:UserInstallation={profile.as_uri()}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(ppt_path),
    ]

    start = time.time()
    last_error = ""
    # v4.1：每线程独立 profile，天然支持并行转换（不再全局串行锁）
    for attempt in (1, 2):
        try:
            proc = subprocess.run(  # noqa: S603（参数列表调用，无 shell）
                cmd,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            if proc.returncode == 0 and expected_pdf.is_file() and expected_pdf.stat().st_size > 0:
                elapsed = time.time() - start
                logger.info("转换成功（第 %d 次）：%s → %s，耗时 %.1fs", attempt, ppt_path.name, expected_pdf, elapsed)
                return ConvertResult(ok=True, pdf_path=expected_pdf, elapsed=elapsed)
            last_error = f"returncode={proc.returncode} stderr={proc.stderr.decode('utf-8', 'replace')[:300]}"
            logger.warning(
                "转换失败（第 %d 次）：%s，%s", attempt, ppt_path.name, last_error
            )
        except subprocess.TimeoutExpired:
            last_error = f"超时（>{timeout}s）"
            logger.warning("转换超时（第 %d 次）：%s", attempt, ppt_path.name)
        except OSError as e:
            last_error = str(e)
            logger.error("转换异常：%s，%s", ppt_path.name, e)
            break  # 环境级错误（soffice 不可执行等）不重试

    logger.error("转换最终失败：%s，%s", ppt_path.name, last_error)
    return ConvertResult(ok=False, error=last_error, elapsed=time.time() - start)
