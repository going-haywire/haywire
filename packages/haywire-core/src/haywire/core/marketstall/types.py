"""Marketstall runtime dataclasses — spec §2 and §14.

The Haybale dataclass replaces the legacy MarketplaceEntry. Adds the `os` field
from §2.1; same shape otherwise. Subscription dataclasses for [[markets]] and
[[stalls]] gain the `blocked` array introduced for the first-install safety
modal (§7.4); data-layer only in this plan, wired through the UI in slice 5.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class Haybale:
    """One entry from a [[haybales]] section. Renamed from MarketplaceEntry."""

    name: str
    min_version: str
    label: str = ""
    description: str = ""
    author: str = ""
    source: str = "pypi"
    install_spec: str = ""
    tags: list[str] = field(default_factory=list)
    os: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    source_url: str = ""
    docs_url: str = ""
    # Runtime-only routing metadata (not persisted).
    source_label: str = ""
    source_file: str = ""
    source_origin: str = ""
    # Cache-only fields (project [[caches]] only).
    via: str = ""
    last_seen: str = ""
    stale: bool = False

    _TOML_FIELDS: ClassVar[tuple[str, ...]] = (
        "name",
        "label",
        "min_version",
        "description",
        "author",
        "source",
        "install_spec",
        "tags",
        "os",
        "dependencies",
        "source_url",
        "docs_url",
        "via",
        "last_seen",
        "stale",
    )

    def to_dict(self) -> dict:
        """TOML-serializable dict; omits empty/default-valued fields."""
        result: dict = {}
        for f in self._TOML_FIELDS:
            val = getattr(self, f)
            if val:
                result[f] = val
        return result


@dataclass(frozen=True)
class Subscription:
    """One [[markets]] or [[stalls]] entry. Same shape; distinction is which list it lives in.

    Per spec §3.1 / §7.4: `blocked` holds names the user actively rejected via
    the first-install safety modal. Per-subscription; un-blockable only by
    editing the marketplace file.
    """

    url: str
    ignores: list[str] = field(default_factory=list)
    doubles: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)


@dataclass
class MarketplaceFile:
    """Parsed ~/.haywire/db/haybale-marketplace/marketplace.toml — spec §3.1.

    Three section types:
      - [[markets]]: subscriptions to remote marketplaces
      - [[stalls]]: subscriptions to remote marketstalls
      - [[haybales]]: inline haybale entries (PyPI-only / aggregator-publisher case)

    `[[heaps]]` and `[[caches]]` never appear in the global file.
    """

    markets: list[Subscription] = field(default_factory=list)
    stalls: list[Subscription] = field(default_factory=list)
    haybales: list[Haybale] = field(default_factory=list)


@dataclass
class ProjectMarketplaceFile:
    """Parsed <project>/.haywire/marketplace.toml — spec §3.2.

    Two section types:
      - [[heaps]]: unpublished path-based libraries (written by haywire init)
      - [[caches]]: refresh result; Haybale entries with via/last_seen/stale set

    `[[markets]]` and `[[stalls]]` never appear in the project file.
    """

    heaps: list[dict] = field(default_factory=list)
    caches: list[Haybale] = field(default_factory=list)


class RefreshOutcome(enum.Enum):
    """Tri-state per-subscription refresh result — spec §7.3."""

    FRESH = "fresh"  # HTTP 200; cache overwritten
    CACHE_FALLBACK = "cache_fallback"  # HTTP failed; body served from cache
    UNAVAILABLE = "unavailable"  # HTTP failed; no cache


@dataclass(frozen=True)
class FetchResult:
    """Output of fetch_with_cache_fallback. Always populated when no exception is raised."""

    body: str
    outcome: RefreshOutcome
    cache_age: float | None  # Set when outcome is CACHE_FALLBACK; None for FRESH.


@dataclass
class RefreshReport:
    """Summary of a refresh run — spec §9.

    Per §7.3, sources_fetched + sources_from_cache + sources_unavailable always
    partition the active subscription set. `sources_from_cache` is the new
    middle tier that distinguishes "everything fresh" from "we recovered from
    cache" — both produce a populated catalog but only the latter warrants the
    toast "N sources served from cache" line.
    """

    sources_fetched: int = 0
    sources_from_cache: int = 0
    sources_unavailable: int = 0
    unavailable_urls: list[str] = field(default_factory=list)
    haybales_resolved: int = 0
    new_stale: int = 0
    updates_available: int = 0
