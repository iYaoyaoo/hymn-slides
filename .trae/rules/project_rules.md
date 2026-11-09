# 项目规范 v3.3（最终定稿）：诗歌投影（HymnSlides）— Windows/macOS 教会诗歌 PPT 放映管理器

## 1. 角色与工作方式
你是本项目唯一开发工程师，全程负责：规划→开发→测试→调试→打包→CI 发布。
- 注释与文档用简体中文，标识符用英文。
- 开工前建立 docs/PLAN.md 与 docs/PROGRESS.md，全程更新。
- 核心逻辑必须有 pytest 单元测试；所有核心能力必须提供 CLI 验证入口（--scan、--render-test、--list-screens、--selftest），GUI 无法由你点击验证。
- 开发机事实约束：本开发机为 Intel macOS（x86_64）。项目内所有 Python 调用一律使用 python3 命令（禁用 python 裸命令）；本机可原生构建并直接验收 mac-intel 产物；windows 与 mac-arm64 产物由 CI 构建。
- 开发机显示器事实：本机第二屏为 iPad（经 Sidecar 扩展接入，对系统与程序而言是一块普通外接显示器，非镜像）；断开 Sidecar 即变为单屏，用于拔屏与单屏路径测试。显示器实现不得对屏幕身份做任何特殊假设（不得硬编码屏幕名/序号）。
- 目标平台：Windows 10/11 x64、macOS 12+（arm64 与 Intel x64 均为必做）。Intel 产物优先由 CI 的 Rosetta 路径构建（详见 P8），本机原生构建作为验收对照与 Plan B。禁止使用平台专属 API；所有路径用 pathlib；所有外部子进程用参数列表调用（禁 shell 拼接），确保中文/空格文件名两平台可用。
- 素材事实约束：全部 PPT 均为静态内容（文字+图片），无动画/音视频——渲染管线无需考虑动态内容保真。

## 2. 技术栈（锁定，禁止更换）
- Python 3.11+；GUI：PySide6（启用 Qt 高 DPI 缩放）
- 渲染管线：LibreOffice 无头（soffice --headless --convert-to pdf）→ pypdfium2（PDF→页面图片+文字提取）
- 索引：SQLite；打包：PyInstaller；CI：GitHub Actions 三 job 矩阵
- LibreOffice 交付策略：便携捆绑优先（发布包内 libreoffice/ 目录）+ 系统安装回退；禁止 COM / MS Office / WPS 依赖
- 依赖固定版本写入 requirements.txt

## 3. 硬性约束
1. 代码中不允许 TODO/占位/伪代码，交付即可运行。
2. 耗时操作（扫描/转换/渲染）一律后台线程，禁止阻塞 UI 主线程。
3. 全程 pathlib + UTF-8。
4. 异常写 logs/app.log（RotatingFileHandler），禁止静默失败；单文件转换失败→UI"转换失败"角标，禁止崩溃。
5. 数据目录：QStandardPaths（AppLocalDataLocation / AppCacheLocation）；便携模式：程序目录存在 portable.flag 时，配置/缓存/日志全部落在程序目录 data/ 下（U 盘分发场景；macOS 上判定为 .app 同级目录存在 portable.flag）。
6. 配置用 QSettings(IniFormat)：主目录（默认=可执行文件所在目录，frozen 用 sys.executable）、soffice 路径、缓存上限、放映确认开关。
7. soffice 探测顺序（src/render/lo_detect.py，结果写日志）：①配置手动指定 ②捆绑目录：Windows=<exe目录>\libreoffice\program\soffice.exe；macOS=<.app>/Contents/Resources/libreoffice/LibreOffice.app/Contents/MacOS/soffice ③系统安装：Windows=注册表/Program Files\LibreOffice；macOS=/Applications/LibreOffice.app。全部失败→启动时清晰提示引导安装。
8. 调用 soffice 用独立临时 profile（-env:UserInstallation 指向数据目录 lo_profile/），避免与用户打开的 LibreOffice 冲突。
9. 每阶段完成 git commit，格式「P{N}: 摘要」。

## 4. 支持格式
.ppt .pptx .pps .ppsx .pot .potx .odp

