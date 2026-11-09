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
| 文档（PRD/PLAN） | 进行中 | - |
| P0 | 未开始 | - |
| P1 | 未开始 | - |
| P2 | 未开始 | - |
| P3 | 未开始 | - |
| P4 | 未开始 | - |
| P5 | 未开始 | - |
| P6 | 未开始 | - |
| P7 | 未开始 | - |
| P8 | 未开始 | - |
