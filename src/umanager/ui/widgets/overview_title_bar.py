from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class OverviewTitleBarWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._title_label = QLabel("总览")
        self._title_label.setStyleSheet("font-size: 16pt; font-weight: bold;")

        self._count_label = QLabel("(0 个设备)")
        self._count_label.setStyleSheet("font-size: 10pt; color: gray;")

        self._status_label = QLabel("扫描中...")
        self._status_label.setStyleSheet("font-size: 9pt; color: #2196F3;")
        self._status_label.setVisible(False)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._title_label)
        layout.addSpacing(8)
        layout.addWidget(self._count_label)
        layout.addStretch()
        layout.addWidget(self._status_label)

        self.setLayout(layout)

    def set_device_count(self, count: int) -> None:
        self._count_label.setText(f"({count} 个设备)")

    def set_scanning(self, is_scanning: bool) -> None:
        self._status_label.setVisible(is_scanning)

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)
