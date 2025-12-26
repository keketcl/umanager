from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from umanager.backend.filesystem.protocol import FileEntry
from umanager.ui.states import FileManagerState, FileManagerStateManager


class _FileEntryTableModel(QtCore.QAbstractTableModel):
    _COLUMNS = ("名称", "类型", "大小", "修改时间")

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._entries: tuple[FileEntry, ...] = ()
        self._min_column_widths = self._compute_min_column_widths()

    @staticmethod
    def _compute_min_column_widths() -> dict[int, int]:
        if QtWidgets.QApplication.instance() is None:
            return {}

        fm = QtGui.QFontMetrics(QtWidgets.QApplication.font())
        padding = fm.averageCharWidth() * 2

        type_width = max(
            fm.horizontalAdvance("目录"),
            fm.horizontalAdvance("txt 文件"),
            fm.horizontalAdvance("文件"),
            fm.horizontalAdvance("类型"),
        )
        size_width = max(
            fm.horizontalAdvance("9999999999"),
            fm.horizontalAdvance("大小"),
        )
        modified_width = max(
            fm.horizontalAdvance("2025-12-26 23:59:59"),
            fm.horizontalAdvance("修改时间"),
        )

        return {
            1: type_width + padding,
            2: size_width + padding,
            3: modified_width + padding,
        }

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
                if entry.is_dir:
                    return "目录"

                ext = entry.path.suffix
                if ext:
                    return f"{ext.lstrip('.')} 文件"
                return "文件"
            if column == 2:
                return "" if entry.is_dir else str(entry.size)
            if column == 3:
                return "" if entry.mtime is None else entry.mtime.strftime("%Y-%m-%d %H:%M:%S")
            return None

        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            return int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            return str(entry.path)

        if role == QtCore.Qt.ItemDataRole.SizeHintRole:
            width = self._min_column_widths.get(column)
            if width is None:
                return None
            return QtCore.QSize(width, 0)

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
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self._table)

        self._table.selectionModel().currentChanged.connect(self._on_current_changed)
        self._table.doubleClicked.connect(self._on_double_clicked)
        self._table.installEventFilter(self)

        self._state_manager.stateChanged.connect(self._on_state_changed)
        self._state_manager.selectedEntryChanged.connect(self._sync_selection_from_state)

        self._on_state_changed(self._state_manager.state())

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if obj is self._table and event.type() == QtCore.QEvent.Type.KeyPress:
            if not isinstance(event, QtGui.QKeyEvent):
                return super().eventFilter(obj, event)
            key_event = event
            if key_event.key() in {
                int(QtCore.Qt.Key.Key_Return),
                int(QtCore.Qt.Key.Key_Enter),
            }:
                self._state_manager.enter_selected()
                return True
            if key_event.key() == int(QtCore.Qt.Key.Key_Backspace):
                self._state_manager.go_up()
                return True
        return super().eventFilter(obj, event)

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

    @QtCore.Slot(QtCore.QModelIndex)
    def _on_double_clicked(self, index: QtCore.QModelIndex) -> None:
        entry = self._model.entry_at(index.row())
        self._state_manager.set_selected_entry(entry)
        self._state_manager.enter_selected()

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
