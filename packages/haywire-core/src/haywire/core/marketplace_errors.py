"""Custom exceptions for the two-tier marketplace runtime (spec §6)."""

from __future__ import annotations


class MalformedGlobalMarketplaceError(RuntimeError):
    """Raised when ~/.haywire/marketplace.toml is invalid (TOML parse error or schema violation).

    Per spec §6, the Library Manager refuses to start when this is raised; the
    UI surfaces the error with an "Edit file" button as the only recovery path.
    """


class DuplicateLocalNameError(RuntimeError):
    """Raised when the user-global marketplace already has a [[locals]] entry with the given name.

    This is the G5 collision (spec §6) — already enforced by Plan D's _check_global_collision
    at haywire init time. Phase 1 migrates the existing check to use this exception class.
    """


class DuplicatePackageNameError(RuntimeError):
    """Raised when a direct [[packages]] entry collides with an existing one by name.

    Per spec §6 "Two [[packages]] (direct) entries with the same name in the global —
    refused at UI write time and by the parser."
    """


class RemoteFetchError(RuntimeError):
    """Raised by the HTTP cache layer when a remote URL is unreachable.

    Always caught by the refresh orchestrator and converted to fallback-on-cache
    behavior with a "stale" badge. Never propagates to the UI as an exception;
    the UI sees a "N source unavailable" banner instead.
    """
