from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from umanager.ui.widgets import OverviewTitleBar

if __name__ == "__main__":
    app = QApplication([])

    root = QWidget()
    root.setWindowTitle("OverviewTitleBar Test")
    layout = QVBoxLayout(root)

    title_bar = OverviewTitleBar()

    # 测试设备计数变化
    title_bar.set_device_count(0)

    # 模拟设备扫描：3秒后显示扫描状态，5秒后完成扫描并显示3个设备
    def start_scanning():
        title_bar.set_scanning(True)
        print("Started scanning...")

    def finish_scanning():
        title_bar.set_scanning(False)
        title_bar.set_device_count(3)
        print("Finished scanning, found 3 devices")

    QTimer.singleShot(3000, start_scanning)
    QTimer.singleShot(5000, finish_scanning)

    layout.addWidget(title_bar)
    layout.addStretch()
    root.setLayout(layout)
    root.resize(600, 150)
    root.show()

    app.exec()
