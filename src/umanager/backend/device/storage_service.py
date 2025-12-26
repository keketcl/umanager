from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

import wmi

from .base_service import UsbBaseDeviceService
from .protocol import (
    DeviceEjectResult,
    UsbDeviceId,
    UsbStorageDeviceInfo,
    UsbStorageDeviceProtocol,
    UsbVolumeInfo,
)
from .registry import RegistryDeviceUtil


class _WmiDiskDrive(Protocol):
    PNPDeviceID: str


class _PnPEntity(Protocol):
    PNPDeviceID: str
    HardwareID: Optional[list[str]]


class _WmiDiskPartition(Protocol):
    pass


class _WmiLogicalDisk(Protocol):
    DeviceID: Optional[str]
    FileSystem: Optional[str]
    VolumeName: Optional[str]
    Size: Optional[str]
    FreeSpace: Optional[str]


@dataclass(frozen=True, slots=True)
class _StorageScanResult:
    device_ids: list[UsbDeviceId]
    volumes_by_instance_id: dict[str, list[UsbVolumeInfo]]


class UsbStorageDeviceService(UsbStorageDeviceProtocol):
    _wmi_provider: Any
    _base_device_service: UsbBaseDeviceService
    _usb_device_ids_cache: Optional[list[UsbDeviceId]]
    _usb_volumes_map_cache: Optional[dict[str, list[UsbVolumeInfo]]]
    _usb_disk_drives_cache: Optional[list[_WmiDiskDrive]]

    def __init__(self, base_device_service: UsbBaseDeviceService) -> None:
        self._wmi_provider = wmi.WMI()
        self._base_device_service = base_device_service
        self._usb_device_ids_cache = None
        self._usb_volumes_map_cache = None
        self._usb_disk_drives_cache = None

    def refresh(self) -> None:
        self._base_device_service.refresh()

        self._usb_device_ids_cache = None
        self._usb_volumes_map_cache = None
        self._usb_disk_drives_cache = None

    def list_storage_device_ids(self) -> list[UsbDeviceId]:
        return self._get_usb_device_ids()

    def get_storage_device_info(self, device_id: UsbDeviceId) -> UsbStorageDeviceInfo:
        if not any(d.instance_id == device_id.instance_id for d in self._get_usb_device_ids()):
            raise FileNotFoundError(f"USB storage device not found: {device_id.instance_id}")

        base = self._base_device_service.get_base_device_info(device_id)
        volumes = self._get_usb_volumes_map().get(device_id.instance_id, [])
        return UsbStorageDeviceInfo(base=base, volumes=volumes)

    def eject_storage_device(self, device_id: UsbDeviceId) -> DeviceEjectResult:
        if not any(d.instance_id == device_id.instance_id for d in self._get_usb_device_ids()):
            raise FileNotFoundError(f"USB storage device not found: {device_id.instance_id}")

        result = RegistryDeviceUtil.request_device_eject(device_id.instance_id)
        if result.success:
            self.refresh()
        return result

    def _get_usb_device_ids(self) -> list[UsbDeviceId]:
        if not self._usb_device_ids_cache:
            scan = self._scan_usb_storage_devices_uncached()
            self._usb_device_ids_cache = scan.device_ids
            self._usb_device_ids_cache.sort(key=lambda d: d.instance_id.casefold())
            self._usb_volumes_map_cache = scan.volumes_by_instance_id

        return self._usb_device_ids_cache

    def _get_usb_volumes_map(self) -> dict[str, list[UsbVolumeInfo]]:
        if not self._usb_volumes_map_cache:
            scan = self._scan_usb_storage_devices_uncached()
            self._usb_volumes_map_cache = scan.volumes_by_instance_id
            self._usb_device_ids_cache = scan.device_ids
            self._usb_device_ids_cache.sort(key=lambda d: d.instance_id.casefold())

        return self._usb_volumes_map_cache

    def _get_usb_disk_drives(self) -> list[_WmiDiskDrive]:
        if not self._usb_disk_drives_cache:
            self._usb_disk_drives_cache = self._scan_usb_disk_drives_uncached()

        return self._usb_disk_drives_cache

    def _scan_usb_storage_devices_uncached(self) -> _StorageScanResult:
        entities = self._base_device_service.get_usb_pnp_entities()

        storage_instance_ids: list[str] = []
        for entity in entities:
            if self._is_usb_storage_pnp_entity(entity):
                instance_id = entity.PNPDeviceID
                storage_instance_ids.append(instance_id)

        device_ids: list[UsbDeviceId] = []
        volumes_by_instance_id: dict[str, list[UsbVolumeInfo]] = {}

        disk_volume_map: dict[str, list[UsbVolumeInfo]] = {}
        for disk in self._get_usb_disk_drives():
            instance_id = disk.PNPDeviceID
            disk_volume_map[instance_id] = self._get_volumes_for_disk(disk)

        for instance_id in storage_instance_ids:
            device_ids.append(UsbDeviceId(instance_id=instance_id))
            volumes_by_instance_id[instance_id] = disk_volume_map.get(instance_id, [])

        return _StorageScanResult(
            device_ids=device_ids,
            volumes_by_instance_id=volumes_by_instance_id,
        )

    def _is_usb_storage_pnp_entity(self, entity: _PnPEntity) -> bool:
        instance_id = entity.PNPDeviceID
        if instance_id.upper().startswith("USBSTOR\\"):
            return True

        hardware_ids = getattr(entity, "HardwareID", None) or []
        for hid in hardware_ids:
            if str(hid).upper().startswith("USBSTOR\\"):
                return True

        return False

    def _scan_usb_disk_drives_uncached(self) -> list[_WmiDiskDrive]:
        return self._wmi_provider.Win32_DiskDrive(InterfaceType="USB")

    def _get_volumes_for_disk(self, disk: _WmiDiskDrive) -> list[UsbVolumeInfo]:
        volumes: list[UsbVolumeInfo] = []

        try:
            partitions = disk.associators("Win32_DiskDriveToDiskPartition")  # type: ignore[attr-defined]
        except Exception:
            partitions = []

        for part in partitions or []:
            volumes.extend(self._get_volumes_for_partition(part))

        volumes.sort(key=lambda v: (v.drive_letter or "").casefold())
        return volumes

    def _get_volumes_for_partition(self, partition: _WmiDiskPartition) -> list[UsbVolumeInfo]:
        logical_disks: list[_WmiLogicalDisk]
        try:
            logical_disks = list(
                partition.associators("Win32_LogicalDiskToPartition")  # type: ignore[attr-defined]
            )
        except Exception:
            logical_disks = []

        res: list[UsbVolumeInfo] = []
        for ld in logical_disks:
            drive = getattr(ld, "DeviceID", None)
            if drive:
                mount_path = Path(f"{drive}\\")
            else:
                mount_path = None

            total_bytes = self._parse_optional_int(getattr(ld, "Size", None))
            free_bytes = self._parse_optional_int(getattr(ld, "FreeSpace", None))

            res.append(
                UsbVolumeInfo(
                    drive_letter=drive,
                    mount_path=mount_path,
                    file_system=getattr(ld, "FileSystem", None),
                    volume_label=getattr(ld, "VolumeName", None),
                    total_bytes=total_bytes,
                    free_bytes=free_bytes,
                )
            )

        return res

    def _parse_optional_int(self, value: object) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            s = str(value).strip()
            if not s:
                return None
            return int(s)
        except Exception:
            return None
