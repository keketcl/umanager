from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Optional

from PySide6 import QtCore

import pythoncom

from ...backend.device import (
    UsbBaseDeviceInfo,
    UsbBaseDeviceProtocol,
    UsbStorageDeviceInfo,
    UsbStorageDeviceProtocol,
)


@dataclass(frozen=True, slots=True)
class OverviewState:
    """总览页的不可变状态。"""

    devices: tuple[UsbBaseDeviceInfo | UsbStorageDeviceInfo, ...] = ()
    selected_device: Optional[tuple[UsbBaseDeviceInfo, Optional[UsbStorageDeviceInfo]]] = None
    is_scanning: bool = False
    device_count: int = 0


class _AsyncCallSignals(QtCore.QObject):
    finished = QtCore.Signal(object)
    error = QtCore.Signal(object)


class _AsyncCall(QtCore.QRunnable):
    def __init__(self, func: Callable[[], object]) -> None:
        super().__init__()
        self._func = func
        self.signals = _AsyncCallSignals()

    @QtCore.Slot()
    def run(self) -> None:
        # 初始化 COM（WMI 需要）
        pythoncom.CoInitialize()
        try:
            result = self._func()
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(exc)
            return
        finally:
            pythoncom.CoUninitialize()
        self.signals.finished.emit(result)


class OverviewStateManager(QtCore.QObject):
    """总览页状态管理器。

    职责：
    - 管理设备列表状态
    - 管理选中设备状态
    - 管理扫描状态
    - 异步加载设备
    - 发射状态变化信号
    """

    # 状态变化信号
    stateChanged = QtCore.Signal(object)  # OverviewState
    devicesChanged = QtCore.Signal(object)  # tuple[DeviceInfo, ...]
    selectedDeviceChanged = QtCore.Signal(object, object)  # (base, storage)
    scanningChanged = QtCore.Signal(bool)
    deviceCountChanged = QtCore.Signal(int)

    # 操作信号
    refreshStarted = QtCore.Signal()
    refreshFinished = QtCore.Signal()
    refreshFailed = QtCore.Signal(object)  # Exception

    # 请求信号（UI 应连接这些信号）
    fileManagerRequested = QtCore.Signal(object, object)  # (base, storage)
    detailsRequested = QtCore.Signal(object, object)  # (base, storage)
    ejectRequested = QtCore.Signal(object, object)  # (base, storage)

    def __init__(
        self,
        parent: QtCore.QObject,
        base_service_factory: Callable[[], UsbBaseDeviceProtocol],
        storage_service_factory: Callable[[UsbBaseDeviceProtocol], UsbStorageDeviceProtocol],
    ) -> None:
        super().__init__(parent)
        self._state = OverviewState()
        self._base_service_factory = base_service_factory
        self._storage_service_factory = storage_service_factory
        self._refresh_generation = 0

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
        """设置设备列表，并且无论是否变化都清除扫描状态。

        说明：
        - 之前若设备列表不变会提前返回，导致 `is_scanning` 保持为 True，阻止再次刷新。
        - 现在即使设备列表内容未发生变化，也会将扫描状态置为 False 并发射相应信号。
        """
        devices_tuple = tuple(devices)
        count = len(devices_tuple)

        # 判断设备列表是否真的发生变化
        changed = devices_tuple != self._state.devices or count != self._state.device_count

        # 始终清除扫描状态；如设备列表变化则一并更新设备与计数
        new_state = replace(self._state, is_scanning=False)
        if changed:
            new_state = replace(new_state, devices=devices_tuple, device_count=count)

        self._set_state(new_state)

        # 发射变化信号：设备/计数仅在变化时发射；扫描结束始终发射
        if changed:
            self.devicesChanged.emit(self._state.devices)
            self.deviceCountChanged.emit(self._state.device_count)
        self.scanningChanged.emit(False)

    @QtCore.Slot(object, object)
    def set_selected_device(
        self, base: Optional[UsbBaseDeviceInfo], storage: Optional[UsbStorageDeviceInfo]
    ) -> None:
        """设置选中设备。"""
        new_selection = (base, storage) if base is not None else None
        if new_selection == self._state.selected_device:
            return

        self._set_state(replace(self._state, selected_device=new_selection))
        self.selectedDeviceChanged.emit(base, storage)

    def _set_scanning(self, is_scanning: bool) -> None:
        """设置扫描状态。"""
        if is_scanning == self._state.is_scanning:
            return
        self._set_state(replace(self._state, is_scanning=is_scanning))
        self.scanningChanged.emit(is_scanning)

    # --- 异步操作 ---

    @QtCore.Slot()
    def refresh(self) -> None:
        """刷新设备列表（异步）。"""
        if self._state.is_scanning:
            return  # 已有刷新任务在进行中

        self._refresh_generation += 1
        generation = self._refresh_generation

        self._set_scanning(True)
        self.refreshStarted.emit()

        def do_refresh() -> tuple[int, list]:
            # 在工作线程中创建服务实例
            base_service = self._base_service_factory()
            storage_service = self._storage_service_factory(base_service)

            # 刷新设备列表
            base_service.refresh()
            storage_service.refresh()

            base_ids = base_service.list_base_device_ids()
            storage_ids = {i.instance_id for i in storage_service.list_storage_device_ids()}

            devices = []
            for dev_id in base_ids:
                base_info = base_service.get_base_device_info(dev_id)
                if dev_id.instance_id in storage_ids:
                    try:
                        storage_info = storage_service.get_storage_device_info(dev_id)
                        devices.append(storage_info)
                    except Exception:
                        devices.append(base_info)
                else:
                    devices.append(base_info)

            return generation, devices

        task = _AsyncCall(do_refresh)
        task.signals.finished.connect(self._on_refresh_finished)
        task.signals.error.connect(self._on_refresh_failed)
        QtCore.QThreadPool.globalInstance().start(task)

    @QtCore.Slot(object)
    def _on_refresh_finished(self, result: object) -> None:
        """刷新完成回调。"""
        if not isinstance(result, tuple) or len(result) != 2:
            return

        generation, devices = result
        if generation != self._refresh_generation:
            return  # 忽略过时的结果

        self.set_devices(devices)
        self.refreshFinished.emit()

    @QtCore.Slot(object)
    def _on_refresh_failed(self, exc: object) -> None:
        """刷新失败回调。"""
        self._set_scanning(False)
        self.scanningChanged.emit(False)
        self.refreshFailed.emit(exc)

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
        """请求安全弹出设备。"""
        if self._state.selected_device is None:
            return
        base, storage = self._state.selected_device
        # 仅存储型设备允许安全弹出
        if storage is not None:
            self.ejectRequested.emit(base, storage)

    @QtCore.Slot(object, object)
    def handle_device_activated(
        self, base: UsbBaseDeviceInfo, storage: Optional[UsbStorageDeviceInfo]
    ) -> None:
        """处理设备双击激活（默认打开文件管理器）。"""
        if storage is not None:
            self.fileManagerRequested.emit(base, storage)
