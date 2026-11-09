"""pytest 全局夹具：离屏 QApplication（CI 无显示器环境）。

必须在任何测试运行前创建 QApplication——否则 src.utils.paths._ensure_core_app
会先创建 QCoreApplication 单例，之后无法升级为 QApplication（qFatal）。
"""
from __future__ import annotations

import os

# 必须在导入任何 Qt 模块之前设置
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

# 模块级创建并持有，防止 GC
_APP: QApplication | None = QApplication.instance()
if not isinstance(_APP, QApplication):
    _APP = QApplication([])

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return _APP
