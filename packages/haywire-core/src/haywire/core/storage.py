"""Per-library persistent storage directory helper."""

from __future__ import annotations

from pathlib import Path


def library_storage_dir(caller_module: str) -> Path:
    """Return (and create) ``~/.haywire/db/<top_package>/`` for the calling module.

    Pass ``__name__`` as the argument — the top-level package is derived
    automatically, so ``haybale_marketplace.config`` → ``haybale_marketplace``.
    """
    top = caller_module.split(".")[0]
    path = Path.home() / ".haywire" / "db" / top
    path.mkdir(parents=True, exist_ok=True)
    return path
