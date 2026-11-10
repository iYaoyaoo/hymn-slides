"""LibreOffice 引擎（v4 兜底）：复用现有 PDF→pypdfium2 管线。

与 RenderCache 协作：引擎负责逻辑，缓存目录由 RenderCache 提供
（LO 的 PDF 转换产物较大，必须走缓存；PowerPoint/WPS 导出为单页 PNG 无需中间产物）。
"""
from __future__ import annotations

from pathlib import Path

from src.render import converter, pdfrender
from src.render.engine import BaseEngine, ShowSession
from src.utils.logger import get_logger

logger = get_logger("lo_engine")


class _LoShowSession(ShowSession):
    """LO 无原生放映控制：放映窗由 ProjectionWindow 实现（ShowController 分支处理）。

    此会话仅用于接口完整性，不会被创建——EngineChain 中 LO 引擎的
    start_show 返回占位会话以便统一调度（见 ShowController：LO 走投影窗路径）。
    """

    def __init__(self):
        self._page = 0

    def current_page(self) -> int:
        return self._page

    def next_page(self) -> None:
        self._page += 1

    def prev_page(self) -> None:
        self._page = max(0, self._page - 1)

    def end(self) -> None:
        self._page = 0


class LibreOfficeEngine(BaseEngine):
    """LO 引擎：render 走 PDF 管线（由 RenderCache 提供 pdf 缓存），show 走投影窗。"""

    name = "libreoffice"
    supports_render = True
    supports_show = True

    def __init__(self, pdf_provider=None):
        # pdf_provider: Callable[[Path], Path]，由 RenderCache 注入（避免循环依赖）
        self._pdf_provider = pdf_provider

    def set_pdf_provider(self, provider) -> None:
        self._pdf_provider = provider

    def _pdf_for(self, ppt: Path) -> Path:
        if self._pdf_provider is None:
            from src.render.thumbnail import RenderCache

            self._pdf_provider = RenderCache().pdf_for
        return self._pdf_provider(ppt)

    # ---------- render ----------

    def page_count(self, ppt: Path) -> int:
        return pdfrender.page_count(self._pdf_for(ppt))

    def export_page(self, ppt: Path, page_index: int, width_px: int, out_png: Path) -> Path:
        return pdfrender.save_page_png(self._pdf_for(ppt), page_index, width_px, out_png)

    def extract_texts(self, ppt: Path) -> list[tuple[int, str]]:
        return pdfrender.extract_texts(self._pdf_for(ppt))

    # ---------- show ----------

    def start_show(self, ppt: Path, screen_rect: tuple[int, int, int, int]) -> ShowSession:
        # LO 放映由 ShowController 通过 ProjectionWindow 实现；此方法仅满足接口
        return _LoShowSession()
