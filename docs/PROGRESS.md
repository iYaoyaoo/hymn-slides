# PROGRESS 进度记录

## 环境探测结论（P0 前置）

- OS：macOS（Intel x86_64），Python：/usr/local/bin/python3 = 3.16.0a1（universal2 pkg，platform.machine()=x86_64）
- ⚠️ 差异 1：python3 为 3.16.0a1（alpha），PySide6 无 cp316 轮子（pip 报 No matching distribution found）。
  决策（最简方案）：安装 uv → uv python install 3.12 → 项目 .venv（stable），项目内所有调用仍以 python3 命令执行（venv 激活后 python3 即 3.12）。CI 端不受影响（setup-python 用稳定版）。
- LibreOffice：/Applications/LibreOffice.app 存在（soffice 位于 Contents/MacOS/soffice）✓
- ⚠️ 差异 2：~/诗歌素材/ 不存在（已用 ls/find 核实）。
  决策（最简方案）：按规范以 tools/make_samples.py 生成测试素材（.pptx 直生 + .ppt/.pps 由 soffice 转换，中文文件名、3 层目录、含 50+ 页大文件），作为 --scan/--render-test 验收素材源。
- 显示器：2 块（内置 2880x1800 主屏 + Sidecar iPad 扩展屏 2650x1784，非镜像）✓
- git remote：https://github.com/iYaoyaoo/hymn-slides.git，main 分支 ✓
- tools/downloads/ 已有 LibreOffice_26.8.2_MacOS_x86-64.dmg（Intel dmg 提前就位）✓

## 阶段进度

| 阶段 | 状态 | 完成时间 |
|---|---|---|
| 文档（PRD/PLAN） | 完成 | 2026-11-09 |
| P0 | 完成 | 2026-11-09 |
| P1 | 完成 | 2026-11-09 |
| P2 | 完成 | 2026-11-09 |
| P3 | 完成 | 2026-11-09 |
| P4 | 完成 | 2026-11-09 |
| P5 | 完成 | 2026-11-09 |
| P6 | 完成 | 2026-11-09 |
| P7 | 未开始 | - |
| P8 | 未开始 | - |

## P0 验收记录（2026-11-09）

- 稳定 Python：uv 安装 cpython-3.12.16 (x86_64) → .venv；依赖：PySide6 6.12.0 / pypdfium2 5.15.1 / pytest 9.2.0 / python-pptx 1.0.2 / pyinstaller 6.22.3（已固定于 requirements.txt）
- pytest：`13 passed in 0.18s`
- `python3 main.py --selftest` → `SELFTEST RESULT: PASS`（OS: Darwin 24.6.0 x86_64；Python 3.12.16；LibreOffice 系统安装命中 /Applications/LibreOffice.app/Contents/MacOS/soffice，来源=system）
- `python3 main.py`（GUI）后台运行 5 秒无崩溃（空主窗口正常启动）
- 决策记录：selftest 模块放 src/utils/selftest.py（规范目录结构未指定位置，取最简方案）
- 修复记录：GUI 启动改为先建 QApplication 再初始化日志（避免 QCoreApplication 单例冲突）

## P1 验收记录（2026-11-09）

- docs/schema.md 先行入库；模块：models.py（SUPPORTED_EXTS/SlideFile/ScanStats/SearchResult）、scanner.py（递归+隐藏/系统目录跳过+Office 临时文件跳过）、indexer.py（SQLite，mtime+size 增量，删除级联清 slide_texts）、search.py（LIKE 转义+片段【】高亮+文件名优先去重）
- pytest：`27 passed in 0.38s`（含扫描/增量/级联删除/中文搜索/CLI 端到端）
- `python3 main.py --scan /tmp/scan_demo` → `文件总数: 2（新增 2 / 更新 0 / 跳过 0 / 删除 2），耗时 0.00s` exit=0（"删除 2"为清理此前 CLI 测试残留行，符合增量预期）
- 决策记录：全文搜索 v1 用 LIKE（素材规模小，不引入 FTS5）；--scan 支持可选 PATH 参数（验收需要指定目录，主目录默认值不变）
- 修复记录：QStandardPaths 枚举为 CacheLocation（非 AppCacheLocation）

## P2 验收记录（2026-11-09）

- 模块：converter.py（无头转换，独立 profile，120s 超时+重试 1 次）、pdfrender.py（pypdfium2 渲染 256/1920px+逐页文字提取）、thumbnail.py（RenderCache：pdf/img256/img1920 三级目录，key=sha1(路径+mtime)，超限最旧淘汰）
- 决策记录：渲染出图引入 Pillow 13.0.0（pypdfium2 to_pil 配套，最简方案，已固定版本）；测试夹具 PDF（tests/fixtures/样本.pdf，LO 生成 38KB）入库，使无 LO 的 CI 也能跑渲染/提取测试；真实转换类测试无 LO 环境自动 skip（CI Windows/macOS pytest 阶段无 LO，非失败）
- make_samples：`python3 tools/make_samples.py --with-legacy` → 8 个文件（5 .pptx + .ppt/.pps 3 个，3 层中文目录，52 页大文件）
- pytest：`41 passed in 16.63s`
- `python3 main.py --render-test samples` → 3/3 成功：诗歌敬拜.pps 2页 PDF 32KB｜缩略图 5KB｜放映页 41KB；诗歌敬拜.pptx 2页；诗歌合集.pptx 52页 PDF 112KB｜放映页 65KB（exit=0）
- 修复记录：pypdfium2 页码越界抛 PdfiumError（非 IndexError），测试按实际异常断言

