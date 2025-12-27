from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QInputDialog, QVBoxLayout, QWidget

from umanager.backend.filesystem.protocol import FileEntry, FileSystemProtocol
from umanager.ui.states import FileManagerState, FileManagerStateManager
from umanager.ui.widgets import (
    FileManagerButtonBarWidget,
    FileManagerListWidget,
    FileManagerPathBarWidget,
)


class FileManagerPageView(QWidget):
    def __init__(
        self,
        filesystem: FileSystemProtocol,
        *,
        initial_directory: str | Path | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._state_manager = FileManagerStateManager(self, filesystem)

        self._path_bar = FileManagerPathBarWidget(self)
        self._button_bar = FileManagerButtonBarWidget(self)
        self._file_list = FileManagerListWidget(self._state_manager, self)

        layout = QVBoxLayout(self)
        layout.addWidget(self._path_bar)
        layout.addWidget(self._button_bar)
        layout.addWidget(self._file_list, 1)
        self.setLayout(layout)

        self._path_bar.go_up_requested.connect(self._state_manager.go_up)
        self._state_manager.stateChanged.connect(self._on_state_changed)

        self._button_bar.create_requested.connect(self._state_manager.request_create_file)
        self._button_bar.create_directory_requested.connect(
            self._state_manager.request_create_directory
        )
        self._button_bar.open_requested.connect(self._state_manager.enter_selected)
        self._button_bar.copy_requested.connect(self._state_manager.copy_selected)
        self._button_bar.cut_requested.connect(self._state_manager.cut_selected)
        self._button_bar.paste_requested.connect(self._state_manager.paste)
        self._button_bar.delete_requested.connect(self._state_manager.delete_selected)
        self._button_bar.rename_requested.connect(self._state_manager.request_rename_selected)

        self._state_manager.createFileDialogRequested.connect(self._on_create_file_dialog_requested)
        self._state_manager.createDirectoryDialogRequested.connect(
            self._on_create_directory_dialog_requested
        )
        self._state_manager.renameDialogRequested.connect(self._on_rename_dialog_requested)

        self._on_state_changed(self._state_manager.state())

        if initial_directory is not None:
            self.set_directory(initial_directory)

    def state_manager(self) -> FileManagerStateManager:
        return self._state_manager

    def set_directory(self, directory: str | Path | None) -> None:
        self._state_manager.set_current_directory(directory)

    @Slot(object)
    def _on_state_changed(self, state: object) -> None:
        # Only the unified stateChanged is used for state updates.
        if not isinstance(state, FileManagerState):
            return
        self._path_bar.set_path(state.current_directory)

    @Slot()
    def _on_create_file_dialog_requested(self, directory: object) -> None:
        _ = directory
        name, ok = QInputDialog.getText(self, "创建文件", "文件名")
        if not ok:
            return
        self._state_manager.create_file(name)

    @Slot()
    def _on_create_directory_dialog_requested(self, directory: object) -> None:
        _ = directory
        name, ok = QInputDialog.getText(self, "创建目录", "目录名")
        if not ok:
            return
        self._state_manager.create_directory(name)

    @Slot()
    def _on_rename_dialog_requested(self, entry: object) -> None:
        if not isinstance(entry, FileEntry):
            return
        name, ok = QInputDialog.getText(self, "重命名", "新名称", text=entry.name)
        if not ok:
            return
        self._state_manager.rename_selected(name)
