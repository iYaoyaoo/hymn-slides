"""诗歌投影（HymnSlides）入口。

CLI 验证入口（规范 §3）：--scan --render-test --list-screens --selftest
不带参数启动 GUI。
"""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hymn-slides", description="诗歌投影：Windows/macOS 教会诗歌 PPT 放映管理器"
    )
    parser.add_argument("--scan", metavar="PATH", nargs="?", const="DEFAULT", help="扫描主目录（或指定目录）并输出统计")
    parser.add_argument("--render-test", metavar="PATH", nargs="?", const="DEFAULT", help="对素材执行转换并渲染出图（默认主目录，最多 3 个文件）")
    parser.add_argument("--list-screens", action="store_true", help="枚举显示器（P5 实现）")
    parser.add_argument("--selftest", action="store_true", help="环境自检（OS/Python/LibreOffice）")
    return parser


def cmd_selftest() -> int:
    from src.utils.selftest import run_selftest

    ok, report = run_selftest()
    print(report)
    return 0 if ok else 1


def cmd_scan(target: str | None) -> int:
    from pathlib import Path

    from src.core.config import Config
    from src.core.indexer import Indexer

    root = Path(target).expanduser() if target and target != "DEFAULT" else Config().main_dir
    with Indexer() as idx:
        stats = idx.sync_scan(root)
    print(f"扫描目录: {root}")
    print(
        f"文件总数: {stats.scanned}（新增 {stats.added} / 更新 {stats.updated} / "
        f"跳过 {stats.unchanged} / 删除 {stats.removed}），耗时 {stats.elapsed:.2f}s"
    )
    if stats.errors:
        for e in stats.errors:
            print(f"错误: {e}")
        return 1
    return 0


def cmd_render_test(target: str | None) -> int:
    """转换素材为 PDF 并渲染页面出图（P2 验收：双级缓存 256px / 1920px）。"""
    from pathlib import Path

    from src.core.config import Config
    from src.core.scanner import scan_directory
    from src.render.thumbnail import RenderCache

    root = Path(target).expanduser() if target and target != "DEFAULT" else Config().main_dir
    files = scan_directory(root)[:3]  # 最多 3 个文件，控制验收时长
    if not files:
        print(f"目录中未找到支持的 PPT 文件: {root}")
        return 1

    cache = RenderCache()
    print(f"渲染测试（目录: {root}，取前 {len(files)} 个文件）")
    failures = 0
    for sf in files:
        try:
            pdf = cache.pdf_for(sf.path)
            n = cache.page_count(sf.path)
            t0 = cache.thumb(sf.path, 0)
            t1 = cache.thumb(sf.path, min(1, n - 1)) if n > 1 else None
            show = cache.show_page(sf.path, 0)
            print(f"  {sf.name}: {n} 页 | PDF {pdf.stat().st_size // 1024}KB")
            print(f"    缩略图256px: {t0.stat().st_size // 1024}KB, {t1.stat().st_size // 1024}KB")
            print(f"    放映页1920px: {show.stat().st_size // 1024}KB")
        except Exception as e:  # noqa: BLE001（单文件失败记日志继续，不崩溃）
            failures += 1
            print(f"  {sf.name}: 失败（{e}）")
    print(f"结果: {len(files) - failures}/{len(files)} 成功")
    return 0 if failures == 0 else 1


def cmd_list_screens() -> int:
    print("--list-screens 将在阶段 P5 实现（放映与多屏）")
    return 2


def run_gui() -> int:
    from PySide6.QtWidgets import QApplication

    # 先建 QApplication（QStandardPaths/日志目录依赖实例），再初始化日志
    app = QApplication(sys.argv)
    app.setOrganizationName("HymnSlides")
    app.setApplicationName("HymnSlides")

    from src.ui.main_window import MainWindow
    from src.utils.logger import setup_logging

    setup_logging()

    win = MainWindow()
    win.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not (args.selftest or args.scan is not None or args.render_test is not None or args.list_screens):
        return run_gui()

    from src.utils.logger import setup_logging

    setup_logging()

    if args.selftest:
        return cmd_selftest()
    if args.scan is not None:
        return cmd_scan(args.scan)
    if args.render_test is not None:
        return cmd_render_test(args.render_test)
    return cmd_list_screens()


if __name__ == "__main__":
    sys.exit(main())
