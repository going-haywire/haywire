"""Two-tier marketplace runtime (spec §6).

Owns:
  - GlobalMarketplace dataclass: parsed representation of ~/.haywire/marketplace.toml.
  - RemoteSubscription dataclass: a single [[marketplaces]] or [[marketstalls]] entry.
  - parse_global_marketplace(path): TOML → GlobalMarketplace, with schema validation.
  - parse_project_marketplace(path): TOML → ProjectMarketplace (added in Task 5).
  - refresh(): the orchestrator (added in Phase 2).

Schemas mirror spec §6:
  Global file: [[marketplaces]], [[marketstalls]], [[packages]], [[locals]].
  Project file: [[locals]], [[packages]] (with via/last_seen/stale).

The parser raises MalformedGlobalMarketplaceError on TOML parse errors, schema
violations (G5 duplicate locals, duplicate direct packages), or missing required
fields. Per spec §6, the Library Manager refuses to start when this is raised.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import toml

from haywire.core.marketplace import MarketplaceEntry
from haywire.core.marketplace_errors import (
    DuplicateLocalNameError,
    DuplicatePackageNameError,
    MalformedGlobalMarketplaceError,
)


@dataclass(frozen=True)
class RemoteSubscription:
    """A single [[marketplaces]] or [[marketstalls]] entry in the global marketplace.

    Per spec §6, both subscription types share the same shape: url + ignores
    + doubles. The distinction (marketplace vs marketstall) lives in which
    list of GlobalMarketplace the subscription belongs to.
    """

    url: str
    ignores: list[str] = field(default_factory=list)
    doubles: list[str] = field(default_factory=list)


@dataclass
class GlobalMarketplace:
    """Parsed representation of ~/.haywire/marketplace.toml.

    Four section types per spec §6 — all four are optional and can be empty.
    [[locals]] entries are raw dicts (Plan D's pattern); [[packages]] entries
    are MarketplaceEntry (the §7 schema); subscriptions are RemoteSubscription.
    """

    marketplaces: list[RemoteSubscription] = field(default_factory=list)
    marketstalls: list[RemoteSubscription] = field(default_factory=list)
    packages: list[MarketplaceEntry] = field(default_factory=list)
    locals_: list[dict] = field(default_factory=list)


def _parse_subscription(raw: dict, kind: str) -> RemoteSubscription:
    """Parse a single [[marketplaces]] or [[marketstalls]] entry."""
    url = raw.get("url")
    if not isinstance(url, str) or not url:
        raise MalformedGlobalMarketplaceError(f"[[{kind}]] entry missing required `url` field")
    return RemoteSubscription(
        url=url,
        ignores=list(raw.get("ignores", [])),
        doubles=list(raw.get("doubles", [])),
    )


def _parse_package_entry(raw: dict) -> MarketplaceEntry:
    """Parse a single [[packages]] entry — matches §7 MarketplaceEntry schema."""
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise MalformedGlobalMarketplaceError("[[packages]] entry missing required `name` field")
    return MarketplaceEntry(
        name=name,
        min_version=raw.get("min_version", ""),
        label=raw.get("label", ""),
        description=raw.get("description", ""),
        author=raw.get("author", ""),
        source=raw.get("source", "pypi"),
        install_spec=raw.get("install_spec", name),
        tags=list(raw.get("tags", [])),
        dependencies=list(raw.get("dependencies", [])),
        source_url=raw.get("source_url", ""),
        docs_url=raw.get("docs_url", ""),
        via=raw.get("via", ""),
        last_seen=raw.get("last_seen", ""),
        stale=bool(raw.get("stale", False)),
    )


def _parse_local_entry(raw: dict) -> dict:
    """Parse a single [[locals]] entry (Plan D's schema: name + path + optional metadata)."""
    name = raw.get("name")
    path = raw.get("path")
    if not isinstance(name, str) or not name:
        raise MalformedGlobalMarketplaceError("[[locals]] entry missing required `name`")
    if not isinstance(path, str) or not path:
        raise MalformedGlobalMarketplaceError(f"[[locals]] entry {name!r} missing required `path`")
    # Keep all fields verbatim — locals are a flexible schema.
    return dict(raw)


def parse_global_marketplace(path: Path) -> GlobalMarketplace:
    """Parse ~/.haywire/marketplace.toml into a GlobalMarketplace.

    Returns an empty GlobalMarketplace if the path doesn't exist.
    Raises MalformedGlobalMarketplaceError on TOML parse errors, schema
    violations, or duplicate names in [[locals]] / [[packages]].
    """
    if not path.is_file():
        return GlobalMarketplace()

    try:
        data = toml.loads(path.read_text(encoding="utf-8"))
    except toml.TomlDecodeError as exc:
        raise MalformedGlobalMarketplaceError(f"malformed marketplace.toml at {path}: {exc}") from exc

    marketplaces = [_parse_subscription(raw, "marketplaces") for raw in data.get("marketplaces", [])]
    marketstalls = [_parse_subscription(raw, "marketstalls") for raw in data.get("marketstalls", [])]
    packages = [_parse_package_entry(raw) for raw in data.get("packages", [])]
    locals_raw = [_parse_local_entry(raw) for raw in data.get("locals", [])]

    # Duplicate-name check for [[locals]] (G5) and [[packages]] (spec §6 "refused at parse time").
    _check_no_duplicate_names(locals_raw, "locals", DuplicateLocalNameError)
    _check_no_duplicate_names([{"name": p.name} for p in packages], "packages", DuplicatePackageNameError)

    return GlobalMarketplace(
        marketplaces=marketplaces,
        marketstalls=marketstalls,
        packages=packages,
        locals_=locals_raw,
    )


def _check_no_duplicate_names(
    entries: list[dict],
    section: str,
    error_cls: type[Exception],
) -> None:
    """Raise MalformedGlobalMarketplaceError (via error_cls) on duplicate `name` values.

    `error_cls` is the specific sub-exception (DuplicateLocalNameError or
    DuplicatePackageNameError), but the message wraps it as Malformed... so
    the Library Manager startup hook (Phase 3) catches it via the parent class.
    """
    seen: set[str] = set()
    for entry in entries:
        name = entry.get("name")
        if name in seen:
            raise MalformedGlobalMarketplaceError(
                f"duplicate {section} entry: {name!r} appears twice in the global marketplace"
            )
        if name is not None:
            seen.add(name)


@dataclass
class ProjectMarketplace:
    """Parsed representation of <project>/.haywire/marketplace.toml.

    Two section types per spec §6:
      - [[locals]]: project-scoped editable libraries, written by haywire init.
      - [[packages]]: the cache populated by refresh — entries carry via,
        last_seen, and stale fields.

    Unlike GlobalMarketplace, this does NOT have [[marketplaces]] or [[marketstalls]] —
    those are user-curated subscriptions that live only in the global file.
    """

    locals_: list[dict] = field(default_factory=list)
    packages: list[MarketplaceEntry] = field(default_factory=list)


def parse_project_marketplace(path: Path) -> ProjectMarketplace:
    """Parse <project>/.haywire/marketplace.toml.

    Returns an empty ProjectMarketplace if the file doesn't exist. Silently
    drops any [[marketplaces]] or [[marketstalls]] sections that may
    accidentally appear (the project shape doesn't have them).

    Raises MalformedGlobalMarketplaceError on TOML parse errors. We reuse
    the global error class here — Plan E callers catch the same exception
    for both files.
    """
    if not path.is_file():
        return ProjectMarketplace()

    try:
        data = toml.loads(path.read_text(encoding="utf-8"))
    except toml.TomlDecodeError as exc:
        raise MalformedGlobalMarketplaceError(
            f"malformed project marketplace.toml at {path}: {exc}"
        ) from exc

    locals_raw = [_parse_local_entry(raw) for raw in data.get("locals", [])]
    packages = [_parse_package_entry(raw) for raw in data.get("packages", [])]

    return ProjectMarketplace(locals_=locals_raw, packages=packages)


def serialize_global_marketplace(gm: GlobalMarketplace) -> str:
    """Serialize a GlobalMarketplace to a TOML string.

    Section order matches spec §6: [[marketplaces]], [[marketstalls]],
    [[packages]], [[locals]]. Empty sections are omitted (no header at all,
    not even an empty list) — Plan B's "skip empty" pattern.
    """
    data: dict[str, list[dict]] = {}

    if gm.marketplaces:
        data["marketplaces"] = [_subscription_to_dict(sub) for sub in gm.marketplaces]
    if gm.marketstalls:
        data["marketstalls"] = [_subscription_to_dict(sub) for sub in gm.marketstalls]
    if gm.packages:
        data["packages"] = [pkg.to_dict() for pkg in gm.packages]
    if gm.locals_:
        data["locals"] = list(gm.locals_)

    return toml.dumps(data)


def _subscription_to_dict(sub: RemoteSubscription) -> dict:
    """Serialize a RemoteSubscription back to its TOML dict shape.

    Always emits `ignores` and `doubles` arrays (even when empty) so users
    editing the file see the schema. Spec §6's example explicitly shows
    `ignores = []` and `doubles = []` on every subscription.
    """
    return {
        "url": sub.url,
        "ignores": list(sub.ignores),
        "doubles": list(sub.doubles),
    }


def serialize_project_marketplace(pm: ProjectMarketplace) -> str:
    """Serialize a ProjectMarketplace to a TOML string.

    Section order: [[locals]] first (written once by haywire init),
    then [[packages]] (the refresh cache). Empty sections are omitted.
    Per spec §6, [[marketplaces]] and [[marketstalls]] never appear
    in the project file.
    """
    data: dict[str, list[dict]] = {}
    if pm.locals_:
        data["locals"] = list(pm.locals_)
    if pm.packages:
        data["packages"] = [pkg.to_dict() for pkg in pm.packages]
    return toml.dumps(data)
