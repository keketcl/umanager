from __future__ import annotations

from PySide6.QtWidgets import QApplication

from umanager.backend.device import UsbBaseDeviceService, UsbStorageDeviceService
from umanager.backend.filesystem.service import FileSystemService
from umanager.ui.views import RootWindowView


def main() -> None:
    app = QApplication([])

    base_service = UsbBaseDeviceService()
    storage_service = UsbStorageDeviceService(base_service)
    filesystem = FileSystemService()

    window = RootWindowView(
        base_service=base_service,
        storage_service=storage_service,
        filesystem=filesystem,
    )
    window.setWindowTitle("USB Manager")
    window.resize(1100, 720)
    window.show()

    app.exec()
