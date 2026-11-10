# 诗歌投影 HymnSlides

Windows / macOS 教会诗歌 PPT 放映管理器：大搜索框 + 全高目录树定位诗歌，F5/双击一键多屏放映（放映窗置于第二显示器、演示者窗置于主显示器）。支持 PowerPoint / WPS / LibreOffice 三级引擎回退。

## 功能

- **界面（v4）**：上方大搜索区（主视觉）+ 下方全高目录树（类访达列表：目录+诗歌文件）；树支持一键展开/收起
- **搜索**：Ctrl+F 聚焦，300ms 防抖实时搜索文件名与幻灯片全文；命中后树仅显示命中文件及其目录层级，清空恢复全树
- **放映**：双击文件或 F5 启动；双屏自动布局（放映窗→第二显示器，演示者窗→主显示器，含当前/下一页缩略、进度、计时器）；单屏 3 秒倒计时确认（可关）；放映屏被拔自动结束并提示
- **引擎三级回退（v4）**：PowerPoint → WPS → LibreOffice，应用于放映、页面图片与全文文字提取；可在设置中手动指定路径
- **文件操作**：树中文件右键"在文件管理器中显示"；便携模式（程序目录放置 `portable.flag`，数据全部落程序目录 `data/`，适合 U 盘分发）

## 支持格式

`.ppt .pptx .pps .ppsx .pot .potx .odp`

## 安装

从 [Releases](https://github.com/iYaoyaoo/hymn-slides/releases) 下载对应平台 zip（附 SHA256SUMS.txt）：

| 产物 | 平台 |
|---|---|
| windows.zip | Windows 10/11 x64 |
| mac-arm64.zip | Apple Silicon（M1 及之后） |
| mac-intel.zip | Intel Mac（可经 Rosetta 在 Apple Silicon 运行，建议只装 Intel 机器） |

- **Windows**：解压后运行 `HymnSlides\HymnSlides.exe`
- **macOS**：**包未签名/未公证，首次打开需右键点按 → 打开**

## 前置要求（重要）

本程序**不内置渲染引擎**，需要系统安装以下任一软件：

1. **Microsoft PowerPoint**（推荐，放映保真最高）
2. **WPS Office**（仅 Windows 支持自动化放映）
3. **LibreOffice**（免费开源：<https://www.libreoffice.org>）

三者均未安装时启动会弹窗引导下载。

## 快捷键

| 键 | 功能 |
|---|---|
| Ctrl+F（Cmd+F） | 聚焦搜索 |
| 双击文件 / F5 | 放映 |
| ←→/Space/PgUp/PgDn | 翻页 |
| Esc | 退出放映 / 清空搜索 |

## 已知限制

1. 需要系统安装 PowerPoint / WPS / LibreOffice 之一；均未安装时仅能浏览文件树（会弹窗引导）。
2. macOS 下 PowerPoint 仅支持放映控制（放映窗口位置由 PowerPoint 自身偏好决定）；缩略图/全文/页面图片需 LibreOffice；WPS macOS 无自动化接口不支持。
3. LibreOffice 路径为静态渲染：动画/切换/嵌入音视频不保留；PowerPoint/WPS 原生放映保真最高。
4. macOS 包未签名/未公证：首次打开需右键→打开。
5. 旧格式 `.ppt` 在 LibreOffice 路径下个别版式可能有细微差异；PowerPoint/WPS 路径无此问题。
6. Intel mac 属上游夕阳平台：依赖停发后 Intel 包将停留在最后可用版本（依赖版本已锁定），属预期行为而非缺陷。

## 开发

```bash
python3 -m pip install -r requirements.txt
python3 tools/make_samples.py --with-legacy   # 生成测试素材（需 LibreOffice）
python3 -m pytest tests/                      # 全量测试
python3 main.py --selftest                     # 环境自检（引擎三级链）
python3 main.py --scan                         # 扫描索引统计
python3 main.py --render-test samples           # 渲染管线验收
python3 main.py --list-screens                  # 显示器枚举
python3 tools/build.py --arch x86_64           # 本机构建（mac-intel）
```

技术栈：Python 3.11+ / PySide6 / PowerPoint·WPS COM（Windows，pywin32）/ PowerPoint AppleScript（macOS）/ LibreOffice 无头 → pypdfium2 / SQLite(WAL) / PyInstaller。
设计文档见 `docs/`（PRD、PLAN、PROGRESS、schema、发布说明）。
