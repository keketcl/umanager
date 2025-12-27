from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Tuple, Union

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget

from umanager.backend.device import UsbBaseDeviceInfo, UsbStorageDeviceInfo, UsbVolumeInfo

DeviceRow = Tuple[UsbBaseDeviceInfo, Optional[UsbStorageDeviceInfo]]
DeviceItem = Union[UsbBaseDeviceInfo, UsbStorageDeviceInfo]


class _DeviceInfoTableModel(QAbstractTableModel):
    def __init__(
        self, devices: Optional[List[DeviceRow]] = None, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._devices: list[DeviceRow] = list(devices) if devices else []
        self._columns: list[tuple[str, Callable[[DeviceRow], str]]] = [
            ("产品", lambda d: d[0].product or ""),
            ("序列号", lambda d: d[0].serial_number or ""),
            ("卷标", self._format_volume_labels),
            ("速度 (Mbps)", self._format_speed),
            ("剩余容量/总容量 (GB)", self._format_capacity),
        ]

    @staticmethod
    def _format_speed(device: DeviceRow) -> str:
        base, _storage = device
        if base.speed_mbps is None:
            return ""
        return f"{base.speed_mbps:.0f}"

    @staticmethod
    def _format_volume_labels(device: DeviceRow) -> str:
        _base, storage = device
        volumes = _safe_volumes(storage.volumes if storage else None)
        labels: list[str] = [v.volume_label for v in volumes if v.volume_label]
        return ", ".join(labels)

    @staticmethod
    def _format_capacity(device: DeviceRow) -> str:
        _base, storage = device
        volumes = _safe_volumes(storage.volumes if storage else None)
        capacity_strs: list[str] = []
        for v in volumes:
            if v.free_bytes is not None and v.total_bytes is not None:
                free_gb = _bytes_to_gb_str(v.free_bytes)
                total_gb = _bytes_to_gb_str(v.total_bytes)
                capacity_strs.append(f"{free_gb}/{total_gb}")
        return ", ".join(capacity_strs)

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]
        if parent and parent.isValid():
            return 0
        return len(self._devices)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]
        if parent and parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.EditRole):
            return None
        device = self._devices[index.row()]
        _, accessor = self._columns[index.column()]
        return accessor(device)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._columns[section][0]
        return str(section + 1)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:  # type: ignore[override]
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def set_devices(self, devices: Iterable[DeviceItem]) -> None:
        self.beginResetModel()
        self._devices = [_to_device_row(d) for d in devices]
        self.endResetModel()

    def device_at(self, row: int) -> Optional[DeviceRow]:
        if 0 <= row < len(self._devices):
            return self._devices[row]
        return None


class DeviceInfoListWidget(QWidget):
    device_activated = Signal(object, object)
    selection_changed = Signal(object, object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._table = QTableView(self)
        self._model = _DeviceInfoTableModel()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.setFocusPolicy(Qt.NoFocus)  # 禁用行获取键盘焦点时的虚线光标
        self._table.doubleClicked.connect(self._emit_device_activated)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)
        self.setLayout(layout)

    def set_devices(self, devices: Iterable[DeviceItem]) -> None:
        self._model.set_devices(devices)
        self._table.resizeColumnsToContents()

    def current_device(self) -> tuple[Optional[UsbBaseDeviceInfo], Optional[UsbStorageDeviceInfo]]:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None, None
        row = self._model.device_at(indexes[0].row())
        if row is None:
            return None, None
        return row

    def _emit_device_activated(self, index: QModelIndex) -> None:
        device = self._model.device_at(index.row())
        if device is not None:
            base, storage = device
            self.device_activated.emit(base, storage)

    def _on_selection_changed(self) -> None:
        base, storage = self.current_device()
        self.selection_changed.emit(base, storage)


def _bytes_to_gb_str(value: int) -> str:
    gb = value / (1024**3)
    return f"{gb:.1f}"


def _safe_volumes(volumes: Optional[list[UsbVolumeInfo]]) -> list[UsbVolumeInfo]:
    if volumes is None:
        return []
    return list(volumes)


def _to_device_row(device: DeviceItem) -> DeviceRow:
    if isinstance(device, UsbStorageDeviceInfo):
        return device.base, device
    return device, None
