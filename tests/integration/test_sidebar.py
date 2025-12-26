"""侧边栏集成测试：验证设备列表显示、选中、信号发出等核心功能。"""

from PySide6.QtWidgets import QApplication

from umanager.backend.device import (
    UsbBaseDeviceInfo,
    UsbDeviceId,
    UsbStorageDeviceInfo,
    UsbVolumeInfo,
)
from umanager.ui.widgets import SidebarWidget


def _create_mock_storage_device(
    instance_id: str,
    product: str,
    drive_letter: str | None = None,
    volume_label: str | None = None,
) -> UsbStorageDeviceInfo:
    """创建模拟存储设备用于测试。"""
    device_id = UsbDeviceId(instance_id=instance_id)
    base = UsbBaseDeviceInfo(
        id=device_id,
        product=product,
        serial_number=f"SN_{instance_id[-4:]}",
    )
    volumes = []
    if drive_letter:
        volumes.append(
            UsbVolumeInfo(
                drive_letter=drive_letter,
                volume_label=volume_label,
                total_bytes=16_000_000_000,
                free_bytes=8_000_000_000,
            )
        )
    return UsbStorageDeviceInfo(base=base, volumes=volumes)


if __name__ == "__main__":
    app = QApplication([])

    sidebar = SidebarWidget()
    sidebar.setWindowTitle("侧边栏测试")
    sidebar.resize(300, 500)

    # 连接信号以查看行为
    sidebar.overview_requested.connect(lambda: print("✓ 总览请求信号"))
    sidebar.device_requested.connect(
        lambda device_id: print(f"✓ 设备请求信号: {device_id.instance_id}")
    )
    sidebar.selection_changed.connect(
        lambda device_id: print(
            f"✓ 选中变化: {device_id.instance_id if device_id else '总览'}"
        )
    )

    # 模拟设备数据
    devices = [
        _create_mock_storage_device(
            "USB\\VID_1234&PID_5678\\001", "Kingston DataTraveler", "E:", "KINGSTON"
        ),
        _create_mock_storage_device(
            "USB\\VID_ABCD&PID_EFGH\\002", "SanDisk Cruzer", "F:", "SANDISK"
        ),
        _create_mock_storage_device(
            "USB\\VID_9999&PID_8888\\003", "External HDD", "G:", "BACKUP"
        ),
    ]

    print("\n=== 初始状态：仅显示总览 ===")
    print("提示：侧边栏应显示一个'总览'条目")

    print("\n=== 测试1：设置设备列表 ===")
    sidebar.set_devices(devices)
    print(f"已添加 {len(devices)} 个设备")
    print("提示：侧边栏应显示 1 个总览 + 3 个设备条目")

    print("\n=== 测试2：点击条目触发信号 ===")
    print("请点击侧边栏条目，观察控制台输出信号")

    print("\n=== 测试3：程序化选中总览 ===")
    sidebar.select_overview()
    print("已调用 select_overview()")

    print("\n=== 测试4：程序化选中设备 ===")
    sidebar.select_device(devices[1].base.id)
    print(f"已选中设备: {devices[1].base.product}")

    print("\n=== 测试5：更新设备列表（保留选中） ===")
    # 移除第二个设备，当前选中的设备消失
    updated_devices = [devices[0], devices[2]]
    sidebar.set_devices(updated_devices)
    print("已移除 SanDisk 设备，选中应回退到总览")

    print("\n=== 测试6：再次更新列表（保留选中） ===")
    sidebar.select_device(devices[2].base.id)  # 选中 External HDD
    sidebar.set_devices(updated_devices)  # 刷新列表但设备仍存在
    print("设备列表刷新，但选中设备仍存在，应保持选中")

    print("\n=== 测试7：添加新设备 ===")
    new_device = _create_mock_storage_device(
        "USB\\VID_AAAA&PID_BBBB\\004", "New USB Drive", "H:", "NEWDRIVE"
    )
    sidebar.set_devices(updated_devices + [new_device])
    print(f"已添加新设备: {new_device.base.product}")

    print("\n=== 测试完成 ===")
    print("可以手动与侧边栏交互，点击不同条目查看信号输出")

    sidebar.show()
    app.exec()
