from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from umanager.ui.widgets import OverviewButtonBar

if __name__ == "__main__":
    app = QApplication([])

    root = QWidget()
    root.setWindowTitle("OverviewButtonBar Test")
    layout = QVBoxLayout(root)

    button_bar = OverviewButtonBar()
    button_bar.open_file_manager.connect(lambda: print("Signal: open_file_manager"))
    button_bar.view_details.connect(lambda: print("Signal: view_details"))
    button_bar.eject_device.connect(lambda: print("Signal: eject_device"))

    layout.addStretch()
    layout.addWidget(button_bar)
    root.setLayout(layout)
    root.resize(600, 200)
    root.show()

    app.exec()
