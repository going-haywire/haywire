"""Refresh pipeline.

Filter functions (apply_ignores, apply_blocked, apply_heaps_shadow,
apply_first_come_first_served) are pure transformations over Haybale lists.

The pipeline runs in three phases so a UI can show what a refresh would do
before it does it:

  fetch_sources()  network, no writes  → FetchedSources
  resolve()        pure, no writes     → ResolvedCatalog
  apply()          the only mutation   → RefreshReport

`refresh()` composes all three for callers that don't need the intermediate
steps.

Conflict-resolution order:
  1. apply_blocked per subscription (hide rejected names)
  2. apply_ignores per subscription (skip names with another preferred source)
  3. apply_heaps_shadow across the combined candidate list
  4. apply_first_come_first_served as the deterministic safety net
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

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
    Haybale,
    ProjectMarketplaceFile,
    RefreshOutcome,
    RefreshReport,
    ResolvedCatalog,
    SourceOutcome,
)


def _count_updates_available(final: list[Haybale]) -> int:
    """For each non-stale cached haybale, compare its
    `version` against the installed distribution version. Count
    entries where ``installed < cache.version``.

    Stale entries are skipped (the upstream wasn't reachable; the stored
    version is the old value and would falsely report "up-to-date").
    Uninstalled haybales are skipped (nothing to update).
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


def apply_ignores(haybales: list[Haybale], ignores: list[str]) -> list[Haybale]:
    """Drop haybales whose name is in `ignores`.

    The user picked another source for these names at conflict-
    resolution time; this subscription is asked to step aside.
    """
    if not ignores:
        return list(haybales)
    ignored = set(ignores)
    return [h for h in haybales if h.name not in ignored]


def apply_blocked(haybales: list[Haybale], blocked: list[str]) -> list[Haybale]:
    """Drop haybales whose name is in `blocked`.

    The user actively rejected these names via the first-install
    safety modal. Identical filter shape to apply_ignores; semantically a
    stronger statement (the haybale is hidden from the UI rather than just
    deduplicated against another source).
    """
    if not blocked:
        return list(haybales)
    blocked_set = set(blocked)
    return [h for h in haybales if h.name not in blocked_set]


def apply_heaps_shadow(heaps: list[dict], haybales: list[Haybale]) -> list[Haybale]:
    """Drop haybales whose name matches any heap's name.

    Local heaps always win. The dropped haybale's
    contribution is silently shadowed — no prompt, no diagnostic.
    """
    if not heaps:
        return list(haybales)
    heap_names = {h.get("name") for h in heaps if isinstance(h.get("name"), str)}
    return [hb for hb in haybales if hb.name not in heap_names]


def apply_first_come_first_served(haybales: list[Haybale]) -> list[Haybale]:
    """Deduplicate by name, keeping the first occurrence.

    A safety net for cases the per-subscription `ignores`
    didn't cover (hand-edited marketplace file, or a brand-new collision the
    UI never prompted for).
    """
    seen: set[str] = set()
    out: list[Haybale] = []
    for hb in haybales:
        if hb.name in seen:
            continue
        seen.add(hb.name)
        out.append(hb)
    return out


