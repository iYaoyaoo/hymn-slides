"""Windows COM 引擎（PowerPoint / WPS，v4 规范 F5）。

仅 Windows 可用。WPS 的演示组件 COM 接口与 PowerPoint 对象模型同构，共用一套实现。
pywin32 仅在 Windows 安装（requirements 环境标记）。COM 调用线程安全注意：
后台线程调用前需 CoInitialize（本模块在每次调用内处理）。
"""
from __future__ import annotations

import threading
from pathlib import Path

from src.render.engine import BaseEngine, ShowSession
from src.utils.logger import get_logger

logger = get_logger("com_engine")

PROG_IDS = {
    "powerpoint": ["PowerPoint.Application"],
    "wps": ["Kwpp.Application", "wpp.Application", "KWPP.Application"],
}


def _com_ready() -> bool:
    try:
        import win32com.client  # noqa: F401
        import pythoncom  # noqa: F401
    except ImportError:
        logger.error("pywin32 未安装（应仅在 Windows 安装）")
        return False
    return True


class _ComInit:
    """线程内一次性 CoInitialize（COM 对象按线程初始化）。"""

    _local = threading.local()

    @classmethod
    def ensure(cls) -> None:
        if not getattr(cls._local, "inited", False):
            import pythoncom

            pythoncom.CoInitialize()
            cls._local.inited = True


class ComShowSession(ShowSession):
    """COM 放映会话：页码轮询/翻页/结束。"""

    def __init__(self, app, presentation, name: str):
        self._app = app
        self._pres = presentation
        self._name = name

    def _show_window(self):
        try:
            return self._pres.SlideShowWindow
        except Exception:  # noqa: BLE001（COM 异常统一按"无放映窗"处理）
            return None

    def current_page(self) -> int:
        _ComInit.ensure()
        w = self._show_window()
        if w is None:
            return 0
        try:
            return int(w.View.Slide.SlideIndex)
        except Exception:  # noqa: BLE001
            return 0

    def next_page(self) -> None:
        _ComInit.ensure()
        w = self._show_window()
        if w is not None:
            w.View.Next()

    def prev_page(self) -> None:
        _ComInit.ensure()
        w = self._show_window()
        if w is not None:
            w.View.Previous()

    def end(self) -> None:
        _ComInit.ensure()
        w = self._show_window()
        if w is not None:
            try:
                w.View.Exit()
            except Exception as e:  # noqa: BLE001
                logger.warning("结束放映（%s）异常：%s", self._name, e)
        try:
            self._pres.Close()
        except Exception as e:  # noqa: BLE001
            logger.warning("关闭演示文稿（%s）异常：%s", self._name, e)


class ComEngine(BaseEngine):
    """PowerPoint/WPS 共用 COM 实现（接口同构）。"""

    supports_render = True
    supports_show = True

    def __init__(self, name: str):
        assert name in PROG_IDS, f"未知 COM 引擎：{name}"
        self.name = name
        self._prog_ids = PROG_IDS[name]

    # ---------- 基础 ----------

    def _dispatch(self):
        _ComInit.ensure()
        import win32com.client

        last_err = None
        for pid in self._prog_ids:
            try:
                return win32com.client.Dispatch(pid)
            except Exception as e:  # noqa: BLE001
                last_err = e
        raise RuntimeError(f"COM Dispatch 失败（{self._prog_ids}）：{last_err}")

    def _open(self, app, ppt: Path, with_window: bool):
        # ReadOnly=msoTrue(1)，WithWindow=msoFalse(0)/msoTrue(-1)
        return app.Presentations.Open(
            str(ppt), True, False, with_window
        )

    # ---------- render 能力 ----------

    def page_count(self, ppt: Path) -> int:
        app = self._dispatch()
        try:
            pres = self._open(app, ppt, with_window=False)
            try:
                return int(pres.Slides.Count)
            finally:
                pres.Close()
        finally:
            self._quit_if_idle(app)

    def export_page(self, ppt: Path, page_index: int, width_px: int, out_png: Path) -> Path:
        app = self._dispatch()
        try:
            pres = self._open(app, ppt, with_window=False)
            try:
                setup = pres.PageSetup
                ratio = float(setup.SlideHeight) / float(setup.SlideWidth)
                height = int(round(width_px * ratio))
                out_png.parent.mkdir(parents=True, exist_ok=True)
                pres.Slides(page_index + 1).Export(str(out_png), "PNG", width_px, height)
                return out_png
            finally:
                pres.Close()
        finally:
            self._quit_if_idle(app)

    def extract_texts(self, ppt: Path) -> list[tuple[int, str]]:
        app = self._dispatch()
        try:
            pres = self._open(app, ppt, with_window=False)
            try:
                texts: list[tuple[int, str]] = []
                for i in range(1, pres.Slides.Count + 1):
                    parts: list[str] = []
                    for shape in pres.Slides(i).Shapes:
                        try:
                            if shape.HasTextFrame and shape.TextFrame.HasText:
                                parts.append(shape.TextFrame.TextRange.Text)
                        except Exception:  # noqa: BLE001（非文本形状跳过）
                            continue
                    texts.append((i, "\n".join(parts).strip()))
                return texts
            finally:
                pres.Close()
        finally:
            self._quit_if_idle(app)

    # ---------- show 能力 ----------

    def start_show(self, ppt: Path, screen_rect: tuple[int, int, int, int]) -> ShowSession:
        x, y, w, h = screen_rect[:4]
        app = self._dispatch()
        pres = self._open(app, ppt, with_window=False)
        settings = pres.SlideShowSettings
        window = settings.Run()
        # 将放映窗定位到目标屏（v4 F4：放映置于非主显示器）
        window.Left = x
        window.Top = y
        window.Width = w
        window.Height = h
        logger.info("COM 放映已启动（%s，屏幕 rect=%s）", self.name, screen_rect[:4])
        return ComShowSession(app, pres, self.name)

    # ---------- 辅助 ----------

    @staticmethod
    def _quit_if_idle(app) -> None:
        """PowerPoint/WPS 常驻进程属正常行为；不做强制退出，避免干扰用户打开的其他文档。"""
        return


def make_com_engine(name: str) -> ComEngine:
    if not _com_ready():
        raise RuntimeError("pywin32 不可用，无法创建 COM 引擎")
    return ComEngine(name)
