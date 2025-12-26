from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout

from umanager.backend.device import (
    UsbBaseDeviceService,
    UsbStorageDeviceService,
    UsbDeviceId,
)
from umanager.ui.widgets import DeviceInfoListWidget


def build_devices(base_service: UsbBaseDeviceService, storage_service: UsbStorageDeviceService):
    base_ids = base_service.list_base_device_ids()
    storage_ids = {i.instance_id for i in storage_service.list_storage_device_ids()}

    items = []
    for dev_id in base_ids:
        base_info = base_service.get_base_device_info(dev_id)
        if dev_id.instance_id in storage_ids:
            try:
                storage_info = storage_service.get_storage_device_info(dev_id)
                items.append(storage_info)
            except Exception:
                items.append(base_info)
        else:
            items.append(base_info)
    return items


if __name__ == "__main__":
    app = QApplication([])

    base_device_service = UsbBaseDeviceService()
    storage_device_service = UsbStorageDeviceService(base_device_service)
    devices = build_devices(base_device_service, storage_device_service)

    root = QWidget()
    layout = QVBoxLayout(root)

    widget = DeviceInfoListWidget()
    widget.set_devices(devices)
    widget.device_activated.connect(lambda base, storage: print("activated:", base, storage))
    widget.selection_changed.connect(lambda base, storage: print("selected:", base, storage))

    layout.addWidget(widget)
    root.setLayout(layout)
    root.resize(900, 480)
    root.show()

    app.exec()