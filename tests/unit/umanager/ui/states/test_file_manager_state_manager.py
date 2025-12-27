from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest
from PySide6 import QtCore

from umanager.backend.filesystem.protocol import (
    CopyOptions,
    DeleteOptions,
    FileEntry,
    FileSystemProtocol,
)
from umanager.ui.states import FileManagerState, FileManagerStateManager


class FakeFileSystem(FileSystemProtocol):
    def __init__(self) -> None:
        self._dirs: set[Path] = set()
        self._files: dict[Path, bytes] = {}
        self.opened_files: list[Path] = []

    def add_dir(self, path: Path) -> None:
        self._ensure_dir(path)

    def add_file(self, path: Path, content: bytes = b"") -> None:
        self._ensure_dir(path.parent)
        self._files[path] = content

    def list_directory(self, directory: str | Path, options=None) -> list[FileEntry]:  # type: ignore[override]
        directory = Path(directory)
        if directory not in self._dirs:
            raise FileNotFoundError(directory)

        entries: list[FileEntry] = []
        for d in self._dirs:
            if d != directory and d.parent == directory:
                entries.append(self._make_entry(d))
        for f in self._files:
            if f.parent == directory:
                entries.append(self._make_entry(f))

        entries.sort(key=lambda e: e.name.casefold())
        return entries

    def touch_file(self, path: str | Path, *, exist_ok: bool = True, parents: bool = False) -> Path:  # type: ignore[override]
        path = Path(path)
        if parents:
            self._ensure_dir(path.parent)
        elif path.parent not in self._dirs:
            raise FileNotFoundError(path.parent)

        if not exist_ok and path in self._files:
            raise FileExistsError(path)
        self._files.setdefault(path, b"")
        return path

    def create_text_file(
        self,
        path: str | Path,
        text: str,
        *,
        encoding: str = "utf-8",
        exist_ok: bool = True,
        parents: bool = False,
    ) -> Path:  # type: ignore[override]
        path = Path(path)
        if parents:
            self._ensure_dir(path.parent)
        elif path.parent not in self._dirs:
            raise FileNotFoundError(path.parent)

        if not exist_ok and path in self._files:
            raise FileExistsError(path)
        self._files[path] = text.encode(encoding)
        return path

    def make_directory(
        self,
        path: str | Path,
        *,
        exist_ok: bool = True,
        parents: bool = False,
    ) -> Path:  # type: ignore[override]
        path = Path(path)
        if parents:
            self._ensure_dir(path)
        else:
            if path.parent not in self._dirs:
                raise FileNotFoundError(path.parent)
            if path in self._dirs and not exist_ok:
                raise FileExistsError(path)
            self._dirs.add(path)
        return path

    def copy_path(
        self,
        src: str | Path,
        dst: str | Path,
        *,
        options: CopyOptions | None = None,
    ) -> Path:  # type: ignore[override]
        options = options or CopyOptions()
        src = Path(src)
        dst = Path(dst)

        if src in self._dirs:
            if not options.recursive:
                raise IsADirectoryError(src)
            raise NotImplementedError("FakeFileSystem: directory copy not implemented")

        if src not in self._files:
            raise FileNotFoundError(src)

        if dst in self._files and not options.overwrite:
            raise FileExistsError(dst)

        self._ensure_dir(dst.parent)
        self._files[dst] = self._files[src]
        return dst

    def move_path(self, src: str | Path, dst: str | Path, *, overwrite: bool = False) -> Path:  # type: ignore[override]
        src = Path(src)
        dst = Path(dst)

        if src in self._dirs:
            raise NotImplementedError("FakeFileSystem: directory move not implemented")

        if src not in self._files:
            raise FileNotFoundError(src)

        if dst in self._files and not overwrite:
            raise FileExistsError(dst)

        self._ensure_dir(dst.parent)
        self._files[dst] = self._files.pop(src)
        return dst

    def rename(self, src: str | Path, new_name: str, *, overwrite: bool = False) -> Path:  # type: ignore[override]
        src = Path(src)
        return self.move_path(src, src.parent / new_name, overwrite=overwrite)

    def delete(self, path: str | Path, *, options: DeleteOptions | None = None) -> None:  # type: ignore[override]
        options = options or DeleteOptions()
        path = Path(path)

        if path in self._files:
            del self._files[path]
            return

        if path in self._dirs:
            if not options.recursive:
                raise IsADirectoryError(path)

            # Remove nested files/dirs.
            for f in list(self._files):
                if path in f.parents:
                    del self._files[f]
            for d in sorted(self._dirs, key=lambda p: len(p.parts), reverse=True):
                if d == path or path in d.parents:
                    self._dirs.discard(d)
            return

        if options.force:
            return
        raise FileNotFoundError(path)

    def open_file_external(self, path: str | Path) -> None:  # type: ignore[override]
        self.opened_files.append(Path(path))
        return

    def path_exists(self, path: str | Path) -> bool:  # type: ignore[override]
        path = Path(path)
        return path in self._dirs or path in self._files

    def _ensure_dir(self, path: Path) -> None:
        cur = path
        # Build parents from root-ish to leaf.
        parts = list(cur.parts)
        if not parts:
            return
        acc = Path(parts[0])
        self._dirs.add(acc)
        for part in parts[1:]:
            acc = acc / part
            self._dirs.add(acc)

    def _make_entry(self, path: Path) -> FileEntry:
        is_dir = path in self._dirs
        is_file = path in self._files
        size = len(self._files.get(path, b"")) if is_file else 0
        return FileEntry(
            path=path,
            name=path.name,
            is_dir=is_dir,
            is_file=is_file,
            is_symlink=False,
            size=size,
            mtime=None,
            hidden=False,
        )


