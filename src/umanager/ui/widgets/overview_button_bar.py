from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class OverviewButtonBar(QWidget):
    """总览页按钮栏，水平布局，居右对齐。

    包含三个按钮：
    - 管理文件：打开选中设备的文件浏览器
    - 查看具体信息：显示选中设备的详细信息
    - 安全弹出：安全移除选中设备
    """

    open_file_manager = Signal()
    view_details = Signal()
    eject_device = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._open_file_btn = QPushButton("管理文件")
        self._view_details_btn = QPushButton("查看具体信息")
        self._eject_btn = QPushButton("安全弹出")

        # 连接信号
        self._open_file_btn.clicked.connect(self.open_file_manager.emit)
        self._view_details_btn.clicked.connect(self.view_details.emit)
        self._eject_btn.clicked.connect(self.eject_device.emit)

        # 布局：水平，居右
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()  # 填充左侧空间，使按钮右对齐
        layout.addWidget(self._open_file_btn)
        layout.addWidget(self._view_details_btn)
        layout.addWidget(self._eject_btn)

        self.setLayout(layout)

    # --- 公共 API ---
    def set_enabled(self, enabled: bool) -> None:
        """启用或禁用所有按钮。"""
        self._open_file_btn.setEnabled(enabled)
        self._view_details_btn.setEnabled(enabled)
        self._eject_btn.setEnabled(enabled)

    def set_file_manager_enabled(self, enabled: bool) -> None:
        """单独启用或禁用管理文件按钮。"""
        self._open_file_btn.setEnabled(enabled)

    def set_details_enabled(self, enabled: bool) -> None:
        """单独启用或禁用查看具体信息按钮。"""
        self._view_details_btn.setEnabled(enabled)

    def set_eject_enabled(self, enabled: bool) -> None:
        """单独启用或禁用安全弹出按钮。"""
        self._eject_btn.setEnabled(enabled)
