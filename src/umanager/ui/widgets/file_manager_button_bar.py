from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QStyle, QToolButton, QWidget


class FileManagerButtonBarWidget(QWidget):
    refresh_requested = Signal()
    create_requested = Signal()
    create_directory_requested = Signal()
    open_requested = Signal()
    copy_requested = Signal()
    cut_requested = Signal()
    paste_requested = Signal()
    delete_requested = Signal()
    rename_requested = Signal()
    show_hidden_toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        style = self.style()

        button_style = Qt.ToolButtonStyle.ToolButtonTextBesideIcon

        self._refresh_btn = QToolButton(self)
        self._refresh_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self._refresh_btn.setText("刷新")
        self._refresh_btn.setToolButtonStyle(button_style)
        self._refresh_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._refresh_btn.setAutoRaise(True)

        self._create_btn = QToolButton(self)
        self._create_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self._create_btn.setText("新建文件")
        self._create_btn.setToolButtonStyle(button_style)
        self._create_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._create_btn.setAutoRaise(True)

        self._create_dir_btn = QToolButton(self)
        self._create_dir_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self._create_dir_btn.setText("新建目录")
        self._create_dir_btn.setToolButtonStyle(button_style)
        self._create_dir_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._create_dir_btn.setAutoRaise(True)

        self._open_btn = QToolButton(self)
        self._open_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self._open_btn.setText("打开")
        self._open_btn.setToolButtonStyle(button_style)
        self._open_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._open_btn.setAutoRaise(True)

        self._copy_btn = QToolButton(self)
        self._copy_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogStart))
        self._copy_btn.setText("复制")
        self._copy_btn.setToolButtonStyle(button_style)
        self._copy_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._copy_btn.setAutoRaise(True)

        self._cut_btn = QToolButton(self)
        self._cut_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogOkButton))
        self._cut_btn.setText("剪切")
        self._cut_btn.setToolButtonStyle(button_style)
        self._cut_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._cut_btn.setAutoRaise(True)

        self._paste_btn = QToolButton(self)
        self._paste_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self._paste_btn.setText("粘贴")
        self._paste_btn.setToolButtonStyle(button_style)
        self._paste_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._paste_btn.setAutoRaise(True)

        self._delete_btn = QToolButton(self)
        self._delete_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self._delete_btn.setText("删除")
        self._delete_btn.setToolButtonStyle(button_style)
        self._delete_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._delete_btn.setAutoRaise(True)

        self._rename_btn = QToolButton(self)
        self._rename_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView))
        self._rename_btn.setText("重命名")
        self._rename_btn.setToolButtonStyle(button_style)
        self._rename_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._rename_btn.setAutoRaise(True)

        self._show_hidden_btn = QToolButton(self)
        self._show_hidden_btn.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self._show_hidden_btn.setText("显示隐藏文件")
        self._show_hidden_btn.setToolButtonStyle(button_style)
        self._show_hidden_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._show_hidden_btn.setAutoRaise(True)
        self._show_hidden_btn.setCheckable(True)
        self._show_hidden_btn.setChecked(False)
        self._show_hidden_btn.setToolTip("切换是否显示隐藏文件")

        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        self._create_btn.clicked.connect(self.create_requested.emit)
        self._create_dir_btn.clicked.connect(self.create_directory_requested.emit)
        self._open_btn.clicked.connect(self.open_requested.emit)
        self._copy_btn.clicked.connect(self.copy_requested.emit)
        self._cut_btn.clicked.connect(self.cut_requested.emit)
        self._paste_btn.clicked.connect(self.paste_requested.emit)
        self._delete_btn.clicked.connect(self.delete_requested.emit)
        self._rename_btn.clicked.connect(self.rename_requested.emit)
        self._show_hidden_btn.toggled.connect(self.show_hidden_toggled.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._refresh_btn)
        layout.addWidget(self._create_btn)
        layout.addWidget(self._create_dir_btn)
        layout.addWidget(self._open_btn)
        layout.addWidget(self._copy_btn)
        layout.addWidget(self._cut_btn)
        layout.addWidget(self._paste_btn)
        layout.addWidget(self._delete_btn)
        layout.addWidget(self._rename_btn)
        layout.addWidget(self._show_hidden_btn)
        layout.addStretch(1)
        self.setLayout(layout)

    def set_show_hidden_checked(self, checked: bool) -> None:
        if self._show_hidden_btn.isChecked() == checked:
            return
        with QSignalBlocker(self._show_hidden_btn):
            self._show_hidden_btn.setChecked(checked)
