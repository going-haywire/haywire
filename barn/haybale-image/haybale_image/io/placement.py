"""Save-target placement: the ``if_exists`` policy and an atomic file write."""

import contextlib
import os
import uuid
from enum import StrEnum
from pathlib import Path


class IfExists(StrEnum):
    """What a save does when its target file already exists."""

    OVERWRITE = "overwrite"
    SKIP = "skip"
    UNIQUE_SUFFIX = "unique-suffix"


def _claim(path: Path) -> bool:
    """Create ``path`` as an empty placeholder; False if it already exists."""
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.close(fd)
    return True


def claim_target(target: Path, if_exists: IfExists) -> Path | None:
    """Decide where a save writes, per ``if_exists``.

    - OVERWRITE: returns ``target``; nothing is created.
    - SKIP: returns ``None`` if ``target`` exists, else ``target``; nothing is created.
      This is check-then-act, not a claim: a concurrent save may still create the file.
    - UNIQUE_SUFFIX: claims ``target`` (or ``stem_1.ext``, ``stem_2.ext``, ...) with
      ``O_CREAT | O_EXCL``, so concurrent saves never pick the same path. The claimed
      file is an empty placeholder that ``atomic_write`` then replaces; the caller must
      pass ``placeholder=True`` to ``atomic_write`` for it.

    Args:
        target: Requested file path.
        if_exists: Policy when ``target`` exists.

    Returns:
        The path to write, or ``None`` to skip the save.

    Raises:
        FileNotFoundError: If the target's folder does not exist (every mode).
    """
    folder = target.parent
    if not folder.is_dir():
        raise FileNotFoundError(f"folder {folder} does not exist — add Create Folder before Save")
    if if_exists is IfExists.OVERWRITE:
        return target
    if if_exists is IfExists.SKIP:
        return None if target.exists() else target
    if _claim(target):
        return target
    n = 1
    while True:
        candidate = target.with_name(f"{target.stem}_{n}{target.suffix}")
        if _claim(candidate):
            return candidate
        n += 1


def atomic_write(target: Path, data: bytes, *, placeholder: bool = False) -> None:
    """Write ``data`` to ``target`` so readers never see a partial file.

    Writes ``.<name>.<uuid8>.tmp`` beside the target (same filesystem), fsyncs it,
    then ``os.replace``s it over ``target``. On failure the temp is removed and the
    error re-raised; ``target`` is removed too only when ``placeholder`` is true.

    Args:
        target: Destination file path.
        data: Bytes to write.
        placeholder: True when ``target`` is the empty placeholder that ``claim_target``
            created for ``IfExists.UNIQUE_SUFFIX``; it is then removed if the write fails.
    """
    tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        if placeholder:
            with contextlib.suppress(OSError):
                target.unlink(missing_ok=True)
        raise
