from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional

from PySide6 import QtCore

from umanager.backend.filesystem.protocol import (
    CopyOptions,
    DeleteOptions,
    FileEntry,
    FileSystemProtocol,
    ListOptions,
)


@dataclass(frozen=True, slots=True)
class FileManagerState:
    current_directory: Optional[Path] = None
    entries: tuple[FileEntry, ...] = ()
    show_hidden: bool = False
    selected_entry: Optional[FileEntry] = None
    clipboard_path: Optional[Path] = None
    clipboard_mode: Optional[str] = None  # "copy" | "cut"

    def selected_path(self) -> Optional[Path]:
        return None if self.selected_entry is None else self.selected_entry.path


class _AsyncCallSignals(QtCore.QObject):
    finished = QtCore.Signal(object)
    error = QtCore.Signal(object)


class _AsyncCall(QtCore.QRunnable):
    def __init__(self, func: Callable[[], object]) -> None:
        super().__init__()
        self._func = func
        self.signals = _AsyncCallSignals()

    @QtCore.Slot()
    def run(self) -> None:
        try:
            result = self._func()
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(exc)
            return
        self.signals.finished.emit(result)


class _OperationHandler(QtCore.QObject):
    def __init__(
        self,
        manager: "FileManagerStateManager",
        name: str,
        on_success: Optional[Callable[[object], None]],
    ) -> None:
        super().__init__(manager)
        self._manager = manager
        self._name = name
        self._on_success = on_success

    @QtCore.Slot(object)
    def on_finished(self, result: object) -> None:
        if self._on_success is not None:
            self._on_success(result)
        self._manager.operationFinished.emit(self._name)
        self._manager._active_operation_handlers.discard(self)
        self.deleteLater()

    @QtCore.Slot(object)
    def on_error(self, exc: object) -> None:
        self._manager.operationFailed.emit(self._name, exc)
        self._manager._active_operation_handlers.discard(self)
        self.deleteLater()


