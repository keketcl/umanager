from pathlib import Path

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from umanager.ui.widgets import FileManagerPathBarWidget

if __name__ == "__main__":
    app = QApplication([])

    root = QWidget()
    root.setWindowTitle("FileManagerPathBar Test")
    layout = QVBoxLayout(root)

    path_bar = FileManagerPathBarWidget()
    path_bar.go_up_requested.connect(lambda: print("Signal: go_up_requested"))
    path_bar.set_path(Path.home() / "Projects" / "umanager" / "some" / "very" / "long" / "path")

    layout.addWidget(path_bar)
    root.setLayout(layout)
    root.show()

    app.exec()
