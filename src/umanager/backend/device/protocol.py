from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol


@dataclass(frozen=True, slots=True)
class DeviceEjectResult:
    success: bool
    attempted_instance_id: str
    config_ret: int
    veto_type: Optional[int] = None
    veto_name: Optional[str] = None


@dataclass(frozen=True, slots=True)
class UsbDeviceId:
    instance_id: str


@dataclass(frozen=True, slots=True)
class UsbBaseDeviceInfo:
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


class UsbBaseDeviceProtocol(Protocol):
    def refresh(self) -> None: ...

    def get_base_device_info(self, device_id: UsbDeviceId) -> UsbBaseDeviceInfo: ...

    def list_base_device_ids(self) -> list[UsbDeviceId]: ...


@dataclass(frozen=True, slots=True)
class UsbVolumeInfo:
    drive_letter: Optional[str] = None
    mount_path: Optional[Path] = None
    file_system: Optional[str] = None
    volume_label: Optional[str] = None
    total_bytes: Optional[int] = None
    free_bytes: Optional[int] = None


@dataclass(frozen=True, slots=True)
class UsbStorageDeviceInfo:
    base: UsbBaseDeviceInfo
    volumes: list[UsbVolumeInfo] = field(default_factory=list)


class UsbStorageDeviceProtocol(Protocol):
    def refresh(self) -> None: ...

    def get_storage_device_info(self, device_id: UsbDeviceId) -> UsbStorageDeviceInfo: ...

    def list_storage_device_ids(self) -> list[UsbDeviceId]: ...

    def eject_storage_device(self, device_id: UsbDeviceId) -> DeviceEjectResult: ...
