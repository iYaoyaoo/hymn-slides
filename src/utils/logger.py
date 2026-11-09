"""日志：RotatingFileHandler 写 logs/app.log，禁止静默失败（规范 §3-4）。"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from src.utils import paths

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger("hymn")
    if _CONFIGURED:
        return logger
    logger.setLevel(level)

    try:
        file_handler = RotatingFileHandler(
            paths.log_dir() / "app.log", maxBytes=1024 * 1024, backupCount=5, encoding="utf-8"
        )
    except OSError:
        # 日志目录不可写时退回控制台，绝不因日志问题中断主流程
        file_handler = None

    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    if file_handler is not None:
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger(name: str = "") -> logging.Logger:
    return logging.getLogger(f"hymn.{name}") if name else logging.getLogger("hymn")
