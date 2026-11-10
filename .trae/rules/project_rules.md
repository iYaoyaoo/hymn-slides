# 项目规范 v4.0（v2 变更单后）：诗歌投影（HymnSlides）— Windows/macOS 教会诗歌 PPT 放映管理器

> v4.0 变更（用户 v2 变更单，2026-11-10）：①放映/渲染引擎改为三级回退链 PowerPoint→WPS→LibreOffice（仅系统安装，不再内置捆绑 LibreOffice）；②产物瘦身为 3 份 zip；③UI 重构为"上方大搜索区+下方全高树视图"，移除中间内容区与预览功能；④新增树右键菜单（在文件管理器中显示）与双击放映；⑤修复扫描大目录卡死（WAL）与双屏放映落主屏问题。旧 v3.3 的"禁止 COM/MS Office/WPS"条款废止。

## 1. 角色与工作方式
你是本项目唯一开发工程师，全程负责：规划→开发→测试→调试→打包→CI 发布。
- 注释与文档用简体中文，标识符用英文。
- 开工前建立 docs/PLAN.md 与 docs/PROGRESS.md，全程更新。
- 核心逻辑必须有 pytest 单元测试；所有核心能力必须提供 CLI 验证入口（--scan、--render-test、--list-screens、--selftest），GUI 无法由你点击验证。
- 开发机事实约束：本开发机为 Intel macOS（x86_64），装有 LibreOffice（无 PowerPoint/WPS——COM/WPS 引擎无法本地实测，靠接口抽象+单元测试替身+人工验收清单）。项目内所有 Python 调用一律使用 python3 命令（禁用 python 裸命令）；本机可原生构建并直接验收 mac-intel 产物；windows 与 mac-arm64 产物由 CI 构建。
- 开发机显示器事实：本机第二屏为 iPad（经 Sidecar 扩展接入，对系统与程序而言是一块普通外接显示器，非镜像）；断开 Sidecar 即变为单屏，用于拔屏与单屏路径测试。显示器实现不得对屏幕身份做任何特殊假设（不得硬编码屏幕名/序号）。
- 目标平台：Windows 10/11 x64、macOS 12+（arm64 与 Intel x64 均为必做）。Intel 产物优先由 CI 的 Rosetta 路径构建，本机原生构建作为验收对照与 Plan B。所有路径用 pathlib；所有外部子进程用参数列表调用（禁 shell 拼接），确保中文/空格文件名两平台可用。
- 素材事实约束：全部 PPT 均为静态内容（文字+图片），无动画/音视频——渲染管线无需考虑动态内容保真。

## 2. 技术栈（v4 锁定）
- Python 3.11+；GUI：PySide6（启用 Qt 高 DPI 缩放）
- **放映/渲染引擎三级回退（全管线：放映、页面图片、全文文字）**：
  1. **PowerPoint**（最高优先级）：Windows=COM 自动化（pywin32，放映窗定位到目标屏、导出 PNG、提取文字、页码同步）；macOS=AppleScript（放映控制；Mac 版无导出图片接口→出图/全文回落 LibreOffice）
  2. **WPS**（无 PowerPoint 时）：Windows=COM（Kwpp/wpp ProgID，接口与 PowerPoint 同构）；macOS 无自动化接口→跳过
  3. **LibreOffice**（兜底，仅系统安装）：soffice 无头 → PDF → pypdfium2（图片+文字）
- 引擎探测顺序与结果写日志；三者皆无→启动弹窗引导下载三者其一（附官网链接）
- 索引：SQLite（WAL 模式）；打包：PyInstaller；CI：GitHub Actions 三 job 矩阵
- 依赖固定版本写入 requirements.txt（pywin32 加 `sys_platform == "win32"` 标记）

