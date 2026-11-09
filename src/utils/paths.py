"""路径计算：可执行目录、便携模式、数据/缓存/日志/LO profile 目录。

全程 pathlib；便携模式判定见规范 §3-5。
"""
from __future__ import annotations

import sys
from pathlib import Path

PORTABLE_FLAG = "portable.flag"
DATA_SUBDIR = "data"

from PySide6.QtCore import QStandardPaths  # noqa: E402（模块级常量前置需要）

_ORG_NAME = "HymnSlides"
_APP_NAME = "HymnSlides"


def exe_dir() -> Path:
    """可执行文件所在目录；开发态（非 frozen）为项目根目录（main.py 所在处）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def app_bundle_dir() -> Path | None:
    """macOS 打包态返回 .app 目录；其余返回 None。"""
    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        macos_dir = exe_dir()  # HymnSlides.app/Contents/MacOS
        if macos_dir.parent.name == "Contents":
            return macos_dir.parent.parent
    return None


def portable_flag_dir() -> Path:
    """portable.flag 的查找目录：macOS 打包态为 .app 同级，其余为 exe_dir。"""
    bundle = app_bundle_dir()
    if bundle is not None:
        return bundle.parent
    return exe_dir()


def is_portable() -> bool:
    return (portable_flag_dir() / PORTABLE_FLAG).is_file()


def _ensure_core_app() -> None:
    """CLI 场景下保证 QStandardPaths 可用（需要 QCoreApplication 实例）。"""
    from PySide6.QtCore import QCoreApplication

    QCoreApplication.setOrganizationName(_ORG_NAME)
    QCoreApplication.setApplicationName(_APP_NAME)
    app = QCoreApplication.instance()
    if app is not None:
        app.setOrganizationName(_ORG_NAME)
        app.setApplicationName(_APP_NAME)
    else:
        QCoreApplication([_APP_NAME])


def qstandard_path(location) -> Path:
    """取 QStandardPaths 标准目录（非便携模式）。"""
    from PySide6.QtCore import QStandardPaths

    _ensure_core_app()
    return Path(QStandardPaths.writableLocation(location))


def data_dir() -> Path:
    """配置/日志等持久数据目录（AppLocalDataLocation；便携模式落程序目录 data/）。"""
    if is_portable():
        return portable_flag_dir() / DATA_SUBDIR
    return qstandard_path(QStandardPaths.StandardLocation.AppLocalDataLocation)


def cache_dir() -> Path:
    """缓存目录（AppCacheLocation；便携模式落 data/cache）。"""
    if is_portable():
        return data_dir() / "cache"
    return qstandard_path(QStandardPaths.StandardLocation.AppCacheLocation)


def log_dir() -> Path:
    p = data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def lo_profile_dir() -> Path:
    """soffice 独立临时 profile 目录（规范 §3-8）。"""
    p = data_dir() / "lo_profile"
    p.mkdir(parents=True, exist_ok=True)
    return p


def default_main_dir() -> Path:
    """默认主目录=可执行文件所在目录（规范 F1）。"""
    return exe_dir()
