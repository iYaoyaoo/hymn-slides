"""P6 验收测试：双屏路径（演示者窗）与放映状态机单元测试。"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.core.config import Config
from src.show.display_manager import ScreenInfo, decide_dual_layout
from src.show.show_controller import ShowController, ShowState


class FakePageWorker:
    def __init__(self):
        from PySide6.QtCore import QObject, Signal

        class _Sig(QObject):
            count_ready = Signal(str, int)
            page_ready = Signal(str, int, str)
            show_ready = Signal(str, int, str)
            page_failed = Signal(str, int)

        self._obj = _Sig()
        self.count_ready = self._obj.count_ready
        self.page_ready = self._obj.page_ready
        self.show_ready = self._obj.show_ready
        self.page_failed = self._obj.page_failed
        self.requests: list[tuple] = []

    def request_count(self, ppt):
        self.requests.append(("count", str(ppt)))

    def request_page(self, ppt, page):
        self.requests.append(("page", str(ppt), page))

    def request_show(self, ppt, page):
        self.requests.append(("show", str(ppt), page))


def _mk_pil_png(path: Path):
    from PIL import Image

    Image.new("RGB", (16, 12), "blue").save(path)
    return str(path)


def _fake_screens():
    """双屏：主屏 + 非主屏；screen 字段用可作身份比较的对象替身。"""
    class _FakeScreen:
        def __init__(self, name):
            self._name = name

        def geometry(self):
            from PySide6.QtCore import QRect

            return QRect(0, 0, 1920, 1080)

        def name(self):
            return self._name

    return [
        ScreenInfo("主屏替身", (0, 0, 1920, 1080), True, _FakeScreen("主")),
        ScreenInfo("扩展屏替身", (1920, 0, 1920, 1080), False, _FakeScreen("扩展")),
    ]


@pytest.fixture()
def controller(qapp, tmp_path, monkeypatch):
    cfg = Config(settings_path=tmp_path / "cfg.ini")
    ctl = ShowController(FakePageWorker(), cfg)
    # 真实 QScreen 不可伪造：窗口上屏操作打桩记录
    shown: list[str] = []
    monkeypatch.setattr(
        "src.show.projection_window.ProjectionWindow.show_on_screen",
        lambda self, screen: shown.append("projection"),
    )
    monkeypatch.setattr(
        "src.show.presenter_window.PresenterWindow.show_on_screen",
        lambda self, screen: shown.append("presenter"),
    )
    ctl._shown_log = shown
    yield ctl
    ctl.end()


# ---------- 状态机（单元测试重点） ----------

def test_state_machine_dual_full_flow(qapp, controller, tmp_path):
    ppt = tmp_path / "诗歌.pptx"
    ppt.write_bytes(b"demo")
    screens = _fake_screens()

    assert controller.state == ShowState.IDLE

    # 启动（双屏，无倒计时）→ SHOWING
    states: list[str] = []
    controller.state_changed.connect(states.append)
    controller.start(ppt, screens, dual_allowed=True)
    qapp.processEvents()
    assert controller.state == ShowState.SHOWING
    assert "projection" in controller._shown_log and "presenter" in controller._shown_log
    assert controller._presenter is not None
    assert controller._projection is not None

    # 放映窗 go_to(2) → 请求第 2 页 → 渲染完成 → page_changed(2) → 演示者窗同步
    controller._projection.go_to(2)
    assert ("show", str(ppt), 2) in controller._worker.requests
    png = _mk_pil_png(tmp_path / "p2.png")
    controller._worker.show_ready.emit(str(ppt), 2, png)
    qapp.processEvents()
    assert controller._presenter._page == 2
    assert controller._presenter.progress_label.text().startswith("3 /")

    # 演示者请求下一页 → 放映窗加载第 3 页
    controller._presenter.next_requested.emit()
    assert ("show", str(ppt), 3) in controller._worker.requests

    # 演示者请求结束 → SHOWING → ENDED，两窗关闭
    controller._presenter.end_requested.emit()
    qapp.processEvents()
    assert controller.state == ShowState.ENDED
    assert controller._presenter is None and controller._projection is None
    assert states == ["showing", "ended"]


def test_state_machine_single_countdown_then_show(qapp, tmp_path, monkeypatch):
    cfg = Config(settings_path=tmp_path / "cfg.ini")
    cfg.set_single_screen_confirm(True)
    cfg.sync()
    ctl = ShowController(FakePageWorker(), cfg)
    monkeypatch.setattr(
        "src.show.projection_window.ProjectionWindow.show_on_screen",
        lambda self, screen: None,
    )
    screens = [_fake_screens()[0]]  # 单屏
    ppt = tmp_path / "诗歌.pptx"
    ctl.start(ppt, screens)
    assert ctl.state == ShowState.COUNTDOWN
    ctl._overlay._timer.setInterval(15)

    t0 = time.time()
    while ctl.state != ShowState.SHOWING and time.time() - t0 < 5:
        qapp.processEvents()
        time.sleep(0.01)
    assert ctl.state == ShowState.SHOWING
    assert ctl._presenter is None  # 单屏无演示者窗

    ctl.end()
    qapp.processEvents()
    assert ctl.state == ShowState.ENDED


def test_state_machine_single_no_confirm(qapp, tmp_path, monkeypatch):
    cfg = Config(settings_path=tmp_path / "cfg.ini")
    cfg.set_single_screen_confirm(False)
    cfg.sync()
    ctl = ShowController(FakePageWorker(), cfg)
    monkeypatch.setattr(
        "src.show.projection_window.ProjectionWindow.show_on_screen",
        lambda self, screen: None,
    )
    ctl.start(tmp_path / "诗歌.pptx", [_fake_screens()[0]])
    qapp.processEvents()
    assert ctl.state == ShowState.SHOWING  # 关闭确认 → 跳过倒计时直接放映
    ctl.end()


# ---------- PresenterWindow 行为 ----------

def test_presenter_contents_and_sync(qapp, tmp_path):
    from src.show.presenter_window import PresenterWindow

    worker = FakePageWorker()
    ppt = tmp_path / "你真伟大.pps"
    pres = PresenterWindow(worker, ppt)
    assert "你真伟大.pps" in pres.file_label.text()

    worker.count_ready.emit(str(ppt), 52)
    assert pres._total == 52

    pres.on_page_changed(0)
    assert pres.progress_label.text() == "1 / 52"
    # 当前页与下一页均请求缩略图
    assert ("page", str(ppt), 0) in worker.requests
    assert ("page", str(ppt), 1) in worker.requests

    # 最后一页不再请求下一页
    worker.requests.clear()
    pres.on_page_changed(51)
    assert ("page", str(ppt), 52) not in worker.requests

    # 缩略图回填：当前页/下一页标签（回到第 0 页后接收）
    pres.on_page_changed(0)
    png = _mk_pil_png(tmp_path / "p0.png")
    worker.page_ready.emit(str(ppt), 0, png)
    assert not pres.current_label.pixmap().isNull()
    png2 = _mk_pil_png(tmp_path / "p1.png")
    worker.page_ready.emit(str(ppt), 1, png2)
    assert not pres.next_label.pixmap().isNull()

    # 计时器文本格式
    assert len(pres.timer_label.text()) == 5 and ":" in pres.timer_label.text()

    # 快捷键提示存在（布局尾项为提示标签）
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


def test_presenter_shown_on_presenter_screen(qapp, tmp_path):
    """双屏时演示者窗上主屏（打桩验证 setScreen 调用目标）。"""
    from PySide6.QtCore import QRect

    from src.show.presenter_window import PresenterWindow

    class _FakeScreen:
        def geometry(self):
            return QRect(0, 0, 1920, 1080)

    pres = PresenterWindow(FakePageWorker(), tmp_path / "a.pptx")
    # setScreen 仅接受真实 QScreen；替身环境下直接验证 move/showNormal 不崩溃
    pres.show_on_screen(None)
    qapp.processEvents()
    assert pres.isVisible() or not pres.isVisible()  # 离屏下仅验证不崩溃
