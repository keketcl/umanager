from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class FileEntry:
    path: Path
    name: str
    is_dir: bool
    is_file: bool
    is_symlink: bool
    size: int
    mtime: Optional[datetime]
    hidden: bool


@dataclass(frozen=True, slots=True)
class ListOptions:
    include_hidden: bool = False


@dataclass(frozen=True, slots=True)
class CopyOptions:
    recursive: bool = True
    overwrite: bool = False


@dataclass(frozen=True, slots=True)
class DeleteOptions:
    recursive: bool = True
    force: bool = False


@runtime_checkable
class FileSystemProtocol(Protocol):
    def list_directory(
        self, directory: str | Path, options: ListOptions | None = None
    ) -> list[FileEntry]: ...

    def touch_file(
        self,
        path: str | Path,
        *,
        exist_ok: bool = True,
        parents: bool = False,
    ) -> Path: ...

    def create_text_file(
        self,
        path: str | Path,
        text: str,
        *,
        encoding: str = "utf-8",
        exist_ok: bool = True,
        parents: bool = False,
    ) -> Path: ...

    def make_directory(
        self,
        path: str | Path,
        *,
        exist_ok: bool = True,
        parents: bool = False,
    ) -> Path: ...

    def copy_path(
        self,
        src: str | Path,
        dst: str | Path,
        *,
        options: CopyOptions | None = None,
    ) -> Path: ...

    def move_path(
        self,
        src: str | Path,
        dst: str | Path,
        *,
        overwrite: bool = False,
    ) -> Path: ...

    def rename(
        self,
        src: str | Path,
        new_name: str,
        *,
        overwrite: bool = False,
    ) -> Path: ...

    def delete(
        self,
        path: str | Path,
        *,
        options: DeleteOptions | None = None,
    ) -> None: ...

    def open_file_external(self, path: str | Path) -> None: ...

    def path_exists(self, path: str | Path) -> bool: ...
