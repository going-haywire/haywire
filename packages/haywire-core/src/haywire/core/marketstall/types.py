"""Marketstall runtime dataclasses.

``Haybale`` is one row in [[haybales]]. The [[markets]] and [[stalls]]
subscription dataclasses carry a ``blocked`` array for the first-install safety modal.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class Haybale:
    """One entry from a [[haybales]] section."""

    name: str
    version: str
    # Full PEP 440 specifier for the framework this library needs
    # (">=0.0.31", "~=0.0.31", ">=0.0.31,<1.0.0") — the author picks the
    # operator, so this is never a bare version. Empty means undeclared.
    requires_haywire: str = ""
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
    examples_url: str = ""
    tests_url: str = ""
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
        "version",
        "requires_haywire",
        "description",
        "author",
        "source",
        "install_spec",
        "tags",
        "os",
        "dependencies",
        "source_url",
        "docs_url",
        "examples_url",
        "tests_url",
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

    `blocked` holds names the user actively rejected via
    the first-install safety modal. Per-subscription; un-blockable only by
    editing the marketplace file.
    """

    url: str
    ignores: list[str] = field(default_factory=list)
    doubles: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)


@dataclass
class MarketplaceFile:
    """Parsed ~/.haywire/db/haybale-marketplace/marketplace.toml.

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
    """Parsed <project>/.haywire/marketplace.toml.

    Two section types:
      - [[heaps]]: unpublished path-based libraries (written by haywire init)
      - [[caches]]: refresh result; Haybale entries with via/last_seen/stale set

    `[[markets]]` and `[[stalls]]` never appear in the project file.
    """

    heaps: list[dict] = field(default_factory=list)
    caches: list[Haybale] = field(default_factory=list)


class RefreshOutcome(enum.Enum):
    """Tri-state per-subscription refresh result."""

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
    """Summary of a refresh run.

    sources_fetched + sources_from_cache + sources_unavailable always
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


@dataclass(frozen=True)
class SourceOutcome:
    """What one subscription URL yielded during the fetch phase.

    ``body`` is None exactly when ``outcome`` is UNAVAILABLE. ``discovered``
    marks a stall URL that came from a [[markets]] body rather than from the
    user's own subscription list — the UI labels those differently because the
    user never subscribed to them directly.
    """

    url: str
    outcome: RefreshOutcome
    body: str | None = None
    cache_age: float | None = None
    discovered: bool = False


@dataclass
class FetchedSources:
    """Read-only result of the fetch phase — no file has been written yet.

    Carries the parsed global marketplace and the previous project file so the
    resolve phase stays a pure function of this object: fetch once, resolve as
    often as the caller likes.
    """

    global_file: MarketplaceFile
    previous: ProjectMarketplaceFile
    outcomes: list[SourceOutcome] = field(default_factory=list)
    discovered_stall_urls: list[str] = field(default_factory=list)

    @property
    def sources_fetched(self) -> int:
        return sum(1 for o in self.outcomes if o.outcome is RefreshOutcome.FRESH)

    @property
    def sources_from_cache(self) -> int:
        return sum(1 for o in self.outcomes if o.outcome is RefreshOutcome.CACHE_FALLBACK)

    @property
    def unavailable_urls(self) -> list[str]:
        return [o.url for o in self.outcomes if o.outcome is RefreshOutcome.UNAVAILABLE]


@dataclass
class ResolvedCatalog:
    """The catalog the apply phase would write, plus the deltas that justify it.

    Produced without mutating anything, so a UI can show "3 newly stale, 2
    updates available" and let the user decide whether to commit the write.
    ``newly_stale`` / ``newly_added`` are names, not Haybales — they exist to
    be listed in a confirmation panel.
    """

    haybales: list[Haybale] = field(default_factory=list)
    newly_stale: list[str] = field(default_factory=list)
    newly_added: list[str] = field(default_factory=list)
    updates_available: int = 0

    @property
    def resolved_count(self) -> int:
        return sum(1 for h in self.haybales if not h.stale)
