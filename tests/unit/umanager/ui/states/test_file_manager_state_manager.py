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
from umanager.ui.states import FileManagerStateManager


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

    def copy_path(
        self, src: str | Path, dst: str | Path, *, options: CopyOptions | None = None
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

        dir_changed = SignalCatcher(manager.currentDirectoryChanged)
        refresh_finished = SignalCatcher(manager.refreshFinished)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: len(refresh_finished.calls) >= 1)

            assert dir_changed.calls == [(root,)]
            assert refresh_finished.calls[-1][0] == root
        finally:
            dir_changed.disconnect()
            refresh_finished.disconnect()

        state = manager.state()
        assert state.current_directory == root
        assert len(state.entries) == 2

    def test_show_hidden_change_triggers_refresh(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)

        refresh_finished = SignalCatcher(manager.refreshFinished)
        hidden_changed = SignalCatcher(manager.showHiddenChanged)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: len(refresh_finished.calls) >= 1)
            before = len(refresh_finished.calls)

            manager.set_show_hidden(True)
            wait_until(lambda: len(hidden_changed.calls) >= 1)
            wait_until(lambda: len(refresh_finished.calls) >= before + 1)
        finally:
            refresh_finished.disconnect()
            hidden_changed.disconnect()


class TestDialogs:
    def test_request_create_file_emits_dialog_signal(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)
        manager.set_current_directory(root)

        refresh_finished = SignalCatcher(manager.refreshFinished)
        requested = SignalCatcher(manager.createFileDialogRequested)
        try:
            wait_until(lambda: len(refresh_finished.calls) >= 1)
            manager.request_create_file()
            wait_until(lambda: len(requested.calls) >= 1)
            assert requested.calls[-1][0] == root
        finally:
            refresh_finished.disconnect()
            requested.disconnect()

    def test_request_rename_emits_dialog_signal(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)

        refresh_finished = SignalCatcher(manager.refreshFinished)
        requested = SignalCatcher(manager.renameDialogRequested)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: len(refresh_finished.calls) >= 1)

            entry_a = next(e for e in manager.state().entries if e.name == "a.txt")
            manager.set_selected_entry(entry_a)

            manager.request_rename_selected()
            wait_until(lambda: len(requested.calls) >= 1)
            assert requested.calls[-1][0].path == entry_a.path
        finally:
            refresh_finished.disconnect()
            requested.disconnect()


