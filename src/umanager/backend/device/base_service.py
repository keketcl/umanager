from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Protocol

import wmi

from .protocol import UsbBaseDeviceInfo, UsbBaseDeviceProtocol, UsbDeviceId
from .registry import RegistryDeviceUtil


class PnPEntity(Protocol):
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
    _cached_usb_pnp_entities: list[PnPEntity] = []

    def __init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self._cached_usb_pnp_entities = self._scan_usb_pnp_entities_uncached()

    def list_base_device_ids(self) -> list[UsbDeviceId]:
        entities = self.get_usb_pnp_entities()
        res = [UsbDeviceId(instance_id=e.PNPDeviceID) for e in entities]

        res.sort(key=lambda d: d.instance_id.casefold())
        return res

    def get_base_device_info(self, device_id: UsbDeviceId) -> UsbBaseDeviceInfo:
        entity: PnPEntity | None = None
        for candidate in self.get_usb_pnp_entities():
            if getattr(candidate, "PNPDeviceID", None) == device_id.instance_id:
                entity = candidate
                break
        if entity is None:
            raise FileNotFoundError(f"USB device not found: {device_id.instance_id}")

        parsed = self._parse_usb_ids(device_id.instance_id)
        vendor_id = parsed.vendor_id
        product_id = parsed.product_id
        if vendor_id is None or product_id is None:
            fallback_vendor_id, fallback_product_id = RegistryDeviceUtil.get_usb_vendor_product_id(
                device_id.instance_id
            )
            vendor_id = vendor_id or fallback_vendor_id
            product_id = product_id or fallback_product_id
        manufacturer = getattr(entity, "Manufacturer", None)
        name = getattr(entity, "Name", None)
        description = getattr(entity, "Description", None)

        location_information = RegistryDeviceUtil.get_device_location_information(
            device_id.instance_id
        )
        bus_number = RegistryDeviceUtil.get_device_bus_number(device_id.instance_id)
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
            vendor_id=vendor_id,
            product_id=product_id,
            manufacturer=manufacturer,
            product=name,
            serial_number=parsed.serial_number,
            bus_number=bus_number,
            port_number=port_number,
            usb_version=usb_version,
            speed_mbps=speed_mbps,
            description=description or name,
        )

    def get_usb_pnp_entities(self) -> list[PnPEntity]:
        return self._cached_usb_pnp_entities

    def _scan_usb_pnp_entities_uncached(self) -> list[PnPEntity]:
        entities: list[PnPEntity] = []

        for candidate in self._wmi_provider.Win32_PnPEntity():
            instance_id = getattr(candidate, "PNPDeviceID", None)
            if not instance_id:
                continue

            if not self._is_usb_candidate(candidate):
                continue
            entities.append(candidate)

        return entities

    def _is_usb_candidate(self, candidate: PnPEntity) -> bool:
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
