from PySide6.QtWidgets import QApplication

from umanager.backend.device import UsbBaseDeviceService, UsbStorageDeviceService
from umanager.ui.views import OverviewPage

if __name__ == "__main__":
    app = QApplication([])

    # 创建总览页，传递工厂函数
    overview = OverviewPage(
        base_service_factory=lambda: UsbBaseDeviceService(),
        storage_service_factory=lambda base: UsbStorageDeviceService(base),
    )
    overview.setWindowTitle("USB Manager - 总览（状态管理重构版）")

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

    # 状态变化类信号（加载流程与选择状态）
    sm.refreshStarted.connect(lambda: print("刷新开始"))
    sm.refreshFinished.connect(lambda: print("刷新完成"))
    sm.refreshFailed.connect(lambda e: print(f"刷新失败: {e}"))
    sm.scanningChanged.connect(lambda s: print(f"扫描中: {s}"))
    sm.deviceCountChanged.connect(lambda c: print(f"设备数量: {c}"))
    sm.devicesChanged.connect(lambda d: print(f"设备列表更新，共 {len(d)} 项"))
    sm.selectedDeviceChanged.connect(
        lambda base, storage: print(
            f"选中设备: {getattr(base, 'product', 'None')} | 存储={storage is not None if storage else False}"
        )
    )

    overview.resize(900, 600)
    overview.show()

    app.exec()
