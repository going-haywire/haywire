"""Helpers for the marketplace file: subscriptions, heaps, ignores, cache removals.

Each helper reads the global (or project) file, mutates the parsed structure,
and writes back via the serializer. All operations are idempotent where it
makes sense; raise specific errors otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from haywire.core.marketstall.errors import DuplicateHeapNameError
from haywire.core.marketstall.parsing import (
    parse_global_marketplace,
    parse_project_marketplace,
    serialize_global_marketplace,
    serialize_project_marketplace,
)
from haywire.core.marketstall.types import Haybale, ProjectMarketplaceFile, Subscription


def add_market_subscription_to_global(global_path: Path, url: str) -> None:
    """Append a [[markets]] entry. Idempotent on URL match."""
    mf = parse_global_marketplace(global_path)
    if any(sub.url == url for sub in mf.markets):
        return
    mf.markets.append(Subscription(url=url))
    global_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.write_text(serialize_global_marketplace(mf))


def add_stall_subscription_to_global(global_path: Path, url: str) -> None:
    """Append a [[stalls]] entry. Idempotent on URL match."""
    mf = parse_global_marketplace(global_path)
    if any(sub.url == url for sub in mf.stalls):
        return
    mf.stalls.append(Subscription(url=url))
    global_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.write_text(serialize_global_marketplace(mf))


def add_heap_to_project(
    project_path: Path,
    *,
    name: str,
    path: Path,
    label: str = "",
    description: str = "",
) -> None:
    """Append a [[heaps]] entry to <project>/.haywire/marketplace.toml.

    Raises DuplicateHeapNameError if the name already exists in this project's heaps.
    """
    pm = parse_project_marketplace(project_path)
    for existing in pm.heaps:
        if existing.get("name") == name:
            raise DuplicateHeapNameError(
                f'A local library named "{name}" is already registered '
                f"at {existing.get('path')} in {project_path}."
            )

    entry: dict[str, object] = {"name": name, "path": str(path)}
    if label:
        entry["label"] = label
    if description:
        entry["description"] = description
    pm.heaps.append(entry)

    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_text(serialize_project_marketplace(pm))


def remove_stale_haybale_from_project(project_path: Path, *, name: str) -> bool:
    """Remove a stale [[caches]] entry by name. Returns True iff something removed.

    Refuses to remove a non-stale entry — that would be undone by the next refresh.
    Returns False (no exception) if no entry with the given name exists.
    """
    pm = parse_project_marketplace(project_path)
    keep: list[Haybale] = []
    removed = False
    for entry in pm.caches:
        if entry.name == name:
            if not entry.stale:
                raise ValueError(
                    f"Refusing to remove non-stale haybale {name!r} from {project_path}; "
                    f"only stale entries are user-removable."
                )
            removed = True
            continue
        keep.append(entry)

    if not removed:
        return False

    new_pm = ProjectMarketplaceFile(heaps=list(pm.heaps), caches=keep)
    project_path.write_text(serialize_project_marketplace(new_pm))
    return True


@dataclass(frozen=True)
class SubscriptionConflict:
    """A name collision between an already-resolved haybale and a new subscription's haybale."""

    name: str
    existing_source: str  # URL where the existing haybale was resolved from
    new_source: str  # URL where the new haybale is offered


def _replace_subscription_in_list(
    subs: list[Subscription], target_url: str, transform: Callable[[Subscription], Subscription]
) -> bool:
    """Find a Subscription with `target_url`; replace it with transform(sub). Returns True if changed."""
    for i, sub in enumerate(subs):
        if sub.url != target_url:
            continue
        new_sub = transform(sub)
        if new_sub is sub:
            return False
        subs[i] = new_sub
        return True
    return False


def record_ignore_on_source(global_path: Path, *, source_url: str, haybale_name: str) -> None:
    """Add `haybale_name` to the `ignores` array of the subscription at `source_url`.

    Idempotent: if the name is already in `ignores`, no write happens.
    Searches both [[markets]] and [[stalls]] — first match wins.
    """
    mf = parse_global_marketplace(global_path)

    def add_ignore(sub: Subscription) -> Subscription:
        if haybale_name in sub.ignores:
            return sub  # Idempotent.
        return Subscription(
            url=sub.url,
            ignores=[*sub.ignores, haybale_name],
            doubles=list(sub.doubles),
            blocked=list(sub.blocked),
        )

    changed = _replace_subscription_in_list(mf.markets, source_url, add_ignore)
    if not changed:
        changed = _replace_subscription_in_list(mf.stalls, source_url, add_ignore)

    if changed:
        global_path.write_text(serialize_global_marketplace(mf))


def record_block_on_source(global_path: Path, *, source_url: str, haybale_name: str) -> None:
    """Add `haybale_name` to the `blocked` array of the subscription at `source_url`.

    Idempotent. Searches both [[markets]] and [[stalls]] — first match wins.
    Per spec §7.4: blocked entries are persistent; un-block only by editing the file.
    """
    mf = parse_global_marketplace(global_path)

    def add_block(sub: Subscription) -> Subscription:
        if haybale_name in sub.blocked:
            return sub
        return Subscription(
            url=sub.url,
            ignores=list(sub.ignores),
            doubles=list(sub.doubles),
            blocked=[*sub.blocked, haybale_name],
        )

    changed = _replace_subscription_in_list(mf.markets, source_url, add_block)
    if not changed:
        changed = _replace_subscription_in_list(mf.stalls, source_url, add_block)

    if changed:
        global_path.write_text(serialize_global_marketplace(mf))


def detect_subscription_conflicts(existing: list[Haybale], new: list[Haybale]) -> list[SubscriptionConflict]:
    """Return one SubscriptionConflict per name collision between existing and new haybales.

    `source_origin` is a runtime-only Haybale field; when empty, the conflict
    reports "(unknown)" so the UI can still render something.
    """
    existing_by_name = {h.name: h for h in existing}
    out: list[SubscriptionConflict] = []
    for new_h in new:
        if new_h.name not in existing_by_name:
            continue
        existing_h = existing_by_name[new_h.name]
        out.append(
            SubscriptionConflict(
                name=new_h.name,
                existing_source=existing_h.source_origin or "(unknown)",
                new_source=new_h.source_origin or "(unknown)",
            )
        )
    return out


def resolve_block_target(global_path: Path, via_url: str) -> str | None:
    """Pick the subscription URL that should receive a block for `via_url`.

    Spec §7.4: the Block button writes to the subscription that resolved this
    haybale. Three cases:
      - Direct stall: via matches a [[stalls]] URL → return that URL.
      - Direct market: via matches a [[markets]] URL → return that URL.
      - Transitive: via is a discovered stall (not in [[stalls]]); fall back
        to the FIRST [[markets]] URL — the user only controls the aggregator.

    Returns None when via is empty OR no subscription can plausibly own it
    (e.g. no markets subscriptions and no matching stall).
    """
    if not via_url:
        return None

    mf = parse_global_marketplace(global_path)

    # Direct stall match.
    for sub in mf.stalls:
        if sub.url == via_url:
            return sub.url

    # Direct market match (rare — markets normally serve [[stalls]] discovery,
    # not haybales directly; but if a market is inline-haybales-only, via could
    # equal market.url).
    for sub in mf.markets:
        if sub.url == via_url:
            return sub.url

    # Transitive fallback: assume the haybale arrived via an aggregator.
    # Return the first [[markets]] URL. (Future refinement: track which market
    # discovered which stall; for now, first-aggregator-wins is acceptable.)
    if mf.markets:
        return mf.markets[0].url

    return None