@pytest.fixture(scope="module")
def qapp() -> QtCore.QCoreApplication:
    app = QtCore.QCoreApplication.instance()
    if app is None:
        app = QtCore.QCoreApplication([])
    return app


class SignalCatcher:
    def __init__(self, signal: Any) -> None:
        self._signal = signal
        self.calls: list[tuple[Any, ...]] = []
        signal.connect(self._handler)

    def _handler(self, *args: Any) -> None:
        self.calls.append(args)

    def disconnect(self) -> None:
        self._signal.disconnect(self._handler)


def wait_until(condition: Callable[[], bool], *, timeout_ms: int = 2000) -> None:
    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)

    poll = QtCore.QTimer()
    poll.setInterval(0)

    def check() -> None:
        if condition():
            loop.quit()

    poll.timeout.connect(check)
    poll.start()

    while timer.isActive() and not condition():
        loop.exec()

    poll.stop()
    assert condition(), "timed out waiting for condition"


def make_manager(
    app: QtCore.QCoreApplication,
) -> tuple[FileManagerStateManager, FakeFileSystem, Path, Path]:
    fs = FakeFileSystem()
    base = Path("base")
    root = base / "root"
    dst = base / "dst"
    fs.add_dir(base)
    fs.add_dir(root)
    fs.add_dir(dst)
    fs.add_file(root / "a.txt", b"1")
    fs.add_file(root / "b", b"22")

    manager = FileManagerStateManager(app, fs)
    return manager, fs, root, dst


class TestRefresh:
    def test_set_current_directory_emits_and_refreshes(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)

        state_changed = SignalCatcher(manager.stateChanged)
        try:
            manager.set_current_directory(root)
            wait_until(
                lambda: (
                    manager.state().current_directory == root
                    and not manager.state().is_refreshing
                    and len(manager.state().entries) == 2
                )
            )

            assert any(
                isinstance(args[0], FileManagerState) and args[0].current_directory == root
                for args in state_changed.calls
            )
        finally:
            state_changed.disconnect()

        state = manager.state()
        assert state.current_directory == root
        assert len(state.entries) == 2

    def test_show_hidden_change_triggers_refresh(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)

        state_changed = SignalCatcher(manager.stateChanged)
        try:
            manager.set_current_directory(root)
            wait_until(
                lambda: manager.state().current_directory == root
                and not manager.state().is_refreshing
            )

            manager.set_show_hidden(True)
            wait_until(lambda: manager.state().show_hidden is True)
            wait_until(
                lambda: manager.state().current_directory == root
                and not manager.state().is_refreshing
            )

            # Ensure we observed a "refreshing" transition.
            assert any(
                isinstance(args[0], FileManagerState) and args[0].is_refreshing
                for args in state_changed.calls
            )
        finally:
            state_changed.disconnect()


