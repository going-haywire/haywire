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

import datetime as _dt
import hashlib
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import toml

from haywire.core.marketplace import MarketplaceEntry
from haywire.core.marketplace_errors import (
    DuplicateLocalNameError,
    DuplicatePackageNameError,
    MalformedGlobalMarketplaceError,
    RemoteFetchError,
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


_CACHE_HASH_LEN = 16


def _url_hash(url: str) -> str:
    """Return a short hex hash for a URL. Used as the cache filename stem."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:_CACHE_HASH_LEN]


def _cache_path(url: str) -> Path:
    """Return ~/.haywire/cache/<url-hash>.toml for the given URL."""
    return Path.home() / ".haywire" / "cache" / f"{_url_hash(url)}.toml"


def cache_write(url: str, body: str) -> None:
    """Cache a successful HTTP response. Overwrites any previous entry for the same URL."""
    path = _cache_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def cache_read(url: str) -> tuple[str | None, float | None]:
    """Return (cached_body, age_in_seconds) for a URL, or (None, None) if no cache."""
    path = _cache_path(url)
    if not path.is_file():
        return None, None
    body = path.read_text(encoding="utf-8")
    age = time.time() - path.stat().st_mtime
    return body, age


@dataclass(frozen=True)
class FetchResult:
    """Result of fetch_with_cache_fallback. body is always populated;
    from_cache is True iff we served from cache (because the remote failed)."""

    body: str
    from_cache: bool
    cache_age: float | None  # Set when from_cache=True; None on fresh fetch.


def fetch_with_cache_fallback(url: str, *, timeout: float = 5.0) -> FetchResult:
    """Fetch a URL. On success, cache + return the body. On failure, return cached body if any.

    Raises RemoteFetchError only when the URL fails AND no cache exists.
    Per spec §6: "Cache invalidation: only by successful re-fetch on next refresh."
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        cache_write(url, body)
        return FetchResult(body=body, from_cache=False, cache_age=None)
    except (OSError, urllib.error.URLError):
        cached, age = cache_read(url)
        if cached is not None:
            return FetchResult(body=cached, from_cache=True, cache_age=age)
        raise RemoteFetchError(f"failed to fetch {url} and no cache available") from None


def parse_marketstall_body(body: str) -> list[MarketplaceEntry]:
    """Parse a fetched marketstall TOML body into a list of MarketplaceEntry.

    A marketstall is [[packages]]-only per spec §7. Other sections (locals,
    marketplaces) are silently ignored — a remote marketstall shouldn't have
    them, but if a misbehaving server returns extra sections we just skip them.

    Returns an empty list on malformed TOML or missing [[packages]]. The
    caller (refresh orchestrator) decides what to do with an empty result.
    """
    try:
        data = toml.loads(body)
    except toml.TomlDecodeError:
        return []

    try:
        return [_parse_package_entry(raw) for raw in data.get("packages", [])]
    except MalformedGlobalMarketplaceError:
        return []


@dataclass(frozen=True)
class RemoteMarketplaceContents:
    """Result of parsing a fetched remote marketplace body.

    Per spec §6 line 186-188, resolution is one level deep — a remote
    marketplace's own [[marketplaces]] entries are ignored. We only consume
    its [[marketstalls]] URLs and [[packages]] entries.
    """

    marketstall_urls: list[str] = field(default_factory=list)
    packages: list[MarketplaceEntry] = field(default_factory=list)


def parse_remote_marketplace_body(body: str) -> RemoteMarketplaceContents:
    """Parse a fetched remote marketplace TOML body into its consumable sections.

    Resolution is one level deep: [[marketplaces]] entries are ignored.
    Malformed TOML or schema violations return an empty RemoteMarketplaceContents
    (the orchestrator treats this as "source unavailable").
    """
    try:
        data = toml.loads(body)
    except toml.TomlDecodeError:
        return RemoteMarketplaceContents()

    marketstall_urls: list[str] = []
    for raw in data.get("marketstalls", []):
        url = raw.get("url")
        if isinstance(url, str) and url:
            marketstall_urls.append(url)

    try:
        packages = [_parse_package_entry(raw) for raw in data.get("packages", [])]
    except MalformedGlobalMarketplaceError:
        packages = []

    return RemoteMarketplaceContents(
        marketstall_urls=marketstall_urls,
        packages=packages,
    )


def apply_ignores(packages: list[MarketplaceEntry], ignores: list[str]) -> list[MarketplaceEntry]:
    """Filter out packages whose name is in `ignores`.

    Per spec §6 conflict-resolution table: `ignores` lives on the YIELDING
    source — when a user picks between A and B for `haybale-foo`, the losing
    entry's parent source gets `haybale-foo` added to its `ignores` array.
    Refresh honors this by skipping the named packages from that source.
    """
    if not ignores:
        return packages
    ignored_set = set(ignores)
    return [p for p in packages if p.name not in ignored_set]


def apply_locals_shadow(
    locals_: list[dict],
    packages: list[MarketplaceEntry],
) -> list[MarketplaceEntry]:
    """Drop packages whose name matches a [[locals]] entry's name.

    Per spec §6 conflict-resolution table row 3: [[locals]] always wins. The
    other source's contribution is silently shadowed (no diagnostic, no prompt).
    Returns the filtered list of packages; locals are returned separately by
    the orchestrator since they have a different schema.
    """
    if not locals_:
        return packages
    local_names = {entry.get("name") for entry in locals_ if isinstance(entry.get("name"), str)}
    return [p for p in packages if p.name not in local_names]


def apply_first_come_first_served(
    packages: list[MarketplaceEntry],
) -> list[MarketplaceEntry]:
    """Deduplicate by name, keeping the first occurrence.

    Per spec §6 conflict-resolution table row 2. By the time refresh calls
    this, `ignores` arrays on yielding sources should already handle the
    conflict resolution — this is a safety net for any case the UI prompt
    missed (or for users who hand-edited the global marketplace).
    """
    seen: set[str] = set()
    out: list[MarketplaceEntry] = []
    for pkg in packages:
        if pkg.name in seen:
            continue
        seen.add(pkg.name)
        out.append(pkg)
    return out


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string with trailing Z."""
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mark_stale_against_previous(
    fresh: list[MarketplaceEntry],
    previous: list[MarketplaceEntry],
) -> list[MarketplaceEntry]:
    """Compute the new project cache by marking missing entries as stale.

    Per spec §6 line 196-203:
      - Entries present in both keep their fresh data (no stale flag).
      - Entries in previous but not fresh become stale (stale=True + last_seen).
      - Entries already stale in previous keep their original last_seen
        (avoid bumping the timestamp every refresh — that would make stale
        age meaningless).
      - Entries only in fresh are passed through unchanged.

    Returns the combined list. The caller decides display order.
    """
    out: list[MarketplaceEntry] = list(fresh)
    out_names = {p.name for p in out}

    now = _now_iso()
    for prev in previous:
        if prev.name in out_names:
            continue  # Still present in fresh — already in `out`.
        if prev.stale:
            # Re-mark stale without bumping the timestamp.
            out.append(prev)
        else:
            # Newly stale: copy the previous entry and set stale + last_seen.
            stale_copy = MarketplaceEntry(
                name=prev.name,
                min_version=prev.min_version,
                label=prev.label,
                description=prev.description,
                author=prev.author,
                source=prev.source,
                install_spec=prev.install_spec,
                tags=list(prev.tags),
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
            out.append(stale_copy)
    return out


@dataclass
class RefreshReport:
    """Summary of a refresh run, surfaced to the UI."""

    sources_fetched: int = 0
    sources_unavailable: int = 0
    unavailable_urls: list[str] = field(default_factory=list)
    packages_resolved: int = 0
    new_stale: int = 0


def refresh(global_path: Path, project_path: Path) -> RefreshReport:
    """Run the 7-step refresh from spec §6.

    1. Read global.
    2. For each [[marketplaces]] entry, fetch + parse (one level deep).
    3. For each [[marketstalls]] entry (direct + discovered), fetch + parse.
    4. Build flat candidate list.
    5. Apply ignores per source, then locals shadow, then first-come dedup.
    6. Write project marketplace (locals preserved + resolved packages + stale-marked).
    7. Diff against previous to compute stale; mark_stale_against_previous handles it.

    Returns a RefreshReport for the UI.
    """
    report = RefreshReport()
    gm = parse_global_marketplace(global_path)
    pm_prev = parse_project_marketplace(project_path)

    # Step 2: fetch each [[marketplaces]] (one level deep)
    # and accumulate the marketstall URLs we discover.
    discovered_marketstall_urls: list[str] = []
    remote_marketplace_packages: list[MarketplaceEntry] = []
    for sub in gm.marketplaces:
        try:
            result = fetch_with_cache_fallback(sub.url)
        except RemoteFetchError:
            report.sources_unavailable += 1
            report.unavailable_urls.append(sub.url)
            continue
        report.sources_fetched += 1
        contents = parse_remote_marketplace_body(result.body)
        discovered_marketstall_urls.extend(contents.marketstall_urls)
        # Apply this source's ignores to its direct [[packages]] contribution.
        remote_marketplace_packages.extend(apply_ignores(contents.packages, sub.ignores))

    # Step 3: fetch each [[marketstalls]] — direct (gm.marketstalls) + discovered.
    direct_marketstall_packages: list[MarketplaceEntry] = []
    seen_marketstall_urls: set[str] = set()
    for sub in gm.marketstalls:
        if sub.url in seen_marketstall_urls:
            continue
        seen_marketstall_urls.add(sub.url)
        try:
            result = fetch_with_cache_fallback(sub.url)
        except RemoteFetchError:
            report.sources_unavailable += 1
            report.unavailable_urls.append(sub.url)
            continue
        report.sources_fetched += 1
        pkgs = parse_marketstall_body(result.body)
        direct_marketstall_packages.extend(apply_ignores(pkgs, sub.ignores))

    discovered_marketstall_packages: list[MarketplaceEntry] = []
    for url in discovered_marketstall_urls:
        if url in seen_marketstall_urls:
            continue
        seen_marketstall_urls.add(url)
        try:
            result = fetch_with_cache_fallback(url)
        except RemoteFetchError:
            report.sources_unavailable += 1
            report.unavailable_urls.append(url)
            continue
        report.sources_fetched += 1
        discovered_marketstall_packages.extend(parse_marketstall_body(result.body))

    # Step 4: flat candidate list, in the order spec §6 step 4 prescribes:
    #   global [[packages]] + global [[locals]] (kept separate) + marketstalls +
    #   remote-marketplace [[packages]].
    candidates: list[MarketplaceEntry] = list(gm.packages)
    candidates.extend(direct_marketstall_packages)
    candidates.extend(discovered_marketstall_packages)
    candidates.extend(remote_marketplace_packages)

    # Step 5: conflict resolution
    resolved = apply_locals_shadow(gm.locals_ + pm_prev.locals_, candidates)
    resolved = apply_first_come_first_served(resolved)

    # Step 7 (logically): mark stale.
    final_packages = mark_stale_against_previous(resolved, pm_prev.packages)

    report.packages_resolved = sum(1 for p in final_packages if not p.stale)
    report.new_stale = sum(
        1
        for p in final_packages
        if p.stale and p.name not in {prev.name for prev in pm_prev.packages if prev.stale}
    )

    # Step 6: write project marketplace — locals from the project file are preserved.
    new_pm = ProjectMarketplace(
        locals_=list(pm_prev.locals_),
        packages=final_packages,
    )
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_text(serialize_project_marketplace(new_pm))

    return report


def add_local_to_global(
    global_path: Path,
    *,
    name: str,
    path: Path,
    label: str = "",
    description: str = "",
) -> None:
    """Append a [[locals]] entry to the user-global marketplace.

    Raises DuplicateLocalNameError if an entry with the same name already
    exists (spec §6 G5 — name collision between projects). Preserves all
    other sections ([[marketplaces]], [[marketstalls]], [[packages]]) verbatim.

    This is the canonical helper for haywire init (Plan D's pattern) and any
    other writer that adds a single local. Composes the Phase 1 parser +
    serializer so the read/append/write is atomic.
    """
    gm = parse_global_marketplace(global_path)

    for existing in gm.locals_:
        if existing.get("name") == name:
            raise DuplicateLocalNameError(
                f'A project library named "{name}" is already registered '
                f"at {existing.get('path')} in {global_path}. "
                f"Rename your new project or remove the conflicting entry."
            )

    entry: dict[str, object] = {"name": name, "path": str(path)}
    if label:
        entry["label"] = label
    if description:
        entry["description"] = description
    gm.locals_.append(entry)

    global_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.write_text(serialize_global_marketplace(gm))


def add_local_to_project(
    project_path: Path,
    *,
    name: str,
    path: Path,
    label: str = "",
    description: str = "",
) -> None:
    """Append a [[locals]] entry to a project's <project>/.haywire/marketplace.toml.

    Raises DuplicateLocalNameError if an entry with the same name already
    exists in that project's [[locals]]. Preserves any existing [[packages]]
    entries verbatim.

    Used by `haywire init` to scaffold the project's own library entry and,
    in --dev mode, the dev-repo barn libraries the user wants to test against.
    """
    pm = parse_project_marketplace(project_path)

    for existing in pm.locals_:
        if existing.get("name") == name:
            raise DuplicateLocalNameError(
                f'A local library named "{name}" is already registered '
                f"at {existing.get('path')} in {project_path}."
            )

    entry: dict[str, object] = {"name": name, "path": str(path)}
    if label:
        entry["label"] = label
    if description:
        entry["description"] = description
    pm.locals_.append(entry)

    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_text(serialize_project_marketplace(pm))


def add_marketplace_subscription_to_global(global_path: Path, url: str) -> None:
    """Append a [[marketplaces]] entry to the user-global marketplace.

    Idempotent: subscribing to the same URL twice silently keeps the existing
    entry. Preserves all other sections verbatim.
    """
    gm = parse_global_marketplace(global_path)
    if any(sub.url == url for sub in gm.marketplaces):
        return
    gm.marketplaces.append(RemoteSubscription(url=url, ignores=[], doubles=[]))
    global_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.write_text(serialize_global_marketplace(gm))


def add_marketstall_subscription_to_global(global_path: Path, url: str) -> None:
    """Append a [[marketstalls]] entry to the user-global marketplace.

    Idempotent: subscribing to the same URL twice silently keeps the existing
    entry. Preserves all other sections verbatim.
    """
    gm = parse_global_marketplace(global_path)
    if any(sub.url == url for sub in gm.marketstalls):
        return
    gm.marketstalls.append(RemoteSubscription(url=url, ignores=[], doubles=[]))
    global_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.write_text(serialize_global_marketplace(gm))


def add_direct_package_to_global(global_path: Path, toml_block: str) -> None:
    """Append a direct [[packages]] entry from a user-pasted TOML block.

    Raises ValueError if the block is malformed TOML or has no [[packages]]
    section. Raises DuplicatePackageNameError if the package name already
    exists in [[packages]] (spec §6 conflict-resolution row 5: refused at
    UI write time).
    """
    try:
        data = toml.loads(toml_block)
    except toml.TomlDecodeError as exc:
        raise ValueError(f"invalid TOML in pasted block: {exc}") from exc

    raw_packages = data.get("packages", [])
    if not raw_packages:
        raise ValueError(
            "pasted block has no [[packages]] section. "
            "Expected a [[packages]] entry with name + min_version + source."
        )

    new_entries = [_parse_package_entry(raw) for raw in raw_packages]

    gm = parse_global_marketplace(global_path)
    existing_names = {pkg.name for pkg in gm.packages}
    for new_pkg in new_entries:
        if new_pkg.name in existing_names:
            raise DuplicatePackageNameError(
                f'A direct [[packages]] entry named "{new_pkg.name}" already exists. '
                f"Remove the existing entry first or rename the new one."
            )

    gm.packages.extend(new_entries)
    global_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.write_text(serialize_global_marketplace(gm))


@dataclass(frozen=True)
class SubscriptionConflict:
    """A name collision between an existing resolved package and a new subscription's package."""

    name: str
    existing_source: str  # URL of the source that originally provided this package
    new_source: str  # URL of the new subscription


def detect_subscription_conflicts(
    existing: list[MarketplaceEntry],
    new: list[MarketplaceEntry],
) -> list[SubscriptionConflict]:
    """Detect name collisions between existing resolved packages and a new subscription.

    Each conflict carries the name + both source URLs (read from source_origin).
    The UI prompt (Task 29) shows the user one row per conflict and writes the
    chosen `ignores` via record_ignore_on_source.

    `source_origin` is a runtime-only MarketplaceEntry field (not persisted).
    When it's empty (the entry wasn't routed through refresh), the conflict
    reports "(unknown)" so the UI can still render something meaningful.
    """
    existing_by_name = {pkg.name: pkg for pkg in existing}
    conflicts: list[SubscriptionConflict] = []
    for new_pkg in new:
        if new_pkg.name not in existing_by_name:
            continue
        existing_pkg = existing_by_name[new_pkg.name]
        conflicts.append(
            SubscriptionConflict(
                name=new_pkg.name,
                existing_source=existing_pkg.source_origin or "(unknown)",
                new_source=new_pkg.source_origin or "(unknown)",
            )
        )
    return conflicts


def record_ignore_on_source(
    global_path: Path,
    *,
    source_url: str,
    package_name: str,
) -> None:
    """Add `package_name` to the `ignores` array of the [[marketplaces]] or
    [[marketstalls]] entry at `source_url`.

    Idempotent: if the name is already in `ignores`, no-op. Per spec §6
    conflict-resolution: "ignores lives on the YIELDING side."
    """
    gm = parse_global_marketplace(global_path)
    changed = False

    for sub_list in (gm.marketplaces, gm.marketstalls):
        for i, sub in enumerate(sub_list):
            if sub.url != source_url:
                continue
            if package_name in sub.ignores:
                return  # Idempotent.
            new_ignores = list(sub.ignores)
            new_ignores.append(package_name)
            sub_list[i] = RemoteSubscription(url=sub.url, ignores=new_ignores, doubles=list(sub.doubles))
            changed = True
            break
        if changed:
            break

    if changed:
        global_path.write_text(serialize_global_marketplace(gm))
