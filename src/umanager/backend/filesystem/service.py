from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

import win32api
import win32file

from .protocol import CopyOptions, DeleteOptions, FileEntry, ListOptions


class FileSystemService:
    def list_directory(
        self, directory: str | Path, options: ListOptions | None = None
    ) -> list[FileEntry]:
        options = options or ListOptions()
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(directory)
        if not directory.is_dir():
            raise NotADirectoryError(directory)

        entries: list[FileEntry] = []
        for child in directory.iterdir():
            is_hidden = self._is_hidden(child)
            if not options.include_hidden and is_hidden:
                continue

            stat = child.stat()
            entry = FileEntry(
                path=child,
                name=child.name,
                is_dir=child.is_dir(),
                is_file=child.is_file(),
                is_symlink=child.is_symlink(),
                size=stat.st_size,
                mtime=datetime.fromtimestamp(stat.st_mtime),
                hidden=is_hidden,
            )
            entries.append(entry)

        entries.sort(key=lambda e: e.name.casefold())
        return entries

    def _is_hidden(self, path: str | Path) -> bool:
        try:
            attr = win32api.GetFileAttributes(str(path))
            return bool(attr & win32file.FILE_ATTRIBUTE_HIDDEN)
        except Exception:
            raise OSError(f"Could not check whether the file is hidden: {path}")

    def touch_file(
        self,
        path: str | Path,
        *,
        exist_ok: bool = True,
        parents: bool = False,
    ) -> Path:
        path = Path(path)
        if parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=exist_ok)
        return path

    def make_directory(
        self,
        path: str | Path,
        *,
        exist_ok: bool = True,
        parents: bool = False,
    ) -> Path:
        path = Path(path)
        path.mkdir(parents=parents, exist_ok=exist_ok)
        return path

    def copy_path(
        self,
        src: str | Path,
        dst: str | Path,
        *,
        options: CopyOptions | None = None,
    ) -> Path:
        options = options or CopyOptions()

        src = Path(src)
        if not src.exists():
            raise FileNotFoundError(f"Source path does not exist: {src}")

        dst = Path(dst)

        def copy_file(file_src: str | Path, file_dst: str | Path) -> str:
            file_src = Path(file_src)
            file_dst = Path(file_dst)
            if not options.overwrite and file_dst.exists():
                raise FileExistsError(f"Destination path already exists: {file_dst}")
            file_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_src, file_dst)
            return str(file_dst)

        if src.is_file():
            copy_file(src, dst)
        elif src.is_dir():
            if not options.recursive:
                raise IsADirectoryError(f"Source is a directory but recursive=False: {src}")
            if dst.exists() and not dst.is_dir():
                if options.overwrite:
                    self.delete(dst)
                else:
                    raise IsADirectoryError(f"Destination is not a directory: {dst}")
            shutil.copytree(src, dst, dirs_exist_ok=True, copy_function=copy_file)
        else:
            raise TypeError(f"Unsupported path type: {src}")

        return dst

    def move_path(
        self,
        src: str | Path,
        dst: str | Path,
        *,
        overwrite: bool = False,
    ) -> Path:
        src = Path(src)
        if not src.exists():
            raise FileNotFoundError(f"Source path does not exist: {src}")

        dst = Path(dst)

        if src.is_file():
            if dst.exists() and not overwrite:
                raise FileExistsError(f"Destination path already exists: {dst}")
            if dst.exists() and overwrite:
                if dst.is_dir():
                    raise IsADirectoryError(f"Destination is a directory: {dst}")
                dst.unlink()
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
        elif src.is_dir():
            if dst.exists() and not dst.is_dir():
                if overwrite:
                    self.delete(dst)
                else:
                    raise IsADirectoryError(f"Destination is not a directory: {dst}")

            if dst.exists() and dst.is_dir():
                for child in src.iterdir():
                    self.move_path(child, dst / child.name, overwrite=overwrite)
                src.rmdir()
                return dst

            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
        else:
            raise TypeError(f"Unsupported path type: {src}")

        return dst

    def rename(
        self,
        src: str | Path,
        new_name: str,
        *,
        overwrite: bool = False,
    ) -> Path:
        src = Path(src)
        dst = src.parent / new_name
        return self.move_path(src, dst, overwrite=overwrite)

    def delete(
        self,
        path: str | Path,
        *,
        options: DeleteOptions | None = None,
    ) -> None:
        options = options or DeleteOptions()

        path = Path(path)
        if not path.exists():
            if options.force:
                return
            else:
                raise FileNotFoundError(f"Path does not exist: {path}")

        if path.is_file():
            os.remove(path)
        elif path.is_dir():
            if options.recursive:
                shutil.rmtree(path)
            else:
                raise IsADirectoryError(f"Could not recursively remove directory: {path}")
        else:
            raise TypeError(f"Unsupported path type: {path}")

    def open_file_external(self, path: str | Path) -> None:
        if not self.path_exists(path):
            raise FileNotFoundError(f"Path does not exist: {path}")
        os.startfile(str(path))

    def path_exists(self, path: str | Path) -> bool:
        path = Path(path)
        return path.exists()
