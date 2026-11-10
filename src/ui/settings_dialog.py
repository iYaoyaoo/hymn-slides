"""设置对话框（v4）：主目录 / 引擎路径（PowerPoint/WPS/LibreOffice）/ 缓存上限 / 单屏放映确认。"""
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
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # 主目录
        self.main_dir_edit = QLineEdit(str(config.main_dir))
        browse_main = QPushButton("浏览…")
        browse_main.clicked.connect(lambda: self._pick_dir(self.main_dir_edit, "选择主目录"))
        row_main = QHBoxLayout()
        row_main.addWidget(self.main_dir_edit)
        row_main.addWidget(browse_main)
        form.addRow("主目录：", row_main)

        # 引擎：显示自动探测结果
        from src.render.engine_detect import detect_from_config

        cands = detect_from_config(config)
        detect_text = "\n".join(
            f"{'✓' if i.available else '✗'} {i.name}：{i.detail}" for i in cands.infos
        )
        detect_label = QLabel(detect_text)
        detect_label.setWordWrap(True)
        form.addRow("自动探测：", detect_label)

        # PowerPoint 路径
        self.ppt_edit = QLineEdit(config.ppt_path)
        self.ppt_edit.setPlaceholderText("留空=自动（Windows 用注册表；macOS 默认 /Applications/Microsoft PowerPoint.app）")
        browse_ppt = QPushButton("浏览…")
        browse_ppt.clicked.connect(lambda: self._pick_file(self.ppt_edit))
        row_ppt = QHBoxLayout()
        row_ppt.addWidget(self.ppt_edit)
        row_ppt.addWidget(browse_ppt)
        form.addRow("PowerPoint 路径：", row_ppt)

        # WPS 路径
        self.wps_edit = QLineEdit(config.wps_path)
        self.wps_edit.setPlaceholderText("留空=自动（仅 Windows；macOS 不支持自动化）")
        browse_wps = QPushButton("浏览…")
        browse_wps.clicked.connect(lambda: self._pick_file(self.wps_edit))
        row_wps = QHBoxLayout()
        row_wps.addWidget(self.wps_edit)
        row_wps.addWidget(browse_wps)
        form.addRow("WPS 路径：", row_wps)

        # LibreOffice soffice 路径
        self.soffice_edit = QLineEdit(config.soffice_path)
        self.soffice_edit.setPlaceholderText("留空=自动探测系统安装的 LibreOffice")
        browse_lo = QPushButton("浏览…")
        browse_lo.clicked.connect(lambda: self._pick_file(self.soffice_edit))
        row_lo = QHBoxLayout()
        row_lo.addWidget(self.soffice_edit)
        row_lo.addWidget(browse_lo)
        form.addRow("LibreOffice soffice：", row_lo)

        # 缓存上限
        self.cache_spin = QSpinBox()
        self.cache_spin.setRange(64, 1024 * 1024)
        self.cache_spin.setSuffix(" MB")
        self.cache_spin.setValue(config.cache_limit_mb)
        form.addRow("缓存上限：", self.cache_spin)

        # 单屏倒计时确认
        self.confirm_box = QCheckBox("单屏放映前显示 3 秒倒计时确认")
        self.confirm_box.setChecked(config.single_screen_confirm)
        form.addRow("", self.confirm_box)

        layout.addLayout(form)

        note = QLabel(
            "引擎优先级：PowerPoint → WPS → LibreOffice（手动指定路径优先）。\n"
            "引擎路径修改后重启程序生效。便携模式：程序目录放置 portable.flag 后，"
            "配置/缓存/日志全部保存到程序目录 data/ 下。"
        )
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

    # ---------- 浏览按钮 ----------

    @staticmethod
    def _pick_dir(edit: QLineEdit, title: str) -> None:
        d = QFileDialog.getExistingDirectory(None, title, edit.text())
        if d:
            edit.setText(d)

    @staticmethod
    def _pick_file(edit: QLineEdit) -> None:
        f, _ = QFileDialog.getOpenFileName(None, "选择程序路径", edit.text())
        if f:
            edit.setText(f)

    # ---------- 保存 ----------

    def _save(self) -> None:
        main_dir = Path(self.main_dir_edit.text().strip()).expanduser()
        if not main_dir.is_dir():
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "设置", "主目录不存在，请重新选择。")
            return
        old_main = self.config.main_dir
        self.config.set_main_dir(main_dir)
        self.config.set_ppt_path(self.ppt_edit.text().strip())
        self.config.set_wps_path(self.wps_edit.text().strip())
        self.config.set_soffice_path(self.soffice_edit.text().strip())
        self.config.set_cache_limit_mb(self.cache_spin.value())
        self.config.set_single_screen_confirm(self.confirm_box.isChecked())
        self.config.sync()
        self._main_dir_changed = old_main != main_dir
        self.accept()

    @property
    def main_dir_changed(self) -> bool:
        return getattr(self, "_main_dir_changed", False)
