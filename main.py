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
    parser.add_argument("--scan", action="store_true", help="扫描主目录并输出统计（P1 实现）")
    parser.add_argument("--render-test", metavar="PATH", nargs="?", const="DEFAULT", help="对素材执行转换并渲染出图（P2 实现）")
    parser.add_argument("--list-screens", action="store_true", help="枚举显示器（P5 实现）")
    parser.add_argument("--selftest", action="store_true", help="环境自检（OS/Python/LibreOffice）")
    return parser


def cmd_selftest() -> int:
    from src.utils.selftest import run_selftest

    ok, report = run_selftest()
    print(report)
    return 0 if ok else 1


def cmd_scan() -> int:
    print("--scan 将在阶段 P1 实现（当前 P0：扫描/索引/搜索）")
    return 2


def cmd_render_test(target: str | None) -> int:
    print("--render-test 将在阶段 P2 实现（渲染管线）")
    return 2


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

    if not (args.selftest or args.scan or args.render_test is not None or args.list_screens):
        return run_gui()

    from src.utils.logger import setup_logging

    setup_logging()

    if args.selftest:
        return cmd_selftest()
    if args.scan:
        return cmd_scan()
    if args.render_test is not None:
        return cmd_render_test(args.render_test)
    return cmd_list_screens()


if __name__ == "__main__":
    sys.exit(main())
