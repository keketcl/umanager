from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStyle, QToolButton, QWidget


class FileManagerPathBarWidget(QWidget):
    go_up_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._full_path_text = ""

        self._go_up_btn = QToolButton(self)
        self._go_up_btn.setAutoRaise(True)
        self._go_up_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogToParent)
        )
        self._go_up_btn.clicked.connect(self.go_up_requested.emit)

        self._path_label = QLabel(self)
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._path_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._go_up_btn)
        layout.addWidget(self._path_label, 1)
        self.setLayout(layout)

    def set_path(self, path: str | Path | None) -> None:
        if path is None:
            self._full_path_text = ""
        else:
            self._full_path_text = str(Path(path))
        self._update_elided_text()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        fm = QFontMetrics(self._path_label.font())
        available = max(0, self._path_label.width())
        self._path_label.setText(
            fm.elidedText(
                self._full_path_text,
                Qt.TextElideMode.ElideLeft,
                available,
            )
        )
        self._path_label.setToolTip(self._full_path_text)