def _now_iso() -> str:
    """Current UTC time as ISO 8601 with trailing Z."""
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mark_stale_against_previous(
    fresh: list[Haybale],
    *,
    previous: list[Haybale],
) -> list[Haybale]:
    """Return a list where missing-from-fresh entries are stale-marked from previous.

    Semantics:
      - Entries in both: fresh wins (newest data, stale=False).
      - Entries in previous but not fresh: copied over, marked stale.
        If previous already had stale=True, the existing last_seen is preserved
        (we don't keep bumping the timestamp on each refresh).
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
        # Newly stale: copy, set stale + last_seen.
        out.append(
            Haybale(
                name=prev.name,
                version=prev.version,
                requires_haywire=prev.requires_haywire,
                label=prev.label,
                description=prev.description,
                author=prev.author,
                source=prev.source,
                install_spec=prev.install_spec,
                tags=list(prev.tags),
                os=list(prev.os),
                dependencies=list(prev.dependencies),
                source_url=prev.source_url,
                docs_url=prev.docs_url,
                examples_url=prev.examples_url,
                tests_url=prev.tests_url,
                source_label=prev.source_label,
                source_file=prev.source_file,
                source_origin=prev.source_origin,
                via=prev.via,
                last_seen=now,
                stale=True,
            )
        )
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

    Steps 1–3 of the pipeline: parse the global marketplace and the previous
    project file, fetch each [[markets]] subscription one level deep to
    discover stall URLs, then fetch every [[stalls]] URL (direct first, then
    discovered). Bodies are kept unparsed-into-candidates on the result so
    :func:`resolve` stays pure — this is the only phase that touches the
    network, and it is the expensive one (one HTTP round-trip per source).

    Nothing here mutates the project file, so a caller may show the per-source
    outcomes and stop without having changed anything.
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


def resolve(fetched: FetchedSources) -> ResolvedCatalog:
    """Phase 2 — turn fetched bodies into the catalog that would be written.

    Steps 4–6: apply each subscription's blocked/ignores filters, combine
    candidates (inline [[haybales]], then stalls, then market-inline — the
    order that gives FCFS stable provenance), shadow local heaps, dedupe, and
    stale-mark against the previous [[caches]].

    Pure: no network, no writes. The deltas on the result (``newly_stale``,
    ``newly_added``) exist so a caller can present the consequences of the
    write before :func:`apply` performs it.
    """
    mf = fetched.global_file
    pm_prev = fetched.previous

    market_haybales: list[Haybale] = []
    for sub in mf.markets:
        body = _body_for(fetched, sub.url)
        if body is None:
            continue
        contents = parse_remote_marketplace_body(body)
        filtered = apply_blocked(contents.haybales, sub.blocked)
        filtered = apply_ignores(filtered, sub.ignores)
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
        hb = parse_marketstall_body(body)
        hb = apply_blocked(hb, sub.blocked)
        hb = apply_ignores(hb, sub.ignores)
        for h in hb:
            h.via = sub.url
        stall_haybales.extend(hb)

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
        stall_haybales.extend(discovered_hb)

    candidates: list[Haybale] = list(mf.haybales) + stall_haybales + market_haybales

    candidates = apply_heaps_shadow(pm_prev.heaps, candidates)
    candidates = apply_first_come_first_served(candidates)

    # Drop blocked names from the previous list before stale-rescue: blocked
    # entries must disappear, not be re-added as stale.
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
    )


def apply(
    fetched: FetchedSources,
    resolved: ResolvedCatalog,
    *,
    project_path: Path,
    cache_dir: Path | None = None,
) -> RefreshReport:
    """Phase 3 — write the project file and GC the caches. The only mutation.

    Step 7. Split out so the two read-only phases can be shown to the user
    first; everything that makes a refresh irreversible happens here.
    """
    mf = fetched.global_file
    pm_prev = fetched.previous
    final = resolved.haybales

    new_pm = ProjectMarketplaceFile(heaps=list(pm_prev.heaps), caches=final)
    project_path.parent.mkdir(parents=True, exist_ok=True)
    body = serialize_project_marketplace(new_pm)
    project_path.write_text(body if body else "")

    # GC orphan cache files. Active URLs = all subscription URLs + discovered.
    active_urls: set[str] = (
        {s.url for s in mf.markets} | {s.url for s in mf.stalls} | set(fetched.discovered_stall_urls)
    )
    gc_orphans(active_urls, cache_dir=cache_dir)

    # GC doc caches for libraries no longer in the resolved catalog.
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

    The convenience composition for callers that have no UI to step through
    the phases (the farmhand tool, first-enable auto-refresh). A caller that
    wants to show the user what a refresh *would* do before writing anything
    should drive the three phases itself.
    """
    fetched = fetch_sources(global_path=global_path, project_path=project_path, cache_dir=cache_dir)
    resolved = resolve(fetched)
    return apply(fetched, resolved, project_path=project_path, cache_dir=cache_dir)