## 5. 功能规格
- F1 目录管理：默认主目录=可执行文件所在目录；设置对话框可切换；portable.flag 触发便携模式。
- F2 文件夹穿透：递归扫描（跳过隐藏/系统目录）；目录树+内容区+面包屑+后退/前进。
- F3 Mac 访达风格：工具栏（面包屑+视图切换+搜索框）、左侧目录树、图标视图（缩略图网格）/列表视图、底部状态栏（文件数/扫描状态）。
- F4 搜索定位：Ctrl+F（macOS 兼容 Cmd+F）聚焦；300ms 防抖实时搜索；范围=文件名模糊+幻灯片全文（文字取自 PDF，pypdfium2 提取）；结果面板双击定位并选中。
- F5 预览：选中→右侧预览面板逐页缩略图（懒加载）；双击→全屏预览（←→翻页，Esc 退出）。
- F6 放映：F5 键/按钮启动。≥2 显示器→无边框全屏放映窗置于非主显示器+演示者窗置于主显示器；单屏→3 秒倒计时确认后本屏放映。放映页按 1920px 宽渲染并缓存。演示者窗含：当前/下一页缩略图、进度 x/y、计时器、文件名、快捷键提示。翻页同步；Esc 结束。
- F7 显示器管理：QScreen 枚举；screenAdded/screenRemoved 动态响应（放映屏被拔→自动结束并提示）；--list-screens CLI；禁止对屏幕身份（名称/序号/型号）做任何特殊假设，仅依据"是否主显示器"与几何位置决策。
- F8 快捷键：Enter=预览、Ctrl+F/Cmd+F=搜索、F5=放映、←→/Space/PgUp/PgDn=翻页、Esc=退出、F11=全屏预览；"在文件管理器中显示"=平台分支（Windows: explorer /select；macOS: open -R）。

## 6. 目录结构（必须遵守）
hymn-slides/
├─ main.py                # CLI：--scan --render-test --list-screens --selftest
├─ src/
│  ├─ core/    (scanner.py indexer.py search.py models.py config.py)
│  ├─ render/  (lo_detect.py converter.py pdfrender.py thumbnail.py)
│  ├─ ui/      (main_window.py finder_view.py sidebar.py search_bar.py preview_panel.py settings_dialog.py)
│  ├─ show/    (display_manager.py projection_window.py presenter_window.py show_controller.py)
│  └─ utils/   (logger.py paths.py)
├─ tools/
│  ├─ make_samples.py     # 生成测试素材（.pptx 用 python-pptx 直接生成；.ppt/.pps 由 soffice 转换 .pptx 得到）
│  ├─ bundle_lo.py        # 从 tools/downloads/ 官方包提取便携 libreoffice/，或 --download 自动下载并 SHA256 校验。来源常量分三份：Windows x64 msi、macOS aarch64 dmg、macOS x86_64 dmg（hdiutil 挂载提取 LibreOffice.app）；若上游已停发 Intel dmg，则固定使用最后一个提供 Intel 构建的版本并在 README 标注；版本常量首次固化后不变
│  └─ build.py            # PyInstaller 构建入口（--variant full|lite；接受 --arch arm64|x86_64）。mac 产物必须做架构断言：主程序与 PySide6/pypdfium2 核心二进制经 lipo -info 校验，须含 x86_64 或 arm64（按 --arch），禁止与目标不符；断言失败=构建失败。full 时将 libreoffice/ 复制进发布目录，macOS 复制进 .app/Contents/Resources/
├─ .github/workflows/release.yml
├─ tests/  docs/  dist/(gitignore)  requirements.txt  README.md  .gitignore

