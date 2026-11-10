"""R3 验收测试（v4）：显示器决策、--list-screens、投影窗翻页、倒计时确认、状态机。"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.core.config import Config
from src.render.engine import BaseEngine
from src.render.engine_detect import (
    ENGINE_LIBREOFFICE,
    EngineCandidates,
    EngineInfo,
)
from src.show.display_manager import (
    ScreenInfo,
    decide_dual_layout,
    decide_show_screen,
    enumerate_screens,
)


# ---------- 决策逻辑（纯函数，无屏幕身份假设） ----------

def _si(name, x, y, w, h, primary=False):
    return ScreenInfo(name=name, geometry=(x, y, w, h), is_primary=primary, screen=None)


def test_decide_show_screen_prefers_primary():
    screens = [_si("A", 0, 0, 1920, 1080), _si("B", 1920, 0, 2560, 1440, primary=True)]
    assert decide_show_screen(screens).is_primary is True


def test_decide_show_screen_fallback_single():
    screens = [_si("仅一块", 0, 0, 1024, 768, primary=False)]
    assert decide_show_screen(screens) is screens[0]


def test_decide_show_screen_empty():
    assert decide_show_screen([]) is None


def test_decide_dual_layout_basic():
    screens = [_si("主", 0, 0, 1920, 1080, primary=True), _si("扩展", 1920, 0, 2560, 1440)]
    show, presenter = decide_dual_layout(screens)
    assert show is screens[1] and presenter is screens[0]


def test_decide_dual_layout_picks_largest_non_primary():
    screens = [
        _si("主", 0, 0, 1920, 1080, primary=True),
        _si("小扩展", 1920, 0, 800, 600),
        _si("大扩展", 2720, 0, 3840, 2160),
    ]
    show, presenter = decide_dual_layout(screens)
    assert show.name == "大扩展"


def test_decide_dual_layout_needs_two():
    assert decide_dual_layout([_si("仅主", 0, 0, 1920, 1080, primary=True)]) == (None, None)


# ---------- 枚举与 CLI ----------

def test_enumerate_screens_offscreen(qapp):
    screens = enumerate_screens()
    assert len(screens) >= 1
    assert sum(1 for s in screens if s.is_primary) == 1


def test_cli_list_screens(qapp, capsys):
    import main as main_mod

    rc = main_mod.main(["--list-screens"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "检测到" in out and "主显示器" in out


# ---------- 投影窗（LO 放映路径） ----------

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


def _key(key):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    return QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


def test_projection_navigation_and_esc(qapp, tmp_path):
    from PySide6.QtCore import Qt

    from src.show.projection_window import ProjectionWindow

    worker = FakePageWorker()
    proj = ProjectionWindow(worker, tmp_path / "诗歌.pptx")
    worker.count_ready.emit(str(tmp_path / "诗歌.pptx"), 5)

    pages: list[int] = []
    proj.page_changed.connect(pages.append)
    proj.keyPressEvent(_key(Qt.Key.Key_Right))
    assert ("show", str(tmp_path / "诗歌.pptx"), 1) in worker.requests
    proj.keyPressEvent(_key(Qt.Key.Key_Space))
    proj.keyPressEvent(_key(Qt.Key.Key_PageUp))
    proj.keyPressEvent(_key(Qt.Key.Key_Left))

    worker.requests.clear()
    proj._page = 0
    proj._requested_page = -1
    proj.keyPressEvent(_key(Qt.Key.Key_Left))
    assert not any(r[0] == "show" for r in worker.requests)

    ended: list[bool] = []
    proj.show_ended.connect(lambda: ended.append(True))
    proj.keyPressEvent(_key(Qt.Key.Key_Escape))
    qapp.processEvents()
    assert ended == [True]
    assert not proj.isVisible()


# ---------- 倒计时确认 ----------

def test_countdown_finishes(qapp):
    from src.show.show_controller import CountdownOverlay

    screens = enumerate_screens()
    overlay = CountdownOverlay(screens[0].screen)
    overlay._timer.setInterval(20)
    done: list[bool] = []
    overlay.countdown_finished.connect(lambda: done.append(True))
    overlay.begin()
    t0 = time.time()
    while not done and time.time() - t0 < 3:
        qapp.processEvents()
        time.sleep(0.02)
    assert done == [True]


def test_countdown_cancel_by_click(qapp):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from src.show.show_controller import CountdownOverlay

    screens = enumerate_screens()
    overlay = CountdownOverlay(screens[0].screen)
    cancelled: list[bool] = []
    overlay.cancelled.connect(lambda: cancelled.append(True))
    overlay.begin()
    overlay._timer.stop()
    ev = QMouseEvent(
        QEvent.Type.MouseButtonPress, QPointF(1, 1), QPointF(1, 1),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    overlay.mousePressEvent(ev)
    assert cancelled == [True]


# ---------- ShowController 状态机（替身引擎链） ----------

class _FakeLoEngine(BaseEngine):
    """替身：声称是 LibreOffice → 走投影窗路径。"""

    name = ENGINE_LIBREOFFICE
    supports_show = True
    supports_render = True


def _fake_chain():
    from src.render.engine import EngineChain

    cands = EngineCandidates(infos=[EngineInfo(ENGINE_LIBREOFFICE, True, True, True)])
    return EngineChain([_FakeLoEngine()], cands)


@pytest.fixture()
def controller(qapp, tmp_path):
    from src.show.show_controller import ShowController

    cfg = Config(settings_path=tmp_path / "cfg.ini")
    ctl = ShowController(FakePageWorker(), cfg, chain=_fake_chain())
    yield ctl
    ctl.end()


def test_controller_no_engine_fails_gracefully(qapp, tmp_path):
    from src.render.engine import EngineChain
    from src.show.show_controller import ShowController

    cfg = Config(settings_path=tmp_path / "cfg.ini")
    ctl = ShowController(FakePageWorker(), cfg, chain=EngineChain([], EngineCandidates()))
    failures: list[str] = []
    ctl.show_failed.connect(failures.append)
    ctl.start(tmp_path / "诗歌.pptx", [])
    assert ctl.state.value == "idle"
    assert failures and "无可用放映引擎" in failures[0]


def test_controller_single_screen_flow(qapp, controller, tmp_path):
    from src.show.show_controller import ShowState

    screens = enumerate_screens()
    assert len(screens) >= 1
    controller.start(tmp_path / "诗歌.pptx", screens)
    if len(screens) < 2 and controller._config.single_screen_confirm:
        assert controller.state == ShowState.COUNTDOWN
        controller._overlay._timer.setInterval(20)
        t0 = time.time()
        while controller.state != ShowState.SHOWING and time.time() - t0 < 5:
            qapp.processEvents()
            time.sleep(0.02)
    assert controller.state == ShowState.SHOWING
    assert controller._projection is not None
    assert controller._presenter is None  # 单屏无演示者窗

    controller.end()
    qapp.processEvents()
    assert controller.state == ShowState.ENDED


def test_controller_repeat_start_ignored(qapp, controller, tmp_path):
    from src.show.show_controller import ShowState

    screens = enumerate_screens()
    if len(screens) >= 2:
        pytest.skip("本机双屏时无倒计时分支，本用例验证倒计时中的重复启动忽略")
    controller.start(tmp_path / "A.pptx", screens)
    controller.start(tmp_path / "B.pptx", screens)  # 进行中 → 忽略
    assert controller.requested_ppt().name == "A.pptx"


# ---------- MainWindow 放映入口 ----------

@pytest.fixture()
def window(qapp, tmp_path):
    from src.ui.main_window import MainWindow

    tree = tmp_path / "主目录"
    tree.mkdir()
    (tree / "诗歌.pptx").write_bytes(b"demo")
    cfg = Config(settings_path=tmp_path / "config.ini")
    cfg.set_main_dir(tree)
    cfg.sync()
    win = MainWindow(config=cfg, db_path=tmp_path / "idx.db", scan_fulltext=False)
    yield win
    win.close()


def test_f5_without_selection_hints(qapp, window):
    window.start_show_from_selection()
    assert "请先在树中选择" in window.statusBar().currentMessage()


def test_f5_with_selection_starts_show(qapp, window, tmp_path, monkeypatch):
    import time

    t0 = time.time()
    while window.tree.topLevelItemCount() == 0 and time.time() - t0 < 8:
        qapp.processEvents()
        time.sleep(0.05)
    target = str(window.config.main_dir / "诗歌.pptx")
    window.tree.select_file(target)
    calls: list[tuple] = []
    monkeypatch.setattr(
        window.show_controller, "start",
        lambda ppt, screens: calls.append((ppt, len(screens))),
    )
    window.start_show_from_selection()
    assert len(calls) == 1 and calls[0][0].name == "诗歌.pptx"
    assert calls[0][1] >= 1

    # 双击文件 = 放映（同一入口）
    calls.clear()
    window.tree.file_double_clicked.emit(target)
    assert len(calls) == 1
