from __future__ import annotations

import ctypes
import re
from dataclasses import dataclass
from typing import Optional, Protocol

import wmi

from .protocol import UsbBaseDeviceInfo, UsbBaseDeviceProtocol, UsbDeviceId


class _PnPEntity(Protocol):
    PNPDeviceID: str
    Name: Optional[str]
    Manufacturer: Optional[str]
    Description: Optional[str]
    Caption: Optional[str]
    Service: Optional[str]
    PNPClass: Optional[str]
    CompatibleID: Optional[list[str]]
    HardwareID: Optional[list[str]]


@dataclass(frozen=True, slots=True)
class _ParsedUsbIds:
    vendor_id: Optional[str]
    product_id: Optional[str]
    serial_number: Optional[str]


class UsbBaseDeviceService(UsbBaseDeviceProtocol):
    _VID_PATTERN = re.compile(r"VID_([0-9A-Fa-f]{4})")
    _PID_PATTERN = re.compile(r"PID_([0-9A-Fa-f]{4})")

    _wmi_provider = wmi.WMI()

    def list_base_device_ids(self) -> list[UsbDeviceId]:
        entities = self._scan_usb_pnp_entities()
        res = [UsbDeviceId(instance_id=e.PNPDeviceID) for e in entities]

        res.sort(key=lambda d: d.instance_id.casefold())
        return res

    def get_base_device_info(self, device_id: UsbDeviceId) -> UsbBaseDeviceInfo:
        entity: _PnPEntity | None = None
        for candidate in self._scan_usb_pnp_entities():
            if getattr(candidate, "PNPDeviceID", None) == device_id.instance_id:
                entity = candidate
                break
        if entity is None:
            raise FileNotFoundError(f"USB device not found: {device_id.instance_id}")

        parsed = self._parse_usb_ids(device_id.instance_id)
        manufacturer = getattr(entity, "Manufacturer", None)
        name = getattr(entity, "Name", None)
        description = getattr(entity, "Description", None)

        location_information = self._get_device_location_information(device_id.instance_id)
        bus_number = self._get_device_bus_number(device_id.instance_id)
        _, port_number = self._parse_bus_port(location_information)

        compatible_ids = getattr(entity, "CompatibleID", None)
        service = getattr(entity, "Service", None)
        caption = getattr(entity, "Caption", None)
        usb_version, speed_mbps = self._infer_usb_speed(
            compatible_ids=compatible_ids,
            service=service or "<unknown-service>",
            name=name or "<unknown-name>",
            description=description or "<unknown-description>",
            caption=caption or "<unknown-caption>",
        )

        return UsbBaseDeviceInfo(
            id=device_id,
            vendor_id=parsed.vendor_id,
            product_id=parsed.product_id,
            manufacturer=manufacturer,
            product=name,
            serial_number=parsed.serial_number,
            bus_number=bus_number,
            port_number=port_number,
            usb_version=usb_version,
            speed_mbps=speed_mbps,
            description=description or name,
        )

    def _get_device_location_information(self, instance_id: str) -> Optional[str]:
        # Maps to DEVPKEY_Device_LocationInfo (SPDRP_LOCATION_INFORMATION).
        SPDRP_LOCATION_INFORMATION = 0x0000000D
        return self._setupapi_get_device_property_string(
            instance_id,
            SPDRP_LOCATION_INFORMATION,
        )

    def _get_device_bus_number(self, instance_id: str) -> Optional[int]:
        # Maps to SPDRP_BUSNUMBER.
        SPDRP_BUSNUMBER = 0x00000015
        return self._setupapi_get_device_property_dword(instance_id, SPDRP_BUSNUMBER)

    def _setupapi_get_device_property_string(self, instance_id: str, prop: int) -> Optional[str]:
        raw = self._setupapi_get_device_property_raw(instance_id, prop)
        if raw is None:
            return None
        # REG_SZ UTF-16LE string, null-terminated.
        return raw.decode("utf-16le", errors="ignore").rstrip("\x00") or None

    def _setupapi_get_device_property_dword(self, instance_id: str, prop: int) -> Optional[int]:
        raw = self._setupapi_get_device_property_raw(instance_id, prop)
        if raw is None or len(raw) < 4:
            return None
        return int.from_bytes(raw[:4], byteorder="little", signed=False)

    def _setupapi_get_device_property_raw(self, instance_id: str, prop: int) -> Optional[bytes]:
        # Use SetupDi* to locate the device by instance ID and query SPDRP_* properties.
        instance_id = instance_id.replace("\\\\", "\\")

        DIGCF_PRESENT = 0x00000002
        DIGCF_ALLCLASSES = 0x00000004

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_ulong),
                ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        class SP_DEVINFO_DATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("ClassGuid", GUID),
                ("DevInst", ctypes.c_ulong),
                ("Reserved", ctypes.c_void_p),
            ]

        setupapi = ctypes.WinDLL("setupapi", use_last_error=True)

        SetupDiGetClassDevsW = setupapi.SetupDiGetClassDevsW
        SetupDiGetClassDevsW.argtypes = [
            ctypes.POINTER(GUID),
            ctypes.c_wchar_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        SetupDiGetClassDevsW.restype = ctypes.c_void_p

        SetupDiEnumDeviceInfo = setupapi.SetupDiEnumDeviceInfo
        SetupDiEnumDeviceInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(SP_DEVINFO_DATA),
        ]
        SetupDiEnumDeviceInfo.restype = ctypes.c_bool

        SetupDiGetDeviceInstanceIdW = setupapi.SetupDiGetDeviceInstanceIdW
        SetupDiGetDeviceInstanceIdW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(SP_DEVINFO_DATA),
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        SetupDiGetDeviceInstanceIdW.restype = ctypes.c_bool

        SetupDiGetDeviceRegistryPropertyW = setupapi.SetupDiGetDeviceRegistryPropertyW
        SetupDiGetDeviceRegistryPropertyW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(SP_DEVINFO_DATA),
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        SetupDiGetDeviceRegistryPropertyW.restype = ctypes.c_bool

        SetupDiDestroyDeviceInfoList = setupapi.SetupDiDestroyDeviceInfoList
        SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
        SetupDiDestroyDeviceInfoList.restype = ctypes.c_bool

        hdevinfo = SetupDiGetClassDevsW(None, None, None, DIGCF_PRESENT | DIGCF_ALLCLASSES)
        if not hdevinfo or hdevinfo == ctypes.c_void_p(-1).value:
            return None

        try:
            index = 0
            devinfo = SP_DEVINFO_DATA()
            devinfo.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)

            while SetupDiEnumDeviceInfo(hdevinfo, index, ctypes.byref(devinfo)):
                index += 1

                required = ctypes.c_ulong(0)
                SetupDiGetDeviceInstanceIdW(
                    hdevinfo,
                    ctypes.byref(devinfo),
                    None,
                    0,
                    ctypes.byref(required),
                )
                if required.value == 0:
                    continue

                buf = ctypes.create_unicode_buffer(required.value)
                if not SetupDiGetDeviceInstanceIdW(
                    hdevinfo,
                    ctypes.byref(devinfo),
                    buf,
                    required.value,
                    ctypes.byref(required),
                ):
                    continue

                current_id = buf.value
                if current_id.casefold() != instance_id.casefold():
                    continue

                data_type = ctypes.c_ulong(0)
                required_size = ctypes.c_ulong(0)
                SetupDiGetDeviceRegistryPropertyW(
                    hdevinfo,
                    ctypes.byref(devinfo),
                    prop,
                    ctypes.byref(data_type),
                    None,
                    0,
                    ctypes.byref(required_size),
                )

                if required_size.value == 0:
                    return None

                data = (ctypes.c_ubyte * required_size.value)()
                if not SetupDiGetDeviceRegistryPropertyW(
                    hdevinfo,
                    ctypes.byref(devinfo),
                    prop,
                    ctypes.byref(data_type),
                    ctypes.byref(data),
                    required_size.value,
                    ctypes.byref(required_size),
                ):
                    return None

                return bytes(data)

            return None
        finally:
            SetupDiDestroyDeviceInfoList(hdevinfo)

    def _scan_usb_pnp_entities(self) -> list[_PnPEntity]:
        entities: list[_PnPEntity] = []

        # Scan all devices first, then filter in Python.
        for candidate in self._wmi_provider.Win32_PnPEntity():
            instance_id = getattr(candidate, "PNPDeviceID", None)
            if not instance_id:
                continue

            if not self._is_usb_candidate(candidate):
                continue
            entities.append(candidate)

        return entities

    def _is_usb_candidate(self, candidate: _PnPEntity) -> bool:
        instance_id = str(getattr(candidate, "PNPDeviceID", "") or "")
        if instance_id.startswith("USB"):
            return True

        pnp_class = getattr(candidate, "PNPClass", None)
        if pnp_class and pnp_class.upper() == "USB":
            return True

        hardware_ids = getattr(candidate, "HardwareID", None) or []
        for hid in hardware_ids:
            if hid.startswith("USB\\") or hid.startswith("USBSTOR\\"):
                return True

        compatible_ids = getattr(candidate, "CompatibleID", None) or []
        for cid in compatible_ids:
            if cid.startswith("USB\\"):
                return True

        return False

    def _parse_usb_ids(self, instance_id: str) -> _ParsedUsbIds:
        vid_match = self._VID_PATTERN.search(instance_id)
        vendor_id = vid_match.group(1).upper() if vid_match else None

        pid_match = self._PID_PATTERN.search(instance_id)
        product_id = pid_match.group(1).upper() if pid_match else None

        serial_number: Optional[str] = None
        # Typical formats:
        # - USB\VID_XXXX&PID_YYYY\<serial or location string>
        # - USBSTOR\DISK&VEN_...\<serial or location string>
        parts = instance_id.split("\\\\")
        if len(parts) < 3:
            parts = instance_id.split("\\")
        if len(parts) >= 3 and parts[-1]:
            serial_number = parts[-1]

        return _ParsedUsbIds(
            vendor_id=vendor_id,
            product_id=product_id,
            serial_number=serial_number,
        )

    def _parse_bus_port(
        self,
        location_information: Optional[str],
    ) -> tuple[Optional[int], Optional[int]]:
        if not location_information:
            return None, None

        # Common formats:
        # - "Port_#0004.Hub_#0001"
        # - "Port_#0001.Hub_#0002"
        # Some devices may report different human-readable strings.
        port_number: Optional[int] = None
        bus_number: Optional[int] = None

        port_match = re.search(r"Port_#(\d+)", location_information)
        if port_match:
            port_number = int(port_match.group(1))

        hub_match = re.search(r"Hub_#(\d+)", location_information)
        if hub_match:
            bus_number = int(hub_match.group(1))

        return bus_number, port_number

    def _infer_usb_speed(
        self,
        *,
        compatible_ids: Optional[list[str]],
        service: str,
        name: str,
        description: str,
        caption: str,
    ) -> tuple[Optional[str], Optional[float]]:
        text = " ".join([t for t in [name, description, caption, service] if t])
        compatible = " ".join(compatible_ids or [])

        if (
            "USB30" in compatible.upper()
            or "USBHUB3" in (service or "").upper()
            or "SUPERSPEED" in text.upper()
            or "3.0" in name.upper()
        ):
            return "3.0", 5000.0
        elif "SUPERSPEEDPLUS" in text.upper():
            return "3.1", 10000.0
        elif "HIGH-SPEED" in text.upper() or "HIGHSPEED" in text.upper():
            return "2.0", 480.0
        elif "FULL-SPEED" in text.upper() or "FULLSPEED" in text.upper():
            return "1.1", 12.0
        elif "LOW-SPEED" in text.upper() or "LOWSPEED" in text.upper():
            return "1.0", 1.5
        else:
            return None, None
