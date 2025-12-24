from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol


@dataclass(frozen=True, slots=True)
class UsbDeviceId:
    instance_id: str


@dataclass(frozen=True, slots=True)
class UsbDeviceInfo:
    id: UsbDeviceId
    vendor_id: Optional[str] = None
    product_id: Optional[str] = None
    manufacturer: Optional[str] = None
    product: Optional[str] = None
    serial_number: Optional[str] = None
    bus_number: Optional[int] = None
    port_number: Optional[int] = None
    usb_version: Optional[str] = None
    speed_mbps: Optional[float] = None
    description: Optional[str] = None


class UsbDeviceProtocol(Protocol):
    def get_device_info(self, device_id: UsbDeviceId) -> UsbDeviceInfo: ...

    def list_device_ids(self) -> list[UsbDeviceId]: ...


@dataclass(frozen=True, slots=True)
class UsbVolumeInfo:
    drive_letter: Optional[str] = None
    mount_path: Optional[Path] = None
    file_system: Optional[str] = None
    volume_label: Optional[str] = None
    total_bytes: Optional[int] = None
    free_bytes: Optional[int] = None


@dataclass(frozen=True, slots=True)
class UsbStorageDeviceInfo(UsbDeviceInfo):
    volumes: list[UsbVolumeInfo] = None  # type: ignore[assignment]


class UsbStorageDeviceProtocol(Protocol):
    def get_storage_device_info(self, device_id: UsbDeviceId) -> UsbStorageDeviceInfo: ...

    def list_storage_device_ids(self) -> list[UsbDeviceId]: ...