class TestDialogs:
    def test_request_create_file_emits_dialog_signal(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)
        manager.set_current_directory(root)

        requested = SignalCatcher(manager.createFileDialogRequested)
        try:
            wait_until(
                lambda: manager.state().current_directory == root
                and not manager.state().is_refreshing
            )
            manager.request_create_file()
            wait_until(lambda: len(requested.calls) >= 1)
            assert requested.calls[-1][0] == root
        finally:
            requested.disconnect()

    def test_request_create_directory_emits_dialog_signal(
        self, qapp: QtCore.QCoreApplication
    ) -> None:
        manager, _fs, root, _dst = make_manager(qapp)
        manager.set_current_directory(root)

        requested = SignalCatcher(manager.createDirectoryDialogRequested)
        try:
            wait_until(
                lambda: manager.state().current_directory == root
                and not manager.state().is_refreshing
            )
            manager.request_create_directory()
            wait_until(lambda: len(requested.calls) >= 1)
            assert requested.calls[-1][0] == root
        finally:
            requested.disconnect()

    def test_request_rename_emits_dialog_signal(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)

        requested = SignalCatcher(manager.renameDialogRequested)
        try:
            manager.set_current_directory(root)
            wait_until(
                lambda: manager.state().current_directory == root
                and not manager.state().is_refreshing
            )

            entry_a = next(e for e in manager.state().entries if e.name == "a.txt")
            manager.set_selected_entry(entry_a)

            manager.request_rename_selected()
            wait_until(lambda: len(requested.calls) >= 1)
            assert requested.calls[-1][0].path == entry_a.path
        finally:
            requested.disconnect()


