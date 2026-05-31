"""Custom exceptions for the marketstall runtime."""

from __future__ import annotations


class MalformedMarketplaceError(RuntimeError):
    """Raised when a marketplace or marketstall file is invalid.

    Covers TOML parse errors and schema violations in both
    ~/.haywire/db/haybale-marketplace/marketplace.toml (global) and
    <project>/.haywire/marketplace.toml (project). The Library
    Manager surfaces this with an Edit File banner; it does not recover
    automatically.
    """


class DuplicateHeapNameError(RuntimeError):
    """Raised when adding a [[heaps]] entry with a name that already exists.

    Applies to project marketplaces (heaps live only there).
    haywire init may swallow this for idempotent re-runs of the same dev-repo
    library declaration.
    """


class RemoteFetchError(RuntimeError):
    """Raised by the HTTP cache layer when a remote URL is unreachable AND no cache exists.

    Always caught by the refresh orchestrator and converted to the `unavailable`
    tri-state outcome; never propagates to the UI as an exception.
    """
