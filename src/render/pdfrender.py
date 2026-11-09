"""PDF 处理：pypdfium2 渲染页面图片 + 逐页文字提取（渲染管线第二级）。"""
from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium

from src.utils.logger import get_logger

logger = get_logger("pdfrender")

# 双级缓存宽度（规范 P2：256px 浏览 / 1920px 放映按需）
THUMB_WIDTH_PX = 256
SHOW_WIDTH_PX = 1920


def page_count(pdf_path: Path) -> int:
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(doc)
    finally:
        doc.close()


def render_page(pdf_path: Path, page_index: int, width_px: int) -> "Image":
    """渲染指定页（0 起）为指定宽度的 RGB 图像（高度按比例）。"""
    from PIL import Image

    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        page = doc[page_index]
        scale = width_px / page.get_width()
        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil().convert("RGB")
        pil.load()
        return pil
    finally:
        doc.close()


def save_page_png(pdf_path: Path, page_index: int, width_px: int, out_png: Path) -> Path:
    img = render_page(pdf_path, page_index, width_px)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, format="PNG")
    logger.debug("渲染页面：%s 第 %d 页 @%dpx → %s", pdf_path.name, page_index + 1, width_px, out_png)
    return out_png


def extract_texts(pdf_path: Path) -> list[tuple[int, str]]:
    """逐页提取文字：返回 [(页码(1起), 文字), ...]，供全文索引。"""
    doc = pdfium.PdfDocument(str(pdf_path))
    out: list[tuple[int, str]] = []
    try:
        for i, page in enumerate(doc):
            try:
                textpage = page.get_textpage()
                text = textpage.get_text_bounded() or ""
                textpage.close()
            except Exception as e:  # noqa: BLE001（单页提取失败不影响其他页）
                logger.warning("文字提取失败 %s 第 %d 页：%s", pdf_path.name, i + 1, e)
                text = ""
            out.append((i + 1, text.strip()))
    finally:
        doc.close()
    return out
