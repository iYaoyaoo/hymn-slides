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
| P7 | 完成 | 2026-11-09 |
| P8 | 干跑全绿，未发版 | - |

## v2 变更单（2026-11-10，用户多轮确认后锁定）

- **背景**：CI 干跑三 job 全绿后，用户真机验收提出重构需求，经三轮复述确认锁定（原 v1.0.0 取消发布，本批并入新 v1.0.0）。
- **引擎链**：PowerPoint（Windows COM/mac AppleScript）→ WPS（Windows COM）→ LibreOffice（仅系统安装，兜底管线复用）；全管线（放映/页面图片/全文）统一回退；不再内置捆绑 LO（bundle_lo.py 将删除）；三者皆无→弹窗引导下载。设置界面可手动指定引擎路径（自动探测为默认）。
- **UI**：上方放大居中搜索区 + 下方全高树（访达列表样式，目录+文件，一键展开/收起）；搜索命中→过滤树为"命中文件+祖先链"；取消：中间图标/列表内容区、右侧预览面板、全屏预览、面包屑/前进后退。新增：树右键"在文件管理器中显示"、双击文件=放映（与 F5 并存）。
- **产物**：3 份 zip（windows / mac-arm64 / mac-intel，约 40MB），无 lite/full 之分；CI 不再下载/提取 LO。
- **缺陷修复**：①扫描大目录卡死（SQLite 切 WAL + 短事务）②放映落主屏（双屏布局加固+日志可诊断）。
- **执行计划**：R0 规范文档 → R1 引擎层 → R2 UI 重构 → R3 放映整合 → R4 构建/CI → R5 真机验收 → R6 tag v1.0.0 发布。
- 平台事实：开发机无 PowerPoint/WPS，COM/AppleScript 引擎靠接口抽象+替身单测+CI 冒烟+人工复核（决策规则 §8）。

## v2 变更实施记录（2026-11-10）

- **R0**：规范 v4.0（project_rules.md 全量改写）、PRD v2.0、本变更单。commit 83f6e6d。
- **R1 引擎层**（commit fe025b3）：engine_detect.py（三级链探测：注册表 ProgID/文件存在性，手动指定优先；mac WPS 跳过；mac PPT 仅放映能力）、engine.py（BaseEngine/EngineChain 能力路由：render/show 分离，mac PPT→LO 渲染回落）、com_engine.py（Windows COM：PowerPoint/WPS 同构实现，线程 CoInitialize、Slides.Export、TextFrame 遍历、SlideShowWindow 定位）、as_engine.py（mac PowerPoint AppleScript 放映控制；精确 AppleScript 语法列入人工复核）、lo_engine.py、lo_detect 去 bundled、thumbnail.py 引擎链路由改写、indexer WAL（卡死修复①）、config 新增 ppt_path/wps_path、selftest 报告引擎链、pywin32==310（win32 标记）。本机意外发现装有 PowerPoint → mac 放映引擎链=powerpoint（真实可测）。
- **R2/R3/R5 UI+放映+设置**（commit 9803aaf）：hymn_tree.py（目录树+搜索过滤命中+祖先链+一键展开/收起+右键菜单平台分支+双击放映）、main_window.py 重构（上方大搜索区主视觉+全高树+状态栏；防抖 300ms；Ctrl+F/F5/Esc 快捷键）、删除 finder_view/sidebar/search_bar/preview_panel、ShowController v4（引擎链感知：原生放映会话轮询同步 vs LO 投影窗双路径；投影窗显示后二次断言几何修复"落主屏"；单屏倒计时保留；拔屏检测两路径全覆盖）、设置对话框（引擎探测展示+三引擎手动路径+缓存+倒计时+便携说明）、删除 ThumbWorker。测试全面重写（树构建/过滤/定位/右键命令/双击/搜索树过滤/Esc 恢复/原生会话双屏全流程/演示者结束/拔屏）。77 passed。
- **R4/R6 构建与交付**（commit 281b2aa）：build.py 单变体（--arch 必选；三重 lipo 断言；产物 windows.zip/mac-arm64.zip/mac-intel.zip）、删除 bundle_lo.py、release.yml 去 LO（三 job 大幅提速）、README/RELEASE_NOTES v4（三级引擎/前置要求/快捷键/已知限制）。
- **本地验收（R6）**：pytest `77 passed`；`--selftest` PASS（渲染=libreoffice 放映=powerpoint）；`--scan samples` 8 文件（顺带清理用户 app 索引残留 2872 行）；`--render-test samples` 3/3 出图（52 页大文件放映页 65KB）；`--list-screens` 2 屏（含 Sidecar）；本地构建 mac-intel.zip（4812ac74…619a0d）三重架构断言+selftest PASS。v4 GUI 启动 10s 无崩溃。
- **v4 CI 干跑**：run 42756045267（281b2aa）进行中。
- 人工复核清单（真机，开发机无法自动化）：Windows PowerPoint/WPS COM 放映与定位、mac PowerPoint AppleScript 放映语法、双屏/单屏真实观感。

