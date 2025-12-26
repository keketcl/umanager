from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from umanager.backend.device import UsbDeviceId, UsbStorageDeviceInfo


class SidebarWidget(QWidget):
    """侧边栏：包含总览入口与存储类 USB 设备条目。"""

    overview_requested = Signal()
    device_requested = Signal(object)  # UsbDeviceId
    selection_changed = Signal(object)  # Optional[UsbDeviceId]

    _OVERVIEW_KEY = "__overview__"

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SingleSelection)
        self._list.itemClicked.connect(self._on_item_clicked)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list)
        self.setLayout(layout)

        self._rebuild_items([], preserve_selection=False)

    # 公共 API
    def set_devices(self, devices: Iterable[UsbStorageDeviceInfo]) -> None:
        """更新设备列表，保留当前选中设备（若仍存在），否则回到总览。"""
        device_list = list(devices)
        self._rebuild_items(device_list, preserve_selection=True)

    def select_overview(self) -> None:
        self._select_item_by_key(self._OVERVIEW_KEY)

    def select_device(self, device_id: UsbDeviceId | str | None) -> None:
        if device_id is None:
            self.select_overview()
            return
        key = device_id.instance_id if isinstance(device_id, UsbDeviceId) else str(device_id)
        self._select_item_by_key(key)

    # 内部逻辑
    def _rebuild_items(
        self, devices: list[UsbStorageDeviceInfo], *, preserve_selection: bool
    ) -> None:
        prev_selection = self._current_device_key()

        self._list.clear()

        overview_item = QListWidgetItem("总览")
        overview_item.setData(Qt.UserRole, self._OVERVIEW_KEY)
        self._list.addItem(overview_item)

        for storage in sorted(devices, key=self._device_sort_key):
            label = self._format_device_label(storage)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, storage.base.id.instance_id)
            tooltip = self._format_device_tooltip(storage)
            if tooltip:
                item.setToolTip(tooltip)
            self._list.addItem(item)

        target_key = prev_selection if preserve_selection else self._OVERVIEW_KEY
        if target_key and not self._select_item_by_key(target_key):
            self._select_item_by_key(self._OVERVIEW_KEY)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.UserRole)
        if key == self._OVERVIEW_KEY:
            self.overview_requested.emit()
            self.selection_changed.emit(None)
            return

        device_id = UsbDeviceId(instance_id=str(key))
        self.device_requested.emit(device_id)
        self.selection_changed.emit(device_id)

    def _current_device_key(self) -> Optional[str]:
        selected = self._list.selectedItems()
        if not selected:
            return None
        key = selected[0].data(Qt.UserRole)
        if key is None:
            return None
        return str(key)

    def _select_item_by_key(self, key: str) -> bool:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if str(item.data(Qt.UserRole)) == key:
                self._list.setCurrentItem(item)
                return True
        return False

    @staticmethod
    def _format_device_label(storage: UsbStorageDeviceInfo) -> str:
        name = storage.base.product or storage.base.description or "存储设备"
        volumes = storage.volumes or []
        drive = volumes[0].drive_letter if volumes else None
        if drive:
            return f"{name} ({drive})"
        return name

    @staticmethod
    def _format_device_tooltip(storage: UsbStorageDeviceInfo) -> str:
        parts: list[str] = []
        base = storage.base
        if base.product:
            parts.append(base.product)
        if base.serial_number:
            parts.append(f"SN: {base.serial_number}")
        labels = [v.volume_label for v in storage.volumes or [] if v.volume_label]
        drives = [v.drive_letter for v in storage.volumes or [] if v.drive_letter]
        if labels:
            parts.append(f"卷标: {', '.join(labels)}")
        if drives:
            parts.append(f"盘符: {', '.join(drives)}")
        return "\n".join(parts)

    @staticmethod
    def _device_sort_key(storage: UsbStorageDeviceInfo) -> tuple[str, str]:
        name = storage.base.product or storage.base.description or ""
        return (name.casefold(), storage.base.id.instance_id.casefold())
