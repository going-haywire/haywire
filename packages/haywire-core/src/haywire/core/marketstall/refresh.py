"""Refresh pipeline.

Three phases, so a refresh can be described before it is committed:

  fetch_sources()  network, no writes  → FetchedSources
  resolve()        pure, no writes     → ResolvedCatalog
  apply()          the only mutation   → RefreshReport

`refresh()` composes all three. The filter functions (apply_blocked,
apply_heaps_shadow) are pure transformations over Haybale lists.

Conflict-resolution order:
  1. apply_blocked per subscription (hide rejected names)
  2. apply_heaps_shadow across the combined candidate list
  3. dedupe, honouring `preference` where the user named a winner and falling
     back to first-come-first-served where they have not
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import replace
from pathlib import Path
from typing import Callable

from haywire.core.library.haybale import Haybale
from haywire.core.marketstall.cache import (
    fetch_with_cache_fallback,
    gc_doc_dirs,
    gc_orphans,
)
from haywire.core.marketstall.errors import RemoteFetchError
from haywire.core.marketstall.parsing import (
    parse_global_marketplace,
    parse_marketstall_body,
    parse_project_marketplace,
    parse_remote_marketplace_body,
    serialize_project_marketplace,
)
from haywire.core.marketstall.types import (
    FetchedSources,
    MarketplaceFile,
    ProjectMarketplaceFile,
    RefreshOutcome,
    RefreshReport,
    ResolvedCatalog,
    SourceCollision,
    SourceOutcome,
)


def _count_updates_available(final: list[Haybale]) -> int:
    """Count haybales whose installed distribution is older than the catalog version.

    Skips stale entries, whose stored version predates an unreachable upstream,
    entries with no version, haybales that are not installed, and versions that
    are not parseable.
    """
    import importlib.metadata as _meta

    from packaging.version import InvalidVersion, Version

    count = 0
    for h in final:
        if h.stale or not h.version:
            continue
        try:
            installed = _meta.version(h.name)
        except _meta.PackageNotFoundError:
            continue
        try:
            if Version(installed) < Version(h.version):
                count += 1
        except InvalidVersion:
            continue
    return count


def preferred_sources(mf: MarketplaceFile) -> dict[str, str]:
    """Map ``haybale name -> the subscription URL the user wants it from``.

    A name claimed by two subscriptions (hand-edit only) resolves to the first
    in file order and is still reported as a collision, so it can be re-settled.
    """
    out: dict[str, str] = {}
    for sub in [*mf.markets, *mf.stalls]:
        for name in sub.preference:
            out.setdefault(name, sub.url)
    return out


def apply_blocked(haybales: list[Haybale], blocked: list[str]) -> list[Haybale]:
    """Drop haybales whose name is in `blocked`.

    Stronger than a preference: the haybale is hidden entirely, not passed over
    in favour of another source.
    """
    if not blocked:
        return list(haybales)
    blocked_set = set(blocked)
    return [h for h in haybales if h.name not in blocked_set]


def apply_heaps_shadow(heaps: list[dict], haybales: list[Haybale]) -> list[Haybale]:
    """Drop haybales whose name matches any heap's name.

    Local heaps always win, and the shadowing is silent — no prompt, no
    diagnostic.
    """
    if not heaps:
        return list(haybales)
    heap_names = {h.get("name") for h in heaps if isinstance(h.get("name"), str)}
    return [hb for hb in haybales if hb.name not in heap_names]


def dedupe_reporting_collisions(
    haybales: list[Haybale],
    preferences: dict[str, str] | None = None,
    *,
    same_library: Callable[[Haybale, Haybale], bool] | None = None,
) -> tuple[list[Haybale], list[SourceCollision]]:
    """Deduplicate by name, returning both the survivors and what was discarded.

    The winner is the copy whose ``via`` or ``owner_url`` the user preferred;
    with no preference, or one naming a source that no longer offers the name,
    the first candidate wins, which depends on subscription order. Candidate
    order is preserved on both sides: a preferred copy takes the position of
    the first candidate for its name, so honouring a preference never
    reshuffles the catalog. A name with a single candidate reports no
    collision.

    Args:
        preferences: Haybale name to the source URL that should win it, as
            built by :func:`preferred_sources`.
        same_library: Decides whether two claimants for a name are one library
            seen through several feeds. One dissenting claimant marks the whole
            group ``same_library=False``. Omitted, every same-name candidate
            counts as the same library.
    """
    prefs = preferences or {}
    grouped: dict[str, list[Haybale]] = {}
    for hb in haybales:
        grouped.setdefault(hb.name, []).append(hb)

    out: list[Haybale] = []
    collisions: list[SourceCollision] = []
    for name, candidates in grouped.items():
        wanted = prefs.get(name)
        winner = next((h for h in candidates if wanted in (h.via, h.owner_url)), candidates[0])
        out.append(winner)
        if losers := [h for h in candidates if h is not winner]:
            collisions.append(
                SourceCollision(
                    name=name,
                    winner_url=winner.via,
                    winner_version=winner.version,
                    losers=[(h.via, h.version) for h in losers],
                    loser_owners=[h.owner_url or h.via for h in losers],
                    same_library=(
                        True if same_library is None else all(same_library(winner, h) for h in losers)
                    ),
                )
            )
    return out, collisions


def _now_iso() -> str:
    """Current UTC time as ISO 8601 with trailing Z."""
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mark_stale_against_previous(
    fresh: list[Haybale],
    *,
    previous: list[Haybale],
) -> list[Haybale]:
    """Return a list where missing-from-fresh entries are stale-marked from previous.

    - Entries in both: fresh wins, stale=False.
    - Entries in previous but not fresh: copied over and marked stale, with
      ``last_seen`` set to now. An entry already stale keeps its existing
      ``last_seen`` instead of having it bumped again.
    - Entries only in fresh: passed through unchanged.
    """
    fresh_names = {h.name for h in fresh}
    out: list[Haybale] = list(fresh)
    now = _now_iso()

    for prev in previous:
        if prev.name in fresh_names:
            continue
        if prev.stale:
            out.append(prev)
            continue
        # `replace`, not a field-by-field rebuild: a field added to Haybale is
        # then carried across a refresh without touching this line.
        out.append(replace(prev, last_seen=now, stale=True))
    return out


def _fetch_url(url: str, *, cache_dir: Path | None, discovered: bool = False) -> SourceOutcome:
    """Fetch one URL into a SourceOutcome. Never raises RemoteFetchError."""
    try:
        result = fetch_with_cache_fallback(url, cache_dir=cache_dir)
    except RemoteFetchError:
        return SourceOutcome(url=url, outcome=RefreshOutcome.UNAVAILABLE, discovered=discovered)
    return SourceOutcome(
        url=url,
        outcome=result.outcome,
        body=result.body,
        cache_age=result.cache_age,
        discovered=discovered,
    )


def fetch_sources(
    *,
    global_path: Path,
    project_path: Path,
    cache_dir: Path | None = None,
) -> FetchedSources:
    """Phase 1 — read the config files and fetch every subscription. No writes.

    Parses the global marketplace and the previous project file, fetches each
    [[markets]] subscription one level deep to discover stall URLs, then
    fetches every [[stalls]] URL, direct ones before discovered ones. A URL
    already fetched is not fetched twice.

    The only phase that touches the network: one HTTP round-trip per source.
    Bodies are returned unparsed, and nothing on disk changes.
    """
    mf = parse_global_marketplace(global_path)
    pm_prev = parse_project_marketplace(project_path)

    fetched = FetchedSources(global_file=mf, previous=pm_prev)

    # [[markets]] — fetched one level deep for the stall URLs they reference.
    for sub in mf.markets:
        outcome = _fetch_url(sub.url, cache_dir=cache_dir)
        fetched.outcomes.append(outcome)
        if outcome.body is None:
            continue
        contents = parse_remote_marketplace_body(outcome.body)
        fetched.discovered_stall_urls.extend(contents.stall_urls)

    # [[stalls]] — direct subscriptions, then the ones markets pointed at.
    seen_stall_urls: set[str] = set()
    for sub in mf.stalls:
        if sub.url in seen_stall_urls:
            continue
        seen_stall_urls.add(sub.url)
        fetched.outcomes.append(_fetch_url(sub.url, cache_dir=cache_dir))

    for url in fetched.discovered_stall_urls:
        if url in seen_stall_urls:
            continue
        seen_stall_urls.add(url)
        # Discovered stalls are anonymous (no parent Subscription).
        fetched.outcomes.append(_fetch_url(url, cache_dir=cache_dir, discovered=True))

    return fetched


def _body_for(fetched: FetchedSources, url: str) -> str | None:
    for outcome in fetched.outcomes:
        if outcome.url == url:
            return outcome.body
    return None


def candidate_haybales(fetched: FetchedSources, *, honour_blocked: bool = True) -> list[Haybale]:
    """Every haybale the fetched bodies offer, stamped with its provenance.

    Each haybale's ``via`` is set to the URL it came from; one discovered
    through a [[markets]] body also gets ``owner_url``, the subscription the
    user controls. Order is inline [[haybales]], then stalls, then
    market-inline — the order that decides a collision the user has expressed
    no preference about.

    ``honour_blocked=False`` keeps the names a subscription blocks, so a caller
    can show a blocked claimant. A refresh always drops them.
    """
    mf = fetched.global_file

    def _blocked(haybales: list[Haybale], blocked: list[str]) -> list[Haybale]:
        return apply_blocked(haybales, blocked) if honour_blocked else list(haybales)

    market_haybales: list[Haybale] = []
    for sub in mf.markets:
        body = _body_for(fetched, sub.url)
        if body is None:
            continue
        contents = parse_remote_marketplace_body(body)
        filtered = _blocked(contents.haybales, sub.blocked)
        for h in filtered:
            h.via = sub.url
        market_haybales.extend(filtered)

    stall_haybales: list[Haybale] = []
    seen_stall_urls: set[str] = set()
    for sub in mf.stalls:
        if sub.url in seen_stall_urls:
            continue
        seen_stall_urls.add(sub.url)
        body = _body_for(fetched, sub.url)
        if body is None:
            continue
        hb = _blocked(parse_marketstall_body(body), sub.blocked)
        for h in hb:
            h.via = sub.url
        stall_haybales.extend(hb)

    # Stalls a [[markets]] body pointed at. `via` stays the stall URL the
    # haybale came from; `owner_url` is the aggregator, the only subscription
    # a preference for it can be written against.
    owner = mf.markets[0].url if mf.markets else ""
    for url in fetched.discovered_stall_urls:
        if url in seen_stall_urls:
            continue
        seen_stall_urls.add(url)
        body = _body_for(fetched, url)
        if body is None:
            continue
        discovered_hb = parse_marketstall_body(body)
        for h in discovered_hb:
            h.via = url
            h.owner_url = owner
        stall_haybales.extend(discovered_hb)

    return list(mf.haybales) + stall_haybales + market_haybales


def resolve(
    fetched: FetchedSources,
    *,
    same_library: Callable[[Haybale, Haybale], bool] | None = None,
) -> ResolvedCatalog:
    """Phase 2 — turn fetched bodies into the catalog that would be written.

    Applies each subscription's blocked filter, combines the candidates (see
    :func:`candidate_haybales` for the order), shadows local heaps, dedupes
    honouring ``preference``, and stale-marks against the previous [[caches]].
    A blocked name is dropped from the previous list too, so it disappears
    rather than returning as stale.

    Pure: no network, no writes.

    Args:
        same_library: The identity policy, passed through to
            :func:`dedupe_reporting_collisions`.
    """
    mf = fetched.global_file
    pm_prev = fetched.previous

    candidates = candidate_haybales(fetched)

    candidates = apply_heaps_shadow(pm_prev.heaps, candidates)
    candidates, collisions = dedupe_reporting_collisions(
        candidates, preferred_sources(mf), same_library=same_library
    )

    blocked_names: set[str] = set()
    for sub in mf.markets:
        blocked_names.update(sub.blocked)
    for sub in mf.stalls:
        blocked_names.update(sub.blocked)
    prev_unblocked = [p for p in pm_prev.caches if p.name not in blocked_names]
    final = mark_stale_against_previous(candidates, previous=prev_unblocked)

    prev_stale_names = {p.name for p in pm_prev.caches if p.stale}
    prev_names = {p.name for p in pm_prev.caches}
    return ResolvedCatalog(
        haybales=final,
        newly_stale=[h.name for h in final if h.stale and h.name not in prev_stale_names],
        newly_added=[h.name for h in final if not h.stale and h.name not in prev_names],
        updates_available=_count_updates_available(final),
        collisions=collisions,
    )


def apply(
    fetched: FetchedSources,
    resolved: ResolvedCatalog,
    *,
    project_path: Path,
    cache_dir: Path | None = None,
) -> RefreshReport:
    """Phase 3 — write the project file and collect the caches. The only mutation.

    Rewrites <project>/.haywire/marketplace.toml with the resolved catalog,
    keeping the previous [[heaps]], then drops cache files for URLs no longer
    subscribed and doc caches for libraries no longer in the catalog.

    The global marketplace is never written by a refresh: it holds user intent
    (subscriptions, ``preference``, ``blocked``).
    """
    mf = fetched.global_file
    pm_prev = fetched.previous
    final = resolved.haybales

    new_pm = ProjectMarketplaceFile(heaps=list(pm_prev.heaps), caches=final)
    project_path.parent.mkdir(parents=True, exist_ok=True)
    body = serialize_project_marketplace(new_pm)
    project_path.write_text(body if body else "")

    # Discovered stalls count as active: they are refetched on the next run.
    active_urls: set[str] = (
        {s.url for s in mf.markets} | {s.url for s in mf.stalls} | set(fetched.discovered_stall_urls)
    )
    gc_orphans(active_urls, cache_dir=cache_dir)

    gc_doc_dirs({h.name for h in final}, cache_dir=cache_dir)

    return RefreshReport(
        sources_fetched=fetched.sources_fetched,
        sources_from_cache=fetched.sources_from_cache,
        sources_unavailable=len(fetched.unavailable_urls),
        unavailable_urls=list(fetched.unavailable_urls),
        haybales_resolved=resolved.resolved_count,
        new_stale=len(resolved.newly_stale),
        updates_available=resolved.updates_available,
    )


def refresh(
    *,
    global_path: Path,
    project_path: Path,
    cache_dir: Path | None = None,
) -> RefreshReport:
    """Run the whole refresh pipeline in one call: fetch → resolve → apply.

    Writes unconditionally. To describe a refresh before committing it, or to
    supply a ``same_library`` policy, drive the three phases separately.
    """
    fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=cache_dir)
    resolved = resolve(fetched)
    return apply(fetched, resolved, project_path=project_path, cache_dir=cache_dir)