class FileManagerStateManager(QtCore.QObject):
    stateChanged = QtCore.Signal(object)

    currentDirectoryChanged = QtCore.Signal(object)
    entriesChanged = QtCore.Signal(object)
    showHiddenChanged = QtCore.Signal(bool)
    selectedEntryChanged = QtCore.Signal(object)

    refreshStarted = QtCore.Signal(object)
    refreshFinished = QtCore.Signal(object)
    refreshFailed = QtCore.Signal(object)

    refreshRequested = QtCore.Signal(object, bool)

    # UI should connect these to show modal dialogs.
    createFileDialogRequested = QtCore.Signal(object)  # current_directory
    renameDialogRequested = QtCore.Signal(object)  # selected_entry

    clipboardChanged = QtCore.Signal(object, object)  # (clipboard_path, clipboard_mode)

    operationStarted = QtCore.Signal(str)
    operationFinished = QtCore.Signal(str)
    operationFailed = QtCore.Signal(str, object)

    _state: FileManagerState
    _filesystem_service: FileSystemProtocol
    _refresh_generation: int
    _pending_select_path: Optional[Path]
    _active_operation_handlers: set[_OperationHandler]

    def __init__(self, parent: QtCore.QObject, filesystem: FileSystemProtocol) -> None:
        super().__init__(parent)
        self._state = FileManagerState()
        self._filesystem_service = filesystem
        self._refresh_generation = 0
        self._pending_select_path = None
        self._active_operation_handlers = set()

    def state(self) -> FileManagerState:
        return self._state

    @QtCore.Slot(object)
    def set_current_directory(self, directory: str | Path | None) -> None:
        new_directory = None if directory is None else Path(directory)
        if new_directory == self._state.current_directory:
            return

        new_state = replace(self._state, current_directory=new_directory)
        if new_state.selected_entry is not None and new_directory is not None:
            if new_state.selected_entry.path.parent != new_directory:
                new_state = replace(new_state, selected_entry=None)

        self._set_state(new_state)
        self.currentDirectoryChanged.emit(self._state.current_directory)
        self.refresh()

    @QtCore.Slot(bool)
    def set_show_hidden(self, show_hidden: bool) -> None:
        if show_hidden == self._state.show_hidden:
            return
        self._set_state(replace(self._state, show_hidden=show_hidden))
        self.showHiddenChanged.emit(self._state.show_hidden)
        self.refresh()

    @QtCore.Slot(object)
    def set_entries(self, entries: list[FileEntry] | tuple[FileEntry, ...]) -> None:
        entries_tuple = tuple(entries)
        if entries_tuple == self._state.entries:
            return

        selected_path = self._state.selected_path()
        selected_entry: Optional[FileEntry] = None
        if selected_path is not None:
            for entry in entries_tuple:
                if entry.path == selected_path:
                    selected_entry = entry
                    break

        self._set_state(
            replace(
                self._state,
                entries=entries_tuple,
                selected_entry=selected_entry,
            )
        )
        self.entriesChanged.emit(self._state.entries)
        self.selectedEntryChanged.emit(self._state.selected_entry)

    @QtCore.Slot(object)
    def set_selected_entry(self, entry: Optional[FileEntry]) -> None:
        if entry == self._state.selected_entry:
            return
        self._set_state(replace(self._state, selected_entry=entry))
        self.selectedEntryChanged.emit(self._state.selected_entry)

    def refresh(self) -> None:
        directory = self._state.current_directory
        if directory is None:
            return

        filesystem = self._filesystem_service
        if filesystem is None:
            self.refreshRequested.emit(directory, self._state.show_hidden)
            return

        self._refresh_generation += 1
        generation = self._refresh_generation
        include_hidden = self._state.show_hidden

        self.refreshStarted.emit(directory)

        def do_list() -> tuple[int, Path, bool, list[FileEntry]]:
            entries = filesystem.list_directory(
                directory, ListOptions(include_hidden=include_hidden)
            )
            return generation, directory, include_hidden, entries

        task = _AsyncCall(do_list)
        task.signals.finished.connect(self._on_refresh_finished)
        task.signals.error.connect(self._on_refresh_failed)
        QtCore.QThreadPool.globalInstance().start(task)

    @QtCore.Slot(object)
    def _on_refresh_finished(self, result: object) -> None:
        if not isinstance(result, tuple) or len(result) != 4:
            return

        generation, directory, include_hidden, entries = result
        if generation != self._refresh_generation:
            return
        if self._state.current_directory != directory:
            return
        if self._state.show_hidden != include_hidden:
            return

        self.set_entries(entries)

        if self._pending_select_path is not None:
            target = self._pending_select_path
            self._pending_select_path = None
            for entry in self._state.entries:
                if entry.path == target:
                    self.set_selected_entry(entry)
                    break

        self.refreshFinished.emit(self._state.current_directory)

    @QtCore.Slot(object)
    def _on_refresh_failed(self, exc: object) -> None:
        self.refreshFailed.emit(exc)

    def _set_state(self, state: FileManagerState) -> None:
        self._state = state
        self.stateChanged.emit(self._state)

    def _set_clipboard(self, path: Optional[Path], mode: Optional[str]) -> None:
        if path == self._state.clipboard_path and mode == self._state.clipboard_mode:
            return
        self._set_state(replace(self._state, clipboard_path=path, clipboard_mode=mode))
        self.clipboardChanged.emit(self._state.clipboard_path, self._state.clipboard_mode)

    def _run_filesystem_operation(
        self,
        name: str,
        func: Callable[[], object],
        *,
        on_success: Optional[Callable[[object], None]] = None,
    ) -> None:
        self.operationStarted.emit(name)

        task = _AsyncCall(func)

        handler = _OperationHandler(self, name, on_success)
        self._active_operation_handlers.add(handler)
        task.signals.finished.connect(handler.on_finished)
        task.signals.error.connect(handler.on_error)
        QtCore.QThreadPool.globalInstance().start(task)

    # ---- Slots for external UI/actions ----

    @QtCore.Slot()
    def request_create_file(self) -> None:
        if self._state.current_directory is None:
            return
        self.createFileDialogRequested.emit(self._state.current_directory)

    @QtCore.Slot(str)
    def create_file(self, file_name: str) -> None:
        directory = self._state.current_directory
        if directory is None:
            return

        file_name = file_name.strip()
        if not file_name:
            return

        new_path = directory / file_name

        def do_create() -> object:
            return self._filesystem_service.touch_file(new_path, exist_ok=False, parents=False)

        def on_success(_result: object) -> None:
            self._pending_select_path = new_path
            self.refresh()

        self._run_filesystem_operation("create", do_create, on_success=on_success)

    @QtCore.Slot()
    def delete_selected(self) -> None:
        entry = self._state.selected_entry
        if entry is None:
            return

        path = entry.path

        def do_delete() -> object:
            self._filesystem_service.delete(
                path, options=DeleteOptions(recursive=True, force=False)
            )
            return None

        def on_success(_result: object) -> None:
            self.set_selected_entry(None)
            self.refresh()

        self._run_filesystem_operation("delete", do_delete, on_success=on_success)

    @QtCore.Slot()
    def copy_selected(self) -> None:
        entry = self._state.selected_entry
        if entry is None:
            return
        self._set_clipboard(entry.path, "copy")

    @QtCore.Slot()
    def cut_selected(self) -> None:
        entry = self._state.selected_entry
        if entry is None:
            return
        self._set_clipboard(entry.path, "cut")

    @QtCore.Slot()
    def clear_clipboard(self) -> None:
        self._set_clipboard(None, None)

    @QtCore.Slot()
    def paste(self) -> None:
        directory = self._state.current_directory
        if directory is None:
            return

        src = self._state.clipboard_path
        mode = self._state.clipboard_mode
        if src is None or mode not in {"copy", "cut"}:
            return

        dst = directory / src.name
        if dst == src:
            return

        if mode == "copy":

            def do_paste_copy() -> object:
                return self._filesystem_service.copy_path(
                    src,
                    dst,
                    options=CopyOptions(recursive=True, overwrite=False),
                )

            def on_success(_result: object) -> None:
                self.clear_clipboard()
                self._pending_select_path = dst
                self.refresh()

            self._run_filesystem_operation("paste_copy", do_paste_copy, on_success=on_success)
            return

        def do_paste_cut() -> object:
            return self._filesystem_service.move_path(src, dst, overwrite=False)

        def on_success(_result: object) -> None:
            self.clear_clipboard()
            self._pending_select_path = dst
            self.refresh()

        self._run_filesystem_operation("paste_cut", do_paste_cut, on_success=on_success)

    @QtCore.Slot()
    def request_rename_selected(self) -> None:
        entry = self._state.selected_entry
        if entry is None:
            return
        self.renameDialogRequested.emit(entry)

    @QtCore.Slot()
    def enter_selected(self) -> None:
        entry = self._state.selected_entry
        if entry is None:
            return

        if entry.is_dir:
            self.set_current_directory(entry.path)
            return

        path = entry.path

        def do_open() -> object:
            self._filesystem_service.open_file_external(path)
            return None

        self._run_filesystem_operation("open", do_open)

    @QtCore.Slot()
    def go_up(self) -> None:
        directory = self._state.current_directory
        if directory is None:
            return

        parent = directory.parent
        if parent == directory:
            return

        self.set_current_directory(parent)

    @QtCore.Slot(str)
    def rename_selected(self, new_name: str) -> None:
        entry = self._state.selected_entry
        if entry is None:
            return

        new_name = new_name.strip()
        if not new_name:
            return

        src = entry.path

        def do_rename() -> object:
            return self._filesystem_service.rename(src, new_name, overwrite=False)

        def on_success(result: object) -> None:
            if isinstance(result, Path):
                self._pending_select_path = result
            else:
                self._pending_select_path = src.parent / new_name
            self.set_selected_entry(None)
            self.refresh()

        self._run_filesystem_operation("rename", do_rename, on_success=on_success)
