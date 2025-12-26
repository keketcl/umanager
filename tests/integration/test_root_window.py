import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from umanager.backend.device import UsbBaseDeviceService, UsbStorageDeviceService
from umanager.backend.filesystem.service import FileSystemService
from umanager.ui.views import RootWindowView

if __name__ == "__main__":
    app = QApplication([])

    auto_quit_ms = int(os.getenv("UMANAGER_AUTO_QUIT_MS", "0"))
    if auto_quit_ms > 0:
        QTimer.singleShot(auto_quit_ms, app.quit)

    base_service = UsbBaseDeviceService()
    storage_service = UsbStorageDeviceService(base_service)
    filesystem = FileSystemService()

    window = RootWindowView(
        base_service=base_service,
        storage_service=storage_service,
        filesystem=filesystem,
    )
    window.setWindowTitle("USB Manager - RootWindow")

    mainarea = window.main_area()
    sm = mainarea.state_manager()

    last: dict[str, object] = {
        "is_scanning": None,
        "device_count": None,
        "devices_len": None,
        "storages_len": None,
        "last_operation": None,
    }

    def on_state_changed(state: object) -> None:
        if not hasattr(state, "is_scanning"):
            return

        is_scanning = getattr(state, "is_scanning")
        device_count = getattr(state, "device_count")
        devices = getattr(state, "devices")
        storages = getattr(state, "storages")
        last_operation = getattr(state, "last_operation")
        last_operation_error = getattr(state, "last_operation_error")

        if last["is_scanning"] != is_scanning:
            print(f"[RootWindow/MainArea] 扫描中: {is_scanning}")
            last["is_scanning"] = is_scanning

        if last["device_count"] != device_count:
            print(f"[RootWindow/MainArea] 设备数量: {device_count}")
            last["device_count"] = device_count

        devices_len = len(devices) if devices is not None else 0
        if last["devices_len"] != devices_len:
            print(f"[RootWindow/MainArea] 设备列表更新，共 {devices_len} 项")
            last["devices_len"] = devices_len

        storages_len = len(storages) if storages is not None else 0
        if last["storages_len"] != storages_len:
            print(f"[RootWindow/MainArea] 存储设备数量: {storages_len}")
            last["storages_len"] = storages_len

        if last_operation is not None and last_operation != last["last_operation"]:
            if last_operation == "refresh":
                if last_operation_error is None:
                    print("[RootWindow/MainArea] 刷新完成")
                else:
                    print(f"[RootWindow/MainArea] 刷新失败: {last_operation_error}")
            last["last_operation"] = last_operation

    sm.stateChanged.connect(on_state_changed)

    window.resize(1200, 760)
    window.show()

    app.exec()
