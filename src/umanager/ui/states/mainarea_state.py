from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Optional

from PySide6 import QtCore

from umanager.backend.device import (
    DeviceEjectResult,
    UsbBaseDeviceInfo,
    UsbBaseDeviceProtocol,
    UsbDeviceId,
    UsbStorageDeviceInfo,
    UsbStorageDeviceProtocol,
)


@dataclass(frozen=True, slots=True)
class MainAreaState:
    """主区域（MainArea）的全局状态。

    该状态是全局“设备扫描/刷新”的唯一数据源（后续也会承载侧边栏、文件页缓存等）。
    当前最小落地只包含：
    - 扫描态
    - 总览展示用设备列表
    - 存储设备字典（后续给 Sidebar / FileManager 使用）
    - 异步操作结果
    """

    is_scanning: bool = False

    devices: tuple[UsbBaseDeviceInfo | UsbStorageDeviceInfo, ...] = ()
    device_count: int = 0

    storages: dict[UsbDeviceId, UsbStorageDeviceInfo] = field(default_factory=dict)

    refresh_error: Optional[object] = None
    active_operations: tuple[str, ...] = ()
    last_operation: Optional[str] = None
    last_operation_error: Optional[object] = None
    last_eject_result: Optional[DeviceEjectResult] = None


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
        try:
            result = self._func()
        except Exception as exc:  # noqa: BLE001
            try:
                self.signals.error.emit(exc)
            except RuntimeError:
                pass
            return

        try:
            self.signals.finished.emit(result)
        except RuntimeError:
            pass


class MainAreaStateManager(QtCore.QObject):
    """主区域状态管理器（最小版）。

    说明：
    - 负责刷新/扫描并维护 devices/storages/is_scanning 等全局状态。
    - 目前还未包含页面切换、文件页缓存、全局禁用等 UI 行为（后续在 mainarea_view 落地）。
    """

    stateChanged = QtCore.Signal(object)  # MainAreaState

    def __init__(
        self,
        parent: QtCore.QObject,
        base_service: UsbBaseDeviceProtocol,
        storage_service: UsbStorageDeviceProtocol,
    ) -> None:
        super().__init__(parent)
        self._state = MainAreaState()
        self._base_service = base_service
        self._storage_service = storage_service

        self._is_closing = False
        self._refresh_generation = 0
        self._eject_generation = 0

    def state(self) -> MainAreaState:
        return self._state

    def set_closing(self, is_closing: bool) -> None:
        """窗口关闭后标记丢弃异步结果。"""
        self._is_closing = is_closing

    def _set_state(self, state: MainAreaState) -> None:
        self._state = state
        self.stateChanged.emit(self._state)

    def _start_operation(self, name: str) -> None:
        active = set(self._state.active_operations)
        if name in active:
            return
        active.add(name)
        self._set_state(replace(self._state, active_operations=tuple(sorted(active))))

    def _finish_operation(
        self,
        name: str,
        *,
        error: Optional[object],
        eject_result: Optional[DeviceEjectResult] = None,
    ) -> None:
        active = set(self._state.active_operations)
        active.discard(name)

        state = replace(
            self._state,
            active_operations=tuple(sorted(active)),
            last_operation=name,
            last_operation_error=error,
        )
        if name == "eject":
            state = replace(state, last_eject_result=eject_result)
        if name == "refresh":
            state = replace(state, refresh_error=error)

        self._set_state(state)

    @QtCore.Slot()
    def refresh(self) -> None:
        if self._state.is_scanning:
            return

        self._refresh_generation += 1
        generation = self._refresh_generation

        self._start_operation("refresh")
        self._set_state(replace(self._state, is_scanning=True, refresh_error=None))

        def do_refresh() -> tuple[int, tuple, dict]:
            base_service = self._base_service
            storage_service = self._storage_service

            base_service.refresh()
            storage_service.refresh()

            base_ids = base_service.list_base_device_ids()
            storage_ids = storage_service.list_storage_device_ids()

            storages: dict[UsbDeviceId, UsbStorageDeviceInfo] = {}
            for dev_id in storage_ids:
                try:
                    storages[dev_id] = storage_service.get_storage_device_info(dev_id)
                except Exception:
                    # 某些设备可能在读取存储信息时失败；此时仍允许其以 base 设备展示
                    continue

            devices: list[UsbBaseDeviceInfo | UsbStorageDeviceInfo] = []
            for dev_id in base_ids:
                base_info = base_service.get_base_device_info(dev_id)
                storage_info = storages.get(dev_id)
                devices.append(storage_info if storage_info is not None else base_info)

            return generation, tuple(devices), storages

        task = _AsyncCall(do_refresh)
        task.signals.finished.connect(self._on_refresh_finished)
        task.signals.error.connect(self._on_refresh_failed)
        QtCore.QThreadPool.globalInstance().start(task)

    @QtCore.Slot(object)
    def _on_refresh_finished(self, payload: object) -> None:
        if self._is_closing:
            return

        if not isinstance(payload, tuple) or len(payload) != 3:
            return

        generation, devices, storages = payload
        if generation != self._refresh_generation:
            return

        if not isinstance(devices, tuple) or not isinstance(storages, dict):
            return

        self._set_state(
            replace(
                self._state,
                devices=devices,
                device_count=len(devices),
                storages=storages,
                is_scanning=False,
                refresh_error=None,
            )
        )
        self._finish_operation("refresh", error=None)

    @QtCore.Slot(object)
    def _on_refresh_failed(self, exc: object) -> None:
        if self._is_closing:
            return

        self._set_state(replace(self._state, is_scanning=False, refresh_error=exc))
        self._finish_operation("refresh", error=exc)

    @QtCore.Slot(UsbDeviceId)
    def eject_storage_device(self, device_id: UsbDeviceId) -> None:
        if self._state.is_scanning:
            return

        self._eject_generation += 1
        generation = self._eject_generation

        self._start_operation("eject")
        self._set_state(replace(self._state, is_scanning=True, last_eject_result=None))

        def do_eject() -> tuple[int, DeviceEjectResult]:
            result = self._storage_service.eject_storage_device(device_id)
            return generation, result

        task = _AsyncCall(do_eject)
        task.signals.finished.connect(self._on_eject_finished)
        task.signals.error.connect(self._on_eject_failed)
        QtCore.QThreadPool.globalInstance().start(task)

    @QtCore.Slot(object)
    def _on_eject_finished(self, payload: object) -> None:
        if self._is_closing:
            return

        if not isinstance(payload, tuple) or len(payload) != 2:
            self._set_state(replace(self._state, is_scanning=False))
            self._finish_operation("eject", error=RuntimeError("invalid eject payload"))
            return

        generation, result = payload
        if generation != self._eject_generation:
            return

        if not isinstance(result, DeviceEjectResult):
            self._set_state(replace(self._state, is_scanning=False))
            self._finish_operation("eject", error=RuntimeError("invalid eject result type"))
            return

        self._set_state(replace(self._state, is_scanning=False, last_eject_result=result))
        self._finish_operation("eject", error=None, eject_result=result)

        if result.success:
            self.refresh()

    @QtCore.Slot(object)
    def _on_eject_failed(self, exc: object) -> None:
        if self._is_closing:
            return

        self._set_state(replace(self._state, is_scanning=False))
        self._finish_operation("eject", error=exc)