## v4.2 修复+变更（2026-11-10，用户真机闪退报告 + 指令"完全取消预览功能"）

- **闪退根因（崩溃报告分析）**：Thread 14 SIGSEGV 于 `libpdfium.dylib FPDF_LoadPage → CPDF_ColorSpace::CreateBufAndSetDefaultColor`——pdfium 内部状态**非线程安全**，v4.1 的 3 路并行全文提取（及 PageRenderWorker 缩略渲染）并发调用 pdfium 触发竞态段错误。
- **修复①（闪退）**：pdfrender.py 全部 pdfium 入口（page_count/render_page/extract_texts）经模块级 RLock 全局串行；soffice 转换（秒级大头）仍 3 路并行，回填速度不受影响。新增 4 线程并发提取测试。
- **变更②（取消预览，用户指令）**：演示者窗改纯文字视图（进度 x/y 大号主视觉、计时器、文件名、快捷键、按钮），移除当前/下一页缩略图；PageRenderWorker 删除 256px 通道（page_ready/request_page）；RenderCache 删除 thumb()/img256 管线；--render-test 改验 1920px 放映页。LO 投影窗 1920px 放映页保留（放映本体，非预览）。规范 F4 已同步。
- **附带清理**：删除 v3 遗留 dist_staging/（1.5G 捆绑 LO 解包，污染 pytest 收集），.gitignore 增补。
- **附带修复**：test_p3 并行断言竞态（瞬时替身任务可能被单工作线程吞掉，加 50ms 阻塞确定性触发多线程）。
- 验收：pytest `79 passed`；`--selftest` PASS；`--render-test samples` 3/3（放映页 1920px 出图）。

## v4.1 修复（2026-11-10，用户真机反馈：2872 文件首扫树空白+卡顿）

- **根因 1（致命，树空白）**：ScanWorker 把"元数据扫描"与"全文提取"串在一个 done 信号里——2872 文件的全文转换需数小时，期间树永远空白。
  修复：新增 `tree_ready` 信号，元数据同步完成立即发（树秒出、可搜索文件名）；全文提取降为后台任务（状态栏提示"后台建立全文索引 x/y（可正常使用）"）。
- **根因 2（慢）**：全文提取全局转换锁串行（每文件 5-15s × 2872 ≈ 数小时）。
  修复：3 路 ThreadPoolExecutor 并行 + converter 移除全局锁 + LO profile 改为**每线程**子目录（`p{pid}_{tid}`，并行无头实例互不冲突，同时天然支持用户双开）；3000 文件预计 40-80 分钟后台完成（期间应用完全可用）。
- **根因 3（脆弱）**：单文件非 RenderError 异常会中断整个回填线程 → done 永不发出。修复：逐文件兜底捕获，失败仅记日志跳过。
- **附带发现并修复（真实索引缺陷）**：`sync_scan` 会删除**不属于本次扫描根**的数据库行（此前 --scan samples 误删用户 2872 行真实索引即此因）。修复：删除与全文回填均限定扫描根（`is_relative_to`），多根历史索引互不破坏。
- 测试：新增并行/韧性/根过滤测试（替身 cache，多线程断言、失败文件 page_count 保持 NULL、外部根行不触碰）；`78 passed`。真实素材 8/8 全文提取验证 ✓。
- 本地构建 mac-intel.zip SHA256 9fa9d9d7…b63a78（三重断言+selftest PASS）；CI 干跑 run（72518b1）进行中。

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

## P7 验收记录（2026-11-09）

