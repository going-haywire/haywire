"""Custom exceptions for the marketstall runtime."""

from __future__ import annotations


class MalformedMarketplaceError(RuntimeError):
    """Raised when a marketplace or marketstall file is invalid.

    Covers TOML parse errors and schema violations in both
    ~/.haywire/db/haybale-marketplace/marketplace.toml (global) and
    <project>/.haywire/marketplace.toml (project).
    """


class DuplicateHeapNameError(RuntimeError):
    """Raised when adding a [[heaps]] entry with a name that already exists.

    Applies to project marketplaces (heaps live only there).
    """


class RemoteFetchError(RuntimeError):
    """Raised by the HTTP cache layer when a remote URL is unreachable and no cache exists."""
