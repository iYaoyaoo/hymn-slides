"""设置对话框：主目录 / soffice 路径 / 缓存上限 / 单屏放映确认开关（规范 §3-6、F1）。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("设置")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.main_dir_edit = QLineEdit(str(config.main_dir))
        browse_main = QPushButton("浏览…")
        browse_main.clicked.connect(self._browse_main_dir)
        row_main = QHBoxLayout()
        row_main.addWidget(self.main_dir_edit)
        row_main.addWidget(browse_main)
        form.addRow("主目录：", row_main)

        self.soffice_edit = QLineEdit(config.soffice_path)
        self.soffice_edit.setPlaceholderText("留空=自动探测（捆绑目录→系统安装）")
        browse_lo = QPushButton("浏览…")
        browse_lo.clicked.connect(self._browse_soffice)
        row_lo = QHBoxLayout()
        row_lo.addWidget(self.soffice_edit)
        row_lo.addWidget(browse_lo)
        form.addRow("LibreOffice soffice 路径：", row_lo)

        self.cache_spin = QSpinBox()
        self.cache_spin.setRange(64, 1024 * 1024)
        self.cache_spin.setSuffix(" MB")
        self.cache_spin.setValue(config.cache_limit_mb)
        form.addRow("缓存上限：", self.cache_spin)

        self.confirm_box = QCheckBox("单屏放映前显示 3 秒倒计时确认")
        self.confirm_box.setChecked(config.single_screen_confirm)
        form.addRow("", self.confirm_box)

        layout.addLayout(form)

        note = QLabel("便携模式：程序目录放置 portable.flag 后，配置/缓存/日志全部保存到程序目录 data/ 下。")
        note.setWordWrap(True)
        layout.addWidget(note)

        btns = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(self._save)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def _browse_main_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择主目录", self.main_dir_edit.text())
        if d:
            self.main_dir_edit.setText(d)

    def _browse_soffice(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        f, _ = QFileDialog.getOpenFileName(self, "选择 soffice 可执行文件", self.soffice_edit.text())
        if f:
            self.soffice_edit.setText(f)

    def _save(self) -> None:
        main_dir = Path(self.main_dir_edit.text().strip()).expanduser()
        if not main_dir.is_dir():
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "设置", "主目录不存在，请重新选择。")
            return
        old_main = self.config.main_dir
        self.config.set_main_dir(main_dir)
        self.config.set_soffice_path(self.soffice_edit.text().strip())
        self.config.set_cache_limit_mb(self.cache_spin.value())
        self.config.set_single_screen_confirm(self.confirm_box.isChecked())
        self.config.sync()
        self._main_dir_changed = old_main != main_dir
        self.accept()

    @property
    def main_dir_changed(self) -> bool:
        return getattr(self, "_main_dir_changed", False)
