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

from .main_area_state import MainAreaState, MainAreaStateManager


@dataclass(frozen=True, slots=True)
class OverviewState:
    devices: tuple[UsbBaseDeviceInfo | UsbStorageDeviceInfo, ...] = ()
    selected_device: Optional[tuple[UsbBaseDeviceInfo, Optional[UsbStorageDeviceInfo]]] = None
    is_scanning: bool = False
    device_count: int = 0

    refresh_error: Optional[object] = None
    active_operations: tuple[str, ...] = ()  # e.g. ("refresh", "eject")
    last_operation: Optional[str] = None  # "refresh" | "eject"
    last_operation_error: Optional[object] = None
    last_eject_result: Optional[DeviceEjectResult] = None


class OverviewStateManager(QtCore.QObject):
    stateChanged = QtCore.Signal(object)  # OverviewState

    fileManagerRequested = QtCore.Signal(object, object)  # (base, storage)
    detailsRequested = QtCore.Signal(object, object)  # (base, storage)
    ejectRequested = QtCore.Signal(object, object)  # (base, storage)

    def __init__(
        self,
        parent: QtCore.QObject,
        main_area_state_manager: MainAreaStateManager,
    ) -> None:
        super().__init__(parent)
        self._state = OverviewState()
        self._main_area = main_area_state_manager
        self._last_seen_main_area_op: Optional[str] = None

        self._main_area.stateChanged.connect(self._on_main_area_state_changed)

    def state(self) -> OverviewState:
        return self._state

    def _set_state(self, state: OverviewState) -> None:
        self._state = state
        self.stateChanged.emit(self._state)

    @QtCore.Slot(object)
    def set_devices(self, devices: list | tuple) -> None:
        _ = devices

    @QtCore.Slot(object, object)
    def set_selected_device(
        self,
        base: Optional[UsbBaseDeviceInfo],
        storage: Optional[UsbStorageDeviceInfo],
    ) -> None:
        new_selection = (base, storage) if base is not None else None
        if new_selection == self._state.selected_device:
            return

        self._set_state(replace(self._state, selected_device=new_selection))

    def _set_scanning(self, is_scanning: bool) -> None:
        _ = is_scanning

    @QtCore.Slot()
    def refresh(self) -> None:
        self._main_area.refresh()

    @QtCore.Slot(object)
    def _on_main_area_state_changed(self, state: object) -> None:
        if not isinstance(state, MainAreaState):
            return

        selected_device = self._state.selected_device
        if (
            state.last_operation == "refresh"
            and state.last_operation != self._last_seen_main_area_op
            and not state.is_scanning
        ):
            selected_device = None

        self._last_seen_main_area_op = state.last_operation

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

    @QtCore.Slot()
    def request_file_manager(self) -> None:
        if self._state.selected_device is None:
            return
        base, storage = self._state.selected_device
        if storage is not None:
            self.fileManagerRequested.emit(base, storage)

    @QtCore.Slot()
    def request_details(self) -> None:
        if self._state.selected_device is None:
            return
        base, storage = self._state.selected_device
        self.detailsRequested.emit(base, storage)

    @QtCore.Slot()
    def request_eject(self) -> None:
        if self._state.selected_device is None:
            return

        base, storage = self._state.selected_device
        if storage is None:
            return

        self.ejectRequested.emit(base, storage)

        device_id: UsbDeviceId = storage.base.id
        self._main_area.eject_storage_device(device_id)

    @QtCore.Slot(object, object)
    def handle_device_activated(
        self, base: UsbBaseDeviceInfo, storage: Optional[UsbStorageDeviceInfo]
    ) -> None:
        if storage is not None:
            self.fileManagerRequested.emit(base, storage)
