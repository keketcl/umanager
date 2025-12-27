from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class CreateFileDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("创建文件")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("文件名"))
        self._name_edit = QLineEdit(self)
        layout.addWidget(self._name_edit)

        layout.addWidget(QLabel("初始内容"))
        self._content_edit = QTextEdit(self)
        layout.addWidget(self._content_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def file_name(self) -> str:
        return self._name_edit.text()

    def initial_text(self) -> str:
        return self._content_edit.toPlainText()
