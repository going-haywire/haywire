"""The Haywire Studio application package."""

from __future__ import annotations


def __getattr__(name: str):
    # Lazy so that `import haywire_studio.security.*` (package init always runs
    # first) doesn't eagerly chain through .app -> auth.gate -> auth.live ->
    # auth.roster, which Task 1 of ADR 0028 deletes. Tasks 3/4/7 repair that
    # chain onto security.document; this indirection can go once they land.
    if name == "main":
        from .app import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["main"]