## 7. 阶段计划与验收
- P0 骨架与环境：双平台环境探测（OS/Python/LO 三候选来源，--selftest 报告）、目录骨架、git init、空主窗口。验收：python3 main.py 无报错运行。
- P1 扫描/索引/搜索：schema 先入 docs/schema.md；递归+mtime 增量索引；文件名+全文搜索；pytest 用 tmp_path 夹具。验收：pytest 全绿 + --scan 统计输出。
- P2 渲染管线：converter（超时 120s、失败重试 1 次）、pypdfium2 渲染+文字提取、双级缓存（256px 浏览 / 1920px 放映按需）。验收：pytest 全绿 + make_samples + --render-test 对素材出图。
- P3 访达界面：F2/F3，缩略图网格真实可用。验收：程序稳定运行（GUI 留人工）。
- P4 搜索与预览：F4/F5。验收：同上。
- P5 放映与多屏：F6 单屏路径 + F7。验收：--list-screens 正确（应能列出本机两块屏，含 Sidecar 扩展屏）、单屏倒计时放映可用。
- P6 演示者模式：F6 双屏路径。验收：放映/演示者状态机单元测试；双屏联动留人工。
- P7 本地打包（Intel Mac 原生构建）：PyInstaller --onedir --windowed 构建 .app（本机 Python 为 x86_64，产物即原生 x86_64）；lite 变体直接构建；full 变体需 tools/downloads/ 存在 LibreOffice 官方 macOS Intel dmg（bundle_lo.py --download 可自动获取），经 hdiutil 提取 LibreOffice.app 复制进 .app/Contents/Resources/libreoffice/；build.py 对主程序做 lipo -info 断言须含 x86_64。验收：构建产物在本机右键打开正常运行，--selftest 全绿（结果写日志并由 build.py 校验）；产物为 mac-intel-lite.zip 与 mac-intel-full.zip（full 视 dmg 而定，无则标注"由 CI 产出"并继续，不停滞）。
- P8 CI 与交付：release.yml（tag v* 触发，另含 workflow_dispatch 干跑入口）。三个必做 job，全部失败即发布失败，均不允许跳过：
  ① windows-latest（x64）：pip 安装→pytest→bundle_lo.py --download(Windows msi)→build.py 构建 lite 与 full 两变体→两份 zip→SHA256；
  ② macos-latest（arm64 原生）：pip 安装→pytest（QT_QPA_PLATFORM=offscreen）→bundle_lo.py --download(mac aarch64 dmg)→build.py --variant full --arch arm64→未签名 .app 入 zip→SHA256；
  ③ macos-latest（Intel，Rosetta 路径）：softwareupdate --install-rosetta --agree-to-license（幂等）→curl 下载 python.org universal2 安装包并 sudo installer -pkg 安装→此后所有 python/pip/pytest/PyInstaller 命令一律加 arch -x86_64 前缀（pip 解析 x86_64 轮子）→pytest（offscreen；若 Rosetta 下 offscreen 环境异常，允许按决策规则降级为 --selftest 并记录，但架构断言不可豁免）→bundle_lo.py --download(mac Intel dmg)→build.py --variant full --arch x86_64（含 lipo 架构断言）→.app 入 zip→SHA256。
  干跑三 job 全绿后：从 Actions 产物中下载 mac-intel-full.zip 至本机，右键打开跑通一次双屏放映（iPad Sidecar 作为第二屏），作为 CI Rosetta 构建产物的真机验收，与 P7 本地构建对照一致即确认通过。
  Plan B（仅当 Rosetta Intel job 经两轮修复仍失败时启用）：以 P7 本地构建的 mac-intel-full.zip 人工上传至 Release 替代 CI 产物，在 PROGRESS.md 与交付报告中明确记录"Intel 包为本地原生构建"，其余三产物仍由 CI 自动产出；此为保交付的降级路径，不算项目失败。
  Release 产物共 4 份：windows-lite.zip、windows-full.zip、mac-arm64-full.zip、mac-intel-full.zip，附各产物 SHA256。验收：先 workflow_dispatch 干跑三 job 全绿（含本机下载 Intel 包真机验收），再打 v1.0.0 tag 正式发布。最后：README（安装/LibreOffice 说明/已知限制/快捷键）、全量 pytest、git tag、输出交付报告。

## 8. 决策规则
- 规格未覆盖：取与规范一致的最简方案，记 PROGRESS.md，禁止自行加需求。
- 受阻超 30 分钟：换绕行方案并标注"待人工复核"，不得停滞。
- 无法本地验证的平台项（windows GUI / mac-arm64）：靠 CI 冒烟（offscreen 启动测试）+ 人工复核清单，不算失败。
- 单个 .ppt 转换失败：日志+角标，不算阶段失败。

## 9. 已知限制（如实写入 README）
- 静态渲染：动画/切换/嵌入音视频不保留（本项目素材已确认全部为静态文字+图片，此限制无实际影响；但 README 需如实说明，防止用户日后放入含动画文件时困惑）。
- macOS 包未签名/未公证：首次打开需右键→打开。
- Full 版体积：下载约 400MB / 解压约 1.2GB（含完整 LibreOffice）；Lite 版约 40MB，需系统已装 LibreOffice 或联网下载。
- 旧格式 .ppt 转换后个别版式可能与 PowerPoint 显示有细微差异，取决于 LibreOffice 对旧格式的支持度。
- v1 不做 LibreOffice 裁剪（体积优化留 v1.1）。
- Intel mac 属上游夕阳平台：Qt/PySide6 与 LibreOffice 当前仍提供 Intel 构建但终将停发；届时 Intel 包将停留在最后可用版本（依赖版本已按固定策略锁定），属预期行为而非缺陷。
- mac-intel 包在 Apple Silicon 机器上可经 Rosetta 运行，但性能与耗电不如原生，建议 Intel 包只装 Intel 机器；arm64 包不可在 Intel 机器运行。
