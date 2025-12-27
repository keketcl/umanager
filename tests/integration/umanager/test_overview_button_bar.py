from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from umanager.ui.widgets import OverviewButtonBarWidget

if __name__ == "__main__":
    app = QApplication([])

    root = QWidget()
    root.setWindowTitle("OverviewButtonBar Test")
    layout = QVBoxLayout(root)

    button_bar = OverviewButtonBarWidget()
    button_bar.refresh_devices.connect(lambda: print("Signal: refresh_devices"))
    button_bar.view_details.connect(lambda: print("Signal: view_details"))
    button_bar.eject_device.connect(lambda: print("Signal: eject_device"))

    layout.addStretch()
    layout.addWidget(button_bar)
    root.setLayout(layout)
    root.resize(600, 200)
    root.show()

    app.exec()