## P3 验收记录（2026-11-09）

- 模块：main_window.py（工具栏/导航历史/状态栏/worker 接线）、finder_view.py（图标/列表双视图、面包屑、转换失败角标）、sidebar.py（QFileSystemModel 目录树，隐藏目录过滤）、settings_dialog.py（主目录/soffice/缓存上限/单屏确认）、workers.py（ScanWorker/ThumbWorker 后台线程，规范结构未列此文件，记录决策）
- pytest：`51 passed in 29.63s`（离屏 GUI 测试 + 导航历史 + 状态栏统计 + 设置写入 + 扫描线程）
- GUI 实测：主目录指向 samples 启动，10 秒无崩溃；日志确认扫描 8 文件、soffice 探测命中、缩略图缓存生成 8 张 PNG / 5 份 PDF；无 ERROR（3 条 ERROR 为 pytest 错误路径用例）
- 启动时 LO 缺失弹窗引导安装（离屏环境仅记日志不弹模态框，防 CI 卡死）
- 修复记录：① QFileSystemModel 位于 QtWidgets 而非 QtCore；② QDir.entryInfoList 用 setSorting 而非位置参数；③ **conftest 必须在任何测试前创建 QApplication**——否则 paths._ensure_core_app 先建 QCoreApplication 单例，后续无法升级（qFatal abort）
- 留人工：目录树点击、图标/列表切换、设置对话框交互、转换失败角标显示（GUI 操作项）

## P4 验收记录（2026-11-09）

- 模块：search_bar.py（SearchBar 300ms 防抖 + SearchResultsPanel 双击定位）、preview_panel.py（PreviewPanel 右侧懒加载 ±5 页窗口 / FullscreenPreview ←→/Space/PgUp/PgDn 翻页、Esc 退出）
- MainWindow 接线：Ctrl/Cmd+F 聚焦搜索（QKeySequence.Find）、F11 全屏预览、Enter/双击=预览、选中变化→右侧预览；内容区 splitter 三栏（目录树｜内容+结果面板｜预览）
- ScanWorker 扩展：扫描后对 page_count 为 NULL 的文件做全文回填（转换+提取+入库），带 progress 信号（状态栏"索引中 x/y"）；converter 增加进程级转换锁（soffice 同 profile 禁并发）
- pytest：`59 passed in 47.29s`（防抖/结果面板/全文搜索/定位选中/懒加载/全屏翻页键盘事件）
- GUI 实测：启动 18 秒无崩溃，日志确认全文回填转换链路正常（诗歌敬拜.pps 4.9s、诗歌合集.pptx 5.8s）
- 修复记录：CLI --scan/--render-test 改用绝对路径（相对路径导致缓存 key 与 GUI 不一致、重复转换）
- 留人工：Ctrl+F 实际键感、预览面板滚动懒加载、全屏预览画面质量（GUI 操作项）

## P5 验收记录（2026-11-09）

- 模块：display_manager.py（QScreen 枚举/screenAdded/screenRemoved 动态响应/decide_* 纯几何决策——主显示器优先、非主取面积最大、无任何身份假设）、projection_window.py（无边框全屏、1920px 页、←→/Space/PgUp/PgDn/Esc）、show_controller.py（idle→countdown→showing→ended 状态机 + 3 秒倒计时确认层 + 拔屏自动结束提示）
- MainWindow：F5 快捷键 → start_show（无选中给状态栏提示）
- pytest：`75 passed in 56.03s`（决策纯函数/枚举/CLI/翻页键盘/倒计时归零与点击取消/状态机流转/F5 接线）
- `python3 main.py --list-screens` → `检测到 2 块显示器：屏幕 1: Built-in Retina Display 1680x1050 @(0,0)（主显示器）；屏幕 2: 随航显示器 1325x892 @(1680,158)` exit=0（Sidecar 扩展屏正确识别）✓
- 修复记录：--list-screens 需先于日志初始化创建 QApplication（QCoreApplication 单例不可升级）；P0 旧"未实现"CLI 断言改为全实现断言
- 留人工：真实屏幕上的倒计时放映观感、Esc 结束、断开 Sidecar 后的拔屏提示（P6 双屏联测时一并人工验证；本机 2 屏常驻，单屏路径需拔 Sidecar 后测试）

## P6 验收记录（2026-11-09）

- 模块：presenter_window.py（当前/下一页 256px 缩略、进度 x/y、elapsed 计时器 mm:ss、文件名、快捷键提示、上一页/下一页/结束按钮 + 键盘）；show_controller.py 扩展双屏编排（≥2 屏且 dual_allowed → decide_dual_layout：放映窗=非主屏，演示者窗=主屏；翻页同步 projection.page_changed→presenter.on_page_changed；presenter next/prev/end → projection.next_page/prev_page/end_show；结束后关两窗）
- MainWindow.start_show 改为 dual_allowed=True（≥2 屏走双屏路径）
- 状态机单元测试：idle→showing→ended（双屏全流程含翻页同步/演示者导航请求）、单屏 COUNTDOWN→SHOWING→ENDED、关闭确认跳过倒计时、双屏无重复窗口
- pytest：`81 passed in 55.26s`（新增 6 测试）
- 决策记录：setScreen 加 QScreen isinstance 守卫（替身屏测试下仅按几何定位，不假设身份）
- 留人工：双屏联动真机验收（iPad Sidecar 第二屏放映、主屏演示者窗、翻页同步、Esc 结束、拔 Sidecar 自动结束+提示）——并入 P8 真机验收清单
