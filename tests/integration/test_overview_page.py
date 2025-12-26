from PySide6.QtWidgets import QApplication

from umanager.backend.device import UsbBaseDeviceService, UsbStorageDeviceService
from umanager.ui.views import OverviewPageView

if __name__ == "__main__":
    app = QApplication([])

    # 创建总览页，传递服务实例
    base_service = UsbBaseDeviceService()
    storage_service = UsbStorageDeviceService(base_service)
    overview = OverviewPageView(
        base_service=base_service,
        storage_service=storage_service,
    )
    overview.setWindowTitle("USB Manager - 总览")

    # 使用状态管理器的信号进行测试
    sm = overview.state_manager()

    # 请求类信号（由按钮或双击触发）
    sm.fileManagerRequested.connect(
        lambda base, storage: print(
            f"打开文件管理器: {getattr(base, 'product', '未知设备')}, 存储={storage is not None}"
        )
    )
    sm.detailsRequested.connect(
        lambda base, storage: print(f"查看详情: {getattr(base, 'product', '未知设备')}")
    )
    sm.ejectRequested.connect(
        lambda base, storage: print(f"安全弹出: {getattr(base, 'product', '未知设备')}")
    )

    # 状态变化：仅订阅 stateChanged
    last = {
        "is_scanning": None,
        "device_count": None,
        "devices_len": None,
        "selected": None,
        "last_operation": None,
    }

    def on_state_changed(state: object) -> None:
        if not hasattr(state, "is_scanning"):
            return

        is_scanning = getattr(state, "is_scanning")
        device_count = getattr(state, "device_count")
        devices = getattr(state, "devices")
        selected = getattr(state, "selected_device")
        last_operation = getattr(state, "last_operation")
        last_operation_error = getattr(state, "last_operation_error")

        if last["is_scanning"] != is_scanning:
            print(f"扫描中: {is_scanning}")
            last["is_scanning"] = is_scanning

        if last["device_count"] != device_count:
            print(f"设备数量: {device_count}")
            last["device_count"] = device_count

        devices_len = len(devices) if devices is not None else 0
        if last["devices_len"] != devices_len:
            print(f"设备列表更新，共 {devices_len} 项")
            last["devices_len"] = devices_len

        if last["selected"] != selected:
            if selected is None:
                print("选中设备: None")
            else:
                base, storage = selected
                print(
                    f"选中设备: {getattr(base, 'product', 'None')} | 存储={storage is not None}"
                )
            last["selected"] = selected

        if last_operation is not None and last_operation != last["last_operation"]:
            if last_operation == "refresh":
                if last_operation_error is None:
                    print("刷新完成")
                else:
                    print(f"刷新失败: {last_operation_error}")
            last["last_operation"] = last_operation

    sm.stateChanged.connect(on_state_changed)

    overview.resize(900, 600)
    overview.show()

    app.exec()