## 3. 硬性约束
1. 代码中不允许 TODO/占位/伪代码，交付即可运行。
2. 耗时操作（扫描/转换/渲染）一律后台线程，禁止阻塞 UI 主线程。
3. 全程 pathlib + UTF-8。
4. 异常写 logs/app.log（RotatingFileHandler），禁止静默失败；单文件转换失败→UI"转换失败"角标，禁止崩溃。
5. 数据目录：QStandardPaths（AppLocalDataLocation / AppCacheLocation）；便携模式：程序目录存在 portable.flag 时，配置/缓存/日志全部落在程序目录 data/ 下（U 盘分发场景；macOS 上判定为 .app 同级目录存在 portable.flag）。
6. 配置用 QSettings(IniFormat)：主目录（默认=可执行文件所在目录，frozen 用 sys.executable）、放映引擎（自动/手动指定 PowerPoint/WPS/LibreOffice 路径）、缓存上限、放映确认开关。
7. 引擎探测顺序（src/render/engine_detect.py，结果写日志）：①配置手动指定 ②PowerPoint（Windows=注册表 ProgID `PowerPoint.Application`；macOS=/Applications/Microsoft PowerPoint.app）③WPS（Windows=注册表 ProgID `Kwpp.Application`/`wpp.Application`；macOS 跳过）④LibreOffice（Windows=注册表/Program Files；macOS=/Applications/LibreOffice.app）。全部失败→启动时弹窗引导下载三者其一（附官网链接）。
8. 调用 soffice 用独立临时 profile（-env:UserInstallation 指向数据目录 lo_profile/，每进程子目录），避免与用户打开的 LibreOffice 冲突。
9. 每阶段完成 git commit，格式「P{N}: 摘要」。

## 4. 支持格式
.ppt .pptx .pps .ppsx .pot .potx .odp

## 5. 功能规格（v4）
- F1 目录管理：默认主目录=可执行文件所在目录；设置对话框可切换；portable.flag 触发便携模式。
- F2 界面（v4 重构）：**上方大搜索区（主视觉居中）+ 下方全高树视图**（类 Mac 访达列表样式：目录+诗歌文件，扫描结果驱动）；树带"一键展开/全部收起"按钮；无中间内容区、无面包屑/后退前进、无预览功能（右侧面板与全屏预览均移除）；状态栏保留（文件数/扫描/放映状态）。
- F3 搜索（v4）：300ms 防抖实时搜索，范围=文件名模糊+幻灯片全文（文字由当前引擎提取）；命中→**直接过滤树**：仅显示命中文件及其祖先目录链，命中项选中并展开；清空→恢复全树。Ctrl+F/Cmd+F 聚焦。
- F4 放映：树中选中文件按 F5 **或双击**启动；文件右键菜单含"在文件管理器中显示"（Windows: explorer /select；macOS: open -R）。≥2 显示器→放映窗置于非主显示器+演示者窗置于主显示器；单屏→3 秒倒计时确认后本屏放映（可在设置关闭）。演示者窗含：当前/下一页缩略图、进度 x/y、计时器、文件名、快捷键提示；翻页同步；Esc 结束。
- F5 引擎（v4）：放映/页面图片/全文文字统一走三级链 PowerPoint→WPS→LibreOffice。PowerPoint/WPS（Windows COM）：放映窗 COM 定位到目标屏；页面图片 Slides.Export；文字遍历 TextFrame。macOS PowerPoint：AppleScript 启动/翻页/结束放映（放映可用）；出图/全文回落 LibreOffice。LibreOffice：现有 PDF 管线。放映页 1920px 宽缓存（引擎导出按此宽度）。
- F6 显示器管理：QScreen 枚举；screenAdded/screenRemoved 动态响应（放映屏被拔→自动结束并提示，原生放映引擎下轮询检测）；--list-screens CLI；仅依据"是否主显示器"与几何决策。
- F7 快捷键（v4）：Ctrl+F/Cmd+F=搜索、双击/F5=放映、←→/Space/PgUp/PgDn=翻页、Esc=退出放映/清空搜索。

