from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from umanager.backend.filesystem.service import FileSystemService
from umanager.ui.states import FileManagerStateManager
from umanager.ui.widgets import FileManagerListWidget


def _populate_temp_dir(root: Path) -> None:
    (root / "folder_a").mkdir()
    (root / "folder_b").mkdir()

    (root / "hello.txt").write_text("hello", encoding="utf-8")
    (root / "data.bin").write_bytes(b"\x00\x01\x02")


if __name__ == "__main__":
    app = QApplication([])

    with tempfile.TemporaryDirectory() as tmp:
        root_path = Path(tmp)
        _populate_temp_dir(root_path)

        filesystem = FileSystemService()
        state_manager = FileManagerStateManager(app, filesystem)

        root = QWidget()
        layout = QVBoxLayout(root)

        widget = FileManagerListWidget(state_manager)
        widget.set_directory(root_path)

        layout.addWidget(widget)
        root.setLayout(layout)
        root.resize(900, 480)
        root.show()

        app.exec()