class TestOperations:
    def test_create_file_emits_operation_and_refreshes(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)

        refresh_finished = SignalCatcher(manager.refreshFinished)
        op_finished = SignalCatcher(manager.operationFinished)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: len(refresh_finished.calls) >= 1)
            before = len(refresh_finished.calls)

            manager.create_file("new.txt")
            wait_until(lambda: any(args[0] == "create" for args in op_finished.calls))
            wait_until(lambda: len(refresh_finished.calls) >= before + 1)
        finally:
            refresh_finished.disconnect()
            op_finished.disconnect()

        assert fs.path_exists(root / "new.txt")
        assert manager.state().selected_entry is not None
        assert manager.state().selected_entry.path == root / "new.txt"

    def test_delete_selected_removes_file(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)

        refresh_finished = SignalCatcher(manager.refreshFinished)
        op_finished = SignalCatcher(manager.operationFinished)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: len(refresh_finished.calls) >= 1)
            before = len(refresh_finished.calls)

            # Select b (no extension)
            entry_b = next(e for e in manager.state().entries if e.name == "b")
            manager.set_selected_entry(entry_b)

            manager.delete_selected()
            wait_until(lambda: any(args[0] == "delete" for args in op_finished.calls))
            wait_until(lambda: len(refresh_finished.calls) >= before + 1)
        finally:
            refresh_finished.disconnect()
            op_finished.disconnect()

        assert not fs.path_exists(root / "b")
        assert manager.state().selected_entry is None

    def test_copy_cut_clipboard_is_mutually_exclusive(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)

        refresh_finished = SignalCatcher(manager.refreshFinished)
        clipboard_changed = SignalCatcher(manager.clipboardChanged)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: len(refresh_finished.calls) >= 1)

            entry_a = next(e for e in manager.state().entries if e.name == "a.txt")
            manager.set_selected_entry(entry_a)

            manager.copy_selected()
            wait_until(
                lambda: any(
                    args[0] == entry_a.path and args[1] == "copy"
                    for args in clipboard_changed.calls
                )
            )

            manager.cut_selected()
            wait_until(
                lambda: any(
                    args[0] == entry_a.path and args[1] == "cut" for args in clipboard_changed.calls
                )
            )
        finally:
            refresh_finished.disconnect()
            clipboard_changed.disconnect()

    def test_rename_selected_renames_file(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)

        refresh_finished = SignalCatcher(manager.refreshFinished)
        op_finished = SignalCatcher(manager.operationFinished)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: len(refresh_finished.calls) >= 1)
            before = len(refresh_finished.calls)

            entry_a = next(e for e in manager.state().entries if e.name == "a.txt")
            manager.set_selected_entry(entry_a)

            manager.rename_selected("renamed.txt")
            wait_until(lambda: any(args[0] == "rename" for args in op_finished.calls))
            wait_until(lambda: len(refresh_finished.calls) >= before + 1)
        finally:
            refresh_finished.disconnect()
            op_finished.disconnect()

        assert not fs.path_exists(root / "a.txt")
        assert fs.path_exists(root / "renamed.txt")

    def test_paste_copy_copies_and_clears_clipboard(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, dst = make_manager(qapp)

        refresh_finished = SignalCatcher(manager.refreshFinished)
        op_finished = SignalCatcher(manager.operationFinished)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: len(refresh_finished.calls) >= 1)

            entry_a = next(e for e in manager.state().entries if e.name == "a.txt")
            manager.set_selected_entry(entry_a)
            manager.copy_selected()

            before = len(refresh_finished.calls)
            manager.set_current_directory(dst)
            wait_until(lambda: any(args[0] == dst for args in refresh_finished.calls[before:]))
            before = len(refresh_finished.calls)

            manager.paste()
            wait_until(lambda: any(args[0] == "paste_copy" for args in op_finished.calls))
            wait_until(lambda: any(args[0] == dst for args in refresh_finished.calls[before:]))
        finally:
            refresh_finished.disconnect()
            op_finished.disconnect()

        assert fs.path_exists(dst / "a.txt")
        assert manager.state().clipboard_path is None
        assert manager.state().clipboard_mode is None

    def test_paste_cut_moves_and_clears_clipboard(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, dst = make_manager(qapp)

        refresh_finished = SignalCatcher(manager.refreshFinished)
        op_finished = SignalCatcher(manager.operationFinished)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: len(refresh_finished.calls) >= 1)

            entry_b = next(e for e in manager.state().entries if e.name == "b")
            manager.set_selected_entry(entry_b)
            manager.cut_selected()

            before = len(refresh_finished.calls)
            manager.set_current_directory(dst)
            wait_until(lambda: any(args[0] == dst for args in refresh_finished.calls[before:]))
            before = len(refresh_finished.calls)

            manager.paste()
            wait_until(lambda: any(args[0] == "paste_cut" for args in op_finished.calls))
            wait_until(lambda: any(args[0] == dst for args in refresh_finished.calls[before:]))
        finally:
            refresh_finished.disconnect()
            op_finished.disconnect()

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

        refresh_finished = SignalCatcher(manager.refreshFinished)
        dir_changed = SignalCatcher(manager.currentDirectoryChanged)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: any(args[0] == root for args in refresh_finished.calls))

            entry_subdir = next(e for e in manager.state().entries if e.path == subdir)
            manager.set_selected_entry(entry_subdir)

            manager.enter_selected()
            wait_until(lambda: any(args[0] == subdir for args in refresh_finished.calls))
            wait_until(lambda: any(args[0] == subdir for args in dir_changed.calls))
        finally:
            refresh_finished.disconnect()
            dir_changed.disconnect()

        assert manager.state().current_directory == subdir
        assert any(e.name == "inside.txt" for e in manager.state().entries)

    def test_enter_file_opens_file(self, qapp: QtCore.QCoreApplication) -> None:
        manager, fs, root, _dst = make_manager(qapp)

        refresh_finished = SignalCatcher(manager.refreshFinished)
        op_finished = SignalCatcher(manager.operationFinished)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: any(args[0] == root for args in refresh_finished.calls))

            entry_a = next(e for e in manager.state().entries if e.name == "a.txt")
            manager.set_selected_entry(entry_a)

            manager.enter_selected()
            wait_until(lambda: any(args[0] == "open" for args in op_finished.calls))
        finally:
            refresh_finished.disconnect()
            op_finished.disconnect()

        assert manager.state().current_directory == root
        assert fs.opened_files == [root / "a.txt"]

    def test_go_up_goes_to_parent(self, qapp: QtCore.QCoreApplication) -> None:
        manager, _fs, root, _dst = make_manager(qapp)
        parent = root.parent

        refresh_finished = SignalCatcher(manager.refreshFinished)
        try:
            manager.set_current_directory(root)
            wait_until(lambda: any(args[0] == root for args in refresh_finished.calls))

            manager.go_up()
            wait_until(lambda: any(args[0] == parent for args in refresh_finished.calls))
        finally:
            refresh_finished.disconnect()

        assert manager.state().current_directory == parent
