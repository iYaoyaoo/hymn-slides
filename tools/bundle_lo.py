"""便携 LibreOffice 捆绑工具（规范 tools/bundle_lo.py）。

- 从 tools/downloads/ 官方包提取便携 libreoffice/
- --download 自动下载并 SHA256 校验
- 来源常量三分：Windows x64 msi / macOS aarch64 dmg / macOS x86_64 dmg
- 版本常量首次固化后不变（26.8.2）
- 若上游停发 Intel dmg，使用最后一个可用版本并在 README 标注

用法：
  python3 tools/bundle_lo.py --platform auto            # 提取已下载的包
  python3 tools/bundle_lo.py --platform auto --download # 缺失时自动下载
"""
from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.logger import setup_logging

LO_VERSION = "26.8.2"
DOWNLOADS_DIR = Path(__file__).resolve().parent / "downloads"
_BASE = f"https://download.documentfoundation.org/libreoffice/stable/{LO_VERSION}"


@dataclass(frozen=True)
class Source:
    key: str
    filename: str
    url: str
    sha256: str


SOURCES = {
    "windows-x64": Source(
        key="windows-x64",
        filename=f"LibreOffice_{LO_VERSION}_Win_x86-64.msi",
        url=f"{_BASE}/win/x86_64/LibreOffice_{LO_VERSION}_Win_x86-64.msi",
        sha256="ff4b911403b67ee9e6249f820f9782c44bb32c94fdaa45b0da53a8e419e5307a",
    ),
    "mac-arm64": Source(
        key="mac-arm64",
        filename=f"LibreOffice_{LO_VERSION}_MacOS_aarch64.dmg",
        url=f"{_BASE}/mac/aarch64/LibreOffice_{LO_VERSION}_MacOS_aarch64.dmg",
        sha256="9f24fe83ab1ed5c95eb3df580119f32932f713e577feeac02bf619fb00749b55",
    ),
    "mac-intel": Source(
        key="mac-intel",
        filename=f"LibreOffice_{LO_VERSION}_MacOS_x86-64.dmg",
        url=f"{_BASE}/mac/x86_64/LibreOffice_{LO_VERSION}_MacOS_x86-64.dmg",
        sha256="0af062779cc17f6f852918b2424c745f7dd2d20d51d7fb8a0925eb92ec0417a7",
    ),
}


def auto_platform() -> str:
    if platform.system() == "Windows":
        return "windows-x64"
    if platform.system() == "Darwin":
        return "mac-intel" if platform.machine() == "x86_64" else "mac-arm64"
    raise SystemExit("不支持的构建平台（仅 Windows / macOS）")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_package(key: str, download: bool) -> Path:
    src = SOURCES[key]
    path = DOWNLOADS_DIR / src.filename
    if path.is_file():
        print(f"已存在：{path}")
    elif download:
        print(f"下载：{src.url}")
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        urllib.request.urlretrieve(src.url, tmp)  # noqa: S310（官方源，固定 URL）
        tmp.rename(path)
    else:
        raise SystemExit(f"缺少官方包：{path}（用 --download 自动获取）")

    actual = sha256_file(path)
    if actual != src.sha256:
        raise SystemExit(f"SHA256 校验失败：{path}\n  期望 {src.sha256}\n  实际 {actual}")
    print(f"SHA256 校验通过：{actual}")
    return path


# ---------- 提取 ----------

def extract_mac_dmg(dmg: Path, out_dir: Path) -> Path:
    """挂载 dmg → 拷贝 LibreOffice.app → out_dir/LibreOffice.app。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "LibreOffice.app"
    if (dest / "Contents" / "MacOS" / "soffice").exists():
        print(f"已提取：{dest}")
        return dest
    mnt = Path(tempfile.mkdtemp(prefix="lo_mount_"))
    subprocess.run(
        ["hdiutil", "attach", str(dmg), "-mountpoint", str(mnt), "-nobrowse", "-readonly"],
        check=True,
        capture_output=True,
    )
    try:
        app_src = mnt / "LibreOffice.app"
        if not app_src.is_dir():
            raise SystemExit(f"dmg 中未找到 LibreOffice.app：{dmg}")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(app_src, dest)
    finally:
        subprocess.run(
            ["hdiutil", "detach", str(mnt)], check=False, capture_output=True
        )
    print(f"提取完成：{dest}")
    return dest


def extract_windows_msi(msi: Path, out_dir: Path) -> Path:
    """msiexec 管理安装提取到 out_dir（Windows CI 用）。返回含 program/soffice.exe 的 libreoffice/ 目录。"""
    if sys.platform != "win32":
        raise SystemExit("Windows msi 提取只能在 Windows 上执行（CI windows job）")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir.parent / "lo_msi_admin"
    if target.exists():
        shutil.rmtree(target)
    subprocess.run(
        ["msiexec", "/a", str(msi), "/qn", f"TARGETDIR={target}"],
        check=True,
        capture_output=True,
    )
    # 管理映像可能直接含 program/，或含 LibreOffice/program/
    for cand in (target, target / "LibreOffice"):
        if (cand / "program" / "soffice.exe").exists():
            if out_dir.exists():
                shutil.rmtree(out_dir)
            shutil.copytree(cand, out_dir)
            shutil.rmtree(target, ignore_errors=True)
            print(f"提取完成：{out_dir}")
            return out_dir
    raise SystemExit(f"msi 提取结果中未找到 program/soffice.exe：{target}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="提取便携 LibreOffice 到 libreoffice/ 目录")
    parser.add_argument("--platform", default="auto", choices=[*SOURCES, "auto"])
    parser.add_argument("--download", action="store_true", help="缺失时自动下载官方包")
    parser.add_argument("--out", default=None, help="输出 libreoffice/ 目录（默认 <repo>/dist_staging/libreoffice）")
    args = parser.parse_args(argv)

    setup_logging()
    key = args.platform if args.platform != "auto" else auto_platform()
    pkg = ensure_package(key, args.download)

    out = Path(args.out) if args.out else Path(__file__).resolve().parents[1] / "dist_staging" / "libreoffice"
    if key == "windows-x64":
        extract_windows_msi(pkg, out)
    else:
        extract_mac_dmg(pkg, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