- tools/bundle_lo.py：来源常量三分已固化（LO_VERSION=26.8.2）：Windows x64 msi（SHA256 ff4b9114…5307a）、mac aarch64 dmg（9f24fe83…49b55）、mac x86_64 dmg（0af06277…41a7a，本机已有）；hdiutil 挂载提取 LibreOffice.app ✓（Intel 与 arm64 dmg 均实测提取成功，arm64 soffice 经 lipo 验证为 arm64）；Windows msi 走 msiexec /a 管理安装提取（CI 端执行）；--download 自动下载+SHA256 校验 ✓
- tools/build.py：PyInstaller --onedir --windowed；--variant full|lite；--arch arm64|x86_64；lipo 架构断言三重（主程序 HymnSlides + PySide6 QtCore.abi3.so + pypdfium2 libpdfium.dylib），断言失败=构建失败 ✓；full 将 libreoffice/ 复制进 .app/Contents/Resources/ ✓；构建后运行产物 --selftest 校验 PASS ✓；ditto 打包 zip + SHA256 输出 ✓
- 产物 1：mac-intel-lite.zip（SHA256 56e5174c76ad0ba3175acbaf26dc606d9a4c17461ad59eacdce4a36339dacdb2）——selftest PASS（LO 来源=system）
- 产物 2：mac-intel-full.zip（SHA256 84c0ff0f126abedbe331d3cbf35d56ce4f9d664c96a8d7ea869b426ec6a2dfa4）——selftest PASS（LO 来源=bundled：<.app>/Contents/Resources/libreoffice/LibreOffice.app/Contents/MacOS/soffice）
- 真机启动：`open dist/HymnSlides.app` 运行 8 秒无崩溃，日志确认扫描 8 文件 + 捆绑 LO 命中（本地构建无隔离属性，等效右键打开）
- 回归：pytest `81 passed`
- 决策记录：full 变体所需 Intel dmg 已在 tools/downloads/（无需 --download 即完成本机构建，符合"无则标注 CI 产出"的更强路径）；msi 与 arm64 dmg 亦提前下载完毕，SHA256 已固化（CI 下载将命中校验）
- 修复记录：PyInstaller 6.22 的 mac .app 布局中 PySide6 位于 Contents/Frameworks/PySide6/QtCore.abi3.so、pdfium 位于 Contents/Resources/pypdfium2_raw/libpdfium.dylib（非 libQtCore.dylib），断言定位已适配

## P8 干跑迭代记录（2026-11-09）

- 干跑 1（7ec7792）：windows pytest 失败——`test_selftest_passes_on_this_machine` 在无 LO 的 CI 上必然失败。修复：无 LO 环境自动 skip。
- 干跑 2（cf29657）：windows 失败于 bundle_lo 中文 print（Windows 控制台 cp1252 → UnicodeEncodeError）。修复：workflow 全局 `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`（符合"全程 UTF-8"约束）。同轮 mac-arm64 与 mac-intel Rosetta 两 job 首次全绿 ✓（Rosetta 路径：install-rosetta → python.org universal2 3.12.10 pkg → arch -x86_64 全链 → lipo 断言通过）。预防性修复：windowed exe 无控制台输出时 selftest 以退出码为准。
- 干跑 3（ce49475）：windows "构建 full" 失败——`HymnSlides.exe --selftest` 180s 超时。根因：PyInstaller `--windowed` 在 Windows 下 sys.stdout/stderr 为 None，`print(report)` 抛 AttributeError → bootloader 弹模态错误框无人点击 → 进程永不退出。修复：main 入口 `_ensure_stdio()`（devnull 兜底）+ 顶层异常写 `HymnSlides-crash.log` 后干净退出（同时提升终端用户崩溃体验）+ build.py 失败时回读崩溃日志。
- 真机观察：用户以 CI 产物（mac-intel-full.zip 解压，AppTranslocation 隔离）真机测试真实素材 `~/Downloads/诗歌投影直放版/`，与本地 pytest 并发导致 3 个测试环境性失败（非代码回归）：
  ① soffice 同一 lo_profile 被两个进程争用 → 转换 rc=1。加固：每进程独立 profile 子目录 `lo_profile/p{pid}/`（退出清理+24h 过期清理），make_samples 同步改造；
  ② SQLite `database is locked`——发现 `set_page_count` 未提交，导致 app 在转换间隙长期持有写锁（真实小 bug）。修复：set_page_count 立即 commit + 连接 timeout 5s→30s。修复后全量 82 passed（用户运行中的是旧版进程，竞态属预期，新版消除）。
- 干跑 5（cc5c262，含全部修复）进行中；干跑 4（b42f7f7，仅 stdio 修复）结果将被其取代。
- python.org universal2 固定为 3.12.10（python.org 最新 3.12.x macOS pkg；3.12.16 无 macos pkg，记录决策）。
- 干跑 4/5（b42f7f7/cc5c262）：windows 仍在"构建 full"失败，但崩溃日志（新增诊断机制）给出真相——不再挂起、bundled LO 命中、selftest 逻辑 PASS，最终死于 `print(report)` 的 UnicodeEncodeError：PyInstaller windowed 模拟流在重定向下非 None 而是真实管道流，编码=Windows ANSI 代码页（cp1252；stderr errors=replace 宽松、stdout strict），中文字符即崩。**决定性修复**：`_ensure_stdio()` 统一 `reconfigure(encoding="utf-8", errors="replace")`——该修复同时是真实中文 Windows（GBK）用户的必要修复。干跑 6（e14e9cd）验证中。
