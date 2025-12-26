from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from umanager.backend.filesystem.protocol import FileEntry
from umanager.ui.states import FileManagerState, FileManagerStateManager


class _FileEntryTableModel(QtCore.QAbstractTableModel):
    _COLUMNS = ("名称", "大小", "修改时间")

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._entries: tuple[FileEntry, ...] = ()

    def set_entries(self, entries: tuple[FileEntry, ...]) -> None:
        if entries == self._entries:
            return
        self.beginResetModel()
        self._entries = entries
        self.endResetModel()

    def entry_at(self, row: int) -> Optional[FileEntry]:
        if row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    def rowCount(
        self,
        parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex(),
    ) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(
        self,
        parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex(),
    ) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal:
            if 0 <= section < len(self._COLUMNS):
                return self._COLUMNS[section]
            return None
        return str(section + 1)

    def data(
        self,
        index: QtCore.QModelIndex | QtCore.QPersistentModelIndex,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ):
        if not index.isValid():
            return None

        entry = self.entry_at(index.row())
        if entry is None:
            return None

        column = index.column()

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if column == 0:
                suffix = "/" if entry.is_dir else ""
                return f"{entry.name}{suffix}"
            if column == 1:
                return "" if entry.is_dir else str(entry.size)
            if column == 2:
                return "" if entry.mtime is None else entry.mtime.strftime("%Y-%m-%d %H:%M:%S")
            return None

        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if column == 1:
                return int(
                    QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
            return int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            return str(entry.path)

        if role == QtCore.Qt.ItemDataRole.UserRole:
            return entry

        return None


class FileManagerListWidget(QtWidgets.QWidget):
    def __init__(
        self,
        state_manager: FileManagerStateManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._state_manager = state_manager
        self._model = _FileEntryTableModel(self)
        self._updating_selection = False

        layout = QtWidgets.QVBoxLayout(self)

        self._table = QtWidgets.QTableView(self)
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )

        layout.addWidget(self._table)

        self._table.selectionModel().currentChanged.connect(self._on_current_changed)

        self._state_manager.stateChanged.connect(self._on_state_changed)
        self._state_manager.selectedEntryChanged.connect(self._sync_selection_from_state)

        self._on_state_changed(self._state_manager.state())

    def set_directory(self, directory: str | Path | None, *, refresh: bool = False) -> None:
        self._state_manager.set_current_directory(directory)
        if refresh:
            self._state_manager.refresh()

    @QtCore.Slot(QtCore.QModelIndex, QtCore.QModelIndex)
    def _on_current_changed(
        self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex
    ) -> None:
        if self._updating_selection:
            return
        entry = self._model.entry_at(current.row())
        self._state_manager.set_selected_entry(entry)

    @QtCore.Slot(object)
    def _on_state_changed(self, state: FileManagerState) -> None:
        self._model.set_entries(state.entries)
        self._sync_selection_from_state(state.selected_entry)

    @QtCore.Slot(object)
    def _sync_selection_from_state(self, selected_entry: Optional[FileEntry]) -> None:
        if self._table.selectionModel() is None:
            return

        self._updating_selection = True
        try:
            selection_model = self._table.selectionModel()
            selection_model.clearSelection()

            if selected_entry is None:
                return

            target_row = None
            for row, entry in enumerate(self._model._entries):  # noqa: SLF001
                if entry.path == selected_entry.path:
                    target_row = row
                    break

            if target_row is None:
                return

            index = self._model.index(target_row, 0)
            selection_model.setCurrentIndex(
                index,
                QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QtCore.QItemSelectionModel.SelectionFlag.Rows,
            )
            self._table.scrollTo(index, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)
        finally:
            self._updating_selection = False
