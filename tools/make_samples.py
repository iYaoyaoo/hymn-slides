"""生成测试素材（规范 tools/make_samples.py）。

- .pptx 用 python-pptx 直接生成（中文文件名、3 层目录、含 50+ 页大文件）
- .ppt/.pps 由 soffice 转换 .pptx 得到

用法：python3 tools/make_samples.py [--out DIR]（默认 <项目根>/samples）
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pptx import Presentation
from pptx.util import Inches, Pt

from src.render.lo_detect import detect_soffice
from src.utils import paths
from src.utils.logger import setup_logging

SAMPLES = [
    # (相对路径, 文件名, [(标题, 正文), ...])
    (
        Path("2026年") / "一季度",
        "奇异恩典.pptx",
        [
            ("奇异恩典", "何等奇妙的救主耶稣\n我罪已得赦免"),
            ("奇异恩典（二）", "前我失丧，今被寻回\n瞎眼今得看见"),
            ("奇异恩典（三）", "如此恩典，使我敬畏\n心得安慰"),
        ],
    ),
    (
        Path("2026年") / "一季度",
        "你真伟大.pptx",
        [
            ("你真伟大", "主啊我神，每逢举目观看"),
            ("你真伟大（二）", "你真伟大，配得尊贵"),
        ],
    ),
    (
        Path("2026年") / "二季度",
        "主在圣殿中.pptx",
        [
            ("主在圣殿中", "肃静！肃静！\n主在圣殿中"),
            ("主在圣殿中（二）", "万民当肃静\n屈膝敬拜"),
        ],
    ),
    (
        Path("2027年") / "敬拜诗集",
        "诗歌敬拜.pptx",
        [
            ("诗歌敬拜", "你们要赞美耶和华"),
            ("诗歌敬拜（二）", "在祂的圣所赞美祂"),
        ],
    ),
]

BIG_FILE_COUNT = 52


def make_pptx(out_path: Path, slides: list[tuple[str, str]]) -> None:
    prs = Presentation()
    for title, body in slides:
        s = prs.slides.add_slide(prs.slide_layouts[0])
        s.shapes.title.text = title
        ph = s.placeholders[1]
        ph.text = body
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)


def make_big_pptx(out_path: Path) -> None:
    prs = Presentation()
    for i in range(1, BIG_FILE_COUNT + 1):
        s = prs.slides.add_slide(prs.slide_layouts[0])
        s.shapes.title.text = f"诗歌合集 第 {i} 首"
        s.placeholders[1].text = f"这是合集第 {i} 首诗歌的内容\n愿荣耀归于至高神"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)


def convert_format(soffice: Path, src: Path, out_dir: Path, fmt: str) -> bool:
    """soffice 转换 .pptx → .ppt/.pps（参数列表调用，独立 profile）。"""
    cmd = [
        str(soffice),
        "--headless",
        "--norestore",
        "--nolockcheck",
        f"-env:UserInstallation={paths.lo_profile_dir().as_uri()}",
        "--convert-to",
        fmt,
        "--outdir",
        str(out_dir),
        str(src),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)  # noqa: S603
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"  转换 {fmt} 失败：{src.name}（{e}）")
        return False
    expected = out_dir / (src.stem + f".{fmt}")
    ok = proc.returncode == 0 and expected.is_file()
    if not ok:
        print(f"  转换 {fmt} 失败：{src.name}（rc={proc.returncode}）")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成诗歌 PPT 测试素材")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "samples"), help="输出目录")
    parser.add_argument("--with-legacy", action="store_true", help="同时生成 .ppt/.pps 旧格式（需 LibreOffice）")
    args = parser.parse_args(argv)

    setup_logging()
    out_root = Path(args.out).expanduser()
    out_root.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    for rel, name, slides in SAMPLES:
        p = out_root / rel / name
        make_pptx(p, slides)
        generated.append(p)
        print(f"生成: {p}")

    big = out_root / Path("2027年") / "敬拜诗集" / "诗歌合集.pptx"
    make_big_pptx(big)
    generated.append(big)
    print(f"生成: {big}（{BIG_FILE_COUNT} 页大文件）")

    # .ppt / .pps 旧格式（由 soffice 转换得来）
    legacy_count = 0
    if args.with_legacy:
        info = detect_soffice()
        if info.found and info.path is not None:
            for src, fmt in ((generated[0], "ppt"), (generated[2], "ppt"), (generated[3], "pps")):
                if convert_format(info.path, src, src.parent, fmt):
                    legacy_count += 1
        else:
            print("警告：未找到 LibreOffice，跳过 .ppt/.pps 生成")

    total = len(generated) + legacy_count
    print(f"完成：共生成 {total} 个文件（.pptx {len(generated)} 个" + (f"，.ppt/.pps {legacy_count} 个" if legacy_count else "") + "）")
    print(f"输出目录：{out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
