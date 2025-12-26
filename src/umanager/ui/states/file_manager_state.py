from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional

from PySide6 import QtCore

from umanager.backend.filesystem.protocol import FileEntry, FileSystemProtocol, ListOptions


@dataclass(frozen=True, slots=True)
class FileManagerState:
    current_directory: Optional[Path] = None
    entries: tuple[FileEntry, ...] = ()
    show_hidden: bool = False
    selected_entry: Optional[FileEntry] = None

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

    _state: FileManagerState
    _filesystem_service: FileSystemProtocol
    _refresh_generation: int

    def __init__(self, parent: QtCore.QObject, filesystem: FileSystemProtocol) -> None:
        super().__init__(parent)
        self._state = FileManagerState()
        self._filesystem_service = filesystem
        self._refresh_generation = 0

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
        self.refreshFinished.emit(self._state.current_directory)

    @QtCore.Slot(object)
    def _on_refresh_failed(self, exc: object) -> None:
        self.refreshFailed.emit(exc)

    def _set_state(self, state: FileManagerState) -> None:
        self._state = state
        self.stateChanged.emit(self._state)
