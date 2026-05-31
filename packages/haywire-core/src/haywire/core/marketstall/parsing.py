"""TOML parsers and serializers for marketplace and marketstall files.

The new section vocabulary:
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

from haywire.core.marketstall.errors import MalformedMarketplaceError
from haywire.core.marketstall.types import Haybale, MarketplaceFile, ProjectMarketplaceFile, Subscription


def _parse_haybale_entry(raw: dict) -> Haybale:
    """Parse one [[haybales]] (or [[caches]]) TOML entry into a Haybale."""
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise MalformedMarketplaceError("[[haybales]] entry missing required `name` field")
    return Haybale(
        name=name,
        min_version=raw.get("min_version", ""),
        label=raw.get("label", ""),
        description=raw.get("description", ""),
        author=raw.get("author", ""),
        source=raw.get("source", "pypi"),
        install_spec=raw.get("install_spec", name),
        tags=list(raw.get("tags", [])),
        os=list(raw.get("os", [])),
        dependencies=list(raw.get("dependencies", [])),
        source_url=raw.get("source_url", ""),
        docs_url=raw.get("docs_url", ""),
        via=raw.get("via", ""),
        last_seen=raw.get("last_seen", ""),
        stale=bool(raw.get("stale", False)),
    )


def _parse_subscription(raw: dict, kind: str) -> Subscription:
    """Parse one [[markets]] or [[stalls]] TOML entry.

    `kind` is the section name ("markets" or "stalls"); used only for error
    messages — the resulting Subscription is identical regardless.
    """
    url = raw.get("url")
    if not isinstance(url, str) or not url:
        raise MalformedMarketplaceError(f"[[{kind}]] entry missing required `url` field")
    return Subscription(
        url=url,
        ignores=list(raw.get("ignores", [])),
        doubles=list(raw.get("doubles", [])),
        blocked=list(raw.get("blocked", [])),
    )


def _parse_heap_entry(raw: dict) -> dict:
    """Parse one [[heaps]] TOML entry. Returns a dict (heap shape is flexible).

    `name` and `path` are required. Other fields (label, description) are
    preserved verbatim so the project marketplace file is round-trippable.
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
    caches = [_parse_haybale_entry(raw) for raw in data.get("caches", [])]
    return ProjectMarketplaceFile(heaps=heaps, caches=caches)


@dataclass(frozen=True)
class RemoteMarketplaceContents:
    """What `parse_remote_marketplace_body` extracts from a [[markets]] response.

    Resolution is one level deep: any [[markets]] entries
    inside the fetched marketplace body are ignored. Only [[stalls]] URLs and
    inline [[haybales]] are consumed.
    """

    stall_urls: list[str] = field(default_factory=list)
    haybales: list[Haybale] = field(default_factory=list)


def parse_marketstall_body(body: str) -> list[Haybale]:
    """Parse a fetched marketstall TOML body into a list of Haybale.

    A marketstall is [[haybales]]-only. Other sections are silently
    dropped — a misbehaving server might return extra sections, but we never
    use them. Returns an empty list on malformed TOML or missing [[haybales]].
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

    One-level-deep: [[markets]] entries inside `body` are silently ignored.
    Malformed TOML returns empty contents (the orchestrator treats as unavailable).
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

    Always emits all four arrays (even when empty) so users editing the file
    see the schema — every subscription declares all four.
    """
    return {
        "url": sub.url,
        "ignores": list(sub.ignores),
        "doubles": list(sub.doubles),
        "blocked": list(sub.blocked),
    }


def serialize_global_marketplace(mf: MarketplaceFile) -> str:
    """Serialize a MarketplaceFile to a TOML string.

    Section order: [[markets]], [[stalls]], [[haybales]].
    Empty sections are omitted entirely (no header) — caller can detect
    "nothing to write" by checking the empty-string result.
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

    Section order: [[heaps]] first (written once by haywire init), then [[caches]]
    (refresh result). Empty sections omitted.
    """
    data: dict[str, list[dict]] = {}
    if pm.heaps:
        data["heaps"] = list(pm.heaps)
    if pm.caches:
        data["caches"] = [h.to_dict() for h in pm.caches]
    return toml.dumps(data) if data else ""
