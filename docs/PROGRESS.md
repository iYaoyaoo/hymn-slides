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
| P2 | 未开始 | - |
| P3 | 未开始 | - |
| P4 | 未开始 | - |
| P5 | 未开始 | - |
| P6 | 未开始 | - |
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
