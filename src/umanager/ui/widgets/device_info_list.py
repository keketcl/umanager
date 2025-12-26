from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Tuple, Union

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget

from umanager.backend.device import UsbBaseDeviceInfo, UsbStorageDeviceInfo, UsbVolumeInfo

DeviceRow = Tuple[UsbBaseDeviceInfo, Optional[UsbStorageDeviceInfo]]
DeviceItem = Union[UsbBaseDeviceInfo, UsbStorageDeviceInfo]


class _DeviceInfoTableModel(QAbstractTableModel):
    """表格模型，用于展示 USB 设备信息（基础 + 存储）。"""

    def __init__(
        self, devices: Optional[List[DeviceRow]] = None, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._devices: list[DeviceRow] = list(devices) if devices else []
        self._columns: list[tuple[str, Callable[[DeviceRow], str]]] = [
            ("制造商", lambda d: d[0].manufacturer or ""),
            ("产品", lambda d: d[0].product or ""),
            ("序列号", lambda d: d[0].serial_number or ""),
            ("USB 版本", lambda d: d[0].usb_version or ""),
            ("速度 (Mbps)", self._format_speed),
            ("卷标", self._format_volume_labels),
            ("文件系统", self._format_file_systems),
            ("容量 (GB)", self._format_total_bytes),
            ("剩余 (GB)", self._format_free_bytes),
        ]

    # --- 数据格式化 ---
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
    def _format_file_systems(device: DeviceRow) -> str:
        _base, storage = device
        volumes = _safe_volumes(storage.volumes if storage else None)
        fs: list[str] = [v.file_system for v in volumes if v.file_system]
        return ", ".join(fs)

    @staticmethod
    def _format_total_bytes(device: DeviceRow) -> str:
        _base, storage = device
        volumes = _safe_volumes(storage.volumes if storage else None)
        total: list[str] = []
        for v in volumes:
            if v.total_bytes is not None:
                total.append(_bytes_to_gb_str(v.total_bytes))
        return ", ".join(total)

    @staticmethod
    def _format_free_bytes(device: DeviceRow) -> str:
        _base, storage = device
        volumes = _safe_volumes(storage.volumes if storage else None)
        free: list[str] = []
        for v in volumes:
            if v.free_bytes is not None:
                free.append(_bytes_to_gb_str(v.free_bytes))
        return ", ".join(free)

    # --- QAbstractTableModel 接口 ---
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

    # --- 数据操作 ---
    def set_devices(self, devices: Iterable[DeviceItem]) -> None:
        self.beginResetModel()
        self._devices = [_to_device_row(d) for d in devices]
        self.endResetModel()

    def device_at(self, row: int) -> Optional[DeviceRow]:
        if 0 <= row < len(self._devices):
            return self._devices[row]
        return None


class DeviceInfoListWidget(QWidget):
    """设备信息列表控件，基于表格布局，适配 Overview 页。"""

    device_activated = Signal(object, object)  # (UsbBaseDeviceInfo, Optional[UsbStorageDeviceInfo])
    selection_changed = Signal(
        object, object
    )  # (UsbBaseDeviceInfo | None, UsbStorageDeviceInfo | None)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._table = QTableView(self)
        self._model = _DeviceInfoTableModel()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.doubleClicked.connect(self._emit_device_activated)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)
        self.setLayout(layout)

    # --- 公共 API ---
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

    # --- 信号处理 ---
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
