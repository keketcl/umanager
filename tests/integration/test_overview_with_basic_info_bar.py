from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from umanager.backend.device import UsbBaseDeviceService, UsbStorageDeviceService
from umanager.ui.views import OverviewPageView
from umanager.ui.widgets import BasicInfoBarWidget

if __name__ == "__main__":
    app = QApplication([])

    # 根容器：顶部基础信息栏 + 下方总览页
    root = QWidget()
    layout = QVBoxLayout(root)

    info_bar = BasicInfoBarWidget()
    info_bar.set_title("USB Manager")
    info_bar.set_subtitle("总览页")
    info_bar.set_status("")

    overview = OverviewPageView(
        base_service_factory=lambda: UsbBaseDeviceService(),
        storage_service_factory=lambda base: UsbStorageDeviceService(base),
    )

    # 信号输出便于观察交互
    sm = overview.state_manager()
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
    sm.refreshStarted.connect(lambda: print("刷新开始"))
    sm.refreshFinished.connect(lambda: print("刷新完成"))
    sm.refreshFailed.connect(lambda e: print(f"刷新失败: {e}"))
    sm.scanningChanged.connect(lambda s: print(f"扫描中: {s}"))
    sm.deviceCountChanged.connect(lambda c: print(f"设备数量: {c}"))
    sm.devicesChanged.connect(lambda d: print(f"设备列表更新，共 {len(d)} 项"))
    sm.selectedDeviceChanged.connect(
        lambda base, storage: print(
            f"选中设备: {getattr(base, 'product', 'None')} | 存储={storage is not None}"
        )
    )

    layout.addWidget(info_bar)
    layout.addWidget(overview, 1)

    root.setWindowTitle("USB Manager - 总览 (含基础信息栏)")
    root.resize(900, 600)
    root.show()

    app.exec()
