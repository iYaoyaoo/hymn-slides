"""PyInstaller 构建入口（v4 规范 §6）。

用法：
  python3 tools/build.py --arch x86_64   # Windows / mac-intel
  python3 tools/build.py --arch arm64    # mac-arm64

规则（v4）：
- 单变体（不再有 lite/full；LibreOffice 不再捆绑，引擎三级链运行时探测）。
- mac 产物必须做架构断言：主程序与 PySide6/pypdfium2 核心二进制经 lipo -info 校验，
  须含 --arch 指定架构；断言失败=构建失败。
- 构建后运行产物的 --selftest，PASS 才算构建成功（结果写日志并由此脚本校验）。
- 产物命名：windows.zip / mac-arm64.zip / mac-intel.zip。
"""
from __future__ import annotations

import argparse
import hashlib
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.logger import setup_logging

REPO = Path(__file__).resolve().parents[1]
DIST = REPO / "dist"
APP_NAME = "HymnSlides"


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("$", " ".join(str(c) for c in cmd[:8]), "…" if len(cmd) > 8 else "")
    return subprocess.run(cmd, check=True, **kw)


def pyinstaller_cmd() -> list[str]:
    return [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onedir", "--windowed",
        "--name", APP_NAME,
        "--paths", str(REPO),
        "--exclude-module", "PyInstaller",
        "--exclude-module", "pytest",
        str(REPO / "main.py"),
    ]


def lipo_arch_ok(binary: Path, want: str) -> bool:
    proc = subprocess.run(["lipo", "-info", str(binary)], capture_output=True, text=True, check=False)
    out = proc.stdout + proc.stderr
    return want in out and proc.returncode == 0


def _resolve_first(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.is_file():
            return p
        if any(p.parent.glob(p.name)):
            return next(p.parent.glob(p.name))
    return None


def assert_mac_arch(app_dir: Path, want: str) -> None:
    """mac 架构断言：主程序 + PySide6(QtCore) + pypdfium2 核心二进制。断言失败=构建失败。"""
    c = app_dir / "Contents"
    main_bin = _resolve_first([c / "MacOS" / APP_NAME])
    qt_core = _resolve_first(
        [
            c / "Frameworks" / "PySide6" / "QtCore.abi3.so",
            c / "Frameworks" / "PySide6" / "Qt" / "lib" / "QtCore.framework" / "Versions" / "A" / "QtCore",
            c / "Frameworks" / "libQtCore.dylib",
        ]
    )
    pdfium = _resolve_first(
        [
            c / "Frameworks" / "pypdfium2_raw.dylib",
            c / "Resources" / "pypdfium2_raw" / "libpdfium*.dylib",
        ]
    )
    for label, p in (("主程序", main_bin), ("PySide6 QtCore", qt_core), ("pypdfium2", pdfium)):
        if p is None:
            raise SystemExit(f"架构断言失败：未找到 {label} 二进制")
        if not lipo_arch_ok(p, want):
            raise SystemExit(f"架构断言失败：{label} {p} 不含 {want}")
        print(f"架构断言通过（{want}）：{label} → {p.name}")


def _dump_crash_log(binary: Path) -> None:
    crash = binary.parent / "HymnSlides-crash.log"
    if crash.is_file():
        print("---- HymnSlides-crash.log ----")
        print(crash.read_text(encoding="utf-8")[:2000])


def run_selftest(binary: Path) -> None:
    """运行产物 --selftest；exit code 0=PASS（结果亦写产物自身日志）。

    Windows --windowed exe 无控制台（stdout 为空），此时以退出码为准。
    """
    proc = subprocess.run([str(binary), "--selftest"], capture_output=True, text=True, timeout=180)
    out = (proc.stdout or "") + (proc.stderr or "")
    if "SELFTEST RESULT: PASS" in out:
        print("产物 --selftest PASS")
        return
    if proc.returncode == 0 and not out.strip():
        print("产物 --selftest PASS（windowed 无控制台输出，以退出码为准；结果已写日志）")
        return
    print(out[-2000:])
    _dump_crash_log(binary)
    raise SystemExit(f"产物 selftest 校验失败（exit={proc.returncode}）")


def make_zip(src: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    if platform.system() == "Darwin" and src.suffix == ".app":
        run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(src), str(zip_path)])
    else:
        import zipfile

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in src.rglob("*"):
                zf.write(p, p.relative_to(src.parent))
    print(f"打包：{zip_path}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HymnSlides PyInstaller 构建（v4 单变体）")
    parser.add_argument("--arch", required=True, choices=["arm64", "x86_64"])
    parser.add_argument("--skip-selftest", action="store_true", help="离屏无引擎环境跳过（架构断言不可豁免）")
    args = parser.parse_args(argv)

    setup_logging()
    is_mac = platform.system() == "Darwin"

    print(f"=== 构建 HymnSlides（arch={args.arch}，v4 单变体）===")
    run(pyinstaller_cmd())

    if is_mac:
        app_dir = DIST / f"{APP_NAME}.app"
        assert_mac_arch(app_dir, args.arch)
        binary = app_dir / "Contents" / "MacOS" / APP_NAME
    else:
        win_dir = DIST / APP_NAME
        binary = win_dir / f"{APP_NAME}.exe"

    if not args.skip_selftest:
        run_selftest(binary)

    tag = ("mac-intel" if args.arch == "x86_64" else "mac-arm64") if is_mac else "windows"
    zip_path = DIST / f"{tag}.zip"
    make_zip(app_dir if is_mac else DIST / APP_NAME, zip_path)
    print(f"SHA256: {sha256_file(zip_path)}  {zip_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