class TestOperations:
    def test_create_file_emits_operation_and_refreshes(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)

        try:
            manager.set_current_directory(root)
            wait_until(
                lambda: manager.state().current_directory == root
                and not manager.state().is_refreshing
            )

            manager.create_file("new.txt")
            wait_until(lambda: manager.state().last_operation == "create")
            wait_until(lambda: manager.state().last_operation_error is None)
            wait_until(lambda: fs.path_exists(root / "new.txt"))
            wait_until(
                lambda: (
                    manager.state().selected_entry is not None
                    and manager.state().selected_entry.path == root / "new.txt"
                )
            )
        finally:
            pass

        assert fs.path_exists(root / "new.txt")
        assert manager.state().selected_entry is not None
        assert manager.state().selected_entry.path == root / "new.txt"

    def test_create_file_can_write_initial_text(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)

        manager.set_current_directory(root)
        wait_until(
            lambda: manager.state().current_directory == root and not manager.state().is_refreshing
        )

        manager.create_file("hello.txt", "line1\nline2")
        wait_until(lambda: manager.state().last_operation == "create")
        wait_until(lambda: manager.state().last_operation_error is None)
        wait_until(lambda: fs.path_exists(root / "hello.txt"))

        assert (root / "hello.txt") in fs._files
        assert fs._files[root / "hello.txt"] == b"line1\nline2"

    def test_create_directory_creates_and_selects(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)

        manager.set_current_directory(root)
        wait_until(
            lambda: manager.state().current_directory == root and not manager.state().is_refreshing
        )

        manager.create_directory("new_folder")
        wait_until(lambda: manager.state().last_operation == "create_dir")
        wait_until(lambda: manager.state().last_operation_error is None)
        wait_until(lambda: fs.path_exists(root / "new_folder"))

        wait_until(
            lambda: (
                manager.state().selected_entry is not None
                and manager.state().selected_entry.path == root / "new_folder"
                and manager.state().selected_entry.is_dir
            )
        )

    def test_delete_selected_removes_file(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)

        manager.set_current_directory(root)
        wait_until(
            lambda: manager.state().current_directory == root and not manager.state().is_refreshing
        )

        # Select b (no extension)
        entry_b = next(e for e in manager.state().entries if e.name == "b")
        manager.set_selected_entry(entry_b)

        manager.delete_selected()
        wait_until(lambda: manager.state().last_operation == "delete")
        wait_until(lambda: manager.state().last_operation_error is None)
        wait_until(lambda: not fs.path_exists(root / "b"))
        wait_until(lambda: manager.state().selected_entry is None)

        assert not fs.path_exists(root / "b")
        assert manager.state().selected_entry is None

    def test_copy_cut_clipboard_is_mutually_exclusive(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)

        manager.set_current_directory(root)
        wait_until(
            lambda: manager.state().current_directory == root and not manager.state().is_refreshing
        )

        entry_a = next(e for e in manager.state().entries if e.name == "a.txt")
        manager.set_selected_entry(entry_a)

        manager.copy_selected()
        wait_until(lambda: manager.state().clipboard_path == entry_a.path)
        wait_until(lambda: manager.state().clipboard_mode == "copy")

        manager.cut_selected()
        wait_until(lambda: manager.state().clipboard_path == entry_a.path)
        wait_until(lambda: manager.state().clipboard_mode == "cut")

    def test_rename_selected_renames_file(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)

        manager.set_current_directory(root)
        wait_until(
            lambda: manager.state().current_directory == root and not manager.state().is_refreshing
        )

        entry_a = next(e for e in manager.state().entries if e.name == "a.txt")
        manager.set_selected_entry(entry_a)

        manager.rename_selected("renamed.txt")
        wait_until(lambda: manager.state().last_operation == "rename")
        wait_until(lambda: manager.state().last_operation_error is None)
        wait_until(lambda: not fs.path_exists(root / "a.txt"))
        wait_until(lambda: fs.path_exists(root / "renamed.txt"))

        assert not fs.path_exists(root / "a.txt")
        assert fs.path_exists(root / "renamed.txt")

    def test_paste_copy_copies_and_clears_clipboard(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, dst = make_manager(qapp)

        manager.set_current_directory(root)
        wait_until(
            lambda: manager.state().current_directory == root and not manager.state().is_refreshing
        )

        entry_a = next(e for e in manager.state().entries if e.name == "a.txt")
        manager.set_selected_entry(entry_a)
        manager.copy_selected()
        wait_until(lambda: manager.state().clipboard_mode == "copy")

        manager.set_current_directory(dst)
        wait_until(
            lambda: manager.state().current_directory == dst and not manager.state().is_refreshing
        )

        manager.paste()
        wait_until(lambda: manager.state().last_operation == "paste_copy")
        wait_until(lambda: manager.state().last_operation_error is None)
        wait_until(lambda: fs.path_exists(dst / "a.txt"))
        wait_until(
            lambda: manager.state().clipboard_path is None
            and manager.state().clipboard_mode is None
        )

        assert fs.path_exists(dst / "a.txt")
        assert manager.state().clipboard_path is None
        assert manager.state().clipboard_mode is None

    def test_paste_cut_moves_and_clears_clipboard(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, dst = make_manager(qapp)

        manager.set_current_directory(root)
        wait_until(
            lambda: manager.state().current_directory == root and not manager.state().is_refreshing
        )

        entry_b = next(e for e in manager.state().entries if e.name == "b")
        manager.set_selected_entry(entry_b)
        manager.cut_selected()
        wait_until(lambda: manager.state().clipboard_mode == "cut")

        manager.set_current_directory(dst)
        wait_until(
            lambda: manager.state().current_directory == dst and not manager.state().is_refreshing
        )

        manager.paste()
        wait_until(lambda: manager.state().last_operation == "paste_cut")
        wait_until(lambda: manager.state().last_operation_error is None)
        wait_until(lambda: not fs.path_exists(root / "b"))
        wait_until(lambda: fs.path_exists(dst / "b"))
        wait_until(
            lambda: manager.state().clipboard_path is None
            and manager.state().clipboard_mode is None
        )

        assert not fs.path_exists(root / "b")
        assert fs.path_exists(dst / "b")
        assert manager.state().clipboard_path is None
        assert manager.state().clipboard_mode is None


class TestNavigation:
    def test_enter_directory_switches_directory(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)
        subdir = root / "subdir"
        fs.add_dir(subdir)
        fs.add_file(subdir / "inside.txt", b"x")

        manager.set_current_directory(root)
        wait_until(
            lambda: manager.state().current_directory == root and not manager.state().is_refreshing
        )

        entry_subdir = next(e for e in manager.state().entries if e.path == subdir)
        manager.set_selected_entry(entry_subdir)

        manager.enter_selected()
        wait_until(lambda: manager.state().current_directory == subdir)
        wait_until(lambda: not manager.state().is_refreshing)

        assert manager.state().current_directory == subdir
        assert any(e.name == "inside.txt" for e in manager.state().entries)

    def test_enter_file_opens_file(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)

        manager.set_current_directory(root)
        wait_until(
            lambda: manager.state().current_directory == root and not manager.state().is_refreshing
        )

        entry_a = next(e for e in manager.state().entries if e.name == "a.txt")
        manager.set_selected_entry(entry_a)

        manager.enter_selected()
        wait_until(lambda: manager.state().last_operation == "open")
        wait_until(lambda: manager.state().last_operation_error is None)

        assert manager.state().current_directory == root
        assert fs.opened_files == [root / "a.txt"]

    def test_go_up_goes_to_parent(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)
        parent = root.parent

        manager.set_current_directory(root)
        wait_until(
            lambda: manager.state().current_directory == root and not manager.state().is_refreshing
        )

        manager.go_up()
        wait_until(lambda: manager.state().current_directory == parent)
        wait_until(lambda: not manager.state().is_refreshing)

        assert manager.state().current_directory == parent
