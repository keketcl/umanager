from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from umanager.backend.device import UsbBaseDeviceProtocol, UsbStorageDeviceProtocol
from umanager.ui.dialogs import DeviceDetailDialog
from umanager.ui.states import OverviewStateManager
from umanager.ui.widgets import (
    DeviceInfoListWidget,
    OverviewButtonBarWidget,
    OverviewTitleBarWidget,
)


class OverviewPageView(QWidget):
    """总览页视图，显示所有 USB 设备信息。

    架构：
    - 使用 OverviewStateManager 管理所有状态和业务逻辑
    - OverviewPage 只负责 UI 展示和响应状态变化
    - 所有 UI 更新都通过状态管理器的信号触发

    包含控件：
    - 标题栏（设备计数、扫描状态）
    - 设备列表
    - 按钮栏（刷新、管理文件、查看详情、安全弹出）
    """

    def __init__(
        self,
        base_service_factory: Callable[[], UsbBaseDeviceProtocol],
        storage_service_factory: Callable[[UsbBaseDeviceProtocol], UsbStorageDeviceProtocol],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        # 创建状态管理器
        self._state_manager = OverviewStateManager(
            self, base_service_factory, storage_service_factory
        )

        # 创建 UI 控件
        self._title_bar = OverviewTitleBarWidget()
        self._device_list = DeviceInfoListWidget()
        self._button_bar = OverviewButtonBarWidget()

        # 连接状态管理器信号到 UI 更新
        self._state_manager.devicesChanged.connect(self._on_devices_changed)
        self._state_manager.deviceCountChanged.connect(self._on_device_count_changed)
        self._state_manager.scanningChanged.connect(self._on_scanning_changed)
        self._state_manager.selectedDeviceChanged.connect(self._on_selected_device_changed)
        self._state_manager.detailsRequested.connect(self._on_details_requested)
        # 额外保障：刷新结束/失败时强制复位 UI（避免潜在竞态）
        self._state_manager.refreshFinished.connect(self._on_refresh_finished)
        self._state_manager.refreshFailed.connect(self._on_refresh_failed)

        # 连接 UI 控件信号到状态管理器
        self._button_bar.refresh_devices.connect(self._state_manager.refresh)
        self._button_bar.open_file_manager.connect(self._state_manager.request_file_manager)
        self._button_bar.view_details.connect(self._state_manager.request_details)
        self._button_bar.eject_device.connect(self._state_manager.request_eject)

        self._device_list.selection_changed.connect(self._state_manager.set_selected_device)
        self._device_list.device_activated.connect(self._state_manager.handle_device_activated)

        # 布局
        layout = QVBoxLayout()
        layout.addWidget(self._title_bar)
        layout.addWidget(self._device_list, 1)  # stretch=1，占用剩余空间
        layout.addWidget(self._button_bar)
        self.setLayout(layout)

        # 初始化按钮状态
        self._update_button_states(None, None)

        # 自动加载设备列表
        self._state_manager.refresh()

    # --- 公共 API ---

    def state_manager(self) -> OverviewStateManager:
        """获取状态管理器（用于外部连接信号）。"""
        return self._state_manager

    def refresh(self) -> None:
        """刷新设备列表（委托给状态管理器）。"""
        self._state_manager.refresh()

    # --- 状态变化响应（UI 更新） ---

    def _on_devices_changed(self, devices: tuple) -> None:
        """设备列表变化时更新 UI。"""
        self._device_list.set_devices(devices)

    def _on_device_count_changed(self, count: int) -> None:
        """设备数量变化时更新标题栏。"""
        self._title_bar.set_device_count(count)

    def _on_scanning_changed(self, is_scanning: bool) -> None:
        """扫描状态变化时更新 UI。"""
        self._title_bar.set_scanning(is_scanning)
        self._button_bar.set_refresh_enabled(not is_scanning)

    def _on_selected_device_changed(self, base, storage) -> None:
        """选中设备变化时更新按钮状态。"""
        self._update_button_states(base, storage)

    def _on_details_requested(self, base, storage) -> None:
        """查看详情：弹出对话框展示完整信息。"""
        if base is None:
            return
        dialog = DeviceDetailDialog(base, storage, parent=self)
        dialog.exec()

    def _update_button_states(self, base, storage) -> None:
        """根据选中设备更新按钮状态。"""
        has_selection = base is not None
        is_storage = storage is not None

        # 管理文件：仅存储设备可用
        self._button_bar.set_file_manager_enabled(is_storage)
        # 查看详情：有选中设备即可
        self._button_bar.set_details_enabled(has_selection)
        # 安全弹出：有选中设备即可
        # 仅存储设备支持安全弹出
        self._button_bar.set_eject_enabled(is_storage)

    # --- 刷新流程的兜底复位 ---
    def _on_refresh_finished(self) -> None:
        """刷新结束时，确保扫描指示与按钮状态复位。"""
        self._title_bar.set_scanning(False)
        self._button_bar.set_refresh_enabled(True)

    def _on_refresh_failed(self, exc: object) -> None:
        """刷新失败时，确保扫描指示与按钮状态复位。"""
        self._title_bar.set_scanning(False)
        self._button_bar.set_refresh_enabled(True)
