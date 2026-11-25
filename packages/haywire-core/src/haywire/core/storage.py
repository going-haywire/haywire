"""Storage directory helpers: a library's folder under ``~/.haywire/db/``, and a ``.haywire/`` folder."""

from __future__ import annotations

from pathlib import Path

#: The folder name of a project's local state (ADR 0096).
HAYWIRE_DIR = ".haywire"

#: What ``.haywire/.gitignore`` holds: everything in the folder, itself included.
_IGNORE_ALL = "*\n"


def library_storage_dir(caller_module: str) -> Path:
    """Return (and create) ``~/.haywire/db/<top_package>/`` for the calling module.

    Pass ``__name__`` as the argument — the top-level package is derived
    automatically, so ``haybale_marketplace.config`` → ``haybale_marketplace``.
    The folder is named after the top-level **module** (``haybale_marketplace``),
    never the distribution (``haybale-marketplace``).
    """
    top = caller_module.split(".")[0]
    path = Path.home() / ".haywire" / "db" / top
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_haywire_dir(directory: Path) -> Path:
    """Create *directory*; when it is a ``.haywire/`` folder, make git ignore all of it.

    Nothing in a project's ``.haywire/`` is committed (ADR 0096), so every
    writer creates the folder through here instead of ``mkdir``. A folder named
    ``.haywire`` gets a ``.gitignore`` holding ``*`` whenever its own does not
    hold that line, replacing what the file held. Any other folder is only
    created.

    Args:
        directory: The folder a file is about to be written into.

    Returns:
        *directory*, for chaining.
    """
    directory.mkdir(parents=True, exist_ok=True)
    if directory.name != HAYWIRE_DIR:
        return directory
    gitignore = directory / ".gitignore"
    try:
        lines = gitignore.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []
    if "*" not in (line.strip() for line in lines):
        gitignore.write_text(_IGNORE_ALL, encoding="utf-8")
    return directory
