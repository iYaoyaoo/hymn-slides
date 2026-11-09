# 诗歌投影 HymnSlides

Windows / macOS 教会诗歌 PPT 放映管理器：访达式文件管理界面，一键在第二显示器全屏放映诗歌，主显示器同步显示演示者控制窗。

## 功能

- **目录管理**：默认主目录为程序所在目录，可在设置中切换；支持便携模式（程序目录放置空文件 `portable.flag`，配置/缓存/日志全部保存在程序目录 `data/` 下，适合 U 盘分发）
- **访达式界面**：目录树 + 面包屑 + 图标/列表视图 + 后退/前进 + 底部状态栏，递归穿透扫描全部子目录（跳过隐藏/系统目录）
- **搜索**：Ctrl+F（macOS: Cmd+F），300ms 防抖实时搜索文件名与幻灯片全文，结果双击定位并选中
- **预览**：选中文件右侧逐页缩略图（懒加载）；Enter/双击全屏预览
- **放映**：F5 启动。双屏时放映窗自动置于第二显示器、演示者窗置于主显示器（当前/下一页缩略图、进度、计时器、快捷键提示）；单屏时 3 秒倒计时确认后本屏放映；放映屏被拔自动结束并提示
- **渲染**：LibreOffice 无头转换 PDF → pypdfium2 渲染（256px 浏览 / 1920px 放映），双级缓存，磁盘缓存上限可配置

## 支持格式

`.ppt .pptx .pps .ppsx .pot .potx .odp`

## 安装

从 [Releases](https://github.com/iYaoyaoo/hymn-slides/releases) 下载对应平台产物（附 SHA256SUMS.txt）：

| 产物 | 说明 |
|---|---|
| windows-lite.zip | 约 40MB，需系统已装 [LibreOffice](https://www.libreoffice.org/) |
| windows-full.zip | 内置便携 LibreOffice，开箱即用（下载约 400MB，解压约 1.2GB） |
| mac-arm64-full.zip | Apple Silicon（M1 及之后） |
| mac-intel-full.zip | Intel Mac（也可经 Rosetta 在 Apple Silicon 运行，但建议只装 Intel 机器） |

- **Windows**：解压后运行 `HymnSlides\HymnSlides.exe`
- **macOS**：**包未签名/未公证，首次打开需右键点按 → 打开**

## 快捷键

| 键 | 功能 |
|---|---|
| Enter / 双击 | 预览 |
| Ctrl+F（Cmd+F） | 搜索 |
| F5 | 放映 |
| ←→/Space/PgUp/PgDn | 翻页 |
| Esc | 退出放映/预览 |
| F11 | 全屏预览 |

## LibreOffice 说明

渲染管线完全基于 LibreOffice（免费开源，不依赖 MS Office/WPS/COM）：

- **Full 版**内置便携 LibreOffice，开箱即用
- **Lite 版**按顺序自动探测：①设置中手动指定的 soffice 路径 ②程序目录捆绑的 `libreoffice/` ③系统安装的 LibreOffice
- 探测失败时启动会弹出安装引导；soffice 转换使用独立临时 profile，不与用户打开的 LibreOffice 冲突

## 已知限制

1. 静态渲染：动画/切换/嵌入音视频不保留（本项目目标素材已确认全部为静态文字+图片；如放入含动画文件，放映为静态近似效果）
2. macOS 包未签名/未公证：首次打开需右键→打开
3. Full 版下载约 400MB / 解压约 1.2GB；Lite 版约 40MB
4. 旧格式 `.ppt` 转换后个别版式可能与 PowerPoint 有细微差异，取决于 LibreOffice 对旧格式的支持度
5. v1 不做 LibreOffice 裁剪（体积优化留 v1.1）
6. Intel mac 属上游夕阳平台：Qt/PySide6 与 LibreOffice 当前仍提供 Intel 构建但终将停发，届时 Intel 包将停留在最后可用版本（依赖版本已锁定），属预期行为而非缺陷
7. mac-intel 包在 Apple Silicon 机器上可经 Rosetta 运行，但性能与耗电不如原生；arm64 包不可在 Intel 机器运行

## 开发

```bash
python3 -m pip install -r requirements.txt
python3 tools/make_samples.py --with-legacy   # 生成测试素材
python3 -m pytest tests/                      # 全量测试
python3 main.py --selftest                    # 环境自检
python3 main.py --scan                        # 扫描索引统计
python3 main.py --render-test samples          # 渲染管线验收
python3 main.py --list-screens                 # 显示器枚举
python3 tools/build.py --variant full --arch x86_64  # 本机构建（mac）
```

技术栈：Python 3.11+ / PySide6 / LibreOffice 无头 / pypdfium2 / SQLite / PyInstaller。
设计文档见 `docs/`（PRD、PLAN、PROGRESS、schema、发布说明）。
