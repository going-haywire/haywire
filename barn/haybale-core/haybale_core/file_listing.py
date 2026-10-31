"""Listing the files of a folder by name patterns, for nodes that iterate over files."""

import fnmatch
import logging
import os
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.volumes import VolumePath

logger = logging.getLogger(__name__)

__all__ = ["folder_root", "list_files"]


def folder_root(folder: "VolumePath") -> Path:
    """Return the location of *folder* on this machine, checked to be a folder.

    Raises:
        NotADirectoryError: *folder* does not exist, or is a file.
        VolumeUndefinedError: *folder*'s volume has no location.
        VolumeEscapeError: *folder* leads outside its volume.
    """
    from haywire.core.volumes import resolve

    root = resolve(folder)
    if not root.is_dir():
        reason = "is not a folder" if root.exists() else "does not exist"
        raise NotADirectoryError(f"folder '{folder}' {reason}")
    return root


def list_files(root: Path, pattern: str, *, recursive: bool) -> list[PurePosixPath]:
    """Return the files under *root* whose name matches *pattern*, relative to *root*, sorted.

    *pattern* holds one or more file-name patterns (``*``, ``?``, ``[…]``) separated
    by ``;``, matched ignoring case; an empty pattern matches every file. Names
    starting with ``.`` are skipped at every depth. A symlinked folder is never
    entered; a symlinked file is listed only when it resolves inside *root*, else it
    is skipped with a warning. A subfolder that cannot be read is skipped with a warning.

    Args:
        root: An existing folder, already symlink-resolved.
        recursive: Also list the files of every subfolder.

    Raises:
        ValueError: A pattern contains ``/`` or ``\\``.
        OSError: *root* cannot be read.

    Example::

        list_files(Path("/scans").resolve(), "*.png;*.jpg", recursive=True)
        # [PurePosixPath('a.png'), PurePosixPath('raw/b.JPG')]
    """
    patterns = [p.strip().casefold() for p in pattern.split(";") if p.strip()] or ["*"]
    for p in patterns:
        if "/" in p or "\\" in p:
            raise ValueError(f"pattern '{p}' contains a folder separator; patterns match file names")

    found: set[PurePosixPath] = set()
    pending: list[tuple[Path, PurePosixPath]] = [(root, PurePosixPath())]
    first = True
    while pending:
        folder, relative = pending.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError as exc:
            if first:
                raise
            logger.warning(f"Skipping folder '{relative}': {exc}")
            continue
        first = False
        for entry in entries:
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if recursive:
                        pending.append((Path(entry.path), relative / entry.name))
                    continue
                if entry.is_symlink():
                    target = Path(entry.path).resolve()
                    if not target.is_relative_to(root):
                        logger.warning(f"Skipping '{relative / entry.name}': it links outside the folder")
                        continue
                    if not target.is_file():
                        continue
                elif not entry.is_file(follow_symlinks=False):
                    continue
            except OSError as exc:
                logger.warning(f"Skipping '{relative / entry.name}': {exc}")
                continue
            name = entry.name.casefold()
            if any(fnmatch.fnmatchcase(name, p) for p in patterns):
                found.add(relative / entry.name)
    return sorted(found, key=str)
