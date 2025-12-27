from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QWidget

from umanager.backend.device import (
    UsbBaseDeviceProtocol,
    UsbDeviceId,
    UsbStorageDeviceInfo,
    UsbStorageDeviceProtocol,
)
from umanager.backend.filesystem.protocol import FileSystemProtocol
from umanager.backend.filesystem.service import FileSystemService
from umanager.ui.states import MainAreaState, MainAreaStateManager
from umanager.ui.views.file_manager_page import FileManagerPageView
from umanager.ui.views.overview_page import OverviewPageView
from umanager.ui.widgets.sidebar import SidebarWidget
from umanager.util.device_change_watcher import UsbDeviceChangeWatcher


class MainAreaView(QWidget):
    def __init__(
        self,
        base_service: UsbBaseDeviceProtocol,
        storage_service: UsbStorageDeviceProtocol,
        *,
        filesystem: Optional[FileSystemProtocol] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._filesystem: FileSystemProtocol = filesystem or FileSystemService()

        self._state_manager = MainAreaStateManager(self, base_service, storage_service)

        self._sidebar = SidebarWidget(self)
        self._sidebar.overview_requested.connect(self.show_overview)
        self._sidebar.device_requested.connect(self.show_device)

        self._stack = QStackedWidget(self)

        self._overview = OverviewPageView(
            base_service=base_service,
            storage_service=storage_service,
            main_area_state_manager=self._state_manager,
            parent=self,
        )
        self._stack.addWidget(self._overview)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, 1)
        self.setLayout(layout)

        self._file_pages: dict[UsbDeviceId, FileManagerPageView] = {}
        self._file_page_roots: dict[UsbDeviceId, str | Path | None] = {}
        self._current_device_id: Optional[UsbDeviceId] = None

        self._unified_refresh_target: Optional[UsbDeviceId] = None
        self._unified_refresh_pending = False
        self._unified_refresh_inflight = False

        self._auto_refresh_pending = False
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.setSingleShot(True)
        self._auto_refresh_timer.setInterval(600)
        self._auto_refresh_timer.timeout.connect(self._trigger_auto_refresh)

        self._device_change_watcher = UsbDeviceChangeWatcher(parent=self)
        self._device_change_watcher.deviceChangeDetected.connect(self._on_device_change_detected)
        self._device_change_watcher.start()

        self._state_manager.stateChanged.connect(self._on_main_area_state_changed)

        self.show_overview()
        self._state_manager.refresh()

    def state_manager(self) -> MainAreaStateManager:
        return self._state_manager

    def sidebar_widget(self) -> SidebarWidget:
        return self._sidebar

    def overview_page(self) -> OverviewPageView:
        return self._overview

    def closeEvent(self, event) -> None:  # noqa: N802
        self._device_change_watcher.stop()
        self._state_manager.set_closing(True)
        super().closeEvent(event)

    @Slot()
    def show_overview(self) -> None:
        self._current_device_id = None
        self._stack.setCurrentWidget(self._overview)
        self._sidebar.select_overview()

    @Slot(object)
    def show_device(self, device_id: object) -> None:
        if not isinstance(device_id, UsbDeviceId):
            return

        storage = self._state_manager.state().storages.get(device_id)
        if storage is None:
            self.show_overview()
            return

        page = self._file_pages.get(device_id)
        if page is None:
            root_dir = self._storage_root_directory(storage)
            page = FileManagerPageView(
                self._filesystem,
                initial_directory=root_dir,
                use_unified_refresh=True,
                parent=self,
            )

            page.refresh_all_requested.connect(
                lambda dev_id=device_id: self._request_unified_refresh(dev_id)
            )

            page.state_manager().directoryUnavailable.connect(
                lambda _dir, _exc, dev_id=device_id: self._on_directory_unavailable(dev_id)
            )

            self._file_pages[device_id] = page
            self._file_page_roots[device_id] = root_dir
            self._stack.addWidget(page)

        current_root = self._storage_root_directory(storage)
        if current_root != self._file_page_roots.get(device_id):
            page.set_directory(current_root)
            self._file_page_roots[device_id] = current_root

        self._current_device_id = device_id
        self._stack.setCurrentWidget(page)
        self._sidebar.select_device(device_id)

    @Slot(object)
    def _on_main_area_state_changed(self, state: object) -> None:
        if not isinstance(state, MainAreaState):
            return

        self._sidebar.set_devices(state.storages.values())

        enabled = not state.is_scanning
        self._sidebar.setEnabled(enabled)
        self._stack.setEnabled(enabled)

        existing = set(state.storages.keys())
        removed = [dev_id for dev_id in list(self._file_pages.keys()) if dev_id not in existing]
        for dev_id in removed:
            page = self._file_pages.pop(dev_id)
            self._file_page_roots.pop(dev_id, None)
            self._stack.removeWidget(page)
            page.deleteLater()

        if self._current_device_id is not None and self._current_device_id not in existing:
            self.show_overview()

        if (
            self._unified_refresh_pending
            and not state.is_scanning
            and not self._unified_refresh_inflight
        ):
            self._unified_refresh_inflight = True
            self._unified_refresh_pending = False
            self._state_manager.refresh()
            return

        if self._auto_refresh_pending and not state.is_scanning:
            self._auto_refresh_pending = False
            if not self._unified_refresh_inflight and not self._unified_refresh_pending:
                self._state_manager.refresh()
            return

        if self._unified_refresh_inflight and not state.is_scanning:
            self._unified_refresh_inflight = False
            self._continue_unified_refresh(state)

    def _request_unified_refresh(self, device_id: UsbDeviceId) -> None:
        self._unified_refresh_target = device_id

        if self._state_manager.state().is_scanning:
            self._unified_refresh_pending = True
            return

        self._unified_refresh_inflight = True
        self._state_manager.refresh()

    def _trigger_auto_refresh(self) -> None:
        if self._unified_refresh_inflight or self._unified_refresh_pending:
            return

        if self._state_manager.state().is_scanning:
            self._auto_refresh_pending = True
            return

        self._state_manager.refresh()

    def _on_device_change_detected(self) -> None:
        self._auto_refresh_timer.start()

    def _continue_unified_refresh(self, state: MainAreaState) -> None:
        device_id = self._unified_refresh_target
        self._unified_refresh_target = None
        if device_id is None:
            return

        if self._current_device_id != device_id:
            return

        storage = state.storages.get(device_id)
        if storage is None:
            self.show_overview()
            return

        root = self._storage_root_directory(storage)
        if root is None:
            self.show_overview()
            return

        page = self._file_pages.get(device_id)
        if page is None:
            self.show_overview()
            return

        if root != self._file_page_roots.get(device_id):
            page.set_directory(root)
            self._file_page_roots[device_id] = root
            return

        page.state_manager().refresh()

    def _on_directory_unavailable(self, device_id: UsbDeviceId) -> None:
        if self._current_device_id != device_id:
            return
        self.show_overview()

    @staticmethod
    def _storage_root_directory(storage: UsbStorageDeviceInfo) -> str | Path | None:
        volumes = storage.volumes or []
        if not volumes:
            return None

        first = volumes[0]
        if first.mount_path is not None:
            return first.mount_path
        if first.drive_letter:
            return f"{first.drive_letter}\\"
        return None
