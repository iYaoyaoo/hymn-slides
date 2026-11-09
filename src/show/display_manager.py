"""显示器管理（F7）：QScreen 枚举、动态增删响应、放映屏决策。

规范硬约束：禁止对屏幕身份（名称/序号/型号）做任何假设，
仅依据“是否主显示器”与几何位置决策。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication

from src.utils.logger import get_logger

logger = get_logger("display_manager")


@dataclass
class ScreenInfo:
    name: str                     # 仅用于展示/日志，不参与决策
    geometry: tuple[int, int, int, int]  # x, y, w, h
    is_primary: bool
    screen: object | None = field(repr=False, default=None)


def enumerate_screens() -> list[ScreenInfo]:
    """枚举当前全部显示器（QGuiApplication.screens()）。"""
    try:
        screens = list(QGuiApplication.screens())
        primary = QGuiApplication.primaryScreen()
    except RuntimeError:
        logger.error("枚举显示器失败：QGuiApplication 不可用")
        return []
    infos: list[ScreenInfo] = []
    for s in screens:
        g = s.geometry()
        infos.append(
            ScreenInfo(
                name=s.name(),
                geometry=(g.x(), g.y(), g.width(), g.height()),
                is_primary=(s is primary),
                screen=s,
            )
        )
    logger.info(
        "显示器枚举：%s",
        "; ".join(f"{i.name} {'(主)' if i.is_primary else ''}{i.geometry}" for i in infos),
    )
    return infos


def decide_show_screen(screens: list[ScreenInfo]) -> ScreenInfo | None:
    """单屏放映目标：主显示器（F6 单屏路径）。"""
    for s in screens:
        if s.is_primary:
            return s
    return screens[0] if screens else None


def decide_dual_layout(screens: list[ScreenInfo]) -> tuple[ScreenInfo | None, ScreenInfo | None]:
    """双屏布局：放映屏=非主显示器，演示者屏=主显示器（F6 双屏路径）。

    多个非主显示器时取几何面积最大者（纯几何决策，无身份假设）。
    """
    if len(screens) < 2:
        return (None, None)
    primary = next((s for s in screens if s.is_primary), None)
    others = [s for s in screens if not s.is_primary]
    if primary is None or not others:
        return (None, None)
    show = max(others, key=lambda s: s.geometry[2] * s.geometry[3])
    return (show, primary)


def screen_from_info(info: ScreenInfo):
    """ScreenInfo → QScreen（若实体仍存在）。"""
    if info.screen is not None:
        current = QGuiApplication.screens()
        if info.screen in current:
            return info.screen
    return None


class DisplayManager(QObject):
    """监听 screenAdded/screenRemoved，动态刷新布局（F7）。"""

    screens_changed = Signal(list)  # list[ScreenInfo]

    def __init__(self, parent=None):
        super().__init__(parent)
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._on_changed)
            app.screenRemoved.connect(self._on_removed_screen)
        self._screens: list[ScreenInfo] = enumerate_screens()

    def _on_changed(self, _screen=None) -> None:
        logger.info("显示器发生增删，刷新布局")
        self._screens = enumerate_screens()
        self.screens_changed.emit(self._screens)

    def _on_removed_screen(self, screen) -> None:
        logger.info("显示器已断开：%s", screen.name())
        self._on_changed(screen)

    @property
    def screens(self) -> list[ScreenInfo]:
        return self._screens

    def refresh(self) -> list[ScreenInfo]:
        self._screens = enumerate_screens()
        return self._screens
