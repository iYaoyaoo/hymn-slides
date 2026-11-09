# PLAN：阶段任务分解与验收标准（P0–P8）

依据：.trae/rules/project_rules.md v3.3 ｜ 全程同步更新 docs/PROGRESS.md

## 通用要求（每阶段硬性）

- pytest 全绿；验收命令真实运行并粘贴输出；更新 PROGRESS.md；git commit「P{N}: 摘要」；自动进入下一阶段。
- 代码无 TODO/占位/伪代码；耗时操作后台线程；异常写日志禁静默失败；pathlib+UTF-8；子进程参数列表调用。

## P0 骨架与环境

- 目录骨架：main.py、src/{core,render,ui,show,utils}、tools/、tests/、docs/、requirements.txt、.gitignore
- 稳定 Python：本机 python3=3.16.0a1 无 PySide6 轮子 → uv 安装 3.12 → .venv，项目内仍以 python3 调用（记录 PROGRESS.md）
- main.py：--selftest（OS/Python/LO 三候选来源探测，结果写日志）、--scan/--render-test/--list-screens 占位于 CLI 分发（实现于对应阶段）
- 空主窗口（PySide6，高 DPI）可运行
- 验收：`.venv/bin/python3 main.py --selftest` 全绿 + `python3 main.py` 无报错启动（人工/超时杀进程）

## P1 扫描/索引/搜索

- docs/schema.md（SQLite：files/slide_texts 表）
- src/core/scanner.py：递归扫描（跳过隐藏/系统目录）；indexer.py：mtime 增量索引；search.py：文件名模糊+全文搜索；models.py/config.py
- 后台线程扫描（UI 侧 P3 接入；本阶段提供可独立调用接口）
- pytest：tmp_path 夹具覆盖扫描/增量/搜索
- 验收：pytest 全绿 + `--scan` 对测试目录输出统计

## P2 渲染管线

- src/render/lo_detect.py：soffice 三级探测（配置→捆绑→系统），结果写日志
- converter.py：soffice --headless --convert-to pdf，独立 profile；超时 120s；失败重试 1 次
- pdfrender.py：pypdfium2 渲染（256px 缩略 / 1920px 放映按需）+ 文字提取（供全文索引）
- thumbnail.py + 双级缓存（缓存上限可配）
- tools/make_samples.py：生成 .pptx（python-pptx，中文文件名、3 层目录、含 50+ 页大文件）；.ppt/.pps 由 soffice 转换 .pptx 得到
- 测试素材说明：~/诗歌素材/ 不存在（P0 已探测）→ 用 make_samples.py 输出目录作为验收素材源（记录 PROGRESS.md）
- 验收：pytest 全绿 + make_samples + `--render-test` 出图

## P3 访达界面（F2/F3）

- main_window.py：工具栏（面包屑+视图切换+搜索框）、左侧 sidebar.py 目录树、finder_view.py 图标/列表视图、底部状态栏
- F1 主目录配置 + portable.flag；settings_dialog.py 骨架
- 扫描/缩略图渲染接入后台线程
- 验收：程序稳定运行，缩略图网格真实可用（GUI 留人工）

## P4 搜索与预览（F4/F5）

- search_bar.py：Ctrl/Cmd+F 聚焦、300ms 防抖、文件名+全文
- 结果面板双击定位并选中；preview_panel.py 右侧逐页缩略图（懒加载）
- 双击全屏预览：←→翻页、Esc 退出、F11 全屏预览
- 验收：同 P3（人工），搜索逻辑有 pytest

## P5 放映与多屏（单屏路径 + F7）

- show/display_manager.py：QScreen 枚举、仅按主显示器+几何决策、动态增删响应
- projection_window.py：无边框全屏、1920px 渲染页、←→/Space/PgUp/PgDn/Esc
- 单屏：3 秒倒计时确认后本屏放映；放映屏被拔→自动结束并提示
- 验收：`--list-screens` 列出本机两块屏（含 Sidecar）；单屏倒计时放映可用（人工）

## P6 演示者模式（双屏路径）

- presenter_window.py：当前/下一页缩略图、进度 x/y、计时器、文件名、快捷键提示
- show_controller.py：状态机（idle→countdown→showing→ended）；翻页同步；Esc 结束
- 验收：状态机 pytest 全绿；双屏联动留人工（iPad Sidecar 第二屏）

## P7 本地打包（Intel Mac 原生构建）

- tools/bundle_lo.py：从 tools/downloads/ 官方包提取 libreoffice/；--download 自动下载+SHA256 校验；来源常量三分（Windows msi / mac aarch64 dmg / mac x86_64 dmg）；Intel dmg 已在 downloads（LibreOffice_26.8.2_MacOS_x86-64.dmg）→ 无需下载
- tools/build.py：PyInstaller --onedir --windowed；--variant full|lite；--arch arm64|x86_64；lipo -info 架构断言（主程序+PySide6/pypdfium2 核心二进制）；full 将 libreoffice/ 复制进 .app/Contents/Resources/
- 产物：mac-intel-lite.zip 与 mac-intel-full.zip
- 验收：右键打开正常运行；--selftest 全绿（结果写日志并由 build.py 校验）

## P8 CI 与交付

- .github/workflows/release.yml：tag v* 触发 + workflow_dispatch 干跑
  - ① windows-latest：pip→pytest→bundle_lo --download→build lite+full→zip→SHA256
  - ② macos-latest(arm64)：pytest(offscreen)→bundle_lo→build --arch arm64→zip→SHA256
  - ③ macos-latest(Intel Rosetta)：install-rosetta→python.org universal2 pkg→arch -x86_64 全链→pytest(offscreen，异常可降级 --selftest 但架构断言不豁免)→build --arch x86_64→zip→SHA256
- 干跑三 job 全绿 → 下载 mac-intel-full.zip 本机右键打开跑通双屏放映（iPad Sidecar）真机验收
- Intel job 两轮修复仍失败 → Plan B：P7 本地构建产物人工上传 Release，明确记录
- 正式发布：v1.0.0 tag → 4 产物 + SHA256 → README（安装/LO 说明/已知限制/快捷键）→ 全量 pytest → 交付报告（产物清单与链接、测试结果、已知限制、人工验收清单）
