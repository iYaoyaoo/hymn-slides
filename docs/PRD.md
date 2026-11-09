# PRD：诗歌投影（HymnSlides）

版本：v1.0 ｜ 依据：.trae/rules/project_rules.md v3.3（唯一权威规范）

## 1. 产品定位

面向教会场景的诗歌 PPT 放映管理器：以"访达式"文件管理界面组织诗歌 PPT，
一键在第二显示器上全屏放映，主显示器同步显示演示者控制窗。
支持 Windows 10/11 x64 与 macOS 12+（arm64 / Intel x64 均为必做；Linux 不做）。

- 素材事实：全部 PPT 为静态内容（文字+图片），无动画/音视频。
- 用户画像：教会放映同工，非技术背景，需"双击即可放映"的极简操作。

## 2. 支持格式

`.ppt .pptx .pps .ppsx .pot .potx .odp`

## 3. 功能需求（F1–F8）

| 编号 | 功能 | 要点 |
|---|---|---|
| F1 | 目录管理 | 默认主目录=可执行文件所在目录；设置对话框切换；portable.flag 触发便携模式（数据全部落程序目录 data/；macOS 判定为 .app 同级目录存在 portable.flag） |
| F2 | 文件夹穿透 | 递归扫描（跳过隐藏/系统目录）；目录树+内容区+面包屑+后退/前进 |
| F3 | 访达风格 UI | 工具栏（面包屑+视图切换+搜索框）、左侧目录树、图标视图（缩略图网格）/列表视图、底部状态栏（文件数/扫描状态） |
| F4 | 搜索定位 | Ctrl+F（macOS: Cmd+F）聚焦；300ms 防抖实时搜索；范围=文件名模糊+幻灯片全文（pypdfium2 提取）；结果面板双击定位并选中 |
| F5 | 预览 | 选中→右侧预览面板逐页缩略图（懒加载）；双击→全屏预览（←→翻页，Esc 退出） |
| F6 | 放映 | F5 启动。≥2 显示器→放映窗置于非主显示器+演示者窗置于主显示器；单屏→3 秒倒计时确认后本屏放映。放映页按 1920px 宽渲染并缓存。演示者窗：当前/下一页缩略图、进度 x/y、计时器、文件名、快捷键提示。翻页同步；Esc 结束 |
| F7 | 显示器管理 | QScreen 枚举；screenAdded/screenRemoved 动态响应（放映屏被拔→自动结束并提示）；--list-screens CLI；仅依据"是否主显示器"与几何位置决策，禁止对屏幕身份做任何假设 |
| F8 | 快捷键 | Enter=预览、Ctrl/Cmd+F=搜索、F5=放映、←→/Space/PgUp/PgDn=翻页、Esc=退出、F11=全屏预览；"在文件管理器中显示"平台分支（Windows: explorer /select；macOS: open -R） |

## 4. 技术方案（锁定）

- Python 3.11+；GUI：PySide6（启用 Qt 高 DPI 缩放）
- 渲染：LibreOffice 无头（`soffice --headless --convert-to pdf`）→ pypdfium2（PDF→页面图片+文字提取）
- 索引：SQLite；打包：PyInstaller；CI：GitHub Actions 三 job 矩阵
- LibreOffice 交付：便携捆绑（Full 版开箱即用）+ 系统安装回退（Lite 版）；禁 COM / MS Office / WPS
- 配置：QSettings(IniFormat)；数据目录：QStandardPaths（AppLocalDataLocation / AppCacheLocation）
- soffice 探测顺序：①配置手动指定 ②捆绑目录 ③系统安装；全部失败→启动提示引导安装
- soffice 调用使用独立临时 profile（`-env:UserInstallation` 指向数据目录 lo_profile/）
- 耗时操作（扫描/转换/渲染）一律后台线程；异常写 logs/app.log（RotatingFileHandler），禁静默失败
- 全程 pathlib + UTF-8；子进程用参数列表调用（禁 shell 拼接）
- 便携模式：程序目录存在 portable.flag → 配置/缓存/日志全部落程序目录 data/

## 5. CLI 验证入口（GUI 无法自动化验证，核心能力必须有 CLI）

`--scan`、`--render-test`、`--list-screens`、`--selftest`

## 6. 交付物

4 份 Release 产物 + SHA256：`windows-lite.zip`、`windows-full.zip`、`mac-arm64-full.zip`、`mac-intel-full.zip`

构建分工：
- windows / mac-arm64：CI 构建
- mac-intel：CI Rosetta 路径为主，本机（Intel Mac）原生构建作为验收对照与 Plan B

## 7. 已知限制（README 如实说明）

1. 静态渲染：动画/切换/嵌入音视频不保留（素材已确认全部静态，无实际影响）。
2. macOS 包未签名/未公证：首次打开需右键→打开。
3. Full 版约 400MB 下载 / 1.2GB 解压；Lite 版约 40MB，需系统已装 LibreOffice 或联网下载。
4. 旧格式 .ppt 个别版式与 PowerPoint 可能有细微差异。
5. v1 不做 LibreOffice 裁剪（留 v1.1）。
6. Intel mac 为上游夕阳平台，依赖停发后 Intel 包将停留在最后可用版本，属预期行为。
7. mac-intel 包可经 Rosetta 在 Apple Silicon 运行，但建议只装 Intel 机器；arm64 包不可在 Intel 机器运行。

## 8. 非目标（v1 不做）

- 动画/音视频保真、跨平台 Linux、歌词投屏、远程控制、云同步、自动更新、多语言 UI（简体中文为准）。
