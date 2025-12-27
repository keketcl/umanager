from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from umanager.ui.widgets import FileManagerButtonBarWidget

if __name__ == "__main__":
    app = QApplication([])

    root = QWidget()
    root.setWindowTitle("FileManagerButtonBar Test")
    layout = QVBoxLayout(root)

    button_bar = FileManagerButtonBarWidget()
    button_bar.refresh_requested.connect(lambda: print("Signal: refresh_requested"))
    button_bar.create_requested.connect(lambda: print("Signal: create_requested"))
    button_bar.create_directory_requested.connect(
        lambda: print("Signal: create_directory_requested")
    )
    button_bar.open_requested.connect(lambda: print("Signal: open_requested"))
    button_bar.copy_requested.connect(lambda: print("Signal: copy_requested"))
    button_bar.cut_requested.connect(lambda: print("Signal: cut_requested"))
    button_bar.paste_requested.connect(lambda: print("Signal: paste_requested"))
    button_bar.delete_requested.connect(lambda: print("Signal: delete_requested"))
    button_bar.rename_requested.connect(lambda: print("Signal: rename_requested"))
    button_bar.show_hidden_toggled.connect(
        lambda checked: print(f"Signal: show_hidden_toggled={checked}")
    )

    layout.addWidget(button_bar)
    root.setLayout(layout)
    root.show()

    app.exec()
