from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from umanager.backend.device import UsbBaseDeviceInfo, UsbStorageDeviceInfo, UsbVolumeInfo


class DeviceDetailDialog(QDialog):
    def __init__(
        self,
        base: UsbBaseDeviceInfo,
        storage: Optional[UsbStorageDeviceInfo] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("设备详细信息")

        layout = QVBoxLayout(self)

        for label, value in self._build_base_lines(base):
            layout.addWidget(QLabel(f"{label}: {value}"))

        if storage is not None:
            for line in self._build_storage_lines(storage):
                layout.addWidget(QLabel(line))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok, parent=self)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _fmt(val: object, default: str = "-") -> str:
        return str(val) if val not in (None, "") else default

    @staticmethod
    def _fmt_hex(val: Optional[str]) -> str:
        if val is None:
            return "-"
        if val.lower().startswith("0x"):
            return val
        return f"0x{val}"

    @staticmethod
    def _fmt_speed(speed: Optional[float]) -> str:
        if speed is None:
            return "-"
        return f"{speed:.0f} Mbps"

    @staticmethod
    def _fmt_bytes(val: Optional[int]) -> str:
        if val is None:
            return "-"
        gb = val / (1024**3)
        return f"{gb:.1f} GB"

    def _build_base_lines(self, base: UsbBaseDeviceInfo) -> list[tuple[str, str]]:
        return [
            ("产品", self._fmt(base.product)),
            ("制造商", self._fmt(base.manufacturer)),
            ("序列号", self._fmt(base.serial_number)),
            ("厂商 ID", self._fmt_hex(base.vendor_id)),
            ("产品 ID", self._fmt_hex(base.product_id)),
            ("USB 版本", self._fmt(base.usb_version)),
            ("速度", self._fmt_speed(base.speed_mbps)),
            ("总线号", self._fmt(base.bus_number)),
            ("端口号", self._fmt(base.port_number)),
            ("描述", self._fmt(base.description)),
        ]

    def _build_storage_lines(self, storage: UsbStorageDeviceInfo) -> list[str]:
        lines: list[str] = []
        for idx, vol in enumerate(storage.volumes):
            prefix = f"卷 {idx + 1}"
            lines.append(prefix)
            lines.append(f"  卷标: {self._fmt(vol.volume_label)}")
            lines.append(f"  文件系统: {self._fmt(vol.file_system)}")
            lines.append(f"  盘符: {self._fmt(self._format_mount(vol))}")
            lines.append(f"  剩余容量: {self._fmt_bytes(vol.free_bytes)}")
            lines.append(f"  总容量: {self._fmt_bytes(vol.total_bytes)}")
        return lines

    @staticmethod
    def _format_mount(vol: UsbVolumeInfo) -> str:
        if vol.drive_letter:
            return vol.drive_letter
        if vol.mount_path:
            return str(vol.mount_path)
        return "-"
