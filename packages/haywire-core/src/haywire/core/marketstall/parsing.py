"""TOML parsers and serializers for marketplace and marketstall files.

The section vocabulary:
  - [[markets]] / [[stalls]]: subscriptions, parsed as Subscription
  - [[haybales]]: inline haybale entries, parsed as Haybale
  - [[heaps]]: path-based libraries (raw dicts), project-only
  - [[caches]]: refresh cache (Haybale with via/last_seen/stale set), project-only

Files:
  - Global marketplace (~/.haywire/db/haybale-marketplace/marketplace.toml):
      [[markets]], [[stalls]], optionally [[haybales]]
  - Project marketplace (<project>/.haywire/marketplace.toml):
      [[heaps]], [[caches]]
  - Marketstall file (marketstall.toml at repo root, or stalls/<dist>.toml):
      [[haybales]] only
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import toml

from haywire.core.library.haybale import Deprecation, Haybale
from haywire.core.marketstall.errors import MalformedMarketplaceError
from haywire.core.marketstall.types import (
    MarketplaceFile,
    ProjectMarketplaceFile,
    Subscription,
)


def _parse_deprecation(raw: dict) -> Deprecation | None:
    """Parse a `[deprecated]` block, or None when absent or unusable.

    Never raises: a malformed notice costs the notice, not the catalog entry.
    ``since`` is required — it decides whether a user's version predates the
    notice — so a block without it yields None; ``reason`` and ``successor``
    default to "".
    """
    block = raw.get("deprecated")
    if not isinstance(block, dict):
        return None
    since = block.get("since")
    if not isinstance(since, str) or not since:
        return None
    reason = block.get("reason")
    successor = block.get("successor")
    return Deprecation(
        since=since,
        reason=reason if isinstance(reason, str) else "",
        successor=successor if isinstance(successor, str) else "",
    )


def _parse_authors(raw: dict) -> list[tuple[str, str]]:
    """``[[authors]]`` tables as ``(name, url)`` pairs.

    Never raises. A nameless or non-table entry is dropped; a missing ``url``
    becomes "". Returns an empty list when there is no ``authors`` list.
    """
    entries = raw.get("authors")
    if not isinstance(entries, list):
        return []
    authors: list[tuple[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        url = entry.get("url")
        authors.append((name, url if isinstance(url, str) else ""))
    return authors


def _parse_haybale_entry(raw: dict) -> Haybale:
    """Parse one [[haybales]] (or [[caches]]) TOML entry into a Haybale.

    An absent ``install_spec`` defaults to ``name``, making the entry a plain
    PyPI requirement.

    Raises:
        MalformedMarketplaceError: ``name`` or ``version`` is missing or empty.
    """
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise MalformedMarketplaceError("[[haybales]] entry missing required `name` field")
    version = raw.get("version")
    if not isinstance(version, str) or not version:
        raise MalformedMarketplaceError(f"[[haybales]] entry {name!r} missing required `version` field")
    return Haybale(
        name=name,
        version=version,
        require=raw.get("require", ""),
        label=raw.get("label", ""),
        description=raw.get("description", ""),
        authors=_parse_authors(raw),
        source=raw.get("source", "pypi"),
        install_spec=raw.get("install_spec", name),
        tags=list(raw.get("tags", [])),
        os=list(raw.get("os", [])),
        on_reload=raw.get("on_reload", "none"),
        linked_libraries=list(raw.get("linked_libraries", [])),
        origin=raw.get("origin", ""),
        origin_provider=raw.get("origin_provider", ""),
        notes=raw.get("notes", ""),
        homepage_url=raw.get("homepage_url", ""),
        documentation_url=raw.get("documentation_url", ""),
        issues_url=raw.get("issues_url", ""),
        examples_path=raw.get("examples_path", ""),
        tests_path=raw.get("tests_path", ""),
        deprecated=_parse_deprecation(raw),
        via=raw.get("via", ""),
        last_seen=raw.get("last_seen", ""),
        stale=bool(raw.get("stale", False)),
    )


def _parse_subscription(raw: dict, kind: str) -> Subscription:
    """Parse one [[markets]] or [[stalls]] TOML entry.

    Args:
        kind: The section name, "markets" or "stalls". Reaches only the error
            message; the resulting Subscription is identical either way.

    Raises:
        MalformedMarketplaceError: ``url`` is missing or empty.
    """
    url = raw.get("url")
    if not isinstance(url, str) or not url:
        raise MalformedMarketplaceError(f"[[{kind}]] entry missing required `url` field")
    return Subscription(
        url=url,
        preference=list(raw.get("preference", [])),
        blocked=list(raw.get("blocked", [])),
    )


def _parse_heap_entry(raw: dict) -> dict:
    """Parse one [[heaps]] TOML entry, returning the raw table.

    Every field is preserved verbatim, so the project marketplace file
    round-trips.

    Raises:
        MalformedMarketplaceError: ``name`` or ``path`` is missing or empty.
    """
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise MalformedMarketplaceError("[[heaps]] entry missing required `name` field")
    path = raw.get("path")
    if not isinstance(path, str) or not path:
        raise MalformedMarketplaceError(f"[[heaps]] entry {name!r} missing required `path`")
    return dict(raw)


def parse_global_marketplace(path: Path) -> MarketplaceFile:
    """Parse ~/.haywire/db/haybale-marketplace/marketplace.toml.

    Returns an empty MarketplaceFile if the path does not exist.
    Raises MalformedMarketplaceError on TOML parse or schema errors.
    """
    if not path.is_file():
        return MarketplaceFile()

    try:
        data = toml.loads(path.read_text(encoding="utf-8"))
    except toml.TomlDecodeError as exc:
        raise MalformedMarketplaceError(f"malformed marketplace.toml at {path}: {exc}") from exc

    markets = [_parse_subscription(raw, "markets") for raw in data.get("markets", [])]
    stalls = [_parse_subscription(raw, "stalls") for raw in data.get("stalls", [])]
    haybales = [_parse_haybale_entry(raw) for raw in data.get("haybales", [])]

    return MarketplaceFile(markets=markets, stalls=stalls, haybales=haybales)


def parse_project_marketplace(path: Path) -> ProjectMarketplaceFile:
    """Parse <project>/.haywire/marketplace.toml.

    Returns an empty ProjectMarketplaceFile if the file doesn't exist.
    Silently drops any [[markets]] / [[stalls]] / [[haybales]] sections that
    may accidentally appear — the project shape doesn't carry subscriptions.
    """
    if not path.is_file():
        return ProjectMarketplaceFile()

    try:
        data = toml.loads(path.read_text(encoding="utf-8"))
    except toml.TomlDecodeError as exc:
        raise MalformedMarketplaceError(f"malformed project marketplace.toml at {path}: {exc}") from exc

    heaps = [_parse_heap_entry(raw) for raw in data.get("heaps", [])]
    # [[caches]] are derived and refetched on every refresh, so a malformed one
    # is discarded rather than raised on — raising would block the very refresh
    # that heals it. [[heaps]] above are user-authored and stay strict.
    try:
        caches = [_parse_haybale_entry(raw) for raw in data.get("caches", [])]
    except MalformedMarketplaceError:
        caches = []
    return ProjectMarketplaceFile(heaps=heaps, caches=caches)


@dataclass(frozen=True)
class RemoteMarketplaceContents:
    """What `parse_remote_marketplace_body` extracts from a [[markets]] response.

    Resolution is one level deep: only [[stalls]] URLs and inline [[haybales]]
    are consumed, and [[markets]] entries inside the fetched body are ignored.
    """

    stall_urls: list[str] = field(default_factory=list)
    haybales: list[Haybale] = field(default_factory=list)


def parse_marketstall_body(body: str) -> list[Haybale]:
    """Parse a fetched marketstall TOML body into a list of Haybale.

    A marketstall is [[haybales]]-only; other sections are silently dropped.
    Never raises: malformed TOML, a missing [[haybales]] section, or a
    malformed entry within it all yield an empty list.
    """
    try:
        data = toml.loads(body)
    except toml.TomlDecodeError:
        return []
    try:
        return [_parse_haybale_entry(raw) for raw in data.get("haybales", [])]
    except MalformedMarketplaceError:
        return []


def parse_remote_marketplace_body(body: str) -> RemoteMarketplaceContents:
    """Parse a fetched remote marketplace body into stall_urls + inline haybales.

    One level deep: [[markets]] entries inside `body` are silently ignored, as
    are [[stalls]] entries with no ``url``. Never raises — malformed TOML
    yields empty contents, and one malformed [[haybales]] entry drops the
    inline haybales while keeping the stall URLs.
    """
    try:
        data = toml.loads(body)
    except toml.TomlDecodeError:
        return RemoteMarketplaceContents()

    stall_urls: list[str] = []
    for raw in data.get("stalls", []):
        url = raw.get("url")
        if isinstance(url, str) and url:
            stall_urls.append(url)

    try:
        haybales = [_parse_haybale_entry(raw) for raw in data.get("haybales", [])]
    except MalformedMarketplaceError:
        haybales = []

    return RemoteMarketplaceContents(stall_urls=stall_urls, haybales=haybales)


def _subscription_to_dict(sub: Subscription) -> dict:
    """Serialize a Subscription back to its TOML dict shape.

    Emits ``preference`` and ``blocked`` even when empty, so a user editing the
    file sees the full schema.
    """
    return {
        "url": sub.url,
        "preference": list(sub.preference),
        "blocked": list(sub.blocked),
    }


def serialize_global_marketplace(mf: MarketplaceFile) -> str:
    """Serialize a MarketplaceFile to a TOML string.

    Section order: [[markets]], [[stalls]], [[haybales]]. Empty sections are
    omitted entirely, so a file with nothing in it serializes to "".
    """
    data: dict[str, list[dict]] = {}
    if mf.markets:
        data["markets"] = [_subscription_to_dict(sub) for sub in mf.markets]
    if mf.stalls:
        data["stalls"] = [_subscription_to_dict(sub) for sub in mf.stalls]
    if mf.haybales:
        data["haybales"] = [h.to_dict() for h in mf.haybales]
    return toml.dumps(data) if data else ""


def serialize_project_marketplace(pm: ProjectMarketplaceFile) -> str:
    """Serialize a ProjectMarketplaceFile to a TOML string.

    Section order: [[heaps]], then [[caches]]. Empty sections are omitted
    entirely, so a file with nothing in it serializes to "".
    """
    data: dict[str, list[dict]] = {}
    if pm.heaps:
        data["heaps"] = list(pm.heaps)
    if pm.caches:
        data["caches"] = [h.to_dict() for h in pm.caches]
    return toml.dumps(data) if data else ""
