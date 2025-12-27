from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from umanager.backend.device import UsbBaseDeviceProtocol, UsbStorageDeviceProtocol
from umanager.backend.filesystem.protocol import FileSystemProtocol
from umanager.ui.views.mainarea_view import MainAreaView
from umanager.ui.widgets.basic_info_bar import BasicInfoBarWidget


class RootWindowView(QWidget):
    def __init__(
        self,
        base_service: UsbBaseDeviceProtocol,
        storage_service: UsbStorageDeviceProtocol,
        *,
        filesystem: Optional[FileSystemProtocol] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._info_bar = BasicInfoBarWidget(self)
        self._info_bar.set_title("UManager")
        self._info_bar.set_status("")

        self._main_area = MainAreaView(
            base_service=base_service,
            storage_service=storage_service,
            filesystem=filesystem,
            parent=self,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._info_bar)
        layout.addWidget(self._main_area, 1)
        self.setLayout(layout)

    def main_area(self) -> MainAreaView:
        return self._main_area

    def info_bar(self) -> BasicInfoBarWidget:
        return self._info_bar
