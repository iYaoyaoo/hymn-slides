"""主窗口：P0 为空骨架，后续阶段逐步装配目录树/内容区/预览/放映。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("诗歌投影 HymnSlides")
        self.resize(1280, 800)
        # 空窗口：P3 起装配访达风格界面
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
