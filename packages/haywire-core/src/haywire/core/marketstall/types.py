"""Marketstall runtime dataclasses.

These describe *distribution and transport* — feeds and refresh runs — not
libraries. ``Haybale`` (the library metadata record itself) lives in
:mod:`haywire.core.library.haybale`; the [[markets]] and [[stalls]]
subscription dataclasses here carry a ``blocked`` array for the first-install
safety modal.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from haywire.core.library.haybale import Haybale


@dataclass(frozen=True)
class Subscription:
    """One [[markets]] or [[stalls]] entry. Same shape; distinction is which list it lives in.

    Both arrays are user intent — a refresh never writes here.

    ``preference`` names the haybales this source should *win* when several
    offer the same name; it is exclusive, so one write settles a collision at
    any source count and the outcome does not depend on subscription order.
    ``blocked`` names those the user rejected in the install-safety modal,
    un-blockable only by editing the file.
    """

    url: str
    preference: list[str] = field(default_factory=list)
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


@dataclass(frozen=True)
class SourceCollision:
    """One library name offered by more than one source during a single resolve.

    Carries versions alongside URLs because the user-visible consequence of a
    collision is usually a version change, not a provenance change.

    Distinct from :class:`SubscriptionConflict`, which is the *add-source*
    check against the cached catalog. This one is a *standing* collision
    between sources already subscribed, detected on every refresh.
    """

    name: str
    winner_url: str
    winner_version: str
    losers: list[tuple[str, str]] = field(default_factory=list)
    """``(source_url, version)`` per discarded copy — the URL to *display*."""

    loser_owners: list[str] = field(default_factory=list)
    """Parallel to ``losers``: the subscription URL a preference for that copy
    must be written against. Differs from the displayed URL only for a stall
    discovered through an aggregator, which the user cannot subscribe to
    directly."""

    same_library: bool = True
    """Whether every claimant is provably the same library.

    ``True`` — several feeds carrying one library; "which source?" is a
    preference, and the versions are comparable.

    ``False`` — different libraries wearing one name, which the marketplace
    has no namespace to prevent. Not a preference: choosing one picks *which
    project you mean*, so the UI must not offer them as interchangeable.

    What counts as "provably the same" is policy the marketplace owns and
    passes to :func:`~haywire.core.marketstall.refresh.resolve`; core records
    the answer without knowing the rule. Defaults ``True`` so a caller that
    supplies no comparator keeps the historical name-is-identity behaviour."""

    @property
    def source_count(self) -> int:
        """How many sources offered this name — winner included."""
        return 1 + len(self.losers)


@dataclass
class ResolvedCatalog:
    """The catalog the apply phase would write, plus the deltas that justify it.

    Produced without mutating anything, so a UI can show "3 newly stale, 2
    updates available" and let the user decide whether to commit the write.
    ``newly_stale`` / ``newly_added`` are names, not Haybales — they exist to
    be listed in a confirmation panel.

    ``collisions`` is the same idea applied to dedup: the names several sources
    offered, and which copy won — so the refresh flow can show a version
    downgrade *before* the write rather than leaving it to be discovered later.
    """

    haybales: list[Haybale] = field(default_factory=list)
    newly_stale: list[str] = field(default_factory=list)
    newly_added: list[str] = field(default_factory=list)
    updates_available: int = 0
    collisions: list[SourceCollision] = field(default_factory=list)

    @property
    def resolved_count(self) -> int:
        return sum(1 for h in self.haybales if not h.stale)
