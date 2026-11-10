"""R3 验收测试（v4 演示者模式）：双屏路径、原生放映会话、状态机。"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.core.config import Config
from src.render.engine import BaseEngine, ShowSession
from src.render.engine_detect import (
    ENGINE_LIBREOFFICE,
    ENGINE_POWERPOINT,
    EngineCandidates,
    EngineInfo,
)
from src.show.display_manager import ScreenInfo


class FakePageWorker:
    def __init__(self):
        from PySide6.QtCore import QObject, Signal

        class _Sig(QObject):
            count_ready = Signal(str, int)
            show_ready = Signal(str, int, str)
            page_failed = Signal(str, int)

        self._obj = _Sig()
        self.count_ready = self._obj.count_ready
        self.show_ready = self._obj.show_ready
        self.page_failed = self._obj.page_failed
        self.requests: list[tuple] = []

    def request_count(self, ppt):
        self.requests.append(("count", str(ppt)))

    def request_show(self, ppt, page):
        self.requests.append(("show", str(ppt), page))


class FakeNativeSession(ShowSession):
    """替身原生放映会话：页码可推进、可被结束。"""

    def __init__(self):
        self._page = 1
        self._ended = False

    def current_page(self) -> int:
        return 0 if self._ended else self._page

    def next_page(self) -> None:
        self._page += 1

    def prev_page(self) -> None:
        self._page = max(1, self._page - 1)

    def end(self) -> None:
        self._ended = True


class FakeNativeEngine(BaseEngine):
    name = ENGINE_POWERPOINT
    supports_show = True

    def __init__(self):
        self.sessions: list[FakeNativeSession] = []
        self.start_calls: list[tuple] = []

    def start_show(self, ppt: Path, screen_rect) -> ShowSession:
        self.start_calls.append((ppt, screen_rect))
        session = FakeNativeSession()
        self.sessions.append(session)
        return session


class _FakeScreen:
    def __init__(self, name):
        self._name = name

    def geometry(self):
        from PySide6.QtCore import QRect

        return QRect(1920, 0, 1920, 1080)

    def name(self):
        return self._name


def _fake_dual_screens():
    return [
        ScreenInfo("主屏替身", (0, 0, 1920, 1080), True, _FakeScreen("主")),
        ScreenInfo("扩展屏替身", (1920, 0, 1920, 1080), False, _FakeScreen("扩展")),
    ]


def _native_chain(engine):
    from src.render.engine import EngineChain

    cands = EngineCandidates(
        infos=[
            EngineInfo(ENGINE_POWERPOINT, True, False, True),
            EngineInfo(ENGINE_LIBREOFFICE, False, False, False),
        ]
    )
    return EngineChain([engine], cands)


# ---------- 原生引擎双屏全流程 ----------

def test_native_dual_show_flow(qapp, tmp_path, monkeypatch):
    from src.show.show_controller import ShowController, ShowState

    ppt = tmp_path / "诗歌.pptx"
    ppt.write_bytes(b"demo")
    engine = FakeNativeEngine()
    cfg = Config(settings_path=tmp_path / "cfg.ini")
    controller = ShowController(FakePageWorker(), cfg, chain=_native_chain(engine))

    shown: list[str] = []
    monkeypatch.setattr(
        "src.show.projection_window.ProjectionWindow.show_on_screen",
        lambda self, screen: shown.append("projection"),
    )
    monkeypatch.setattr(
        "src.show.presenter_window.PresenterWindow.show_on_screen",
        lambda self, screen: shown.append("presenter"),
    )
    # 拔屏检测用替身屏幕集（固定实例，identity 判定需要同一对象）
    fake_screens = _fake_dual_screens()
    monkeypatch.setattr(
        "src.show.show_controller.enumerate_screens", lambda: fake_screens
    )
    try:
        controller.start(ppt, fake_screens)
        qapp.processEvents()
        assert controller.state == ShowState.SHOWING
        assert controller._native is True
        assert "presenter" in shown and "projection" not in shown  # 原生引擎：无投影窗
        assert engine.start_calls and engine.start_calls[0][0] == ppt
        assert controller._presenter is not None

        # 演示者请求翻页 → 会话页码推进 → 轮询同步到演示者窗
        session = engine.sessions[0]
        controller._presenter.next_requested.emit()
        controller._poll_native()  # 手动触发一轮轮询（测试不等 250ms）
        qapp.processEvents()
        assert session._page == 2
        assert controller._presenter._page == 1  # 0 起
        assert controller._presenter.progress_label.text().startswith("2 /")

        # 引擎侧结束（用户在放映窗按 Esc）→ 轮询发现 → ENDED
        session.end()
        controller._poll_native()
        qapp.processEvents()
        assert controller.state == ShowState.ENDED
        assert controller._presenter is None and controller._session is None
    finally:
        controller.end()


def test_native_presenter_end_button(qapp, tmp_path, monkeypatch):
    from src.show.show_controller import ShowController, ShowState

    engine = FakeNativeEngine()
    cfg = Config(settings_path=tmp_path / "cfg.ini")
    controller = ShowController(FakePageWorker(), cfg, chain=_native_chain(engine))
    monkeypatch.setattr(
        "src.show.presenter_window.PresenterWindow.show_on_screen",
        lambda self, screen: None,
    )
    fake_screens = _fake_dual_screens()
    monkeypatch.setattr(
        "src.show.show_controller.enumerate_screens", lambda: fake_screens
    )
    try:
        controller.start(tmp_path / "诗歌.pptx", fake_screens)
        qapp.processEvents()
        assert controller.state == ShowState.SHOWING
        controller._presenter.end_requested.emit()
        qapp.processEvents()
        assert controller.state == ShowState.ENDED
        assert engine.sessions[0]._ended is True
    finally:
        controller.end()


def test_native_screen_unplugged_ends_show(qapp, tmp_path, monkeypatch):
    from src.show.show_controller import ShowController

    engine = FakeNativeEngine()
    cfg = Config(settings_path=tmp_path / "cfg.ini")
    controller = ShowController(FakePageWorker(), cfg, chain=_native_chain(engine))
    monkeypatch.setattr(
        "src.show.presenter_window.PresenterWindow.show_on_screen",
        lambda self, screen: None,
    )
    try:
        controller.start(tmp_path / "诗歌.pptx", _fake_dual_screens())
        qapp.processEvents()
        assert controller.state.value == "showing"
        # 放映屏拔出：enumerate_screens 不再包含目标屏（替身枚举返回真实离屏屏）
        monkeypatch.setattr(
            "src.show.show_controller.enumerate_screens", lambda: []
        )
        controller._poll_native()
        qapp.processEvents()
        assert controller.state.value == "ended"
    finally:
        controller.end()


# ---------- 演示者窗行为（v4.2 纯文字视图） ----------

def test_presenter_contents_and_sync(qapp, tmp_path):
    from src.show.presenter_window import PresenterWindow

    worker = FakePageWorker()
    ppt = tmp_path / "你真伟大.pps"
    pres = PresenterWindow(worker, ppt)
    assert "你真伟大.pps" in pres.file_label.text()
    # v4.2 取消预览：无缩略图标签，仅请求页数（不出图）
    assert not hasattr(pres, "current_label") and not hasattr(pres, "next_label")
    assert ("count", str(ppt)) in worker.requests

    worker.count_ready.emit(str(ppt), 52)
    assert pres._total == 52

    pres.on_page_changed(0)
    assert pres.progress_label.text() == "1 / 52"

    pres.on_page_changed(51)
    assert pres.progress_label.text() == "52 / 52"

    assert len(pres.timer_label.text()) == 5 and ":" in pres.timer_label.text()
    tail_widget = pres.layout().itemAt(pres.layout().count() - 1).widget()
    assert "Esc" in tail_widget.text()


def test_presenter_key_events(qapp, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    from src.show.presenter_window import PresenterWindow

    pres = PresenterWindow(FakePageWorker(), tmp_path / "a.pptx")
    got: list[str] = []
    pres.next_requested.connect(lambda: got.append("next"))
    pres.prev_requested.connect(lambda: got.append("prev"))
    pres.end_requested.connect(lambda: got.append("end"))

    def _key(k):
        return QKeyEvent(QKeyEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier)

    pres.keyPressEvent(_key(Qt.Key.Key_Right))
    pres.keyPressEvent(_key(Qt.Key.Key_Left))
    pres.keyPressEvent(_key(Qt.Key.Key_Escape))
    assert got == ["next", "prev", "end"]
