from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("ClassGuid", _GUID),
        ("DevInst", ctypes.c_ulong),
        ("Reserved", ctypes.c_void_p),
    ]


@dataclass(frozen=True, slots=True)
class _SetupApiFunctions:
    SetupDiGetClassDevsW: Callable[..., int]
    SetupDiEnumDeviceInfo: Callable[..., bool]
    SetupDiGetDeviceInstanceIdW: Callable[..., bool]
    SetupDiGetDeviceRegistryPropertyW: Callable[..., bool]
    SetupDiDestroyDeviceInfoList: Callable[..., bool]


class RegistryDeviceUtil:
    DIGCF_PRESENT = 0x00000002
    DIGCF_ALLCLASSES = 0x00000004

    # SetupAPI registry-backed device property ids.
    SPDRP_LOCATION_INFORMATION = 0x0000000D
    SPDRP_BUSNUMBER = 0x00000015

    _fns: _SetupApiFunctions | None = None

    @classmethod
    def get_device_location_information(cls, instance_id: str) -> Optional[str]:
        return cls._setupapi_get_device_property_string(
            instance_id,
            cls.SPDRP_LOCATION_INFORMATION,
        )

    @classmethod
    def get_device_bus_number(cls, instance_id: str) -> Optional[int]:
        return cls._setupapi_get_device_property_dword(instance_id, cls.SPDRP_BUSNUMBER)

    @classmethod
    def _setupapi_get_device_property_string(cls, instance_id: str, prop: int) -> Optional[str]:
        raw = cls._setupapi_get_device_property_raw(instance_id, prop)
        if raw is None:
            return None
        return raw.decode("utf-16le", errors="ignore").rstrip("\x00") or None

    @classmethod
    def _setupapi_get_device_property_dword(cls, instance_id: str, prop: int) -> Optional[int]:
        raw = cls._setupapi_get_device_property_raw(instance_id, prop)
        if raw is None or len(raw) < 4:
            return None
        return int.from_bytes(raw[:4], byteorder="little", signed=False)

    @classmethod
    def _normalize_instance_id(cls, instance_id: str) -> str:
        return instance_id.replace("\\\\", "\\")

    @classmethod
    def _get_setupapi_functions(cls) -> _SetupApiFunctions:
        if cls._fns is not None:
            return cls._fns

        setupapi = ctypes.WinDLL("setupapi", use_last_error=True)

        SetupDiGetClassDevsW = setupapi.SetupDiGetClassDevsW
        SetupDiGetClassDevsW.argtypes = [
            ctypes.POINTER(_GUID),
            ctypes.c_wchar_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        SetupDiGetClassDevsW.restype = ctypes.c_void_p

        SetupDiEnumDeviceInfo = setupapi.SetupDiEnumDeviceInfo
        SetupDiEnumDeviceInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(_SP_DEVINFO_DATA),
        ]
        SetupDiEnumDeviceInfo.restype = ctypes.c_bool

        SetupDiGetDeviceInstanceIdW = setupapi.SetupDiGetDeviceInstanceIdW
        SetupDiGetDeviceInstanceIdW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_SP_DEVINFO_DATA),
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        SetupDiGetDeviceInstanceIdW.restype = ctypes.c_bool

        SetupDiGetDeviceRegistryPropertyW = setupapi.SetupDiGetDeviceRegistryPropertyW
        SetupDiGetDeviceRegistryPropertyW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_SP_DEVINFO_DATA),
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

        cls._fns = _SetupApiFunctions(
            SetupDiGetClassDevsW=SetupDiGetClassDevsW,
            SetupDiEnumDeviceInfo=SetupDiEnumDeviceInfo,
            SetupDiGetDeviceInstanceIdW=SetupDiGetDeviceInstanceIdW,
            SetupDiGetDeviceRegistryPropertyW=SetupDiGetDeviceRegistryPropertyW,
            SetupDiDestroyDeviceInfoList=SetupDiDestroyDeviceInfoList,
        )
        return cls._fns

    @classmethod
    def _open_device_info_set(cls) -> Optional[int]:
        fns = cls._get_setupapi_functions()
        flags = cls.DIGCF_PRESENT | cls.DIGCF_ALLCLASSES
        hdevinfo = fns.SetupDiGetClassDevsW(None, None, None, flags)
        if not hdevinfo or hdevinfo == ctypes.c_void_p(-1).value:
            return None
        return int(hdevinfo)

    @classmethod
    def _iter_devinfo_data(cls, hdevinfo: int):
        fns = cls._get_setupapi_functions()

        index = 0
        while True:
            devinfo = _SP_DEVINFO_DATA()
            devinfo.cbSize = ctypes.sizeof(_SP_DEVINFO_DATA)
            if not fns.SetupDiEnumDeviceInfo(hdevinfo, index, ctypes.byref(devinfo)):
                break
            index += 1
            yield devinfo

    @classmethod
    def _get_device_instance_id(cls, hdevinfo: int, devinfo: _SP_DEVINFO_DATA) -> Optional[str]:
        fns = cls._get_setupapi_functions()

        required = ctypes.c_ulong(0)
        fns.SetupDiGetDeviceInstanceIdW(
            hdevinfo,
            ctypes.byref(devinfo),
            None,
            0,
            ctypes.byref(required),
        )
        if required.value == 0:
            return None

        buf = ctypes.create_unicode_buffer(required.value)
        if not fns.SetupDiGetDeviceInstanceIdW(
            hdevinfo,
            ctypes.byref(devinfo),
            buf,
            required.value,
            ctypes.byref(required),
        ):
            return None

        return buf.value

    @classmethod
    def _query_registry_property_bytes(
        cls,
        hdevinfo: int,
        devinfo: _SP_DEVINFO_DATA,
        prop: int,
    ) -> Optional[bytes]:
        fns = cls._get_setupapi_functions()

        data_type = ctypes.c_ulong(0)
        required_size = ctypes.c_ulong(0)
        fns.SetupDiGetDeviceRegistryPropertyW(
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
        if not fns.SetupDiGetDeviceRegistryPropertyW(
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

    @classmethod
    def _setupapi_get_device_property_raw(cls, instance_id: str, prop: int) -> Optional[bytes]:
        instance_id = cls._normalize_instance_id(instance_id)
        fns = cls._get_setupapi_functions()

        hdevinfo = cls._open_device_info_set()
        if hdevinfo is None:
            return None

        try:
            for devinfo in cls._iter_devinfo_data(hdevinfo):
                current_id = cls._get_device_instance_id(hdevinfo, devinfo)
                if current_id is None:
                    continue

                if current_id.casefold() != instance_id.casefold():
                    continue

                return cls._query_registry_property_bytes(hdevinfo, devinfo, prop)
            return None
        finally:
            fns.SetupDiDestroyDeviceInfoList(hdevinfo)
