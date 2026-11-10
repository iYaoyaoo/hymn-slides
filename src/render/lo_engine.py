"""LibreOffice 引擎（v4 兜底）：复用现有 PDF→pypdfium2 管线。

与 RenderCache 协作：引擎负责逻辑，缓存目录由 RenderCache 提供
（LO 的 PDF 转换产物较大，必须走缓存；PowerPoint/WPS 导出为单页 PNG 无需中间产物）。

show 能力：LO 无原生放映控制，放映由 ShowController 通过 ProjectionWindow
实现（引擎声明 supports_show=True 以便链上兜底选中；start_show 不会被调用，
继承 BaseEngine 默认抛 EngineUnsupported）。
"""
from __future__ import annotations

from pathlib import Path

from src.render import converter, pdfrender
from src.render.engine import BaseEngine
from src.utils.logger import get_logger

logger = get_logger("lo_engine")


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
