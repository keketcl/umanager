from __future__ import annotations

from getpass import getuser
from typing import Optional

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class BasicInfoBarWidget(QWidget):
    """根窗口顶部的基本信息栏（应用标题 + 副标题/状态）。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._title_label = QLabel("USB Manager")
        self._title_label.setStyleSheet("font-size: 16pt; font-weight: bold;")

        self._subtitle_label = QLabel("")
        self._subtitle_label.setStyleSheet("font-size: 10pt; color: gray;")

        self._user_label = QLabel(f"用户: {getuser()}")
        self._user_label.setStyleSheet("font-size: 10pt; color: #555;")

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 10pt; color: #2196F3;")

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(self._title_label)
        layout.addSpacing(8)
        layout.addWidget(self._subtitle_label)
        layout.addStretch()
        layout.addWidget(self._user_label)
        layout.addSpacing(8)
        layout.addWidget(self._status_label)

        self.setLayout(layout)

    # 公共 API
    def set_title(self, text: str) -> None:
        self._title_label.setText(text)

    def set_subtitle(self, text: str) -> None:
        self._subtitle_label.setText(text)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def set_user(self, text: str) -> None:
        self._user_label.setText(text)
