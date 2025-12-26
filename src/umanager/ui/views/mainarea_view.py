from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Slot
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


class MainAreaView(QWidget):
    """主区域：Sidebar + 可变区域（QStackedWidget）。

    当前落地：
    - MainAreaStateManager 负责刷新/扫描/设备列表（唯一数据源）
    - Sidebar 作为唯一导航入口
    - OverviewPage 仅展示 + 发意图（刷新/详情/弹出）
    - FileManagerPage 按设备缓存创建；设备消失时销毁
    - 刷新期间禁用 Sidebar + 可变区域
    """

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
        self._state_manager.stateChanged.connect(self._on_mainarea_state_changed)

        self._sidebar = SidebarWidget(self)
        self._sidebar.overview_requested.connect(self.show_overview)
        self._sidebar.device_requested.connect(self.show_device)

        self._stack = QStackedWidget(self)

        self._overview = OverviewPageView(
            base_service=base_service,
            storage_service=storage_service,
            mainarea_state_manager=self._state_manager,
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

        self.show_overview()
        self._state_manager.refresh()

    def state_manager(self) -> MainAreaStateManager:
        return self._state_manager

    def sidebar_widget(self) -> SidebarWidget:
        return self._sidebar

    def overview_page(self) -> OverviewPageView:
        return self._overview

    def closeEvent(self, event) -> None:  # noqa: N802
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
            page = FileManagerPageView(self._filesystem, initial_directory=root_dir, parent=self)
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
    def _on_mainarea_state_changed(self, state: object) -> None:
        if not isinstance(state, MainAreaState):
            return

        self._sidebar.set_devices(state.storages.values())

        # 刷新期间禁用交互（允许关闭窗口由窗口系统负责）。
        enabled = not state.is_scanning
        self._sidebar.setEnabled(enabled)
        self._stack.setEnabled(enabled)

        # 设备消失：销毁对应文件页，并在必要时回到总览。
        existing = set(state.storages.keys())
        removed = [dev_id for dev_id in list(self._file_pages.keys()) if dev_id not in existing]
        for dev_id in removed:
            page = self._file_pages.pop(dev_id)
            self._file_page_roots.pop(dev_id, None)
            self._stack.removeWidget(page)
            page.deleteLater()

        if self._current_device_id is not None and self._current_device_id not in existing:
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
