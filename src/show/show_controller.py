"""放映控制器：状态机（idle → countdown → showing → ended）与屏幕布局。

P5：单屏路径（3 秒倒计时确认后本屏放映）。
P6：双屏路径（演示者窗）在本模块扩展。
"""
from __future__ import annotations

import enum
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from src.show.display_manager import ScreenInfo, decide_show_screen, decide_dual_layout
from src.show.projection_window import ProjectionWindow
from src.utils.logger import get_logger

logger = get_logger("show_controller")

COUNTDOWN_SECONDS = 3


class ShowState(enum.Enum):
    IDLE = "idle"
    COUNTDOWN = "countdown"
    SHOWING = "showing"
    ENDED = "ended"


class CountdownOverlay(QWidget):
    """全屏倒计时确认层：3→2→1 后开始放映；Esc/点击取消。"""

    cancelled = Signal()
    countdown_finished = Signal()

    def __init__(self, screen, seconds: int = COUNTDOWN_SECONDS, parent=None):
        super().__init__(parent)
        self._seconds = seconds
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setStyleSheet("background-color: black;")
        from PySide6.QtWidgets import QLabel, QVBoxLayout

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        layout = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: white; font-size: 160px;")
        layout.addWidget(self.label)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        if screen is not None:
            self.setGeometry(screen.geometry())
            self.setScreen(screen)

    def begin(self) -> None:
        self._remaining = self._seconds
        self._render()
        self.showFullScreen()
        self._timer.start()

    def _render(self) -> None:
        self.label.setText(str(self._remaining))

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining > 0:
            self._render()
            return
        self._timer.stop()
        self.close()
        self.countdown_finished.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._timer.stop()
            self.close()
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # 点击即取消确认（避免误放映）
        self._timer.stop()
        self.close()
        self.cancelled.emit()


class ShowController(QObject):
    """放映流程编排：选择目标屏 → 倒计时（可配）→ 放映 → 结束/拔屏恢复。"""

    state_changed = Signal(str)      # ShowState.value
    request_show_for = Signal(str)   # 开始放映的文件路径（UI 状态记录用）

    def __init__(self, page_worker, config, parent=None):
        super().__init__(parent)
        self._worker = page_worker
        self._config = config
        self._state = ShowState.IDLE
        self._projection: ProjectionWindow | None = None
        self._overlay: CountdownOverlay | None = None
        self._screen_removed_watch = None

    @property
    def state(self) -> ShowState:
        return self._state

    def _set_state(self, s: ShowState) -> None:
        self._state = s
        logger.info("放映状态：%s", s.value)
        self.state_changed.emit(s.value)

    # ---------- 启动 ----------

    def start(self, ppt: Path, screens: list[ScreenInfo], dual_allowed: bool = False) -> None:
        """启动放映。单屏：倒计时后本屏放映；≥2 屏且 dual_allowed：放映屏=非主屏。

        P5 阶段 dual_allowed 恒为 False（双屏编排 P6 提供）。
        """
        if self._state in (ShowState.COUNTDOWN, ShowState.SHOWING):
            logger.warning("放映已在进行中，忽略重复启动")
            return

        if len(screens) >= 2 and dual_allowed:
            show_screen, _presenter = decide_dual_layout(screens)
        else:
            show_screen = decide_show_screen(screens)
        if show_screen is None or show_screen.screen is None:
            logger.error("无可用显示器，放映取消")
            return

        self._ppt = Path(ppt)
        self._show_screen = show_screen
        self.request_show_for.emit(str(self._ppt))

        single = len(screens) < 2
        if single and self._config.single_screen_confirm:
            self._set_state(ShowState.COUNTDOWN)
            self._overlay = CountdownOverlay(show_screen.screen)
            self._overlay.countdown_finished.connect(self._begin_projection)
            self._overlay.cancelled.connect(self._on_cancelled)
            self._overlay.begin()
        else:
            # 双屏无需确认，直接放映；单屏关闭确认开关同理
            self._begin_projection()

    # ---------- 内部流转 ----------

    def _begin_projection(self) -> None:
        self._overlay = None
        self._projection = ProjectionWindow(self._worker, self._ppt)
        self._projection.show_ended.connect(self._on_ended)
        self._projection.page_changed.connect(lambda _p: None)
        self._watch_screen_removal()
        self._projection.show_on_screen(self._show_screen.screen)
        self._set_state(ShowState.SHOWING)

    def _on_cancelled(self) -> None:
        self._overlay = None
        self._set_state(ShowState.ENDED)
        self._cleanup()

    def _on_ended(self) -> None:
        self._set_state(ShowState.ENDED)
        self._cleanup()

    def _cleanup(self) -> None:
        self._projection = None
        if self._screen_removed_watch is not None:
            try:
                from PySide6.QtGui import QGuiApplication

                app = QGuiApplication.instance()
                if app is not None:
                    app.screenRemoved.disconnect(self._screen_removed_watch)
            except (RuntimeError, TypeError):
                pass
            self._screen_removed_watch = None

    def _watch_screen_removal(self) -> None:
        """放映屏被拔 → 自动结束并提示（F7）。"""
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is None:
            return

        def on_removed(screen) -> None:
            proj = self._projection
            if proj is not None and proj.current_screen() is screen:
                logger.warning("放映屏已断开：%s，自动结束放映", screen.name())
                proj.end_show()
                import os

                if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
                    return  # 离屏环境不弹模态框
                QMessageBox.information(
                    None,
                    "放映结束",
                    "放映屏已断开，放映已自动结束。",
                )

        self._screen_removed_watch = on_removed
        app.screenRemoved.connect(on_removed)

    # ---------- 外部控制 ----------

    def end(self) -> None:
        if self._projection is not None:
            self._projection.end_show()
        elif self._overlay is not None:
            self._overlay._timer.stop()
            self._overlay.close()
            self._on_cancelled()

    def requested_ppt(self) -> Path | None:
        return getattr(self, "_ppt", None)
