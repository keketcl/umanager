from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from umanager.backend.device import UsbBaseDeviceProtocol, UsbStorageDeviceProtocol
from umanager.ui.dialogs import DeviceDetailDialog
from umanager.ui.states import MainAreaStateManager, OverviewState, OverviewStateManager
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
    - 按钮栏（刷新、查看详情、安全弹出）
    """

    def __init__(
        self,
        base_service: UsbBaseDeviceProtocol,
        storage_service: UsbStorageDeviceProtocol,
        mainarea_state_manager: MainAreaStateManager | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        # MainArea 状态（最小版）：负责刷新/扫描与设备列表
        self._mainarea_state_manager = (
            mainarea_state_manager
            if mainarea_state_manager is not None
            else MainAreaStateManager(self, base_service, storage_service)
        )

        # Overview 状态：仅保留选中与意图发射；其余字段来自 MainAreaState
        self._state_manager = OverviewStateManager(self, self._mainarea_state_manager)

        # 创建 UI 控件
        self._title_bar = OverviewTitleBarWidget()
        self._device_list = DeviceInfoListWidget()
        self._button_bar = OverviewButtonBarWidget()

        # 连接状态管理器信号到 UI 更新（只使用 stateChanged）
        self._state_manager.stateChanged.connect(self._on_state_changed)
        self._state_manager.detailsRequested.connect(self._on_details_requested)

        # 连接 UI 控件信号到状态管理器
        self._button_bar.refresh_devices.connect(self._state_manager.refresh)
        self._button_bar.view_details.connect(self._state_manager.request_details)
        self._button_bar.eject_device.connect(self._state_manager.request_eject)

        self._device_list.selection_changed.connect(self._state_manager.set_selected_device)

        # 布局
        layout = QVBoxLayout()
        layout.addWidget(self._title_bar)
        layout.addWidget(self._device_list, 1)  # stretch=1，占用剩余空间
        layout.addWidget(self._button_bar)
        self.setLayout(layout)

        # 初始化 UI
        self._on_state_changed(self._state_manager.state())

        # 自动加载设备列表
        self._state_manager.refresh()

    # --- 公共 API ---

    def state_manager(self) -> OverviewStateManager:
        """获取状态管理器（用于外部连接信号）。"""
        return self._state_manager

    def mainarea_state_manager(self) -> MainAreaStateManager:
        """获取 MainArea 状态管理器（用于外部连接信号）。"""
        return self._mainarea_state_manager

    def refresh(self) -> None:
        """刷新设备列表（委托给状态管理器）。"""
        self._state_manager.refresh()

    # --- 状态变化响应（UI 更新） ---

    def _on_state_changed(self, state: object) -> None:
        if not isinstance(state, OverviewState):
            return

        self._title_bar.set_device_count(state.device_count)
        self._title_bar.set_scanning(state.is_scanning)
        self._device_list.set_devices(state.devices)
        self._sync_button_states(state)

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

        # 查看详情：有选中设备即可
        self._button_bar.set_details_enabled(has_selection)
        # 安全弹出：有选中设备即可
        # 仅存储设备支持安全弹出
        self._button_bar.set_eject_enabled(is_storage)

    def _sync_button_states(self, state: OverviewState) -> None:
        """统一处理按钮可用性：先处理扫描态，再处理选中态。

        规则：
        - 扫描/刷新中：所有按钮禁用
        - 非扫描：整体启用后，再按选中设备设置每个按钮
        """

        if state.is_scanning:
            self._button_bar.set_enabled(False)
            return

        self._button_bar.set_enabled(True)

        if state.selected_device is None:
            self._update_button_states(None, None)
            return

        base, storage = state.selected_device
        self._update_button_states(base, storage)
