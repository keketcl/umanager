from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from PySide6 import QtCore

from umanager.backend.device import (
    DeviceEjectResult,
    UsbBaseDeviceInfo,
    UsbDeviceId,
    UsbStorageDeviceInfo,
)

from .mainarea_state import MainAreaState, MainAreaStateManager


@dataclass(frozen=True, slots=True)
class OverviewState:
    """总览页的不可变状态。"""

    devices: tuple[UsbBaseDeviceInfo | UsbStorageDeviceInfo, ...] = ()
    selected_device: Optional[tuple[UsbBaseDeviceInfo, Optional[UsbStorageDeviceInfo]]] = None
    is_scanning: bool = False
    device_count: int = 0

    # Async status
    refresh_error: Optional[object] = None
    active_operations: tuple[str, ...] = ()  # e.g. ("refresh", "eject")
    last_operation: Optional[str] = None  # "refresh" | "eject"
    last_operation_error: Optional[object] = None
    last_eject_result: Optional[DeviceEjectResult] = None


class OverviewStateManager(QtCore.QObject):
    """总览页状态管理器。

    职责：
    - 管理设备列表状态
    - 管理选中设备状态
    - 管理扫描状态
    - 异步加载设备
    - 发射状态变化信号
    """

    # 状态变化信号（唯一）
    stateChanged = QtCore.Signal(object)  # OverviewState

    # 请求信号（UI 应连接这些信号）
    fileManagerRequested = QtCore.Signal(object, object)  # (base, storage)
    detailsRequested = QtCore.Signal(object, object)  # (base, storage)
    ejectRequested = QtCore.Signal(object, object)  # (base, storage)

    def __init__(
        self,
        parent: QtCore.QObject,
        mainarea_state_manager: MainAreaStateManager,
    ) -> None:
        super().__init__(parent)
        self._state = OverviewState()
        self._mainarea = mainarea_state_manager
        self._last_seen_mainarea_op: Optional[str] = None

        self._mainarea.stateChanged.connect(self._on_mainarea_state_changed)

    def state(self) -> OverviewState:
        """获取当前状态（只读）。"""
        return self._state

    # --- 状态更新方法 ---

    def _set_state(self, state: OverviewState) -> None:
        """设置新状态并发射信号。"""
        self._state = state
        self.stateChanged.emit(self._state)

    @QtCore.Slot(object)
    def set_devices(self, devices: list | tuple) -> None:
        """兼容旧调用：Overview 不再直接维护设备列表。"""
        _ = devices

    @QtCore.Slot(object, object)
    def set_selected_device(
        self, base: Optional[UsbBaseDeviceInfo], storage: Optional[UsbStorageDeviceInfo]
    ) -> None:
        """设置选中设备。"""
        new_selection = (base, storage) if base is not None else None
        if new_selection == self._state.selected_device:
            return

        self._set_state(replace(self._state, selected_device=new_selection))

    def _set_scanning(self, is_scanning: bool) -> None:
        """兼容旧调用：扫描态来自 MainAreaStateManager。"""
        _ = is_scanning

    # --- 异步操作 ---

    @QtCore.Slot()
    def refresh(self) -> None:
        """刷新设备列表（委托给 MainAreaStateManager）。"""
        self._mainarea.refresh()

    @QtCore.Slot(object)
    def _on_mainarea_state_changed(self, state: object) -> None:
        if not isinstance(state, MainAreaState):
            return

        # 刷新完成后不保留总览选中（按既定规则）。
        selected_device = self._state.selected_device
        if (
            state.last_operation == "refresh"
            and state.last_operation != self._last_seen_mainarea_op
            and not state.is_scanning
        ):
            selected_device = None

        self._last_seen_mainarea_op = state.last_operation

        self._set_state(
            replace(
                self._state,
                devices=state.devices,
                device_count=state.device_count,
                is_scanning=state.is_scanning,
                refresh_error=state.refresh_error,
                active_operations=state.active_operations,
                last_operation=state.last_operation,
                last_operation_error=state.last_operation_error,
                last_eject_result=state.last_eject_result,
                selected_device=selected_device,
            )
        )

    # --- UI 操作槽 ---

    @QtCore.Slot()
    def request_file_manager(self) -> None:
        """请求打开文件管理器。"""
        if self._state.selected_device is None:
            return
        base, storage = self._state.selected_device
        if storage is not None:
            self.fileManagerRequested.emit(base, storage)

    @QtCore.Slot()
    def request_details(self) -> None:
        """请求查看设备详情。"""
        if self._state.selected_device is None:
            return
        base, storage = self._state.selected_device
        self.detailsRequested.emit(base, storage)

    @QtCore.Slot()
    def request_eject(self) -> None:
        """安全弹出选中的存储设备（委托给 MainAreaStateManager）。"""
        if self._state.selected_device is None:
            return

        base, storage = self._state.selected_device
        if storage is None:
            return

        # 保持兼容：仍然发射 ejectRequested（若外部有人监听）。
        self.ejectRequested.emit(base, storage)

        device_id: UsbDeviceId = storage.base.id
        self._mainarea.eject_storage_device(device_id)

    @QtCore.Slot(object, object)
    def handle_device_activated(
        self, base: UsbBaseDeviceInfo, storage: Optional[UsbStorageDeviceInfo]
    ) -> None:
        """处理设备双击激活（默认打开文件管理器）。"""
        if storage is not None:
            self.fileManagerRequested.emit(base, storage)
