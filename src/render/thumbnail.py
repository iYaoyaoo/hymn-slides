"""双级缓存管理：PDF、256px 缩略图、1920px 放映页（按需），含缓存上限淘汰。

目录布局（cache_root 默认为 QStandardPaths CacheLocation / 便携模式 data/cache）：
  cache/pdf/<key>/<stem>.pdf
  cache/img256/<key>/pNNN.png
  cache/img1920/<key>/pNNN.png
key = sha1(绝对路径 + mtime)[:16]（文件变化 → key 变化 → 旧缓存自然失效）
"""
from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path

from src.render import converter, pdfrender
from src.utils import paths
from src.utils.logger import get_logger

logger = get_logger("thumbnail")


class RenderError(Exception):
    """渲染管线失败（转换或渲染），UI 侧转“转换失败”角标。"""


def _file_key(ppt_path: Path) -> str:
    st = ppt_path.stat()
    return hashlib.sha1(f"{ppt_path}|{st.st_mtime_ns}".encode("utf-8")).hexdigest()[:16]


class RenderCache:
    """缓存门面：确保 PDF / 页图片存在，超限淘汰。线程外调用（UI 后台线程逐个调用）。"""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else paths.cache_dir()
        self.pdf_dir = self.root / "pdf"
        self.img256_dir = self.root / "img256"
        self.img1920_dir = self.root / "img1920"
        self._soffice: Path | None = None

    def _soffice_or_raise(self) -> Path:
        if self._soffice is None:
            from src.core.config import Config
            from src.render.lo_detect import detect_soffice

            info = detect_soffice(Config().soffice_path)
            if not info.found or info.path is None:
                raise RenderError("未找到 LibreOffice（soffice），请安装或在设置中手动指定路径")
            self._soffice = info.path
        return self._soffice

    # ---------- PDF ----------

    def pdf_for(self, ppt_path: Path) -> Path:
        """确保 PPT 已转换，返回 PDF 路径；失败抛 RenderError。"""
        key = _file_key(ppt_path)
        out = self.pdf_dir / key / (ppt_path.stem + ".pdf")
        if out.is_file() and out.stat().st_size > 0:
            return out
        result = converter.convert_to_pdf(ppt_path, self.pdf_dir / key, self._soffice_or_raise())
        if not result.ok or result.pdf_path is None:
            raise RenderError(f"转换失败：{ppt_path.name}（{result.error}）")
        return result.pdf_path

    # ---------- 页图片 ----------

    def _page_png(self, ppt_path: Path, page_index: int, width_px: int, base: Path) -> Path:
        pdf = self.pdf_for(ppt_path)
        key = _file_key(ppt_path)
        out = base / key / f"p{page_index:04d}.png"
        if out.is_file() and out.stat().st_size > 0:
            return out
        total = pdfrender.page_count(pdf)
        if not (0 <= page_index < total):
            raise RenderError(f"页码越界：{ppt_path.name} 第 {page_index + 1} 页（共 {total} 页）")
        return pdfrender.save_page_png(pdf, page_index, width_px, out)

    def thumb(self, ppt_path: Path, page_index: int) -> Path:
        """浏览缩略图（256px）。"""
        return self._page_png(ppt_path, page_index, pdfrender.THUMB_WIDTH_PX, self.img256_dir)

    def show_page(self, ppt_path: Path, page_index: int) -> Path:
        """放映页（1920px，按需生成并缓存）。"""
        return self._page_png(ppt_path, page_index, pdfrender.SHOW_WIDTH_PX, self.img1920_dir)

    def page_count(self, ppt_path: Path) -> int:
        return pdfrender.page_count(self.pdf_for(ppt_path))

    def slide_texts(self, ppt_path: Path) -> list[tuple[int, str]]:
        """逐页文字（供全文索引回填）。"""
        return pdfrender.extract_texts(self.pdf_for(ppt_path))

    # ---------- 缓存上限 ----------

    def enforce_limit(self, limit_mb: int) -> int:
        """超过上限时删除最旧缓存文件，返回释放的字节数。"""
        limit_bytes = limit_mb * 1024 * 1024
        files: list[tuple[float, int, Path]] = []
        for base in (self.pdf_dir, self.img256_dir, self.img1920_dir):
            if not base.is_dir():
                continue
            for p in base.rglob("*"):
                if p.is_file():
                    st = p.stat()
                    files.append((st.st_mtime, st.st_size, p))
        total = sum(s for _, s, _ in files)
        if total <= limit_bytes:
            return 0
        freed = 0
        files.sort()  # 最旧优先
        for mtime, size, p in files:
            if total - freed <= limit_bytes:
                break
            try:
                p.unlink()
                freed += size
                d = p.parent
                if d != self.root and not any(d.iterdir()):
                    d.rmdir()
            except OSError as e:
                logger.debug("淘汰缓存文件失败 %s: %s", p, e)
        if freed:
            logger.info("缓存超限（%dMB）：淘汰最旧文件释放 %.1fMB", limit_mb, freed / 1048576)
        return freed

    def purge_file_cache(self, ppt_path: Path) -> None:
        """删除某文件的全部缓存（文件更新后调用）。"""
        key = _file_key(ppt_path)
        for base in (self.pdf_dir, self.img256_dir, self.img1920_dir):
            d = base / key
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)

    def total_size_bytes(self) -> int:
        total = 0
        for base in (self.pdf_dir, self.img256_dir, self.img1920_dir):
            if base.is_dir():
                total += sum(p.stat().st_size for p in base.rglob("*") if p.is_file())
        return total


def refresh_index_fulltext(ppt_path: Path, indexer, cache: RenderCache | None = None) -> int:
    """转换+提取文字+回填索引（页数+全文），返回页数。UI 扫描线程逐文件调用。"""
    cache = cache or RenderCache()
    texts = cache.slide_texts(ppt_path)
    fid = indexer.file_id_by_path(str(ppt_path))
    if fid is None:
        logger.warning("回填全文：文件不在索引中 %s", ppt_path)
        return len(texts)
    indexer.upsert_slide_texts(fid, texts)
    indexer.set_page_count(fid, len(texts))
    return len(texts)
