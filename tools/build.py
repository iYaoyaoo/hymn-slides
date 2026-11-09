"""PyInstaller 构建入口（规范 tools/build.py）。

用法：
  python3 tools/build.py --variant lite  --arch x86_64
  python3 tools/build.py --variant full  --arch x86_64

规则：
- mac 产物必须做架构断言：主程序与 PySide6/pypdfium2 核心二进制经 lipo -info 校验，
  须含 --arch 指定架构；断言失败=构建失败。
- full：将 libreoffice/ 复制进发布目录（macOS 复制进 .app/Contents/Resources/）。
- 构建后运行产物的 --selftest，PASS 才算构建成功（结果写日志并由此脚本校验）。
"""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.logger import setup_logging

REPO = Path(__file__).resolve().parents[1]
DIST = REPO / "dist"
APP_NAME = "HymnSlides"
STAGING_LIBREOFFICE = REPO / "dist_staging" / "libreoffice"


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("$", " ".join(str(c) for c in cmd[:8]), "…" if len(cmd) > 8 else "")
    return subprocess.run(cmd, check=True, **kw)


def pyinstaller_cmd(variant: str) -> list[str]:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onedir", "--windowed",
        "--name", APP_NAME,
        "--paths", str(REPO),
        "--exclude-module", "PyInstaller",
        "--exclude-module", "pytest",
        str(REPO / "main.py"),
    ]
    return cmd


def lipo_arch_ok(binary: Path, want: str) -> bool:
    proc = subprocess.run(["lipo", "-info", str(binary)], capture_output=True, text=True, check=False)
    out = proc.stdout + proc.stderr
    return want in out and proc.returncode == 0


def _resolve_first(paths: list[Path]) -> Path | None:
    """按序返回第一个存在的候选；支持 glob（父目录存在时）。"""
    for p in paths:
        if p.is_file():
            return p
        if any(p.parent.glob(p.name)):
            return next(p.parent.glob(p.name))
    return None


def assert_mac_arch(app_dir: Path, want: str) -> None:
    """mac 架构断言：主程序 + PySide6(QtCore) + pypdfium2 核心二进制（规范：断言失败=构建失败）。"""
    c = app_dir / "Contents"
    main_bin = _resolve_first([c / "MacOS" / APP_NAME])
    qt_core = _resolve_first(
        [
            c / "Frameworks" / "PySide6" / "QtCore.abi3.so",
            c / "Frameworks" / "PySide6" / "Qt" / "lib" / "QtCore.framework" / "Versions" / "A" / "QtCore",
            c / "Frameworks" / "libQtCore.dylib",
            c / "Resources" / "QtCore" / "libQtCore*.dylib",
        ]
    )
    pdfium = _resolve_first(
        [
            c / "Frameworks" / "pypdfium2_raw.dylib",
            c / "Resources" / "pypdfium2_raw" / "libpdfium*.dylib",
            c / "Resources" / "pypdfium2_raw" / "*.so",
        ]
    )
    for label, p in (("主程序", main_bin), ("PySide6 QtCore", qt_core), ("pypdfium2", pdfium)):
        if p is None:
            raise SystemExit(f"架构断言失败：未找到 {label} 二进制")
        if not lipo_arch_ok(p, want):
            raise SystemExit(f"架构断言失败：{label} {p} 不含 {want}")
        print(f"架构断言通过（{want}）：{label} → {p.name}")


def run_selftest(binary: Path) -> None:
    """运行产物 --selftest；exit code 0=PASS（结果亦写产物自身日志）。"""
    proc = subprocess.run([str(binary), "--selftest"], capture_output=True, text=True, timeout=180)
    out = proc.stdout + proc.stderr
    if proc.returncode != 0 or "SELFTEST RESULT: PASS" not in out:
        print(out[-2000:])
        raise SystemExit(f"产物 selftest 校验失败（exit={proc.returncode}）")
    print("产物 --selftest PASS")


def make_zip(src: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    if platform.system() == "Darwin" and src.suffix == ".app":
        run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(src), str(zip_path)])
    else:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in src.rglob("*"):
                zf.write(p, p.relative_to(src.parent))
    print(f"打包：{zip_path}")


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HymnSlides PyInstaller 构建")
    parser.add_argument("--variant", required=True, choices=["lite", "full"])
    parser.add_argument("--arch", required=True, choices=["arm64", "x86_64"])
    parser.add_argument("--lo-dir", default=None, help="libreoffice/ 目录（full 用，默认 dist_staging/libreoffice）")
    parser.add_argument("--skip-selftest", action="store_true", help="离屏无 LO 环境跳过（架构断言不可豁免）")
    args = parser.parse_args(argv)

    setup_logging()

    is_mac = platform.system() == "Darwin"
    if is_mac and platform.machine() != args.arch and not (
        args.arch == "x86_64" and platform.machine() == "i386"
    ):
        print(f"警告：目标架构 {args.arch} 与本机 {platform.machine()} 不一致（交叉构建未启用，按当前解释器架构出包）")

    print(f"=== 构建 HymnSlides {args.variant}（arch={args.arch}）===")
    run(pyinstaller_cmd(args.variant))

    if is_mac:
        app_dir = DIST / f"{APP_NAME}.app"
        assert_mac_arch(app_dir, args.arch)
        binary = app_dir / "Contents" / "MacOS" / APP_NAME
        if args.variant == "full":
            lo_src = Path(args.lo_dir) if args.lo_dir else STAGING_LIBREOFFICE
            if not (lo_src / "LibreOffice.app").is_dir():
                raise SystemExit(f"full 变体缺少 LibreOffice：{lo_src}/LibreOffice.app 不存在")
            res_lo = app_dir / "Contents" / "Resources" / "libreoffice"
            if res_lo.exists():
                shutil.rmtree(res_lo)
            res_lo.mkdir(parents=True)
            run(["cp", "-R", str(lo_src / "LibreOffice.app"), str(res_lo / "LibreOffice.app")])
            print(f"已捆绑 LibreOffice → {res_lo}")
    else:
        win_dir = DIST / APP_NAME
        binary = win_dir / f"{APP_NAME}.exe"
        if args.variant == "full":
            lo_src = Path(args.lo_dir) if args.lo_dir else STAGING_LIBREOFFICE
            dest = win_dir / "libreoffice"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(lo_src, dest)
            print(f"已捆绑 LibreOffice → {dest}")

    # 产物 selftest 校验（离屏无 LO 环境允许跳过 selftest，架构断言不豁免）
    if not args.skip_selftest:
        run_selftest(binary)

    # zip + SHA256
    if is_mac:
        tag = "mac-intel" if args.arch == "x86_64" else "mac-arm64"
    else:
        tag = "windows"
    zip_path = DIST / f"{tag}-{args.variant}.zip"
    make_zip(app_dir if is_mac else win_dir, zip_path)
    print(f"SHA256: {sha256_file(zip_path)}  {zip_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
