# HymnSlides 发布说明

## 概述

诗歌投影（HymnSlides）：面向教会场景的诗歌 PPT 放映管理器。
访达式文件管理界面 + 一键多屏放映（放映窗置于第二显示器、演示者窗置于主显示器）。

## 产物清单（本 Release 附 SHA256SUMS.txt）

| 产物 | 说明 |
|---|---|
| windows-lite.zip | Windows x64，约 40MB，需系统已装 LibreOffice 或联网下载 |
| windows-full.zip | Windows x64，内置便携 LibreOffice，开箱即用 |
| mac-arm64-full.zip | macOS Apple Silicon（arm64），内置便携 LibreOffice |
| mac-intel-full.zip | macOS Intel（x86_64），内置便携 LibreOffice |

## 安装

- Windows：解压 zip，运行 HymnSlides/HymnSlides.exe。Lite 版需先安装 [LibreOffice](https://www.libreoffice.org/)；Full 版无需任何依赖。
- macOS：解压 zip 得 HymnSlides.app。**包未签名/未公证，首次打开请右键点按 → 打开**（Apple Silicon 机器建议使用 arm64 包；mac-intel 包在 Apple Silicon 上可经 Rosetta 运行但性能与耗电不如原生，建议只装 Intel 机器）。

## 快捷键

| 键 | 功能 |
|---|---|
| Enter / 双击 | 预览 |
| Ctrl+F（macOS: Cmd+F） | 搜索（文件名+幻灯片全文） |
| F5 | 放映（双屏自动布局；单屏 3 秒倒计时确认） |
| ←→/Space/PgUp/PgDn | 翻页 |
| Esc | 退出放映/预览 |
| F11 | 全屏预览 |

## 已知限制

1. 静态渲染：动画/切换/嵌入音视频不保留（本项目素材已确认全部为静态文字+图片）。
2. macOS 包未签名/未公证：首次打开需右键→打开。
3. Full 版下载约 400MB / 解压约 1.2GB；Lite 版约 40MB，需系统已装 LibreOffice。
4. 旧格式 .ppt 个别版式与 PowerPoint 可能有细微差异（取决于 LibreOffice 对旧格式的支持度）。
5. v1 不做 LibreOffice 裁剪（体积优化留 v1.1）。
6. Intel mac 属上游夕阳平台：依赖停发后 Intel 包将停留在最后可用版本，属预期行为而非缺陷。
7. 便携模式：程序目录放置空文件 portable.flag 后，配置/缓存/日志全部保存到程序目录 data/ 下（U 盘分发场景）。
