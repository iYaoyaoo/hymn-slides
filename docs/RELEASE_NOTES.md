# HymnSlides 发布说明

## 概述

诗歌投影（HymnSlides）：面向教会场景的诗歌 PPT 放映管理器。
大搜索框 + 全高目录树定位诗歌，F5/双击一键放映；支持 PowerPoint / WPS / LibreOffice 三级引擎回退。

## 产物清单（本 Release 附 SHA256SUMS.txt）

| 产物 | 说明 |
|---|---|
| windows.zip | Windows x64，约 40MB |
| mac-arm64.zip | macOS Apple Silicon（arm64） |
| mac-intel.zip | macOS Intel（x86_64） |

## 前置要求（重要）

本程序**不内置渲染引擎**，需要系统安装以下任一软件：

1. **Microsoft PowerPoint**（推荐，放映保真最高）
2. **WPS Office**（仅 Windows 支持自动化放映）
3. **LibreOffice**（免费开源，https://www.libreoffice.org ）

三者均未安装时，程序启动会弹窗引导下载。

## 安装

- **Windows**：解压 zip，运行 `HymnSlides\HymnSlides.exe`
- **macOS**：解压得 HymnSlides.app。**包未签名/未公证，首次打开请右键点按 → 打开**（mac-intel 包在 Apple Silicon 上可经 Rosetta 运行但建议只装 Intel 机器；arm64 包不可在 Intel 机器运行）

## 快捷键与操作

| 操作 | 功能 |
|---|---|
| Ctrl+F（Cmd+F） | 聚焦搜索（文件名+幻灯片全文） |
| 搜索 | 实时过滤树：仅显示命中文件及其目录层级；清空恢复 |
| 双击文件 / F5 | 放映（双屏时放映窗自动置于第二显示器、演示者窗在主显示器） |
| ←→/Space/PgUp/PgDn | 翻页 |
| Esc | 退出放映 / 清空搜索 |
| 文件右键 | 在文件管理器中显示 |
| 展开全部 / 收起 | 树视图一键展开收起 |

## 引擎说明

- 优先级：PowerPoint → WPS → LibreOffice（可在设置中手动指定路径）
- Windows：PowerPoint/WPS 经 COM 自动化控制放映与内容导出
- macOS：PowerPoint 经 AppleScript 控制放映（放映窗口位置由 PowerPoint 自身偏好决定）；缩略图/全文/页面图片需 LibreOffice；WPS macOS 无自动化接口不支持

## 已知限制

1. 需要系统安装 PowerPoint / WPS / LibreOffice 之一；均未安装时程序仅能浏览文件树（会弹窗引导）。
2. macOS 下 PowerPoint 仅支持放映控制；出图/全文需 LibreOffice；WPS macOS 不支持。
3. LibreOffice 路径为静态渲染：动画/切换/嵌入音视频不保留（PowerPoint/WPS 原生放映保真最高）。
4. macOS 包未签名/未公证：首次打开需右键→打开。
5. 旧格式 .ppt 在 LibreOffice 路径下个别版式可能有细微差异；PowerPoint/WPS 路径无此问题。
6. Intel mac 属上游夕阳平台：依赖停发后 Intel 包将停留在最后可用版本，属预期行为而非缺陷。
7. 便携模式：程序目录放置空文件 portable.flag 后，配置/缓存/日志全部保存在程序目录 data/ 下（U 盘分发场景）。
