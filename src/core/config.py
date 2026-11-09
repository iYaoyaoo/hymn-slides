"""配置：QSettings(IniFormat)。主目录/soffice 路径/缓存上限/放映确认开关（规范 §3-6）。

便携模式下配置文件落程序目录 data/config.ini。
"""
from __future__ import annotations

from pathlib import Path

from src.utils import paths

_ORG = "HymnSlides"
_APP = "HymnSlides"

# 键名（固定，勿改）
KEY_MAIN_DIR = "main_dir"
KEY_SOFFICE = "soffice_path"
KEY_CACHE_LIMIT_MB = "cache_limit_mb"
KEY_SINGLE_SCREEN_CONFIRM = "single_screen_confirm"

DEFAULT_CACHE_LIMIT_MB = 2048


class Config:
    """配置门面：封装 QSettings 读写与默认值。"""

    def __init__(self, settings_path: Path | None = None):
        from PySide6.QtCore import QSettings

        if settings_path is None and paths.is_portable():
            settings_path = paths.data_dir() / "config.ini"
        if settings_path is not None:
            self._settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        else:
            self._settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, _ORG, _APP)
        paths._ensure_core_app()

    # ---- 主目录 ----
    @property
    def main_dir(self) -> Path:
        raw = str(self._settings.value(KEY_MAIN_DIR, ""))
        return Path(raw).expanduser() if raw else paths.default_main_dir()

    def set_main_dir(self, path: Path) -> None:
        self._settings.setValue(KEY_MAIN_DIR, str(path))

    # ---- soffice 路径（手动指定，空=自动探测） ----
    @property
    def soffice_path(self) -> str:
        return str(self._settings.value(KEY_SOFFICE, ""))

    def set_soffice_path(self, value: str) -> None:
        self._settings.setValue(KEY_SOFFICE, value)

    # ---- 缓存上限（MB） ----
    @property
    def cache_limit_mb(self) -> int:
        val = self._settings.value(KEY_CACHE_LIMIT_MB, DEFAULT_CACHE_LIMIT_MB)
        try:
            v = int(val)
        except (TypeError, ValueError):
            v = DEFAULT_CACHE_LIMIT_MB
        return v if v > 0 else DEFAULT_CACHE_LIMIT_MB

    def set_cache_limit_mb(self, mb: int) -> None:
        self._settings.setValue(KEY_CACHE_LIMIT_MB, int(mb))

    # ---- 单屏放映确认开关 ----
    @property
    def single_screen_confirm(self) -> bool:
        val = self._settings.value(KEY_SINGLE_SCREEN_CONFIRM, True)
        if isinstance(val, bool):
            return val
        return str(val).lower() not in ("false", "0", "")

    def set_single_screen_confirm(self, on: bool) -> None:
        self._settings.setValue(KEY_SINGLE_SCREEN_CONFIRM, bool(on))

    def sync(self) -> None:
        self._settings.sync()
