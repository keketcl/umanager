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
    def __init__(
        self,
        base_service: UsbBaseDeviceProtocol,
        storage_service: UsbStorageDeviceProtocol,
        main_area_state_manager: MainAreaStateManager | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._main_area_state_manager = (
            main_area_state_manager
            if main_area_state_manager is not None
            else MainAreaStateManager(self, base_service, storage_service)
        )

        self._state_manager = OverviewStateManager(self, self._main_area_state_manager)

        self._title_bar = OverviewTitleBarWidget()
        self._device_list = DeviceInfoListWidget()
        self._button_bar = OverviewButtonBarWidget()

        self._state_manager.stateChanged.connect(self._on_state_changed)
        self._state_manager.detailsRequested.connect(self._on_details_requested)

        self._button_bar.refresh_devices.connect(self._state_manager.refresh)
        self._button_bar.view_details.connect(self._state_manager.request_details)
        self._button_bar.eject_device.connect(self._state_manager.request_eject)

        self._device_list.selection_changed.connect(self._state_manager.set_selected_device)

        layout = QVBoxLayout()
        layout.addWidget(self._title_bar)
        layout.addWidget(self._device_list, 1)
        layout.addWidget(self._button_bar)
        self.setLayout(layout)

        self._on_state_changed(self._state_manager.state())

        self._state_manager.refresh()

    def state_manager(self) -> OverviewStateManager:
        return self._state_manager

    def main_area_state_manager(self) -> MainAreaStateManager:
        return self._main_area_state_manager

    def refresh(self) -> None:
        self._state_manager.refresh()

    def _on_state_changed(self, state: object) -> None:
        if not isinstance(state, OverviewState):
            return

        self._title_bar.set_device_count(state.device_count)
        self._title_bar.set_scanning(state.is_scanning)
        self._device_list.set_devices(state.devices)
        self._sync_button_states(state)

    def _on_details_requested(self, base, storage) -> None:
        if base is None:
            return
        dialog = DeviceDetailDialog(base, storage, parent=self)
        dialog.exec()

    def _update_button_states(self, base, storage) -> None:
        has_selection = base is not None
        is_storage = storage is not None

        self._button_bar.set_details_enabled(has_selection)
        self._button_bar.set_eject_enabled(is_storage)

    def _sync_button_states(self, state: OverviewState) -> None:
        if state.is_scanning:
            self._button_bar.set_enabled(False)
            return

        self._button_bar.set_enabled(True)

        if state.selected_device is None:
            self._update_button_states(None, None)
            return

        base, storage = state.selected_device
        self._update_button_states(base, storage)
