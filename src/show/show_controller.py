"""放映控制器（v4）：状态机 + 双路径（原生引擎放映 / LibreOffice 投影窗）。

状态机：idle → countdown → showing → ended
- 原生路径（PowerPoint/WPS，COM 或 AppleScript）：引擎自身的放映窗显示放映页；
  演示者窗轮询页码同步；Esc 由引擎放映窗处理（轮询检测结束）。
- LO 路径：ProjectionWindow 无边框全屏 + 键盘翻页（既有实现）。
- 双屏：放映=非主显示器（几何决策，无身份假设）；演示者=主显示器。
- 单屏：可配 3 秒倒计时确认后本屏放映。
- 放映屏被拔：screenRemoved 信号（LO）+ 轮询检测（原生）→ 自动结束并提示。
"""
from __future__ import annotations

import enum
import time
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from src.render.engine import EngineChain, EngineUnsupported
from src.show.display_manager import (
    ScreenInfo,
    decide_dual_layout,
    decide_show_screen,
    enumerate_screens,
)
from src.show.projection_window import ProjectionWindow
from src.utils.logger import get_logger

logger = get_logger("show_controller")

COUNTDOWN_SECONDS = 3
POLL_INTERVAL_MS = 250


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
            from PySide6.QtGui import QScreen

            if isinstance(screen, QScreen):
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
    """放映流程编排（v4：引擎链感知）。"""

    state_changed = Signal(str)      # ShowState.value
    request_show_for = Signal(str)   # 开始放映的文件路径（UI 状态记录用）
    show_failed = Signal(str)        # 启动失败信息（UI 状态栏提示）

    def __init__(self, page_worker, config, parent=None, chain=None):
        super().__init__(parent)
        self._worker = page_worker
        self._config = config
        self._chain_override = chain  # 测试注入替身引擎链（避免真实启动 Office）
        self._state = ShowState.IDLE
        self._projection: ProjectionWindow | None = None
        self._presenter = None
        self._session = None
        self._overlay: CountdownOverlay | None = None
        self._poll_timer: QTimer | None = None
        self._screen_removed_watch = None
        self._native = False
        self._show_screen_info: ScreenInfo | None = None

    @property
    def state(self) -> ShowState:
        return self._state

    def _set_state(self, s: ShowState) -> None:
        self._state = s
        logger.info("放映状态：%s", s.value)
        self.state_changed.emit(s.value)

    # ---------- 启动 ----------

    def start(self, ppt: Path, screens: list[ScreenInfo]) -> None:
        if self._state in (ShowState.COUNTDOWN, ShowState.SHOWING):
            logger.warning("放映已在进行中，忽略重复启动")
            return

        chain = self._chain_override or EngineChain.autodetect(
            ppt_path=self._config.ppt_path,
            wps_path=self._config.wps_path,
            lo_path=self._config.soffice_path,
        )
        show_engine = chain.show_engine()
        if show_engine is None:
            msg = "无可用放映引擎（PowerPoint/WPS/LibreOffice 均未检测到），请安装其一或在设置中指定路径"
            logger.error(msg)
            self.show_failed.emit(msg)
            return
        self._native = show_engine.name != "libreoffice"

        # 目标屏决策（仅几何，无身份假设）
        if len(screens) >= 2:
            show_screen, presenter_screen = decide_dual_layout(screens)
        else:
            show_screen, presenter_screen = decide_show_screen(screens), None
        if show_screen is None or show_screen.screen is None:
            logger.error("无可用显示器，放映取消")
            self.show_failed.emit("无可用显示器，放映取消")
            return

        self._ppt = Path(ppt)
        self._show_screen_info = show_screen
        self._presenter_screen = presenter_screen
        self._chain = chain
        self.request_show_for.emit(str(self._ppt))
        logger.info(
            "放映启动：文件=%s 引擎=%s 路径=%s 模式=%s 目标屏=%s",
            self._ppt.name, show_engine.name,
            "原生" if self._native else "投影窗",
            "双屏" if presenter_screen is not None else "单屏",
            show_screen.geometry,
        )

        single = len(screens) < 2
        if single and self._config.single_screen_confirm:
            self._set_state(ShowState.COUNTDOWN)
            self._overlay = CountdownOverlay(show_screen.screen)
            self._overlay.countdown_finished.connect(self._begin_show)
            self._overlay.cancelled.connect(self._on_cancelled)
            self._overlay.begin()
        else:
            self._begin_show()

    # ---------- 内部流转 ----------

    def _begin_show(self) -> None:
        self._overlay = None
        if self._native:
            ok = self._begin_native_show()
        else:
            ok = self._begin_projection_show()
        if ok:
            self._set_state(ShowState.SHOWING)

    # ---------- 原生引擎路径（PowerPoint/WPS） ----------

    def _begin_native_show(self) -> bool:
        try:
            engine = self._chain.show_engine()
            self._session = engine.start_show(self._ppt, self._show_screen_info.geometry)
        except (EngineUnsupported, RuntimeError) as e:
            logger.error("原生放映启动失败，回落 LibreOffice 投影窗：%s", e)
            self._native = False
            return self._begin_projection_show()
        self._setup_presenter()
        self._start_poll()
        return True

    def _start_poll(self) -> None:
        """轮询页码/放映活性/放映屏在位（原生路径）。"""
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_native)
        self._poll_timer.start()

    def _poll_native(self) -> None:
        if self._session is None:
            return
        # 放映屏被拔检测（原生放映窗由引擎管理，screenRemoved 兜底提示）
        screens = enumerate_screens()
        if self._show_screen_info is not None and self._show_screen_info.screen is not None:
            alive = any(s.screen is self._show_screen_info.screen for s in screens)
            if not alive:
                logger.warning("放映屏已断开，自动结束放映")
                self.end()
                self._notify_screen_removed()
                return
        page = self._session.current_page()
        if page == 0:
            # 引擎侧放映已结束（用户在放映窗按 Esc 等）
            self._on_ended()
            return
        if self._presenter is not None:
            self._presenter.on_page_changed(page - 1)

    # ---------- LibreOffice 投影窗路径 ----------

    def _begin_projection_show(self) -> bool:
        self._projection = ProjectionWindow(self._worker, self._ppt)
        self._projection.show_ended.connect(self._on_ended)
        self._setup_presenter()
        self._watch_screen_removal()
        self._projection.show_on_screen(self._show_screen_info.screen)
        return True

    def _setup_presenter(self) -> None:
        """双屏：演示者窗置于主显示器（两条路径共用）。"""
        if getattr(self, "_presenter_screen", None) is None or self._presenter_screen.screen is None:
            return
        from src.show.presenter_window import PresenterWindow

        self._presenter = PresenterWindow(self._worker, self._ppt)
        self._presenter.next_requested.connect(self._presenter_next)
        self._presenter.prev_requested.connect(self._presenter_prev)
        self._presenter.end_requested.connect(self._presenter_end)
        if self._projection is not None:
            self._projection.page_changed.connect(self._presenter.on_page_changed)
        self._presenter.show_on_screen(self._presenter_screen.screen)

    def _presenter_next(self) -> None:
        if self._session is not None:
            self._session.next_page()
        elif self._projection is not None:
            self._projection.next_page()

    def _presenter_prev(self) -> None:
        if self._session is not None:
            self._session.prev_page()
        elif self._projection is not None:
            self._projection.prev_page()

    def _presenter_end(self) -> None:
        if self._session is not None:
            self._session.end()
            self._on_ended()
        elif self._projection is not None:
            self._projection.end_show()

    # ---------- 结束/清理 ----------

    def _on_cancelled(self) -> None:
        self._overlay = None
        self._set_state(ShowState.ENDED)
        self._cleanup()

    def _on_ended(self) -> None:
        self._set_state(ShowState.ENDED)
        self._cleanup()

    def _cleanup(self) -> None:
        if self._presenter is not None:
            self._presenter.close()
            self._presenter = None
        self._projection = None
        self._session = None
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer.deleteLater()
            self._poll_timer = None
        if self._screen_removed_watch is not None:
            try:
                from PySide6.QtGui import QGuiApplication

                app = QGuiApplication.instance()
                if app is not None:
                    app.screenRemoved.disconnect(self._screen_removed_watch)
            except (RuntimeError, TypeError):
                pass
            self._screen_removed_watch = None
        self._native = False
        self._show_screen_info = None

    def _watch_screen_removal(self) -> None:
        """LO 路径：放映屏被拔 → 自动结束并提示。"""
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is None:
            return

        def on_removed(screen) -> None:
            proj = self._projection
            if proj is not None and proj.current_screen() is screen:
                logger.warning("放映屏已断开：%s，自动结束放映", screen.name())
                proj.end_show()
                self._notify_screen_removed()

        self._screen_removed_watch = on_removed
        app.screenRemoved.connect(on_removed)

    def _notify_screen_removed(self) -> None:
        import os

        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        QMessageBox.information(None, "放映结束", "放映屏已断开，放映已自动结束。")

    # ---------- 外部控制 ----------

    def end(self) -> None:
        if self._session is not None:
            self._session.end()
            self._on_ended()
        elif self._projection is not None:
            self._projection.end_show()
        elif self._overlay is not None:
            self._overlay._timer.stop()
            self._overlay.close()
            self._on_cancelled()

    def requested_ppt(self) -> Path | None:
        return getattr(self, "_ppt", None)
