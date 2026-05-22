"""Refresh pipeline — spec §8.

Filter functions (apply_ignores, apply_blocked, apply_heaps_shadow,
apply_first_come_first_served) are pure transformations over Haybale lists.
The `refresh()` orchestrator composes them with the HTTP cache layer.

Conflict-resolution order (spec §8.2):
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
    Haybale,
    ProjectMarketplaceFile,
    RefreshOutcome,
    RefreshReport,
    Subscription,
)


def apply_ignores(haybales: list[Haybale], ignores: list[str]) -> list[Haybale]:
    """Drop haybales whose name is in `ignores`.

    Per spec §8.2: the user picked another source for these names at conflict-
    resolution time; this subscription is asked to step aside.
    """
    if not ignores:
        return list(haybales)
    ignored = set(ignores)
    return [h for h in haybales if h.name not in ignored]


def apply_blocked(haybales: list[Haybale], blocked: list[str]) -> list[Haybale]:
    """Drop haybales whose name is in `blocked`.

    Per spec §7.4: the user actively rejected these names via the first-install
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

    Per spec §8.2 row 3: local heaps always win. The dropped haybale's
    contribution is silently shadowed — no prompt, no diagnostic.
    """
    if not heaps:
        return list(haybales)
    heap_names = {h.get("name") for h in heaps if isinstance(h.get("name"), str)}
    return [hb for hb in haybales if hb.name not in heap_names]


def apply_first_come_first_served(haybales: list[Haybale]) -> list[Haybale]:
    """Deduplicate by name, keeping the first occurrence.

    Per spec §8.2 row 4: a safety net for cases the per-subscription `ignores`
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

    Semantics per spec §8:
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
                min_version=prev.min_version,
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
                source_label=prev.source_label,
                source_file=prev.source_file,
                source_origin=prev.source_origin,
                via=prev.via,
                last_seen=now,
                stale=True,
            )
        )
    return out


def _fetch_subscription(
    sub: Subscription,
    *,
    cache_dir: Path | None,
    report: RefreshReport,
) -> str | None:
    """Fetch a single subscription and update tri-state counters. Returns body or None."""
    try:
        result = fetch_with_cache_fallback(sub.url, cache_dir=cache_dir)
    except RemoteFetchError:
        report.sources_unavailable += 1
        report.unavailable_urls.append(sub.url)
        return None

    if result.outcome is RefreshOutcome.FRESH:
        report.sources_fetched += 1
    else:
        report.sources_from_cache += 1
    return result.body


def refresh(
    *,
    global_path: Path,
    project_path: Path,
    cache_dir: Path | None = None,
) -> RefreshReport:
    """Run the refresh pipeline — spec §8.

    Step-by-step:
      1. Parse global marketplace + previous project file.
      2. For each [[markets]] subscription: fetch, parse one-level-deep,
         collect referenced [[stalls]] URLs + inline [[haybales]].
      3. For each [[stalls]] subscription (direct + discovered): fetch, parse.
      4. Build candidate list, applying blocked + ignores per-subscription.
      5. Apply heaps shadow + first-come-first-served.
      6. Mark stale against previous project [[caches]].
      7. Write project file. GC orphan cache files. Return report.
    """
    report = RefreshReport()

    mf = parse_global_marketplace(global_path)
    pm_prev = parse_project_marketplace(project_path)

    discovered_stall_urls: list[str] = []
    market_haybales: list[Haybale] = []

    # Step 2: [[markets]] (one level deep)
    for sub in mf.markets:
        body = _fetch_subscription(sub, cache_dir=cache_dir, report=report)
        if body is None:
            continue
        contents = parse_remote_marketplace_body(body)
        discovered_stall_urls.extend(contents.stall_urls)
        filtered = apply_blocked(contents.haybales, sub.blocked)
        filtered = apply_ignores(filtered, sub.ignores)
        market_haybales.extend(filtered)

    # Step 3: [[stalls]] — direct subscriptions.
    seen_stall_urls: set[str] = set()
    stall_haybales: list[Haybale] = []
    for sub in mf.stalls:
        if sub.url in seen_stall_urls:
            continue
        seen_stall_urls.add(sub.url)
        body = _fetch_subscription(sub, cache_dir=cache_dir, report=report)
        if body is None:
            continue
        hb = parse_marketstall_body(body)
        hb = apply_blocked(hb, sub.blocked)
        hb = apply_ignores(hb, sub.ignores)
        stall_haybales.extend(hb)

    # Step 3 (cont.): discovered stalls from markets.
    for url in discovered_stall_urls:
        if url in seen_stall_urls:
            continue
        seen_stall_urls.add(url)
        # Discovered stalls are anonymous (no parent Subscription); fetch directly.
        try:
            result = fetch_with_cache_fallback(url, cache_dir=cache_dir)
        except RemoteFetchError:
            report.sources_unavailable += 1
            report.unavailable_urls.append(url)
            continue
        if result.outcome is RefreshOutcome.FRESH:
            report.sources_fetched += 1
        else:
            report.sources_from_cache += 1
        stall_haybales.extend(parse_marketstall_body(result.body))

    # Step 4: combine candidates. Order: inline [[haybales]] in global, then stalls,
    # then market-inline (gives stable provenance ordering for FCFS).
    candidates: list[Haybale] = list(mf.haybales) + stall_haybales + market_haybales

    # Step 5: heaps shadow + FCFS.
    candidates = apply_heaps_shadow(pm_prev.heaps, candidates)
    candidates = apply_first_come_first_served(candidates)

    # Step 6: stale marking against previous caches.
    final = mark_stale_against_previous(candidates, previous=pm_prev.caches)

    report.haybales_resolved = sum(1 for h in final if not h.stale)
    prev_stale_names = {p.name for p in pm_prev.caches if p.stale}
    report.new_stale = sum(1 for h in final if h.stale and h.name not in prev_stale_names)

    # Step 7: write project file.
    new_pm = ProjectMarketplaceFile(heaps=list(pm_prev.heaps), caches=final)
    project_path.parent.mkdir(parents=True, exist_ok=True)
    body = serialize_project_marketplace(new_pm)
    project_path.write_text(body if body else "")

    # GC orphan cache files. Active URLs = all subscription URLs + discovered.
    active_urls: set[str] = (
        {s.url for s in mf.markets} | {s.url for s in mf.stalls} | set(discovered_stall_urls)
    )
    gc_orphans(active_urls, cache_dir=cache_dir)

    return report
