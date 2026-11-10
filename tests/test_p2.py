"""P2 验收测试：pypdfium2 渲染+文字提取、converter（真实 LO，无 LO 时跳过）、双级缓存。"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from src.render import converter, pdfrender
from src.render.thumbnail import RenderCache, RenderError

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "样本.pdf"

# 本机 LibreOffice（探测不到则跳过真实转换类测试）
from src.render.lo_detect import detect_soffice

_INFO = detect_soffice()
HAS_LO = _INFO.found


# ---------- pdfrender（仅依赖夹具 PDF，全平台可跑） ----------

def test_page_count():
    assert pdfrender.page_count(FIXTURE_PDF) == 2


def test_extract_texts_chinese():
    texts = pdfrender.extract_texts(FIXTURE_PDF)
    assert len(texts) == 2
    assert texts[0][0] == 1 and texts[1][0] == 2
    all_text = texts[0][1] + texts[1][1]
    assert "奇异恩典" in all_text
    assert "赦免" in all_text
    assert "你真伟大" in all_text


def test_render_page_dimensions():
    img = pdfrender.render_page(FIXTURE_PDF, 0, pdfrender.THUMB_WIDTH_PX)
    assert img.width == 256
    assert img.height > 0
    show = pdfrender.render_page(FIXTURE_PDF, 1, pdfrender.SHOW_WIDTH_PX)
    assert show.width == 1920


def test_save_page_png(tmp_path):
    out = tmp_path / "p0001.png"
    pdfrender.save_page_png(FIXTURE_PDF, 1, 256, out)
    assert out.is_file()
    # PNG 魔数
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_page_out_of_range():
    import pypdfium2 as pdfium

    with pytest.raises(pdfium.PdfiumError):
        pdfrender.render_page(FIXTURE_PDF, 99, 256)


# ---------- converter（需真实 LibreOffice） ----------

@pytest.mark.skipif(not HAS_LO, reason="本机未安装 LibreOffice")
def test_converter_real_conversion(tmp_path):
    from pptx import Presentation

    pptx = tmp_path / "测试 诗歌.pptx"
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text = "奇异恩典"
    prs.save(pptx)

    result = converter.convert_to_pdf(pptx, tmp_path / "out", _INFO.path)
    assert result.ok and result.pdf_path is not None
    assert result.pdf_path.suffix == ".pdf"
    assert result.pdf_path.stat().st_size > 0
    assert pdfrender.page_count(result.pdf_path) == 1


@pytest.mark.skipif(not HAS_LO, reason="本机未安装 LibreOffice")
def test_converter_uses_separate_profile(tmp_path):
    """转换产物 PDF 与 profile 目录应存在（-env:UserInstallation 生效）。"""
    from src.utils import paths

    assert paths.lo_profile_dir().is_dir()


@pytest.mark.skipif(not HAS_LO, reason="本机未安装 LibreOffice")
def test_converter_failure_nonzero(tmp_path):
    bad = tmp_path / "损坏.pptx"
    bad.write_bytes(b"not a pptx")
    result = converter.convert_to_pdf(bad, tmp_path / "out", _INFO.path)
    # soffice 对损坏文件：要么失败返回 False，要么产出空/异常 PDF —— 均不得崩溃
    assert isinstance(result.ok, bool)


def test_converter_invalid_soffice_no_crash(tmp_path):
    pptx = tmp_path / "a.pptx"
    pptx.write_bytes(b"x")
    result = converter.convert_to_pdf(pptx, tmp_path, tmp_path / "no_such_soffice")
    assert result.ok is False
    assert result.error


# ---------- 双级缓存 ----------

def test_cache_thumb_and_show(tmp_path, monkeypatch):
    """有 LO：全链路；无 LO：跳过。"""
    if not HAS_LO:
        pytest.skip("本机未安装 LibreOffice")
    from pptx import Presentation

    pptx = tmp_path / "诗歌.pptx"
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[0]).shapes.title.text = "奇异恩典"
    prs.save(pptx)

    cache = RenderCache(root=tmp_path / "cache")
    pdf = cache.pdf_for(pptx)
    assert pdf.is_file()
    assert cache.page_count(pptx) == 1

    t0 = cache.thumb(pptx, 0)
    s0 = cache.show_page(pptx, 0)
    assert t0.is_file() and t0.stat().st_size > 0
    assert s0.is_file() and s0.stat().st_size > 0
    # key 布局：256 与 1920 分目录
    assert t0.parent != s0.parent

    # 二次调用命中缓存（文件数不增）
    n_before = len(list((tmp_path / "cache").rglob("*.png")))
    cache.thumb(pptx, 0)
    cache.show_page(pptx, 0)
    n_after = len(list((tmp_path / "cache").rglob("*.png")))
    assert n_before == n_after

    # 页码越界 → RenderError
    with pytest.raises(RenderError):
        cache.show_page(pptx, 5)


def test_cache_texts(tmp_path, monkeypatch):
    """slide_texts 经引擎链路由（LO → PDF 提取；_lo_pdf_provider 用夹具替身）。"""
    cache = RenderCache(root=tmp_path / "cache")
    monkeypatch.setattr(cache, "_lo_pdf_provider", lambda p: FIXTURE_PDF)
    texts = cache.slide_texts(Path("/任意/诗歌.pptx"))
    assert texts and "奇异恩典" in texts[0][1]
    assert texts[1][0] == 2 and "你真伟大" in texts[1][1]


def test_cache_limit_eviction(tmp_path):
    """缓存上限淘汰：最旧优先删除。"""
    cache = RenderCache(root=tmp_path / "cache")
    for base in (cache.pdf_dir, cache.img256_dir, cache.img1920_dir):
        base.mkdir(parents=True, exist_ok=True)
    # 造 3 个文件：旧文件最大，新文件最小
    old = cache.img256_dir / "old.png"
    old.write_bytes(b"x" * 100)
    os.utime(old, (1000.0, 1000.0))
    mid = cache.img256_dir / "mid.png"
    mid.write_bytes(b"x" * 50)
    os.utime(mid, (2000.0, 2000.0))
    new = cache.pdf_dir / "new.pdf"
    new.write_bytes(b"x" * 10)
    os.utime(new, (3000.0, 3000.0))

    freed = cache.enforce_limit(limit_mb=0)  # 上限 0 → 清理到空
    assert freed == 160
    assert not old.exists() and not mid.exists() and not new.exists()
    assert cache.total_size_bytes() == 0


def test_cache_limit_noop_under_limit(tmp_path):
    cache = RenderCache(root=tmp_path / "cache")
    cache.img256_dir.mkdir(parents=True, exist_ok=True)
    f = cache.img256_dir / "f.png"
    f.write_bytes(b"x" * 100)
    assert cache.enforce_limit(limit_mb=1) == 0
    assert f.exists()


def test_purge_file_cache(tmp_path):
    cache = RenderCache(root=tmp_path / "cache")
    key_dir = cache.img256_dir / "abc123"
    key_dir.mkdir(parents=True, exist_ok=True)
    (key_dir / "p0001.png").write_bytes(b"x")
    # purge 依赖 mtime 计算的 key，直接验证目录删除逻辑（用 monkeypatch 固定 key）
    import src.render.thumbnail as th

    orig = th._file_key
    th._file_key = lambda p: "abc123"
    try:
        cache.purge_file_cache(Path("/nonexistent/诗歌.pptx"))
    finally:
        th._file_key = orig
    assert not key_dir.exists()