## 6. 目录结构（v4）
hymn-slides/
├─ main.py                # CLI：--scan --render-test --list-screens --selftest
├─ src/
│  ├─ core/    (scanner.py indexer.py search.py models.py config.py)
│  ├─ render/  (engine_detect.py engine.py com_engine.py as_engine.py lo_detect.py converter.py pdfrender.py thumbnail.py)
│  ├─ ui/      (main_window.py hymn_tree.py settings_dialog.py)
│  ├─ show/    (display_manager.py projection_window.py presenter_window.py show_controller.py)
│  └─ utils/   (logger.py paths.py selftest.py)
├─ tools/
│  ├─ make_samples.py     # 生成测试素材（.pptx 用 python-pptx 直接生成；.ppt/.pps 由 soffice 转换 .pptx 得到）
│  └─ build.py            # PyInstaller 构建入口（--arch arm64|x86_64；单变体，无 lite/full）。mac 产物必须做架构断言：主程序与 PySide6/pypdfium2 核心二进制经 lipo -info 校验；断言失败=构建失败。
├─ .github/workflows/release.yml
├─ tests/  docs/  dist/(gitignore)  requirements.txt  README.md  .gitignore

## 7. 阶段计划与验收（v4 追加 R0-R6，原 P0-P8 已完成并记录于 PROGRESS.md）
- R0 规范与文档更新（本条完成即 commit）。
- R1 引擎层：engine_detect（探测+手动指定）、统一引擎接口（page_count/export_page/extract_texts/start_show/next/prev/exit/current_page）、COM 引擎（PowerPoint/WPS，Windows）、AppleScript 引擎（mac PowerPoint）、LO 引擎复用现有管线；SQLite WAL。验收：pytest 全绿（COM/AS 用替身单元测试；真引擎留人工）。
- R2 UI 重构：上方搜索区+全高树（过滤/展开收起/右键菜单/双击放映）；移除 finder_view/search_bar/preview_panel/sidebar。验收：pytest 全绿 + GUI 启动稳定（留人工）。
- R3 放映整合：ShowController 双路径（原生引擎放映 vs LO 投影窗）；演示者窗页码轮询同步；双屏布局加固（修复"放映落主屏"）。验收：状态机 pytest + 本机 LO 路径实测。
- R4 构建与 CI：build.py 单变体、产物 windows.zip/mac-arm64.zip/mac-intel.zip、release.yml 去 bundle_lo、pywin32 win32 标记、删除 bundle_lo.py。验收：CI 干跑三 job 全绿。
- R5 真机验收：用户以真实素材验收（Office/WPS 机器验证 COM 路径 + 本机 LO 路径 + 双屏放映）。
- R6 打 tag v1.0.0 正式发布 + README + 交付报告。

## 8. 决策规则
- 规格未覆盖：取与规范一致的最简方案，记 PROGRESS.md，禁止自行加需求。
- 受阻超 30 分钟：换绕行方案并标注"待人工复核"，不得停滞。
- 无法本地验证的平台项（Windows COM/WPS、mac PowerPoint AS）：接口抽象+单元测试替身+CI 冒烟+人工复核清单，不算失败。
- 单个 .ppt 转换失败：日志+提示，不算阶段失败。

## 9. 已知限制（如实写入 README）
- 需要系统安装 PowerPoint / WPS / LibreOffice 之一（安装包不再内置 LibreOffice；均未安装时启动引导下载）。
- macOS 下 PowerPoint 仅支持放映控制（AppleScript），缩略图/全文/页面图片仍需 LibreOffice；WPS macOS 无自动化接口不支持。
- 放映效果与动画保真：PowerPoint/WPS 原生放映保真最高；LibreOffice 路径为静态渲染，动画/切换/嵌入音视频不保留。
- macOS 包未签名/未公证：首次打开需右键→打开。
- 产物约 40MB/份。
- 旧格式 .ppt 在 LibreOffice 路径下个别版式可能有细微差异；PowerPoint/WPS 路径无此问题。
- Intel mac 属上游夕阳平台：依赖停发后 Intel 包将停留在最后可用版本（依赖版本已锁定），属预期行为而非缺陷。
- mac-intel 包在 Apple Silicon 机器上可经 Rosetta 运行，但性能与耗电不如原生；arm64 包不可在 Intel 机器运行。
