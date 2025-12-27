from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from umanager.backend.filesystem.service import FileSystemService
from umanager.ui.views import FileManagerPageView


def _populate_temp_dir(root: Path) -> None:
    (root / "folder_a").mkdir()
    (root / "folder_b").mkdir()

    (root / "hello.txt").write_text("hello", encoding="utf-8")
    (root / "data.bin").write_bytes(b"\x00\x01\x02")

    (root / "folder_a" / "hello2.txt").write_text("hello2", encoding="utf-8")


if __name__ == "__main__":
    app = QApplication([])

    with tempfile.TemporaryDirectory() as tmp:
        root_path = Path(tmp)
        _populate_temp_dir(root_path)

        filesystem = FileSystemService()
        page = FileManagerPageView(filesystem, initial_directory=root_path)
        page.setWindowTitle("FileManagerPage Test")
        page.resize(900, 600)
        page.show()

        app.exec()
