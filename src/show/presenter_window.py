"""演示者窗（F6 双屏路径，v4.2 纯文字视图）：进度 x/y、计时器、文件名、快捷键提示。

v4.2 取消预览：移除当前/下一页缩略图渲染（PageRenderWorker 的 256px 通道已删），
演示者窗不再出图，仅展示文字控制信息。
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils.logger import get_logger

logger = get_logger("presenter")

PRESENTER_WIDTH = 520
PRESENTER_HEIGHT = 380


class PresenterWindow(QWidget):
    """置于主显示器的演示者控制窗（纯文字）。"""

    next_requested = Signal()
    prev_requested = Signal()
    end_requested = Signal()

    def __init__(self, worker, ppt: Path, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._ppt = Path(ppt)
        self._page = 0
        self._total = 0
        self._started_at = time.time()

        self.setWindowTitle("演示者视图")
        self.setFixedSize(PRESENTER_WIDTH, PRESENTER_HEIGHT)

        layout = QVBoxLayout(self)

        self.file_label = QLabel(self._ppt.name)
        self.file_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

        # 当前进度（大号主视觉）
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("font-size: 64px; font-weight: bold;")
        layout.addWidget(self.progress_label, 1)

        self.timer_label = QLabel("00:00")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setStyleSheet("font-size: 24px; color: #444;")
        layout.addWidget(self.timer_label)

        # 控制按钮
        btns = QHBoxLayout()
        btn_prev = QPushButton("上一页 (←)")
        btn_prev.clicked.connect(self.prev_requested.emit)
        btn_next = QPushButton("下一页 (→)")
        btn_next.clicked.connect(self.next_requested.emit)
        btn_end = QPushButton("结束放映 (Esc)")
        btn_end.clicked.connect(self.end_requested.emit)
        btns.addWidget(btn_prev)
        btns.addWidget(btn_next)
        btns.addWidget(btn_end)
        layout.addLayout(btns)

        hint = QLabel("快捷键：←→/Space/PgUp/PgDn 翻页 · Esc 结束放映")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 计时器
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_timer)
        self._elapsed_timer.start()

        worker.count_ready.connect(self._on_count_ready)
        worker.request_count(self._ppt)

    # ---------- 屏幕 ----------

    def show_on_screen(self, screen) -> None:
        if screen is not None:
            from PySide6.QtGui import QScreen

            if isinstance(screen, QScreen):
                self.setScreen(screen)
            g = screen.geometry()
            self.move(g.x() + max(0, (g.width() - self.width()) // 2), g.y() + 20)
        self.showNormal()
        self.raise_()

    # ---------- 状态同步 ----------

    def _on_count_ready(self, ppt: str, count: int) -> None:
        if str(self._ppt) == ppt:
            self._total = count
            self._update_progress()

    def on_page_changed(self, page: int) -> None:
        """放映窗/会话翻页后同步（由 ShowController 驱动）。"""
        self._page = page
        self._update_progress()

    def _update_progress(self) -> None:
        self.progress_label.setText(f"{self._page + 1} / {self._total}")

    def _tick_timer(self) -> None:
        elapsed = int(time.time() - self._started_at)
        self.timer_label.setText(f"{elapsed // 60:02d}:{elapsed % 60:02d}")

    # ---------- 键盘（演示者窗也可翻页/结束，F8） ----------

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self.prev_requested.emit()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Space, Qt.Key.Key_PageDown):
            self.next_requested.emit()
        elif key == Qt.Key.Key_Escape:
            self.end_requested.emit()
        else:
            super().keyPressEvent(event)
