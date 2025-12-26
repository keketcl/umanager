from __future__ import annotations

import ctypes
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from .protocol import DeviceEjectResult


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

    SPDRP_LOCATION_INFORMATION = 0x0000000D
    SPDRP_BUSNUMBER = 0x00000015

    _fns: _SetupApiFunctions | None = None
    _cfg_fns: "_CfgMgr32Functions | None" = None

    _VID_PATTERN = re.compile(r"VID_([0-9A-Fa-f]{4})")
    _PID_PATTERN = re.compile(r"PID_([0-9A-Fa-f]{4})")

    @classmethod
    def get_device_location_information(cls, instance_id: str) -> Optional[str]:
        return cls._setupapi_get_device_property_string_with_parent_fallback(
            instance_id,
            cls.SPDRP_LOCATION_INFORMATION,
        )

    @classmethod
    def get_device_bus_number(cls, instance_id: str) -> Optional[int]:
        return cls._setupapi_get_device_property_dword_with_parent_fallback(
            instance_id,
            cls.SPDRP_BUSNUMBER,
        )

    @classmethod
    def get_usb_vendor_product_id(cls, instance_id: str) -> tuple[Optional[str], Optional[str]]:
        vendor_id: Optional[str] = None
        product_id: Optional[str] = None

        for candidate_id in cls._iter_instance_id_with_ancestors(instance_id):
            if vendor_id is None:
                vid_match = cls._VID_PATTERN.search(candidate_id)
                if vid_match:
                    vendor_id = vid_match.group(1).upper()

            if product_id is None:
                pid_match = cls._PID_PATTERN.search(candidate_id)
                if pid_match:
                    product_id = pid_match.group(1).upper()

            if vendor_id is not None and product_id is not None:
                break

        return vendor_id, product_id

    @classmethod
    def _setupapi_get_device_property_string_with_parent_fallback(
        cls,
        instance_id: str,
        prop: int,
    ) -> Optional[str]:
        for candidate_id in cls._iter_instance_id_with_ancestors(instance_id):
            val = cls._setupapi_get_device_property_string(candidate_id, prop)
            if val is not None:
                return val
        return None

    @classmethod
    def _setupapi_get_device_property_dword_with_parent_fallback(
        cls,
        instance_id: str,
        prop: int,
    ) -> Optional[int]:
        for candidate_id in cls._iter_instance_id_with_ancestors(instance_id):
            val = cls._setupapi_get_device_property_dword(candidate_id, prop)
            if val is not None:
                return val
        return None

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

    @dataclass(frozen=True, slots=True)
    class _CfgMgr32Functions:
        CM_Locate_DevNodeW: Callable[..., int]
        CM_Get_Parent: Callable[..., int]
        CM_Get_Device_IDW: Callable[..., int]
        CM_Request_Device_EjectW: Callable[..., int]

    # cfgmgr32 constants
    _CR_SUCCESS = 0x00000000
    _CR_REMOVE_VETOED = 0x00000017
    _CM_LOCATE_DEVNODE_NORMAL = 0x00000000

    # PNP_VETO_TYPE values (subset)
    PNP_VetoTypeUnknown = 0
    PNP_VetoLegacyDevice = 1
    PNP_VetoPendingClose = 2
    PNP_VetoWindowsApp = 3
    PNP_VetoWindowsService = 4
    PNP_VetoOutstandingOpen = 5
    PNP_VetoDevice = 6
    PNP_VetoDriver = 7
    PNP_VetoIllegalDeviceRequest = 8
    PNP_VetoInsufficientPower = 9
    PNP_VetoNonDisableable = 10
    PNP_VetoLegacyDriver = 11
    PNP_VetoInsufficientRights = 12

    @classmethod
    def _get_cfgmgr32_functions(cls) -> "_CfgMgr32Functions":
        if cls._cfg_fns is not None:
            return cls._cfg_fns

        cfg = ctypes.WinDLL("cfgmgr32", use_last_error=True)

        CM_Locate_DevNodeW = cfg.CM_Locate_DevNodeW
        CM_Locate_DevNodeW.argtypes = [
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_wchar_p,
            ctypes.c_ulong,
        ]
        CM_Locate_DevNodeW.restype = ctypes.c_ulong

        CM_Get_Parent = cfg.CM_Get_Parent
        CM_Get_Parent.argtypes = [
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        CM_Get_Parent.restype = ctypes.c_ulong

        CM_Get_Device_IDW = cfg.CM_Get_Device_IDW
        CM_Get_Device_IDW.argtypes = [
            ctypes.c_ulong,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        CM_Get_Device_IDW.restype = ctypes.c_ulong

        CM_Request_Device_EjectW = cfg.CM_Request_Device_EjectW
        CM_Request_Device_EjectW.argtypes = [
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        CM_Request_Device_EjectW.restype = ctypes.c_ulong

        cls._cfg_fns = cls._CfgMgr32Functions(
            CM_Locate_DevNodeW=CM_Locate_DevNodeW,
            CM_Get_Parent=CM_Get_Parent,
            CM_Get_Device_IDW=CM_Get_Device_IDW,
            CM_Request_Device_EjectW=CM_Request_Device_EjectW,
        )
        return cls._cfg_fns

    @classmethod
    def request_device_eject(cls, instance_id: str) -> DeviceEjectResult:
        normalized = cls._normalize_instance_id(instance_id)

        last_result = DeviceEjectResult(
            success=False,
            attempted_instance_id=normalized,
            config_ret=cls._CR_SUCCESS,
        )

        for candidate_id in cls._iter_instance_id_with_ancestors(normalized):
            res = cls._request_device_eject_single(candidate_id)
            last_result = res
            if res.success:
                return res

            # If vetoed or not removable, trying parent may help.
            # Keep going until ancestors are exhausted.

        return last_result

    @classmethod
    def _request_device_eject_single(cls, instance_id: str) -> DeviceEjectResult:
        cfg = cls._get_cfgmgr32_functions()

        devinst = ctypes.c_ulong(0)
        cr = cfg.CM_Locate_DevNodeW(
            ctypes.byref(devinst),
            cls._normalize_instance_id(instance_id),
            cls._CM_LOCATE_DEVNODE_NORMAL,
        )
        if cr != cls._CR_SUCCESS:
            return DeviceEjectResult(
                success=False,
                attempted_instance_id=instance_id,
                config_ret=int(cr),
            )

        veto_type = ctypes.c_int(0)
        veto_name_buf = ctypes.create_unicode_buffer(1024)
        cr = cfg.CM_Request_Device_EjectW(
            devinst.value,
            ctypes.byref(veto_type),
            veto_name_buf,
            ctypes.c_ulong(len(veto_name_buf)),
            ctypes.c_ulong(0),
        )

        if cr == cls._CR_SUCCESS:
            return DeviceEjectResult(
                success=True,
                attempted_instance_id=instance_id,
                config_ret=int(cr),
            )

        veto_name = veto_name_buf.value or None
        # Only meaningful when vetoed, but harmless to return for other failures.
        return DeviceEjectResult(
            success=False,
            attempted_instance_id=instance_id,
            config_ret=int(cr),
            veto_type=int(veto_type.value) if veto_type is not None else None,
            veto_name=veto_name,
        )

    @classmethod
    def _iter_instance_id_with_ancestors(cls, instance_id: str, *, max_depth: int = 10):
        normalized = cls._normalize_instance_id(instance_id)
        yield normalized

        parents = cls._get_parent_instance_ids(normalized, max_depth=max_depth)
        for p in parents:
            yield p

    @classmethod
    def _get_parent_instance_ids(cls, instance_id: str, *, max_depth: int) -> list[str]:
        cfg = cls._get_cfgmgr32_functions()

        CR_SUCCESS = 0x00000000
        CM_LOCATE_DEVNODE_NORMAL = 0x00000000

        devinst = ctypes.c_ulong(0)
        cr = cfg.CM_Locate_DevNodeW(ctypes.byref(devinst), instance_id, CM_LOCATE_DEVNODE_NORMAL)
        if cr != CR_SUCCESS:
            return []

        res: list[str] = []
        cur = devinst
        for _ in range(max_depth):
            parent = ctypes.c_ulong(0)
            cr = cfg.CM_Get_Parent(ctypes.byref(parent), cur.value, 0)
            if cr != CR_SUCCESS:
                break

            buf = ctypes.create_unicode_buffer(4096)
            cr = cfg.CM_Get_Device_IDW(parent.value, buf, len(buf), 0)
            if cr != CR_SUCCESS:
                break

            parent_id = buf.value
            if not parent_id:
                break

            res.append(parent_id)
            cur = parent

        return res

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
