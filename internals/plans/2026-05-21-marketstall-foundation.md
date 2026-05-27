# Marketstall Distribution — Foundation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the atomic data-layer foundation for the marketstall-distribution spec — rename the runtime vocabulary, add the `Haybale` dataclass with `os` field, ship GitHub + GitLab host providers, rewrite parsers for the new section names, add the `blocked` filter array at the data layer, and convert the refresh result to tri-state with cache GC. No UI changes yet; subsequent slices (author tooling, URL distribution UI, install safety, etc.) get their own plans.

**Architecture:** A single coherent atomic commit-set. The renames + dataclass shape + parsers + state helpers are interlocked — the dataclass field changes ripple into the parsers, which ripple into the state helpers, which ripple into every test file. The whole layer lands together via a series of small TDD tasks. After this plan ships, the runtime speaks the new vocabulary and the UI layer is still calling old-named methods that no longer exist — that's expected; the UI slice plan (slice 3) repoints the UI.

**Tech Stack:** Python 3.12, `dataclasses`, `toml` library, `pytest` (markers: `unit`, `integration`), `ruff`, `mypy`. No new third-party deps.

**Spec reference:** [`internals/specs/marketstall-distribution.md`](../speculatives/archive/marketstall-distribution.md). When this plan says "per §X", it means §X of that spec.

---

## File Structure

### New files (created)

- `packages/haywire-core/src/haywire/core/marketstall/__init__.py` — package marker; exports the new public API (`Haybale`, parsers, state helpers, host-provider re-exports).
- `packages/haywire-core/src/haywire/core/marketstall/types.py` — `Haybale` dataclass (renamed `MarketplaceEntry`) with new `os` field; `MarketplaceFile` / `MarketstallFile` / `Subscription` / `RefreshOutcome` / `RefreshReport` dataclasses; new schema after the rename.
- `packages/haywire-core/src/haywire/core/marketstall/errors.py` — exception types (renamed from `marketplace_errors`): `MalformedMarketplaceError`, `DuplicateHeapNameError`, `RemoteFetchError`. `DuplicatePackageNameError` removed (the direct-paste path is removed per §14).
- `packages/haywire-core/src/haywire/core/marketstall/parsing.py` — `parse_global_marketplace`, `parse_project_marketplace`, `parse_marketstall_body`, `parse_remote_marketplace_body`; serializers; entry parsers for `[[haybales]]`, `[[markets]]`, `[[stalls]]`, `[[heaps]]`, `[[caches]]`.
- `packages/haywire-core/src/haywire/core/marketstall/cache.py` — HTTP cache (`fetch_with_cache_fallback`), tri-state `FetchResult`, cache GC of orphaned files.
- `packages/haywire-core/src/haywire/core/marketstall/refresh.py` — `refresh()` orchestrator, `mark_stale_against_previous`, `apply_heaps_shadow`, `apply_first_come_first_served`, `apply_ignores`, `apply_blocked`, `RefreshReport` updates.
- `packages/haywire-core/src/haywire/core/marketstall/helpers.py` — `add_market_subscription_to_global`, `add_stall_subscription_to_global`, `add_heap_to_project`, `remove_stale_haybale_from_project`, `record_ignore_on_source`, `detect_subscription_conflicts`.
- `packages/haywire-core/src/haywire/core/marketstall/platform.py` — `current_os()` runtime helper mapping `platform.system()` to one of `"macos" | "windows" | "linux" | "other"`.
- `packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py` — exports `HOST_PROVIDERS`, `resolve_host`, `HostProvider`, `ParsedRef`.
- `packages/haywire-core/src/haywire/core/marketstall/host_providers/base.py` — `HostProvider` Protocol, `ParsedRef` frozen dataclass.
- `packages/haywire-core/src/haywire/core/marketstall/host_providers/github.py` — `GitHubProvider`.
- `packages/haywire-core/src/haywire/core/marketstall/host_providers/gitlab.py` — `GitLabProvider`.
- `packages/haywire-core/src/haywire/core/marketstall/host_providers/config.py` — `~/.haywire/config.toml` reader for self-hosted host declarations.
- `packages/haywire-core/src/haywire/core/marketstall/url_resolution.py` — Add-Source URL classification (blob / raw / plain TOML / pasted block); rejects bare repo URLs per §4.2.

### Test files (created, alongside source)

- `tests/marketstall/__init__.py`
- `tests/marketstall/test_haybale_dataclass.py`
- `tests/marketstall/test_errors.py`
- `tests/marketstall/test_parsing.py`
- `tests/marketstall/test_cache.py`
- `tests/marketstall/test_refresh.py`
- `tests/marketstall/test_helpers.py`
- `tests/marketstall/test_platform.py`
- `tests/marketstall/test_host_provider_github.py`
- `tests/marketstall/test_host_provider_gitlab.py`
- `tests/marketstall/test_host_provider_config.py`
- `tests/marketstall/test_url_resolution.py`

### Existing files (modified or deleted)

- `packages/haywire-core/src/haywire/core/marketplace.py` — **deleted**. `MarketplaceEntry` moves to `marketstall/types.py` as `Haybale`.
- `packages/haywire-core/src/haywire/core/marketplace_runtime.py` — **deleted**. Contents reorganized across `marketstall/parsing.py`, `cache.py`, `refresh.py`, `helpers.py`.
- `packages/haywire-core/src/haywire/core/marketplace_errors.py` — **deleted**. Contents move to `marketstall/errors.py`.
- `barn/haybale-studio/haybale_studio/state/marketplace_state.py` — **modified** to import from `haywire.core.marketstall.*`; uses new names (`get_project_haybales`, `remove_stale_haybale`). Does NOT yet route through new helpers for blocked/safety modal (those land in slice 5).
- `packages/haywire-studio/src/haywire_studio/library_manager.py` — **modified** to update imports (`MarketplaceEntry` → `Haybale`). No behavioral change.
- `packages/haywire-studio/src/haywire_studio/share.py` — **modified** to update imports + dataclass field name where used. Section name changes (`[[packages]]` → `[[haybales]]`) land in slice 2 (author tooling); this plan only updates type imports so the file compiles.
- `packages/haywire-studio/src/haywire_studio/config.py` — `_migrate_marketplace_schema_if_needed` and its call site **deleted**.
- `barn/haybale-studio/haybale_studio/editors/library_browser_editor.py` — **modified** to update imports. UI behavior unchanged in this plan.
- `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py` — **modified** to update imports. UI behavior unchanged in this plan.
- `tests/test_marketplace_entry.py` — **moved** to `tests/marketstall/test_haybale_dataclass.py` with renamed assertions.
- `tests/test_marketplace_runtime.py` — **split** across `tests/marketstall/test_parsing.py`, `test_cache.py`, `test_refresh.py`, `test_helpers.py`.
- `tests/test_marketplace_state.py` — **modified** in place; renamed assertions, new module imports.
- `tests/test_marketplace_migration.py` — **deleted**. The migration function it tested is also deleted.
- `docs/reference/glossary.md` — **modified** in lockstep with renames: update marketplace-runtime section entries, add entries for `[[markets]]`, `[[stalls]]`, `[[haybales]]`, `[[heaps]]`, `[[caches]]`, blob URL, raw URL, host provider.

### Files NOT touched in this plan (deferred to later slices)

- `haywire init` (`init.py`) — author tooling, slice 2.
- `haywire share` (`share.py`) — section emission changes, slice 2.
- README marker handling, slice 2.
- Add Source dialog — UI, slice 3.
- Library Browser provenance — UI, slice 3.
- OS multi-select dialog — UI, slice 4.
- First-install safety modal — UI, slice 5.
- Update-available signal — UI, slice 7.
- Drift gate `min_version` lag check — slice 6.

---

## Pre-flight Baseline

Before starting any task, the engineer must establish a baseline. The whole plan assumes a clean tree at start.

- [ ] **Step 0.1: Confirm clean tree**

Run: `git status`
Expected: working tree clean OR only the plan file as the new artifact.

- [ ] **Step 0.2: Run the existing test suite as the baseline**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all unit tests pass. Record the count.

- [ ] **Step 0.3: Run ruff and mypy as baseline**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/marketplace.py packages/haywire-core/src/haywire/core/marketplace_runtime.py packages/haywire-core/src/haywire/core/marketplace_errors.py barn/haybale-studio/haybale_studio/state/marketplace_state.py`
Expected: clean.

Run: `uv run mypy packages/haywire-core/src/haywire/core/marketplace.py packages/haywire-core/src/haywire/core/marketplace_runtime.py packages/haywire-core/src/haywire/core/marketplace_errors.py`
Expected: clean.

If anything is dirty, fix it before starting — the plan assumes a green baseline and "anything new is yours" per CLAUDE.md.


---

## Task 1: Create the `marketstall` package skeleton and `errors.py`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/__init__.py`
- Create: `packages/haywire-core/src/haywire/core/marketstall/errors.py`
- Create: `tests/marketstall/__init__.py`
- Create: `tests/marketstall/test_errors.py`

- [ ] **Step 1.1: Create empty package marker for the source tree**

```bash
mkdir -p packages/haywire-core/src/haywire/core/marketstall
```

Write to `packages/haywire-core/src/haywire/core/marketstall/__init__.py`:

```python
"""Marketstall distribution runtime — spec internals/specs/marketstall-distribution.md.

Replaces the legacy haywire.core.marketplace + marketplace_runtime + marketplace_errors
trio. The submodules here implement the new section vocabulary ([[markets]], [[stalls]],
[[haybales]], [[heaps]], [[caches]]), the host-provider abstraction, and the URL
resolution/refresh pipeline. The directory naming reflects the future haybale-marketplace
carve-out — see §3.1 of the spec.
"""
```

- [ ] **Step 1.2: Create empty test package marker**

```bash
mkdir -p tests/marketstall
```

Write to `tests/marketstall/__init__.py`:

```python
```

- [ ] **Step 1.3: Write the failing test for `errors.py`**

Write to `tests/marketstall/test_errors.py`:

```python
"""Exception types live in haywire.core.marketstall.errors."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_malformed_marketplace_error_is_runtime_error() -> None:
    from haywire.core.marketstall.errors import MalformedMarketplaceError

    assert issubclass(MalformedMarketplaceError, RuntimeError)


@pytest.mark.unit
def test_duplicate_heap_name_error_is_runtime_error() -> None:
    from haywire.core.marketstall.errors import DuplicateHeapNameError

    assert issubclass(DuplicateHeapNameError, RuntimeError)


@pytest.mark.unit
def test_remote_fetch_error_is_runtime_error() -> None:
    from haywire.core.marketstall.errors import RemoteFetchError

    assert issubclass(RemoteFetchError, RuntimeError)


@pytest.mark.unit
def test_duplicate_package_name_error_is_gone() -> None:
    """Direct-paste packages are removed per spec §14; the error class goes with them."""
    from haywire.core.marketstall import errors as errors_module

    assert not hasattr(errors_module, "DuplicatePackageNameError")
```

- [ ] **Step 1.4: Run the test to confirm it fails**

Run: `uv run pytest tests/marketstall/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: haywire.core.marketstall.errors`.

- [ ] **Step 1.5: Implement `errors.py`**

Write to `packages/haywire-core/src/haywire/core/marketstall/errors.py`:

```python
"""Custom exceptions for the marketstall runtime — spec §14."""

from __future__ import annotations


class MalformedMarketplaceError(RuntimeError):
    """Raised when a marketplace or marketstall file is invalid.

    Covers TOML parse errors and schema violations in both
    ~/.haywire/db/haybale-marketplace/marketplace.toml (global) and
    <project>/.haywire/marketplace.toml (project). Per spec §7, the Library
    Manager surfaces this with an Edit File banner; it does not recover
    automatically.
    """


class DuplicateHeapNameError(RuntimeError):
    """Raised when adding a [[heaps]] entry with a name that already exists.

    Applies to project marketplaces (heaps live only there per spec §3.2).
    haywire init may swallow this for idempotent re-runs of the same dev-repo
    library declaration.
    """


class RemoteFetchError(RuntimeError):
    """Raised by the HTTP cache layer when a remote URL is unreachable AND no cache exists.

    Always caught by the refresh orchestrator and converted to the `unavailable`
    tri-state outcome (spec §7.3); never propagates to the UI as an exception.
    """
```

- [ ] **Step 1.6: Run the test to confirm it passes**

Run: `uv run pytest tests/marketstall/test_errors.py -v`
Expected: 4 passed.

- [ ] **Step 1.7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/__init__.py \
        packages/haywire-core/src/haywire/core/marketstall/errors.py \
        tests/marketstall/__init__.py \
        tests/marketstall/test_errors.py
git commit -m "feat(marketstall): add errors module for new runtime package"
```

---

## Task 2: Add `Haybale` dataclass with `os` field

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/types.py`
- Create: `tests/marketstall/test_haybale_dataclass.py`

- [ ] **Step 2.1: Write the failing test**

Write to `tests/marketstall/test_haybale_dataclass.py`:

```python
"""Haybale dataclass — spec §14 rename of MarketplaceEntry, with new `os` field."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_haybale_minimal_construction() -> None:
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="haybale-foo", min_version="0.1.0")
    assert h.name == "haybale-foo"
    assert h.min_version == "0.1.0"
    assert h.label == ""
    assert h.os == []  # absent = all platforms per §2.1


@pytest.mark.unit
def test_haybale_full_construction() -> None:
    from haywire.core.marketstall.types import Haybale

    h = Haybale(
        name="haybale-vision",
        min_version="0.2.0",
        label="Vision",
        description="A library",
        author="Alice",
        source="git",
        install_spec="haybale-vision @ git+https://example.com",
        tags=["vision"],
        os=["macos", "linux"],
        dependencies=["haybale-core"],
        source_url="https://example.com/repo",
        docs_url="https://example.com/docs",
    )
    assert h.os == ["macos", "linux"]
    assert h.tags == ["vision"]


@pytest.mark.unit
def test_haybale_cache_fields_default_empty() -> None:
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1")
    assert h.via == ""
    assert h.last_seen == ""
    assert h.stale is False


@pytest.mark.unit
def test_haybale_to_dict_omits_empty_fields() -> None:
    """Empty list and False-bool fields are omitted via the falsy check.

    Note: defaulted string fields with truthy defaults (e.g. source="pypi")
    are still included — `to_dict()` uses a simple `if val:` falsy check,
    matching the legacy MarketplaceEntry.to_dict() semantics.
    """
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="haybale-foo", min_version="0.1.0")
    d = h.to_dict()
    assert d["name"] == "haybale-foo"
    assert d["min_version"] == "0.1.0"
    # Empty/default falsy fields are omitted.
    assert "os" not in d
    assert "tags" not in d
    assert "dependencies" not in d
    assert "stale" not in d
    assert "label" not in d
    assert "description" not in d
    assert "install_spec" not in d  # default is "" which is falsy


@pytest.mark.unit
def test_haybale_to_dict_includes_os_when_present() -> None:
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="haybale-foo", min_version="0.1.0", os=["macos", "linux"])
    d = h.to_dict()
    assert d["os"] == ["macos", "linux"]


@pytest.mark.unit
def test_haybale_field_order_in_toml_fields() -> None:
    """Spec §2 field-semantics table sets the canonical order; `os` lives between tags and dependencies."""
    from haywire.core.marketstall.types import Haybale

    fields = Haybale._TOML_FIELDS
    assert "os" in fields
    tags_idx = fields.index("tags")
    os_idx = fields.index("os")
    deps_idx = fields.index("dependencies")
    assert tags_idx < os_idx < deps_idx
```

- [ ] **Step 2.2: Run the test to confirm it fails**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -v`
Expected: FAIL — `ModuleNotFoundError: haywire.core.marketstall.types`.

- [ ] **Step 2.3: Implement `Haybale`**

Write to `packages/haywire-core/src/haywire/core/marketstall/types.py`:

```python
"""Marketstall runtime dataclasses — spec §2 and §14.

The Haybale dataclass replaces the legacy MarketplaceEntry. Adds the `os` field
from §2.1; same shape otherwise. Subscription dataclasses for [[markets]] and
[[stalls]] gain the `blocked` array introduced for the first-install safety
modal (§7.4); data-layer only in this plan, wired through the UI in slice 5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class Haybale:
    """One entry from a [[haybales]] section. Renamed from MarketplaceEntry."""

    name: str
    min_version: str
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
        "min_version",
        "description",
        "author",
        "source",
        "install_spec",
        "tags",
        "os",
        "dependencies",
        "source_url",
        "docs_url",
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
```

- [ ] **Step 2.4: Run the test to confirm it passes**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -v`
Expected: 6 passed.

- [ ] **Step 2.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/types.py \
        tests/marketstall/test_haybale_dataclass.py
git commit -m "feat(marketstall): add Haybale dataclass with os field"
```

---

## Task 3: Add `Subscription` dataclass with `blocked` field

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/types.py`
- Modify: `tests/marketstall/test_haybale_dataclass.py` (extend with subscription tests)

- [ ] **Step 3.1: Write the failing test for `Subscription`**

Append to `tests/marketstall/test_haybale_dataclass.py`:

```python
@pytest.mark.unit
def test_subscription_minimal_construction() -> None:
    from haywire.core.marketstall.types import Subscription

    s = Subscription(url="https://example.com/marketplace.toml")
    assert s.url == "https://example.com/marketplace.toml"
    assert s.ignores == []
    assert s.doubles == []
    assert s.blocked == []  # new field per §7.4


@pytest.mark.unit
def test_subscription_with_blocked() -> None:
    from haywire.core.marketstall.types import Subscription

    s = Subscription(
        url="https://example.com/marketstall.toml",
        ignores=["haybale-skip"],
        blocked=["haybale-untrusted"],
    )
    assert s.blocked == ["haybale-untrusted"]


@pytest.mark.unit
def test_subscription_is_frozen() -> None:
    """Frozen so it can live in sets and as dict keys if needed."""
    from haywire.core.marketstall.types import Subscription

    s = Subscription(url="https://example.com/x.toml")
    with pytest.raises((AttributeError, Exception)):
        s.url = "other"  # type: ignore[misc]
```

- [ ] **Step 3.2: Run the test to confirm it fails**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -v -k subscription`
Expected: FAIL — `ImportError: cannot import name 'Subscription'`.

- [ ] **Step 3.3: Add `Subscription` to `types.py`**

Append to `packages/haywire-core/src/haywire/core/marketstall/types.py`:

```python
@dataclass(frozen=True)
class Subscription:
    """One [[markets]] or [[stalls]] entry. Same shape; distinction is which list it lives in.

    Per spec §3.1 / §7.4: `blocked` holds names the user actively rejected via
    the first-install safety modal. Per-subscription; un-blockable only by
    editing the marketplace file.
    """

    url: str
    ignores: list[str] = field(default_factory=list)
    doubles: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
```

- [ ] **Step 3.4: Run the test to confirm it passes**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -v`
Expected: 9 passed.

- [ ] **Step 3.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/types.py \
        tests/marketstall/test_haybale_dataclass.py
git commit -m "feat(marketstall): add Subscription dataclass with blocked array"
```

---

## Task 4: Add file-level container dataclasses (`MarketplaceFile`, `ProjectMarketplaceFile`)

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/types.py`
- Modify: `tests/marketstall/test_haybale_dataclass.py`

- [ ] **Step 4.1: Write the failing test**

Append to `tests/marketstall/test_haybale_dataclass.py`:

```python
@pytest.mark.unit
def test_marketplace_file_default_empty() -> None:
    from haywire.core.marketstall.types import MarketplaceFile

    mf = MarketplaceFile()
    assert mf.markets == []
    assert mf.stalls == []
    assert mf.haybales == []


@pytest.mark.unit
def test_project_marketplace_file_default_empty() -> None:
    from haywire.core.marketstall.types import ProjectMarketplaceFile

    pm = ProjectMarketplaceFile()
    assert pm.heaps == []
    assert pm.caches == []
```

- [ ] **Step 4.2: Run the test to confirm it fails**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -v -k file`
Expected: FAIL — `ImportError`.

- [ ] **Step 4.3: Add the container dataclasses**

Append to `packages/haywire-core/src/haywire/core/marketstall/types.py`:

```python
@dataclass
class MarketplaceFile:
    """Parsed ~/.haywire/db/haybale-marketplace/marketplace.toml — spec §3.1.

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
    """Parsed <project>/.haywire/marketplace.toml — spec §3.2.

    Two section types:
      - [[heaps]]: unpublished path-based libraries (written by haywire init)
      - [[caches]]: refresh result; Haybale entries with via/last_seen/stale set

    `[[markets]]` and `[[stalls]]` never appear in the project file.
    """

    heaps: list[dict] = field(default_factory=list)
    caches: list[Haybale] = field(default_factory=list)
```

- [ ] **Step 4.4: Run the test to confirm it passes**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -v`
Expected: 11 passed.

- [ ] **Step 4.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/types.py \
        tests/marketstall/test_haybale_dataclass.py
git commit -m "feat(marketstall): add MarketplaceFile and ProjectMarketplaceFile containers"
```

---

## Task 5: Tri-state `FetchResult` and `RefreshOutcome` enum

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/types.py`
- Modify: `tests/marketstall/test_haybale_dataclass.py`

- [ ] **Step 5.1: Write the failing test**

Append to `tests/marketstall/test_haybale_dataclass.py`:

```python
@pytest.mark.unit
def test_refresh_outcome_has_three_states() -> None:
    from haywire.core.marketstall.types import RefreshOutcome

    assert RefreshOutcome.FRESH.value == "fresh"
    assert RefreshOutcome.CACHE_FALLBACK.value == "cache_fallback"
    assert RefreshOutcome.UNAVAILABLE.value == "unavailable"


@pytest.mark.unit
def test_fetch_result_fresh() -> None:
    from haywire.core.marketstall.types import FetchResult, RefreshOutcome

    r = FetchResult(body="contents", outcome=RefreshOutcome.FRESH, cache_age=None)
    assert r.outcome is RefreshOutcome.FRESH
    assert r.body == "contents"


@pytest.mark.unit
def test_fetch_result_cache_fallback_has_age() -> None:
    from haywire.core.marketstall.types import FetchResult, RefreshOutcome

    r = FetchResult(body="cached", outcome=RefreshOutcome.CACHE_FALLBACK, cache_age=3600.0)
    assert r.outcome is RefreshOutcome.CACHE_FALLBACK
    assert r.cache_age == 3600.0
```

- [ ] **Step 5.2: Run the test to confirm it fails**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -v -k "outcome or fetch_result"`
Expected: FAIL — `ImportError`.

- [ ] **Step 5.3: Add `RefreshOutcome` enum and `FetchResult`**

Append to `packages/haywire-core/src/haywire/core/marketstall/types.py`:

```python
import enum


class RefreshOutcome(enum.Enum):
    """Tri-state per-subscription refresh result — spec §7.3."""

    FRESH = "fresh"  # HTTP 200; cache overwritten
    CACHE_FALLBACK = "cache_fallback"  # HTTP failed; body served from cache
    UNAVAILABLE = "unavailable"  # HTTP failed; no cache


@dataclass(frozen=True)
class FetchResult:
    """Output of fetch_with_cache_fallback. Always populated when no exception is raised."""

    body: str
    outcome: RefreshOutcome
    cache_age: float | None  # Set when outcome is CACHE_FALLBACK; None for FRESH.
```

Also add the `import enum` line to the top of the file alongside the existing `from dataclasses import ...` line.

- [ ] **Step 5.4: Run the test to confirm it passes**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -v`
Expected: 14 passed.

- [ ] **Step 5.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/types.py \
        tests/marketstall/test_haybale_dataclass.py
git commit -m "feat(marketstall): add RefreshOutcome enum and FetchResult"
```

---

## Task 6: `RefreshReport` with new fields

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/types.py`
- Modify: `tests/marketstall/test_haybale_dataclass.py`

- [ ] **Step 6.1: Write the failing test**

Append to `tests/marketstall/test_haybale_dataclass.py`:

```python
@pytest.mark.unit
def test_refresh_report_default_zeros() -> None:
    from haywire.core.marketstall.types import RefreshReport

    r = RefreshReport()
    assert r.sources_fetched == 0
    assert r.sources_from_cache == 0  # new field per §9
    assert r.sources_unavailable == 0
    assert r.unavailable_urls == []
    assert r.haybales_resolved == 0  # renamed from packages_resolved per §14
    assert r.new_stale == 0
    assert r.updates_available == 0  # new field per §10.3


@pytest.mark.unit
def test_refresh_report_sources_partition() -> None:
    """fetched + from_cache + unavailable must always sum to total subscriptions."""
    from haywire.core.marketstall.types import RefreshReport

    r = RefreshReport(sources_fetched=3, sources_from_cache=1, sources_unavailable=2)
    assert r.sources_fetched + r.sources_from_cache + r.sources_unavailable == 6
```

- [ ] **Step 6.2: Run the test to confirm it fails**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -v -k refresh_report`
Expected: FAIL — `ImportError`.

- [ ] **Step 6.3: Add `RefreshReport`**

Append to `packages/haywire-core/src/haywire/core/marketstall/types.py`:

```python
@dataclass
class RefreshReport:
    """Summary of a refresh run — spec §9.

    Per §7.3, sources_fetched + sources_from_cache + sources_unavailable always
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
```

- [ ] **Step 6.4: Run the test to confirm it passes**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py -v`
Expected: 16 passed.

- [ ] **Step 6.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/types.py \
        tests/marketstall/test_haybale_dataclass.py
git commit -m "feat(marketstall): add RefreshReport with sources_from_cache and updates_available"
```


---

## Task 7: `current_os()` platform helper

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/platform.py`
- Create: `tests/marketstall/test_platform.py`

- [ ] **Step 7.1: Write the failing test**

Write to `tests/marketstall/test_platform.py`:

```python
"""current_os() — spec §2.1 mapping table."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_current_os_maps_darwin_to_macos() -> None:
    from haywire.core.marketstall.platform import current_os

    with patch("haywire.core.marketstall.platform.platform.system", return_value="Darwin"):
        assert current_os() == "macos"


@pytest.mark.unit
def test_current_os_maps_windows_to_windows() -> None:
    from haywire.core.marketstall.platform import current_os

    with patch("haywire.core.marketstall.platform.platform.system", return_value="Windows"):
        assert current_os() == "windows"


@pytest.mark.unit
def test_current_os_maps_linux_to_linux() -> None:
    from haywire.core.marketstall.platform import current_os

    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        assert current_os() == "linux"


@pytest.mark.unit
def test_current_os_maps_unknown_to_other() -> None:
    from haywire.core.marketstall.platform import current_os

    with patch("haywire.core.marketstall.platform.platform.system", return_value="FreeBSD"):
        assert current_os() == "other"


@pytest.mark.unit
def test_haybale_supports_current_when_os_empty() -> None:
    """Empty os list = all platforms per §2.1."""
    from haywire.core.marketstall.platform import haybale_supports_current_os
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1", os=[])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        assert haybale_supports_current_os(h) is True


@pytest.mark.unit
def test_haybale_supports_current_when_listed() -> None:
    from haywire.core.marketstall.platform import haybale_supports_current_os
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1", os=["macos", "linux"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        assert haybale_supports_current_os(h) is True


@pytest.mark.unit
def test_haybale_does_not_support_current_when_not_listed() -> None:
    from haywire.core.marketstall.platform import haybale_supports_current_os
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1", os=["macos"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Linux"):
        assert haybale_supports_current_os(h) is False


@pytest.mark.unit
def test_haybale_on_other_os_blocked_from_all_declared() -> None:
    """`other` is the runtime sentinel; a declared list never includes 'other' so 'other' never matches."""
    from haywire.core.marketstall.platform import haybale_supports_current_os
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1", os=["macos", "linux", "windows"])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="OpenBSD"):
        assert haybale_supports_current_os(h) is False


@pytest.mark.unit
def test_haybale_on_other_os_supported_when_empty() -> None:
    """Pure-Python library with no os declared still installs on unknown OSes."""
    from haywire.core.marketstall.platform import haybale_supports_current_os
    from haywire.core.marketstall.types import Haybale

    h = Haybale(name="x", min_version="0.0.1", os=[])
    with patch("haywire.core.marketstall.platform.platform.system", return_value="Haiku"):
        assert haybale_supports_current_os(h) is True
```

- [ ] **Step 7.2: Run the test to confirm it fails**

Run: `uv run pytest tests/marketstall/test_platform.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 7.3: Implement `platform.py`**

Write to `packages/haywire-core/src/haywire/core/marketstall/platform.py`:

```python
"""Current-OS detection — spec §2.1 mapping table.

`platform.system()` returns OS-family strings; we map them to the four-value
runtime vocabulary (macos | windows | linux | other). `other` is a runtime-only
sentinel — never a declarable value (haywire share rejects it). The absent
default on Haybale.os is the "supports all platforms" case.
"""

from __future__ import annotations

import platform
from typing import Literal

from haywire.core.marketstall.types import Haybale

OsName = Literal["macos", "windows", "linux", "other"]


def current_os() -> OsName:
    """Map `platform.system()` to the four-value runtime OS vocabulary."""
    name = platform.system()
    if name == "Darwin":
        return "macos"
    if name == "Windows":
        return "windows"
    if name == "Linux":
        return "linux"
    return "other"


def haybale_supports_current_os(h: Haybale) -> bool:
    """True iff `h.os` is empty (= all platforms) or contains current_os()."""
    if not h.os:
        return True
    return current_os() in h.os
```

- [ ] **Step 7.4: Run the test to confirm it passes**

Run: `uv run pytest tests/marketstall/test_platform.py -v`
Expected: 9 passed.

- [ ] **Step 7.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/platform.py \
        tests/marketstall/test_platform.py
git commit -m "feat(marketstall): add current_os() and haybale_supports_current_os()"
```

---

## Task 8: Host-provider Protocol + `ParsedRef`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py`
- Create: `packages/haywire-core/src/haywire/core/marketstall/host_providers/base.py`

- [ ] **Step 8.1: Create the host_providers package marker**

```bash
mkdir -p packages/haywire-core/src/haywire/core/marketstall/host_providers
```

Write to `packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py`:

```python
"""Host-provider abstraction — spec §5.

GitHub + GitLab ship in the first cut. Bitbucket and Gitea are deferred.
"""

from haywire.core.marketstall.host_providers.base import HostProvider, ParsedRef

__all__ = ["HostProvider", "ParsedRef", "HOST_PROVIDERS", "resolve_host"]

# Populated by Task 10 once GitHubProvider/GitLabProvider exist.
HOST_PROVIDERS: list[HostProvider] = []


def resolve_host(hostname: str) -> HostProvider | None:
    """Return the first provider that claims this hostname, or None."""
    for provider in HOST_PROVIDERS:
        if provider.matches(hostname):
            return provider
    return None
```

- [ ] **Step 8.2: Write the failing test for `base.py`**

Write to `tests/marketstall/test_host_provider_github.py`:

```python
"""ParsedRef sanity and Protocol shape tests."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_parsed_ref_construction() -> None:
    from haywire.core.marketstall.host_providers.base import ParsedRef

    p = ParsedRef(owner="alice", repo="cool-libs", ref="main", path="marketstall.toml")
    assert p.owner == "alice"
    assert p.repo == "cool-libs"
    assert p.ref == "main"
    assert p.path == "marketstall.toml"


@pytest.mark.unit
def test_parsed_ref_is_frozen() -> None:
    from haywire.core.marketstall.host_providers.base import ParsedRef

    p = ParsedRef(owner="a", repo="b", ref="main", path="x.toml")
    with pytest.raises((AttributeError, Exception)):
        p.owner = "other"  # type: ignore[misc]
```

- [ ] **Step 8.3: Run the test to confirm it fails**

Run: `uv run pytest tests/marketstall/test_host_provider_github.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 8.4: Implement `base.py`**

Write to `packages/haywire-core/src/haywire/core/marketstall/host_providers/base.py`:

```python
"""HostProvider Protocol + ParsedRef — spec §5.1.

No `parse_repo_url` and no `default_branch` — bare repo URLs are rejected
at input time (§4.2), so no provider ever needs to probe for a default branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ParsedRef:
    """The four components of a host-specific blob/raw URL: owner, repo, ref, path."""

    owner: str
    repo: str
    ref: str
    path: str


class HostProvider(Protocol):
    """One git host's URL conventions — spec §5.1."""

    name: str  # "github", "gitlab", etc.

    def matches(self, hostname: str) -> bool:
        """True if this provider handles URLs with this hostname."""
        ...

    def parse_blob_url(self, url: str) -> ParsedRef | None:
        """Parse a blob URL into ParsedRef. None if not a match."""
        ...

    def parse_raw_url(self, url: str) -> ParsedRef | None:
        """Parse a raw URL into ParsedRef. None if not a match."""
        ...

    def raw_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Construct the raw URL for fetching."""
        ...

    def blob_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Construct the share URL (canonical, browser-friendly)."""
        ...
```

- [ ] **Step 8.5: Run the test to confirm it passes**

Run: `uv run pytest tests/marketstall/test_host_provider_github.py -v`
Expected: 2 passed.

- [ ] **Step 8.6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py \
        packages/haywire-core/src/haywire/core/marketstall/host_providers/base.py \
        tests/marketstall/test_host_provider_github.py
git commit -m "feat(marketstall): add HostProvider Protocol and ParsedRef"
```

---

## Task 9: `GitHubProvider`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/host_providers/github.py`
- Modify: `tests/marketstall/test_host_provider_github.py`

- [ ] **Step 9.1: Write the failing tests**

Append to `tests/marketstall/test_host_provider_github.py`:

```python
@pytest.mark.unit
def test_github_matches_github_com() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    assert p.matches("github.com") is True
    assert p.matches("gitlab.com") is False
    assert p.matches("example.com") is False


@pytest.mark.unit
def test_github_parse_blob_url() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    parsed = p.parse_blob_url("https://github.com/alice/cool-libs/blob/main/marketstall.toml")
    assert parsed is not None
    assert parsed.owner == "alice"
    assert parsed.repo == "cool-libs"
    assert parsed.ref == "main"
    assert parsed.path == "marketstall.toml"


@pytest.mark.unit
def test_github_parse_blob_url_with_subpath() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    parsed = p.parse_blob_url(
        "https://github.com/alice/cool-libs/blob/v0.2.0/stalls/haybale-foo.toml"
    )
    assert parsed is not None
    assert parsed.ref == "v0.2.0"
    assert parsed.path == "stalls/haybale-foo.toml"


@pytest.mark.unit
def test_github_parse_blob_url_returns_none_for_non_github() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    assert p.parse_blob_url("https://gitlab.com/x/y/-/blob/main/file.toml") is None
    assert p.parse_blob_url("https://github.com/alice/cool-libs") is None  # no /blob/
    assert p.parse_blob_url("not a url") is None


@pytest.mark.unit
def test_github_parse_raw_url() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    parsed = p.parse_raw_url(
        "https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml"
    )
    assert parsed is not None
    assert parsed.owner == "alice"
    assert parsed.repo == "cool-libs"
    assert parsed.ref == "main"
    assert parsed.path == "marketstall.toml"


@pytest.mark.unit
def test_github_raw_url_construction() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    url = p.raw_url("alice", "cool-libs", "main", "marketstall.toml")
    assert url == "https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml"


@pytest.mark.unit
def test_github_blob_url_construction() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    url = p.blob_url("alice", "cool-libs", "main", "marketstall.toml")
    assert url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"


@pytest.mark.unit
def test_github_roundtrip_blob_to_raw_to_blob() -> None:
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = GitHubProvider()
    original = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    parsed = p.parse_blob_url(original)
    assert parsed is not None
    raw = p.raw_url(parsed.owner, parsed.repo, parsed.ref, parsed.path)
    reparsed = p.parse_raw_url(raw)
    assert reparsed == parsed
    assert p.blob_url(reparsed.owner, reparsed.repo, reparsed.ref, reparsed.path) == original
```

- [ ] **Step 9.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_host_provider_github.py -v`
Expected: FAIL on the new tests with `ModuleNotFoundError`.

- [ ] **Step 9.3: Implement `GitHubProvider`**

Write to `packages/haywire-core/src/haywire/core/marketstall/host_providers/github.py`:

```python
"""GitHubProvider — spec §5.2 row 1.

Blob URL: https://github.com/{owner}/{repo}/blob/{ref}/{path}
Raw URL:  https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}

`{ref}` can be a branch name, tag name, or commit SHA. The provider does not
distinguish — it carries whatever the author shared.
"""

from __future__ import annotations

import re

from haywire.core.marketstall.host_providers.base import ParsedRef

_BLOB_PATTERN = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/blob/(?P<ref>[^/]+)/(?P<path>.+)$"
)
_RAW_PATTERN = re.compile(
    r"^https://raw\.githubusercontent\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/(?P<ref>[^/]+)/(?P<path>.+)$"
)


class GitHubProvider:
    """Built-in provider for github.com (and matched self-hosted aliases via config)."""

    name = "github"

    def matches(self, hostname: str) -> bool:
        return hostname == "github.com"

    def parse_blob_url(self, url: str) -> ParsedRef | None:
        m = _BLOB_PATTERN.match(url)
        if m is None:
            return None
        return ParsedRef(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref"),
            path=m.group("path"),
        )

    def parse_raw_url(self, url: str) -> ParsedRef | None:
        m = _RAW_PATTERN.match(url)
        if m is None:
            return None
        return ParsedRef(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref"),
            path=m.group("path"),
        )

    def raw_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"

    def blob_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://github.com/{owner}/{repo}/blob/{ref}/{path}"
```

- [ ] **Step 9.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_host_provider_github.py -v`
Expected: 10 passed (2 from Task 8 + 8 new).

- [ ] **Step 9.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/host_providers/github.py \
        tests/marketstall/test_host_provider_github.py
git commit -m "feat(marketstall): add GitHubProvider"
```

---

## Task 10: `GitLabProvider`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/host_providers/gitlab.py`
- Create: `tests/marketstall/test_host_provider_gitlab.py`

- [ ] **Step 10.1: Write the failing tests**

Write to `tests/marketstall/test_host_provider_gitlab.py`:

```python
"""GitLabProvider — spec §5.2 row 2."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_gitlab_matches_gitlab_com() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    assert p.matches("gitlab.com") is True
    assert p.matches("github.com") is False


@pytest.mark.unit
def test_gitlab_parse_blob_url() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    parsed = p.parse_blob_url("https://gitlab.com/alice/cool-libs/-/blob/main/marketstall.toml")
    assert parsed is not None
    assert parsed.owner == "alice"
    assert parsed.repo == "cool-libs"
    assert parsed.ref == "main"
    assert parsed.path == "marketstall.toml"


@pytest.mark.unit
def test_gitlab_parse_blob_url_with_subgroup() -> None:
    """GitLab supports nested groups. The 'owner' here is everything before /-/blob/."""
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    parsed = p.parse_blob_url(
        "https://gitlab.com/group/subgroup/proj/-/blob/main/marketstall.toml"
    )
    assert parsed is not None
    assert parsed.owner == "group/subgroup"
    assert parsed.repo == "proj"
    assert parsed.ref == "main"
    assert parsed.path == "marketstall.toml"


@pytest.mark.unit
def test_gitlab_parse_raw_url() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    parsed = p.parse_raw_url("https://gitlab.com/alice/cool-libs/-/raw/main/marketstall.toml")
    assert parsed is not None
    assert parsed.owner == "alice"
    assert parsed.repo == "cool-libs"
    assert parsed.ref == "main"
    assert parsed.path == "marketstall.toml"


@pytest.mark.unit
def test_gitlab_raw_url_construction() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    url = p.raw_url("alice", "cool-libs", "main", "marketstall.toml")
    assert url == "https://gitlab.com/alice/cool-libs/-/raw/main/marketstall.toml"


@pytest.mark.unit
def test_gitlab_blob_url_construction() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    url = p.blob_url("alice", "cool-libs", "main", "marketstall.toml")
    assert url == "https://gitlab.com/alice/cool-libs/-/blob/main/marketstall.toml"


@pytest.mark.unit
def test_gitlab_does_not_parse_github_url() -> None:
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = GitLabProvider()
    assert p.parse_blob_url("https://github.com/alice/x/blob/main/file.toml") is None
    assert p.parse_raw_url("https://raw.githubusercontent.com/a/b/main/f.toml") is None
```

- [ ] **Step 10.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_host_provider_gitlab.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 10.3: Implement `GitLabProvider`**

Write to `packages/haywire-core/src/haywire/core/marketstall/host_providers/gitlab.py`:

```python
"""GitLabProvider — spec §5.2 row 2.

Blob URL: https://gitlab.com/{owner}/{repo}/-/blob/{ref}/{path}
Raw URL:  https://gitlab.com/{owner}/{repo}/-/raw/{ref}/{path}

GitLab supports nested subgroups, so `{owner}` may contain slashes
(e.g. `group/subgroup`). Repos themselves do not contain slashes.
"""

from __future__ import annotations

import re

from haywire.core.marketstall.host_providers.base import ParsedRef

# Greedy owner (captures up to the last segment before /repo/-/blob/...).
_BLOB_PATTERN = re.compile(
    r"^https://gitlab\.com/(?P<owner>.+)/(?P<repo>[^/]+)/-/blob/(?P<ref>[^/]+)/(?P<path>.+)$"
)
_RAW_PATTERN = re.compile(
    r"^https://gitlab\.com/(?P<owner>.+)/(?P<repo>[^/]+)/-/raw/(?P<ref>[^/]+)/(?P<path>.+)$"
)


class GitLabProvider:
    """Built-in provider for gitlab.com."""

    name = "gitlab"

    def matches(self, hostname: str) -> bool:
        return hostname == "gitlab.com"

    def parse_blob_url(self, url: str) -> ParsedRef | None:
        m = _BLOB_PATTERN.match(url)
        if m is None:
            return None
        return ParsedRef(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref"),
            path=m.group("path"),
        )

    def parse_raw_url(self, url: str) -> ParsedRef | None:
        m = _RAW_PATTERN.match(url)
        if m is None:
            return None
        return ParsedRef(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref"),
            path=m.group("path"),
        )

    def raw_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://gitlab.com/{owner}/{repo}/-/raw/{ref}/{path}"

    def blob_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        return f"https://gitlab.com/{owner}/{repo}/-/blob/{ref}/{path}"
```

- [ ] **Step 10.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_host_provider_gitlab.py -v`
Expected: 7 passed.

- [ ] **Step 10.5: Wire providers into the registry**

Modify `packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py`. Replace the `HOST_PROVIDERS: list[HostProvider] = []` line with:

```python
from haywire.core.marketstall.host_providers.github import GitHubProvider
from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

HOST_PROVIDERS: list[HostProvider] = [
    GitHubProvider(),
    GitLabProvider(),
    # BitbucketProvider() — deferred; see spec §5.2
    # GiteaProvider()     — deferred; see spec §5.2
]
```

- [ ] **Step 10.6: Add a registry-level test**

Append to `tests/marketstall/test_host_provider_gitlab.py`:

```python
@pytest.mark.unit
def test_resolve_host_returns_github() -> None:
    from haywire.core.marketstall.host_providers import resolve_host
    from haywire.core.marketstall.host_providers.github import GitHubProvider

    p = resolve_host("github.com")
    assert isinstance(p, GitHubProvider)


@pytest.mark.unit
def test_resolve_host_returns_gitlab() -> None:
    from haywire.core.marketstall.host_providers import resolve_host
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider

    p = resolve_host("gitlab.com")
    assert isinstance(p, GitLabProvider)


@pytest.mark.unit
def test_resolve_host_returns_none_for_unknown() -> None:
    from haywire.core.marketstall.host_providers import resolve_host

    assert resolve_host("bitbucket.org") is None
    assert resolve_host("example.com") is None
```

- [ ] **Step 10.7: Run all host-provider tests**

Run: `uv run pytest tests/marketstall/test_host_provider_github.py tests/marketstall/test_host_provider_gitlab.py -v`
Expected: 20 passed (10 + 10).

- [ ] **Step 10.8: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/host_providers/gitlab.py \
        packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py \
        tests/marketstall/test_host_provider_gitlab.py
git commit -m "feat(marketstall): add GitLabProvider and register both providers"
```


---

## Task 11: Self-hosted host config reader

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/host_providers/config.py`
- Create: `tests/marketstall/test_host_provider_config.py`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py` (resolve_host consults config first)

- [ ] **Step 11.1: Write the failing test**

Write to `tests/marketstall/test_host_provider_config.py`:

```python
"""~/.haywire/config.toml self-hosted host declarations — spec §5.4."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_load_self_hosted_returns_empty_when_file_missing(tmp_path: Path) -> None:
    from haywire.core.marketstall.host_providers.config import load_self_hosted_hosts

    config = tmp_path / "config.toml"
    assert load_self_hosted_hosts(config) == {}


@pytest.mark.unit
def test_load_self_hosted_parses_hosts_section(tmp_path: Path) -> None:
    from haywire.core.marketstall.host_providers.config import load_self_hosted_hosts

    config = tmp_path / "config.toml"
    config.write_text(
        '[[hosts]]\n'
        'hostname = "git.acme.example"\n'
        'provider = "gitlab"\n'
        '\n'
        '[[hosts]]\n'
        'hostname = "code.team.example"\n'
        'provider = "github"\n'
    )

    hosts = load_self_hosted_hosts(config)
    assert hosts == {
        "git.acme.example": "gitlab",
        "code.team.example": "github",
    }


@pytest.mark.unit
def test_load_self_hosted_ignores_unknown_provider(tmp_path: Path) -> None:
    """Entries naming a non-shipped provider are silently dropped."""
    from haywire.core.marketstall.host_providers.config import load_self_hosted_hosts

    config = tmp_path / "config.toml"
    config.write_text(
        '[[hosts]]\n'
        'hostname = "code.example"\n'
        'provider = "gitea"\n'  # deferred — not in the first cut
    )

    assert load_self_hosted_hosts(config) == {}


@pytest.mark.unit
def test_resolve_host_consults_user_config_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A user-declared self-hosted hostname routes to the named built-in provider."""
    from haywire.core.marketstall.host_providers import resolve_host
    from haywire.core.marketstall.host_providers.gitlab import GitLabProvider
    from haywire.core.marketstall.host_providers import config as host_config_module

    config = tmp_path / "config.toml"
    config.write_text(
        '[[hosts]]\n'
        'hostname = "git.acme.example"\n'
        'provider = "gitlab"\n'
    )
    monkeypatch.setattr(host_config_module, "_user_config_path", lambda: config)

    p = resolve_host("git.acme.example")
    assert isinstance(p, GitLabProvider)
```

- [ ] **Step 11.2: Run the test to confirm it fails**

Run: `uv run pytest tests/marketstall/test_host_provider_config.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 11.3: Implement `config.py`**

Write to `packages/haywire-core/src/haywire/core/marketstall/host_providers/config.py`:

```python
"""Self-hosted host declarations from ~/.haywire/config.toml — spec §5.4.

Example:
    [[hosts]]
    hostname = "git.acme.example"
    provider = "gitlab"

Only the shipped provider names ("github", "gitlab") are honored; unknown
providers are silently dropped (Bitbucket/Gitea will become honored once
their providers ship).
"""

from __future__ import annotations

from pathlib import Path

import toml

_SHIPPED_PROVIDERS = {"github", "gitlab"}


def _user_config_path() -> Path:
    """The canonical ~/.haywire/config.toml location. Wrapped for test monkeypatching."""
    return Path.home() / ".haywire" / "config.toml"


def load_self_hosted_hosts(config_path: Path | None = None) -> dict[str, str]:
    """Read [[hosts]] entries; return {hostname: provider_name}.

    Returns empty when the file does not exist or contains no valid entries.
    Drops entries naming providers that haven't shipped yet.
    """
    path = config_path if config_path is not None else _user_config_path()
    if not path.is_file():
        return {}
    try:
        data = toml.loads(path.read_text(encoding="utf-8"))
    except toml.TomlDecodeError:
        return {}

    out: dict[str, str] = {}
    for raw in data.get("hosts", []):
        hostname = raw.get("hostname")
        provider = raw.get("provider")
        if not isinstance(hostname, str) or not hostname:
            continue
        if not isinstance(provider, str) or provider not in _SHIPPED_PROVIDERS:
            continue
        out[hostname] = provider
    return out
```

- [ ] **Step 11.4: Update `resolve_host` to consult user config**

Replace the entire contents of `packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py` with:

```python
"""Host-provider abstraction — spec §5.

GitHub + GitLab ship in the first cut. Bitbucket and Gitea are deferred.
Self-hosted instances declare themselves in ~/.haywire/config.toml — see §5.4.
"""

from haywire.core.marketstall.host_providers.base import HostProvider, ParsedRef
from haywire.core.marketstall.host_providers.github import GitHubProvider
from haywire.core.marketstall.host_providers.gitlab import GitLabProvider
from haywire.core.marketstall.host_providers import config as _host_config

__all__ = ["HostProvider", "ParsedRef", "HOST_PROVIDERS", "resolve_host"]

HOST_PROVIDERS: list[HostProvider] = [
    GitHubProvider(),
    GitLabProvider(),
    # BitbucketProvider() — deferred; see spec §5.2
    # GiteaProvider()     — deferred; see spec §5.2
]

_PROVIDER_BY_NAME: dict[str, HostProvider] = {p.name: p for p in HOST_PROVIDERS}


def resolve_host(hostname: str) -> HostProvider | None:
    """Resolve a hostname to its HostProvider.

    Consults the user's self-hosted config (~/.haywire/config.toml) first; if a
    matching [[hosts]] entry names a shipped provider, that provider handles
    the hostname. Otherwise falls back to built-in `provider.matches(hostname)`.
    """
    user_hosts = _host_config.load_self_hosted_hosts()
    if hostname in user_hosts:
        return _PROVIDER_BY_NAME.get(user_hosts[hostname])

    for provider in HOST_PROVIDERS:
        if provider.matches(hostname):
            return provider
    return None
```

- [ ] **Step 11.5: Run the test to confirm it passes**

Run: `uv run pytest tests/marketstall/test_host_provider_config.py -v`
Expected: 4 passed.

- [ ] **Step 11.6: Run all host-provider tests to confirm nothing broke**

Run: `uv run pytest tests/marketstall/test_host_provider_github.py tests/marketstall/test_host_provider_gitlab.py tests/marketstall/test_host_provider_config.py -v`
Expected: 24 passed.

- [ ] **Step 11.7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/host_providers/config.py \
        packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py \
        tests/marketstall/test_host_provider_config.py
git commit -m "feat(marketstall): add self-hosted host config and integrate into resolve_host"
```

---

## Task 12: URL resolution — Add Source classification

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/url_resolution.py`
- Create: `tests/marketstall/test_url_resolution.py`

- [ ] **Step 12.1: Write the failing tests**

Write to `tests/marketstall/test_url_resolution.py`:

```python
"""URL resolution for Add Source — spec §4.2, §4.3."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_classify_blob_url_github() -> None:
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    result = classify_input("https://github.com/alice/cool-libs/blob/main/marketstall.toml")
    assert result.form is InputForm.BLOB_URL
    assert result.fetch_url == (
        "https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml"
    )
    assert result.persist_url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"


@pytest.mark.unit
def test_classify_raw_url_github() -> None:
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    result = classify_input(
        "https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml"
    )
    assert result.form is InputForm.RAW_URL
    assert result.fetch_url == (
        "https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml"
    )
    # Persisted URL is the canonical blob form for editability later.
    assert result.persist_url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"


@pytest.mark.unit
def test_classify_plain_toml_url() -> None:
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    url = "https://going-haywire.github.io/haywire/marketplace.toml"
    result = classify_input(url)
    assert result.form is InputForm.PLAIN_TOML_URL
    assert result.fetch_url == url
    assert result.persist_url == url


@pytest.mark.unit
def test_classify_file_url() -> None:
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    url = "file:///Users/me/.haywire/db/haybale-marketplace/stalls/x.toml"
    result = classify_input(url)
    assert result.form is InputForm.PLAIN_TOML_URL
    assert result.fetch_url == url
    assert result.persist_url == url


@pytest.mark.unit
def test_classify_bare_repo_url_rejected_github() -> None:
    """Per §4.2: bare repo URLs are rejected at input time. No network probing."""
    from haywire.core.marketstall.url_resolution import (
        BareRepoUrlRejectedError,
        classify_input,
    )

    with pytest.raises(BareRepoUrlRejectedError) as exc_info:
        classify_input("https://github.com/alice/cool-libs")
    assert "marketstall.toml" in str(exc_info.value)
    assert "README" in str(exc_info.value)


@pytest.mark.unit
def test_classify_bare_repo_url_rejected_with_trailing_slash() -> None:
    from haywire.core.marketstall.url_resolution import (
        BareRepoUrlRejectedError,
        classify_input,
    )

    with pytest.raises(BareRepoUrlRejectedError):
        classify_input("https://github.com/alice/cool-libs/")


@pytest.mark.unit
def test_classify_bare_repo_url_rejected_gitlab() -> None:
    from haywire.core.marketstall.url_resolution import (
        BareRepoUrlRejectedError,
        classify_input,
    )

    with pytest.raises(BareRepoUrlRejectedError):
        classify_input("https://gitlab.com/alice/cool-libs")


@pytest.mark.unit
def test_classify_strips_trailing_dot_git() -> None:
    from haywire.core.marketstall.url_resolution import (
        BareRepoUrlRejectedError,
        classify_input,
    )

    with pytest.raises(BareRepoUrlRejectedError):
        classify_input("https://github.com/alice/cool-libs.git")


@pytest.mark.unit
def test_classify_pasted_toml_block() -> None:
    """Form 4: pasted TOML, not a URL."""
    from haywire.core.marketstall.url_resolution import classify_input, InputForm

    block = '[[haybales]]\nname = "haybale-foo"\nmin_version = "0.1.0"\n'
    result = classify_input(block)
    assert result.form is InputForm.PASTED_BLOCK
    assert result.toml_body == block
```

- [ ] **Step 12.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_url_resolution.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 12.3: Implement `url_resolution.py`**

Write to `packages/haywire-core/src/haywire/core/marketstall/url_resolution.py`:

```python
"""Add Source input classification — spec §4.2, §4.3.

Four input forms (form 3 / bare repo URL dropped per inquisition Q4):
  1. Blob URL — host provider rewrites to raw for fetch; blob URL persisted.
  2. Raw URL — fetched as-is; canonical blob URL reconstructed for persistence.
  3. Plain TOML URL — fetched as-is; persisted as-is.
  4. Pasted TOML block — written to ~/.haywire/db/.../stalls/<name>.toml,
     then referenced as file:// (handled by the caller after classify_input).

Bare repo URLs (e.g. `https://github.com/alice/cool-libs`) are rejected with a
clear error pointing at the README marker pattern (§6.6).
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from haywire.core.marketstall.host_providers import HOST_PROVIDERS, resolve_host


class InputForm(enum.Enum):
    """The four accepted input forms — spec §4.2."""

    BLOB_URL = "blob_url"
    RAW_URL = "raw_url"
    PLAIN_TOML_URL = "plain_toml_url"
    PASTED_BLOCK = "pasted_block"


class BareRepoUrlRejectedError(ValueError):
    """Raised when the user pastes a bare repo URL — spec §4.2."""


@dataclass(frozen=True)
class ClassifiedInput:
    """Output of classify_input.

    For URL forms (BLOB_URL, RAW_URL, PLAIN_TOML_URL):
      - fetch_url: the URL the runtime will HTTP-fetch
      - persist_url: the URL written into the marketplace file as the subscription key
      - toml_body: None
    For PASTED_BLOCK:
      - fetch_url: None
      - persist_url: None (caller derives file:// after writing the block to disk)
      - toml_body: the raw TOML the user pasted
    """

    form: InputForm
    fetch_url: str | None = None
    persist_url: str | None = None
    toml_body: str | None = None


_URL_LIKE = re.compile(r"^(https?|file)://", re.IGNORECASE)


def classify_input(user_input: str) -> ClassifiedInput:
    """Classify Add Source input. Raises BareRepoUrlRejectedError on form-3 URLs."""
    stripped = user_input.strip()

    if not _URL_LIKE.match(stripped):
        # Form 4: pasted TOML block.
        return ClassifiedInput(form=InputForm.PASTED_BLOCK, toml_body=user_input)

    # Strip trailing artifacts that browsers/users commonly add.
    normalized = stripped.rstrip("/")
    for suffix in (".git",):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]

    if normalized.startswith("file://"):
        return ClassifiedInput(
            form=InputForm.PLAIN_TOML_URL,
            fetch_url=normalized,
            persist_url=normalized,
        )

    parts = urlsplit(normalized)
    hostname = (parts.hostname or "").lower()
    provider = resolve_host(hostname)

    if provider is not None:
        blob = provider.parse_blob_url(normalized)
        if blob is not None:
            return ClassifiedInput(
                form=InputForm.BLOB_URL,
                fetch_url=provider.raw_url(blob.owner, blob.repo, blob.ref, blob.path),
                persist_url=provider.blob_url(blob.owner, blob.repo, blob.ref, blob.path),
            )

        raw = provider.parse_raw_url(normalized)
        if raw is not None:
            return ClassifiedInput(
                form=InputForm.RAW_URL,
                fetch_url=provider.raw_url(raw.owner, raw.repo, raw.ref, raw.path),
                persist_url=provider.blob_url(raw.owner, raw.repo, raw.ref, raw.path),
            )

        # Provider matched the hostname but URL didn't match blob or raw shape.
        # If the path looks like a bare /owner/repo, reject as form 3.
        path_parts = [p for p in parts.path.split("/") if p]
        if len(path_parts) == 2:
            raise BareRepoUrlRejectedError(
                "Paste the URL to the marketstall.toml file, not the repo. "
                f"Look for a `marketstall:share-url` block in the {hostname} repo's README."
            )

    # No provider matched by hostname — try all providers for blob/raw URL shapes.
    # This handles secondary hostnames like raw.githubusercontent.com that a
    # provider parses but doesn't claim via matches().
    for p in HOST_PROVIDERS:
        blob = p.parse_blob_url(normalized)
        if blob is not None:
            return ClassifiedInput(
                form=InputForm.BLOB_URL,
                fetch_url=p.raw_url(blob.owner, blob.repo, blob.ref, blob.path),
                persist_url=p.blob_url(blob.owner, blob.repo, blob.ref, blob.path),
            )
        raw = p.parse_raw_url(normalized)
        if raw is not None:
            return ClassifiedInput(
                form=InputForm.RAW_URL,
                fetch_url=p.raw_url(raw.owner, raw.repo, raw.ref, raw.path),
                persist_url=p.blob_url(raw.owner, raw.repo, raw.ref, raw.path),
            )

    # No provider parsed it. If it has a bare /owner/repo path on a known git host, reject.
    path_parts = [p for p in parts.path.split("/") if p]
    if hostname in {"github.com", "gitlab.com", "bitbucket.org"} and len(path_parts) == 2:
        raise BareRepoUrlRejectedError(
            "Paste the URL to the marketstall.toml file, not the repo. "
            f"Look for a `marketstall:share-url` block in the {hostname} repo's README."
        )

    # Plain TOML URL — anything else with a path.
    return ClassifiedInput(
        form=InputForm.PLAIN_TOML_URL,
        fetch_url=normalized,
        persist_url=normalized,
    )
```

- [ ] **Step 12.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_url_resolution.py -v`
Expected: 9 passed.

- [ ] **Step 12.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/url_resolution.py \
        tests/marketstall/test_url_resolution.py
git commit -m "feat(marketstall): add URL resolution with four input forms, reject bare repo URLs"
```


---

## Task 13: Entry parsers (haybale, subscription, heap)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/parsing.py`
- Create: `tests/marketstall/test_parsing.py`

- [ ] **Step 13.1: Write the failing tests for entry parsers**

Write to `tests/marketstall/test_parsing.py`:

```python
"""Entry parsers — single-entry dict-to-dataclass conversions."""

from __future__ import annotations

import pytest

from haywire.core.marketstall.errors import MalformedMarketplaceError


@pytest.mark.unit
def test_parse_haybale_entry_minimal() -> None:
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    raw = {"name": "haybale-foo", "min_version": "0.1.0"}
    h = _parse_haybale_entry(raw)
    assert h.name == "haybale-foo"
    assert h.min_version == "0.1.0"
    assert h.os == []


@pytest.mark.unit
def test_parse_haybale_entry_full() -> None:
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    raw = {
        "name": "haybale-vision",
        "min_version": "0.2.0",
        "label": "Vision",
        "description": "X",
        "author": "Alice",
        "source": "git",
        "install_spec": "haybale-vision @ git+...",
        "tags": ["vision"],
        "os": ["macos", "linux"],
        "dependencies": ["haybale-core"],
        "source_url": "https://x.example",
        "docs_url": "https://x.example/docs",
        "via": "https://feed.example",
        "last_seen": "2026-05-20T00:00:00Z",
        "stale": True,
    }
    h = _parse_haybale_entry(raw)
    assert h.os == ["macos", "linux"]
    assert h.stale is True
    assert h.via == "https://feed.example"


@pytest.mark.unit
def test_parse_haybale_entry_missing_name_raises() -> None:
    from haywire.core.marketstall.parsing import _parse_haybale_entry

    with pytest.raises(MalformedMarketplaceError, match="name"):
        _parse_haybale_entry({"min_version": "0.1.0"})


@pytest.mark.unit
def test_parse_subscription_minimal() -> None:
    from haywire.core.marketstall.parsing import _parse_subscription

    raw = {"url": "https://x.example/m.toml"}
    sub = _parse_subscription(raw, "markets")
    assert sub.url == "https://x.example/m.toml"
    assert sub.ignores == []
    assert sub.doubles == []
    assert sub.blocked == []


@pytest.mark.unit
def test_parse_subscription_with_blocked() -> None:
    from haywire.core.marketstall.parsing import _parse_subscription

    raw = {
        "url": "https://x.example/m.toml",
        "ignores": ["haybale-skip"],
        "doubles": [],
        "blocked": ["haybale-untrusted"],
    }
    sub = _parse_subscription(raw, "stalls")
    assert sub.ignores == ["haybale-skip"]
    assert sub.blocked == ["haybale-untrusted"]


@pytest.mark.unit
def test_parse_subscription_missing_url_raises() -> None:
    from haywire.core.marketstall.parsing import _parse_subscription

    with pytest.raises(MalformedMarketplaceError, match="url"):
        _parse_subscription({}, "markets")


@pytest.mark.unit
def test_parse_heap_entry_minimal() -> None:
    from haywire.core.marketstall.parsing import _parse_heap_entry

    raw = {"name": "haybale-my-project", "path": "/abs/path"}
    out = _parse_heap_entry(raw)
    assert out["name"] == "haybale-my-project"
    assert out["path"] == "/abs/path"


@pytest.mark.unit
def test_parse_heap_entry_missing_name_raises() -> None:
    from haywire.core.marketstall.parsing import _parse_heap_entry

    with pytest.raises(MalformedMarketplaceError, match="name"):
        _parse_heap_entry({"path": "/p"})


@pytest.mark.unit
def test_parse_heap_entry_missing_path_raises() -> None:
    from haywire.core.marketstall.parsing import _parse_heap_entry

    with pytest.raises(MalformedMarketplaceError, match="path"):
        _parse_heap_entry({"name": "x"})
```

- [ ] **Step 13.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_parsing.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 13.3: Implement entry parsers**

Write to `packages/haywire-core/src/haywire/core/marketstall/parsing.py`:

```python
"""TOML parsers and serializers for marketplace and marketstall files.

The new section vocabulary per spec §1:
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

from haywire.core.marketstall.errors import MalformedMarketplaceError
from haywire.core.marketstall.types import Haybale, Subscription


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
```

- [ ] **Step 13.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_parsing.py -v`
Expected: 9 passed.

- [ ] **Step 13.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/parsing.py \
        tests/marketstall/test_parsing.py
git commit -m "feat(marketstall): add entry parsers for haybales, subscriptions, heaps"
```

---

## Task 14: File-level parsers (`parse_global_marketplace`, `parse_project_marketplace`)

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/parsing.py`
- Modify: `tests/marketstall/test_parsing.py`

- [ ] **Step 14.1: Write the failing tests for file parsers**

Append to `tests/marketstall/test_parsing.py`:

```python
from pathlib import Path


@pytest.mark.unit
def test_parse_global_marketplace_empty_file_returns_empty(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text("")
    mf = parse_global_marketplace(f)
    assert mf.markets == []
    assert mf.stalls == []
    assert mf.haybales == []


@pytest.mark.unit
def test_parse_global_marketplace_missing_file_returns_empty(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "does-not-exist.toml"
    mf = parse_global_marketplace(f)
    assert mf.markets == []


@pytest.mark.unit
def test_parse_global_marketplace_all_three_sections(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text(
        '[[markets]]\n'
        'url = "https://aggregator.example/marketplace.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
        '\n'
        '[[stalls]]\n'
        'url = "https://alice.example/marketstall.toml"\n'
        'ignores = ["haybale-skip"]\n'
        'doubles = []\n'
        'blocked = ["haybale-untrusted"]\n'
        '\n'
        '[[haybales]]\n'
        'name = "haybale-inline"\n'
        'min_version = "0.1.0"\n'
    )
    mf = parse_global_marketplace(f)
    assert len(mf.markets) == 1
    assert mf.markets[0].url == "https://aggregator.example/marketplace.toml"
    assert len(mf.stalls) == 1
    assert mf.stalls[0].blocked == ["haybale-untrusted"]
    assert len(mf.haybales) == 1
    assert mf.haybales[0].name == "haybale-inline"


@pytest.mark.unit
def test_parse_global_marketplace_malformed_toml_raises(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text("this is = not valid TOML [[")
    with pytest.raises(MalformedMarketplaceError):
        parse_global_marketplace(f)


@pytest.mark.unit
def test_parse_project_marketplace_empty_returns_empty(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_project_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text("")
    pm = parse_project_marketplace(f)
    assert pm.heaps == []
    assert pm.caches == []


@pytest.mark.unit
def test_parse_project_marketplace_both_sections(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import parse_project_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text(
        '[[heaps]]\n'
        'name = "haybale-my-project"\n'
        'path = "/abs/path/to/proj"\n'
        'label = "My Project"\n'
        '\n'
        '[[caches]]\n'
        'name = "haybale-foo"\n'
        'min_version = "0.1.0"\n'
        'via = "https://feed.example/marketstall.toml"\n'
        'last_seen = "2026-05-20T00:00:00Z"\n'
        'stale = false\n'
    )
    pm = parse_project_marketplace(f)
    assert len(pm.heaps) == 1
    assert pm.heaps[0]["name"] == "haybale-my-project"
    assert len(pm.caches) == 1
    assert pm.caches[0].via == "https://feed.example/marketstall.toml"
    assert pm.caches[0].stale is False


@pytest.mark.unit
def test_parse_project_marketplace_drops_global_only_sections(tmp_path: Path) -> None:
    """[[markets]] and [[stalls]] don't belong in a project file; silently dropped."""
    from haywire.core.marketstall.parsing import parse_project_marketplace

    f = tmp_path / "marketplace.toml"
    f.write_text(
        '[[markets]]\n'
        'url = "https://x.example/m.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
    )
    pm = parse_project_marketplace(f)
    # No markets attribute exists on ProjectMarketplaceFile; the section is silently skipped.
    assert pm.heaps == []
    assert pm.caches == []
```

- [ ] **Step 14.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_parsing.py -v -k "parse_global_marketplace or parse_project_marketplace"`
Expected: FAIL on the new tests — `ImportError`.

- [ ] **Step 14.3: Implement file parsers**

Append to `packages/haywire-core/src/haywire/core/marketstall/parsing.py`:

```python
from pathlib import Path

import toml

from haywire.core.marketstall.types import MarketplaceFile, ProjectMarketplaceFile


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
        raise MalformedMarketplaceError(
            f"malformed project marketplace.toml at {path}: {exc}"
        ) from exc

    heaps = [_parse_heap_entry(raw) for raw in data.get("heaps", [])]
    caches = [_parse_haybale_entry(raw) for raw in data.get("caches", [])]
    return ProjectMarketplaceFile(heaps=heaps, caches=caches)
```

- [ ] **Step 14.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_parsing.py -v`
Expected: 16 passed (9 from Task 13 + 7 new).

- [ ] **Step 14.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/parsing.py \
        tests/marketstall/test_parsing.py
git commit -m "feat(marketstall): add file-level parsers for global and project marketplaces"
```

---

## Task 15: Remote-body parsers (marketstall + remote marketplace)

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/parsing.py`
- Modify: `tests/marketstall/test_parsing.py`

- [ ] **Step 15.1: Write the failing tests**

Append to `tests/marketstall/test_parsing.py`:

```python
@pytest.mark.unit
def test_parse_marketstall_body_haybales_only() -> None:
    from haywire.core.marketstall.parsing import parse_marketstall_body

    body = (
        '[[haybales]]\n'
        'name = "haybale-foo"\n'
        'min_version = "0.1.0"\n'
    )
    haybales = parse_marketstall_body(body)
    assert len(haybales) == 1
    assert haybales[0].name == "haybale-foo"


@pytest.mark.unit
def test_parse_marketstall_body_silently_drops_extra_sections() -> None:
    """A marketstall must not contain [[markets]] etc.; if it does, drop them silently per §2."""
    from haywire.core.marketstall.parsing import parse_marketstall_body

    body = (
        '[[markets]]\n'
        'url = "https://x.example/m.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
        '\n'
        '[[haybales]]\n'
        'name = "haybale-foo"\n'
        'min_version = "0.1.0"\n'
    )
    haybales = parse_marketstall_body(body)
    assert len(haybales) == 1
    assert haybales[0].name == "haybale-foo"


@pytest.mark.unit
def test_parse_marketstall_body_malformed_returns_empty() -> None:
    from haywire.core.marketstall.parsing import parse_marketstall_body

    assert parse_marketstall_body("not valid toml [[") == []


@pytest.mark.unit
def test_parse_remote_marketplace_body_collects_stalls_and_haybales() -> None:
    from haywire.core.marketstall.parsing import parse_remote_marketplace_body

    body = (
        '[[stalls]]\n'
        'url = "https://going-haywire.github.io/haywire/stalls/haybale-core.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
        '\n'
        '[[haybales]]\n'
        'name = "haybale-inline"\n'
        'min_version = "0.2.0"\n'
    )
    contents = parse_remote_marketplace_body(body)
    assert len(contents.stall_urls) == 1
    assert (
        contents.stall_urls[0]
        == "https://going-haywire.github.io/haywire/stalls/haybale-core.toml"
    )
    assert len(contents.haybales) == 1
    assert contents.haybales[0].name == "haybale-inline"


@pytest.mark.unit
def test_parse_remote_marketplace_body_ignores_nested_markets() -> None:
    """One-level-deep resolution per §8.1: [[markets]] in a remote marketplace are dropped."""
    from haywire.core.marketstall.parsing import parse_remote_marketplace_body

    body = (
        '[[markets]]\n'
        'url = "https://other-aggregator.example/marketplace.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
    )
    contents = parse_remote_marketplace_body(body)
    assert contents.stall_urls == []
    assert contents.haybales == []


@pytest.mark.unit
def test_parse_remote_marketplace_body_malformed_returns_empty() -> None:
    from haywire.core.marketstall.parsing import parse_remote_marketplace_body

    contents = parse_remote_marketplace_body("not valid toml [[")
    assert contents.stall_urls == []
    assert contents.haybales == []
```

- [ ] **Step 15.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_parsing.py -v -k "marketstall_body or remote_marketplace_body"`
Expected: FAIL — `ImportError`.

- [ ] **Step 15.3: Implement remote-body parsers**

Append to `packages/haywire-core/src/haywire/core/marketstall/parsing.py`:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RemoteMarketplaceContents:
    """What `parse_remote_marketplace_body` extracts from a [[markets]] response.

    Per spec §8.1, resolution is one level deep: any [[markets]] entries
    inside the fetched marketplace body are ignored. Only [[stalls]] URLs and
    inline [[haybales]] are consumed.
    """

    stall_urls: list[str] = field(default_factory=list)
    haybales: list[Haybale] = field(default_factory=list)


def parse_marketstall_body(body: str) -> list[Haybale]:
    """Parse a fetched marketstall TOML body into a list of Haybale.

    A marketstall is [[haybales]]-only per spec §2. Other sections are silently
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
```

- [ ] **Step 15.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_parsing.py -v`
Expected: 22 passed (16 + 6 new).

- [ ] **Step 15.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/parsing.py \
        tests/marketstall/test_parsing.py
git commit -m "feat(marketstall): add remote-body parsers (one-level-deep) for stalls and marketplaces"
```

---

## Task 16: Serializers

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/parsing.py`
- Modify: `tests/marketstall/test_parsing.py`

- [ ] **Step 16.1: Write the failing tests**

Append to `tests/marketstall/test_parsing.py`:

```python
@pytest.mark.unit
def test_serialize_global_marketplace_empty_returns_empty_string() -> None:
    from haywire.core.marketstall.parsing import serialize_global_marketplace
    from haywire.core.marketstall.types import MarketplaceFile

    assert serialize_global_marketplace(MarketplaceFile()) == ""


@pytest.mark.unit
def test_serialize_global_marketplace_emits_blocked_field() -> None:
    from haywire.core.marketstall.parsing import serialize_global_marketplace
    from haywire.core.marketstall.types import MarketplaceFile, Subscription

    mf = MarketplaceFile(
        stalls=[
            Subscription(
                url="https://alice.example/marketstall.toml",
                ignores=["haybale-skip"],
                blocked=["haybale-untrusted"],
            )
        ]
    )
    out = serialize_global_marketplace(mf)
    assert "[[stalls]]" in out
    assert "alice.example/marketstall.toml" in out
    assert "haybale-skip" in out
    assert "haybale-untrusted" in out
    assert "blocked" in out


@pytest.mark.unit
def test_serialize_global_marketplace_roundtrip(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import (
        parse_global_marketplace,
        serialize_global_marketplace,
    )
    from haywire.core.marketstall.types import Haybale, MarketplaceFile, Subscription

    original = MarketplaceFile(
        markets=[Subscription(url="https://agg.example/marketplace.toml")],
        stalls=[
            Subscription(
                url="https://alice.example/marketstall.toml",
                ignores=["haybale-skip"],
                blocked=["haybale-untrusted"],
            )
        ],
        haybales=[Haybale(name="haybale-inline", min_version="0.1.0")],
    )

    f = tmp_path / "marketplace.toml"
    f.write_text(serialize_global_marketplace(original))
    reparsed = parse_global_marketplace(f)
    assert reparsed.markets[0].url == original.markets[0].url
    assert reparsed.stalls[0].blocked == original.stalls[0].blocked
    assert reparsed.haybales[0].name == "haybale-inline"


@pytest.mark.unit
def test_serialize_project_marketplace_roundtrip(tmp_path: Path) -> None:
    from haywire.core.marketstall.parsing import (
        parse_project_marketplace,
        serialize_project_marketplace,
    )
    from haywire.core.marketstall.types import Haybale, ProjectMarketplaceFile

    original = ProjectMarketplaceFile(
        heaps=[{"name": "haybale-x", "path": "/abs/path/x"}],
        caches=[
            Haybale(
                name="haybale-foo",
                min_version="0.1.0",
                via="https://feed.example/marketstall.toml",
                last_seen="2026-05-20T00:00:00Z",
                stale=False,
            )
        ],
    )

    f = tmp_path / "marketplace.toml"
    f.write_text(serialize_project_marketplace(original))
    reparsed = parse_project_marketplace(f)
    assert reparsed.heaps[0]["name"] == "haybale-x"
    assert reparsed.caches[0].via == "https://feed.example/marketstall.toml"
```

- [ ] **Step 16.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_parsing.py -v -k serialize`
Expected: FAIL — `ImportError`.

- [ ] **Step 16.3: Implement serializers**

Append to `packages/haywire-core/src/haywire/core/marketstall/parsing.py`:

```python
def _subscription_to_dict(sub: Subscription) -> dict:
    """Serialize a Subscription back to its TOML dict shape.

    Always emits all four arrays (even when empty) so users editing the file
    see the schema — spec §3.1 example shows them on every subscription.
    """
    return {
        "url": sub.url,
        "ignores": list(sub.ignores),
        "doubles": list(sub.doubles),
        "blocked": list(sub.blocked),
    }


def serialize_global_marketplace(mf: MarketplaceFile) -> str:
    """Serialize a MarketplaceFile to a TOML string.

    Section order matches spec §3.1: [[markets]], [[stalls]], [[haybales]].
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
```

- [ ] **Step 16.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_parsing.py -v`
Expected: 26 passed (22 + 4 new).

- [ ] **Step 16.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/parsing.py \
        tests/marketstall/test_parsing.py
git commit -m "feat(marketstall): add serializers for global and project marketplace files"
```


---

## Task 17: HTTP cache with tri-state `FetchResult`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/cache.py`
- Create: `tests/marketstall/test_cache.py`

- [ ] **Step 17.1: Write the failing tests**

Write to `tests/marketstall/test_cache.py`:

```python
"""HTTP cache — spec §7.3 (tri-state, no TTL, GC of orphans)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from haywire.core.marketstall.errors import RemoteFetchError
from haywire.core.marketstall.types import RefreshOutcome


@pytest.mark.unit
def test_cache_write_and_read_roundtrip(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_read, cache_write

    cache_dir = tmp_path / "cache"
    cache_write("https://x.example/m.toml", "body-text", cache_dir=cache_dir)
    body, age = cache_read("https://x.example/m.toml", cache_dir=cache_dir)
    assert body == "body-text"
    assert age is not None
    assert age >= 0


@pytest.mark.unit
def test_cache_read_missing_returns_none(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_read

    body, age = cache_read("https://x.example/missing.toml", cache_dir=tmp_path)
    assert body is None
    assert age is None


@pytest.mark.unit
def test_url_hash_is_stable() -> None:
    from haywire.core.marketstall.cache import _url_hash

    h1 = _url_hash("https://x.example/m.toml")
    h2 = _url_hash("https://x.example/m.toml")
    assert h1 == h2
    assert h1 != _url_hash("https://y.example/m.toml")


@pytest.mark.unit
def test_fetch_with_cache_fallback_fresh(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import fetch_with_cache_fallback

    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"fresh-body"
        result = fetch_with_cache_fallback(
            "https://x.example/m.toml", cache_dir=tmp_path / "cache"
        )
    assert result.body == "fresh-body"
    assert result.outcome is RefreshOutcome.FRESH
    assert result.cache_age is None


@pytest.mark.unit
def test_fetch_with_cache_fallback_uses_cache_on_failure(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_write, fetch_with_cache_fallback

    cache_dir = tmp_path / "cache"
    cache_write("https://x.example/m.toml", "cached-body", cache_dir=cache_dir)

    with patch("haywire.core.marketstall.cache._urlopen", side_effect=OSError("network down")):
        result = fetch_with_cache_fallback(
            "https://x.example/m.toml", cache_dir=cache_dir
        )
    assert result.body == "cached-body"
    assert result.outcome is RefreshOutcome.CACHE_FALLBACK
    assert result.cache_age is not None


@pytest.mark.unit
def test_fetch_with_cache_fallback_raises_when_no_cache(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import fetch_with_cache_fallback

    with patch("haywire.core.marketstall.cache._urlopen", side_effect=OSError("network down")):
        with pytest.raises(RemoteFetchError):
            fetch_with_cache_fallback(
                "https://x.example/m.toml", cache_dir=tmp_path / "cache"
            )


@pytest.mark.unit
def test_gc_orphans_keeps_active_urls(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_write, gc_orphans

    cache_dir = tmp_path / "cache"
    cache_write("https://active.example/m.toml", "a", cache_dir=cache_dir)
    cache_write("https://orphan.example/m.toml", "o", cache_dir=cache_dir)

    deleted = gc_orphans({"https://active.example/m.toml"}, cache_dir=cache_dir)

    files = sorted(p.name for p in cache_dir.iterdir())
    assert len(files) == 1  # only the active one remains
    assert deleted == 1


@pytest.mark.unit
def test_gc_orphans_no_op_when_all_active(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_write, gc_orphans

    cache_dir = tmp_path / "cache"
    cache_write("https://x.example/m.toml", "body", cache_dir=cache_dir)
    deleted = gc_orphans({"https://x.example/m.toml"}, cache_dir=cache_dir)
    assert deleted == 0


@pytest.mark.unit
def test_gc_orphans_handles_missing_cache_dir(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import gc_orphans

    deleted = gc_orphans({"https://x.example/m.toml"}, cache_dir=tmp_path / "no-cache")
    assert deleted == 0
```

- [ ] **Step 17.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 17.3: Implement `cache.py`**

Write to `packages/haywire-core/src/haywire/core/marketstall/cache.py`:

```python
"""HTTP cache with tri-state outcomes — spec §7.3.

Cache lives at ~/.haywire/cache/<url-hash>.toml. No TTL: entries are valid
until overwritten by a successful fetch. GC removes orphans (cache files
whose URL no longer corresponds to an active subscription) at end of refresh.

`cache_dir` parameter on every function: defaults to ~/.haywire/cache; tests
override to use tmp_path. Keeps the production code testable without
monkey-patching Path.home().
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path

from haywire.core.marketstall.errors import RemoteFetchError
from haywire.core.marketstall.types import FetchResult, RefreshOutcome

_URL_HASH_LEN = 16


def _default_cache_dir() -> Path:
    """Production cache directory: ~/.haywire/cache."""
    return Path.home() / ".haywire" / "cache"


def _url_hash(url: str) -> str:
    """Short hex hash of a URL, used as the cache filename stem."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:_URL_HASH_LEN]


def _cache_path(url: str, *, cache_dir: Path | None = None) -> Path:
    cache_dir = cache_dir if cache_dir is not None else _default_cache_dir()
    return cache_dir / f"{_url_hash(url)}.toml"


def cache_write(url: str, body: str, *, cache_dir: Path | None = None) -> None:
    """Cache a successful HTTP response; overwrites any previous entry."""
    path = _cache_path(url, cache_dir=cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def cache_read(
    url: str, *, cache_dir: Path | None = None
) -> tuple[str | None, float | None]:
    """Return (body, age_in_seconds) for a URL, or (None, None) if no cache."""
    path = _cache_path(url, cache_dir=cache_dir)
    if not path.is_file():
        return None, None
    body = path.read_text(encoding="utf-8")
    age = time.time() - path.stat().st_mtime
    return body, age


def _urlopen(url: str, *, timeout: float):
    """Wrapped urllib.request.urlopen — separate function for ease of patching in tests."""
    return urllib.request.urlopen(url, timeout=timeout)


def fetch_with_cache_fallback(
    url: str,
    *,
    timeout: float = 5.0,
    cache_dir: Path | None = None,
) -> FetchResult:
    """Fetch a URL. On success: cache + return FRESH. On failure: try cache → CACHE_FALLBACK.

    Raises RemoteFetchError only when the URL fails AND no cache exists.
    Never returns UNAVAILABLE — the orchestrator converts the exception into
    that outcome at the call site.
    """
    try:
        with _urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        cache_write(url, body, cache_dir=cache_dir)
        return FetchResult(body=body, outcome=RefreshOutcome.FRESH, cache_age=None)
    except (OSError, urllib.error.URLError):
        cached, age = cache_read(url, cache_dir=cache_dir)
        if cached is not None:
            return FetchResult(
                body=cached, outcome=RefreshOutcome.CACHE_FALLBACK, cache_age=age
            )
        raise RemoteFetchError(f"failed to fetch {url} and no cache available") from None


def gc_orphans(active_urls: set[str], *, cache_dir: Path | None = None) -> int:
    """Delete cache files whose URL is not in `active_urls`. Returns count deleted.

    Per spec §7.3: at end of refresh, drop orphaned <url-hash>.toml files.
    Resolves URLs to their hashes; deletes any cache file whose stem doesn't
    match any active subscription. Missing cache dir returns 0 (nothing to GC).
    """
    cache_dir = cache_dir if cache_dir is not None else _default_cache_dir()
    if not cache_dir.is_dir():
        return 0

    active_hashes = {_url_hash(url) for url in active_urls}
    deleted = 0
    for path in cache_dir.iterdir():
        if not path.is_file() or path.suffix != ".toml":
            continue
        if path.stem not in active_hashes:
            path.unlink()
            deleted += 1
    return deleted
```

- [ ] **Step 17.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_cache.py -v`
Expected: 9 passed.

- [ ] **Step 17.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/cache.py \
        tests/marketstall/test_cache.py
git commit -m "feat(marketstall): add HTTP cache with tri-state FetchResult and GC of orphans"
```

---

## Task 18: Conflict-resolution filters (ignores, blocked, heaps shadow, FCFS)

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/refresh.py`
- Create: `tests/marketstall/test_refresh.py`

- [ ] **Step 18.1: Write the failing tests for filter functions**

Write to `tests/marketstall/test_refresh.py`:

```python
"""Refresh pipeline — conflict resolution filters and orchestrator."""

from __future__ import annotations

import pytest

from haywire.core.marketstall.types import Haybale


def _h(name: str, **kw) -> Haybale:
    """Test helper: build a Haybale with sensible defaults."""
    return Haybale(name=name, min_version=kw.pop("min_version", "0.1.0"), **kw)


@pytest.mark.unit
def test_apply_ignores_filters_by_name() -> None:
    from haywire.core.marketstall.refresh import apply_ignores

    pkgs = [_h("haybale-a"), _h("haybale-b"), _h("haybale-c")]
    out = apply_ignores(pkgs, ["haybale-b"])
    assert [p.name for p in out] == ["haybale-a", "haybale-c"]


@pytest.mark.unit
def test_apply_ignores_empty_list_is_noop() -> None:
    from haywire.core.marketstall.refresh import apply_ignores

    pkgs = [_h("haybale-a")]
    assert apply_ignores(pkgs, []) == pkgs


@pytest.mark.unit
def test_apply_blocked_filters_by_name() -> None:
    from haywire.core.marketstall.refresh import apply_blocked

    pkgs = [_h("haybale-a"), _h("haybale-untrusted"), _h("haybale-c")]
    out = apply_blocked(pkgs, ["haybale-untrusted"])
    assert [p.name for p in out] == ["haybale-a", "haybale-c"]


@pytest.mark.unit
def test_apply_blocked_empty_list_is_noop() -> None:
    from haywire.core.marketstall.refresh import apply_blocked

    pkgs = [_h("haybale-a")]
    assert apply_blocked(pkgs, []) == pkgs


@pytest.mark.unit
def test_apply_heaps_shadow_drops_collisions() -> None:
    """Spec §8.2: heaps always win — any candidate whose name matches a heap is dropped."""
    from haywire.core.marketstall.refresh import apply_heaps_shadow

    heaps = [{"name": "haybale-foo", "path": "/p"}, {"name": "haybale-bar", "path": "/p"}]
    candidates = [_h("haybale-foo"), _h("haybale-baz")]
    out = apply_heaps_shadow(heaps, candidates)
    assert [p.name for p in out] == ["haybale-baz"]


@pytest.mark.unit
def test_apply_heaps_shadow_empty_heaps_noop() -> None:
    from haywire.core.marketstall.refresh import apply_heaps_shadow

    candidates = [_h("haybale-foo")]
    assert apply_heaps_shadow([], candidates) == candidates


@pytest.mark.unit
def test_apply_first_come_first_served_dedups() -> None:
    from haywire.core.marketstall.refresh import apply_first_come_first_served

    candidates = [_h("haybale-foo", label="first"), _h("haybale-foo", label="second")]
    out = apply_first_come_first_served(candidates)
    assert len(out) == 1
    assert out[0].label == "first"


@pytest.mark.unit
def test_apply_first_come_first_served_preserves_distinct_names() -> None:
    from haywire.core.marketstall.refresh import apply_first_come_first_served

    candidates = [_h("haybale-a"), _h("haybale-b"), _h("haybale-c")]
    out = apply_first_come_first_served(candidates)
    assert [p.name for p in out] == ["haybale-a", "haybale-b", "haybale-c"]
```

- [ ] **Step 18.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_refresh.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 18.3: Implement filter functions**

Write to `packages/haywire-core/src/haywire/core/marketstall/refresh.py`:

```python
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

from haywire.core.marketstall.types import Haybale


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
```

- [ ] **Step 18.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_refresh.py -v`
Expected: 8 passed.

- [ ] **Step 18.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/refresh.py \
        tests/marketstall/test_refresh.py
git commit -m "feat(marketstall): add conflict-resolution filters (ignores, blocked, heaps, FCFS)"
```

---

## Task 19: Stale-marking and `mark_stale_against_previous`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/refresh.py`
- Modify: `tests/marketstall/test_refresh.py`

- [ ] **Step 19.1: Write the failing tests**

Append to `tests/marketstall/test_refresh.py`:

```python
@pytest.mark.unit
def test_mark_stale_fresh_only_passes_through() -> None:
    from haywire.core.marketstall.refresh import mark_stale_against_previous

    fresh = [_h("haybale-a"), _h("haybale-b")]
    out = mark_stale_against_previous(fresh, previous=[])
    assert [p.name for p in out] == ["haybale-a", "haybale-b"]
    assert all(not p.stale for p in out)


@pytest.mark.unit
def test_mark_stale_drops_to_previous_only_marks_stale() -> None:
    """Entries in previous but not fresh become stale with a last_seen timestamp."""
    from haywire.core.marketstall.refresh import mark_stale_against_previous

    previous = [_h("haybale-gone")]
    fresh = [_h("haybale-still-here")]
    out = mark_stale_against_previous(fresh, previous=previous)
    by_name = {p.name: p for p in out}
    assert by_name["haybale-gone"].stale is True
    assert by_name["haybale-gone"].last_seen != ""
    assert by_name["haybale-still-here"].stale is False


@pytest.mark.unit
def test_mark_stale_preserves_existing_stale_timestamp() -> None:
    """An entry already stale in previous keeps its last_seen — don't bump on every refresh."""
    from haywire.core.marketstall.refresh import mark_stale_against_previous

    previous = [_h("haybale-old", stale=True, last_seen="2026-01-01T00:00:00Z")]
    out = mark_stale_against_previous([], previous=previous)
    assert len(out) == 1
    assert out[0].stale is True
    assert out[0].last_seen == "2026-01-01T00:00:00Z"


@pytest.mark.unit
def test_mark_stale_entries_in_both_use_fresh_data() -> None:
    """When an entry is in both fresh and previous, fresh wins (no stale flag carry-over)."""
    from haywire.core.marketstall.refresh import mark_stale_against_previous

    previous = [_h("haybale-foo", stale=True, last_seen="2026-01-01T00:00:00Z")]
    fresh = [_h("haybale-foo", label="back-fresh")]
    out = mark_stale_against_previous(fresh, previous=previous)
    assert len(out) == 1
    assert out[0].label == "back-fresh"
    assert out[0].stale is False
```

- [ ] **Step 19.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_refresh.py -v -k mark_stale`
Expected: FAIL — `ImportError`.

- [ ] **Step 19.3: Implement `mark_stale_against_previous`**

Append to `packages/haywire-core/src/haywire/core/marketstall/refresh.py`:

```python
import datetime as _dt


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
```

- [ ] **Step 19.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_refresh.py -v`
Expected: 12 passed (8 + 4 new).

- [ ] **Step 19.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/refresh.py \
        tests/marketstall/test_refresh.py
git commit -m "feat(marketstall): add mark_stale_against_previous"
```


---

## Task 20: `refresh()` orchestrator

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/refresh.py`
- Modify: `tests/marketstall/test_refresh.py`

- [ ] **Step 20.1: Write the failing test for the full orchestrator**

Append to `tests/marketstall/test_refresh.py`:

```python
@pytest.mark.unit
def test_refresh_with_no_subscriptions_writes_empty_project(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import refresh

    global_path = tmp_path / "global.toml"
    global_path.write_text("")
    project_path = tmp_path / "project.toml"

    report = refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")
    assert report.sources_fetched == 0
    assert report.sources_from_cache == 0
    assert report.sources_unavailable == 0
    assert report.haybales_resolved == 0


@pytest.mark.unit
def test_refresh_fetches_stall_subscription(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import refresh

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[stalls]]\n'
        'url = "https://alice.example/marketstall.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    fake_body = (
        '[[haybales]]\n'
        'name = "haybale-foo"\n'
        'min_version = "0.1.0"\n'
    )
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
        report = refresh(
            global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c"
        )

    assert report.sources_fetched == 1
    assert report.haybales_resolved == 1


@pytest.mark.unit
def test_refresh_falls_back_to_cache_when_unreachable(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_write
    from haywire.core.marketstall.refresh import refresh

    cache_dir = tmp_path / "c"
    cache_write(
        "https://alice.example/marketstall.toml",
        '[[haybales]]\nname = "haybale-foo"\nmin_version = "0.1.0"\n',
        cache_dir=cache_dir,
    )

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[stalls]]\n'
        'url = "https://alice.example/marketstall.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    with patch("haywire.core.marketstall.cache._urlopen", side_effect=OSError):
        report = refresh(
            global_path=global_path, project_path=project_path, cache_dir=cache_dir
        )

    assert report.sources_fetched == 0
    assert report.sources_from_cache == 1
    assert report.sources_unavailable == 0
    assert report.haybales_resolved == 1


@pytest.mark.unit
def test_refresh_unavailable_when_no_cache_no_network(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import refresh

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[stalls]]\n'
        'url = "https://gone.example/marketstall.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    with patch("haywire.core.marketstall.cache._urlopen", side_effect=OSError):
        report = refresh(
            global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c"
        )

    assert report.sources_unavailable == 1
    assert "https://gone.example/marketstall.toml" in report.unavailable_urls


@pytest.mark.unit
def test_refresh_applies_blocked_per_subscription(tmp_path: Path) -> None:
    from haywire.core.marketstall.refresh import refresh

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[stalls]]\n'
        'url = "https://alice.example/marketstall.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = ["haybale-untrusted"]\n'
    )
    project_path = tmp_path / "project.toml"

    fake_body = (
        '[[haybales]]\n'
        'name = "haybale-foo"\n'
        'min_version = "0.1.0"\n'
        '\n'
        '[[haybales]]\n'
        'name = "haybale-untrusted"\n'
        'min_version = "0.1.0"\n'
    )
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = fake_body.encode()
        report = refresh(
            global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c"
        )

    assert report.haybales_resolved == 1


@pytest.mark.unit
def test_refresh_gcs_orphan_cache_files(tmp_path: Path) -> None:
    from haywire.core.marketstall.cache import cache_write
    from haywire.core.marketstall.refresh import refresh

    cache_dir = tmp_path / "c"
    cache_write("https://orphan.example/m.toml", "old", cache_dir=cache_dir)
    cache_write(
        "https://active.example/m.toml",
        '[[haybales]]\nname = "haybale-x"\nmin_version = "0.1.0"\n',
        cache_dir=cache_dir,
    )

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[stalls]]\n'
        'url = "https://active.example/m.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    with patch("haywire.core.marketstall.cache._urlopen", side_effect=OSError):
        refresh(global_path=global_path, project_path=project_path, cache_dir=cache_dir)

    remaining = sorted(p.name for p in cache_dir.iterdir() if p.is_file())
    assert len(remaining) == 1  # orphan removed; active retained


@pytest.mark.unit
def test_refresh_one_level_deep_consumes_market_stalls(tmp_path: Path) -> None:
    """A [[markets]] subscription contributes [[stalls]] URLs and inline [[haybales]]."""
    from haywire.core.marketstall.refresh import refresh

    global_path = tmp_path / "global.toml"
    global_path.write_text(
        '[[markets]]\n'
        'url = "https://aggregator.example/marketplace.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
    )
    project_path = tmp_path / "project.toml"

    aggregator_body = (
        '[[stalls]]\n'
        'url = "https://stall.example/marketstall.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
        '\n'
        '[[haybales]]\n'
        'name = "haybale-inline"\n'
        'min_version = "0.1.0"\n'
    )
    stall_body = (
        '[[haybales]]\n'
        'name = "haybale-from-stall"\n'
        'min_version = "0.1.0"\n'
    )

    def fake_urlopen(url, *, timeout):
        from unittest.mock import MagicMock

        m = MagicMock()
        if "aggregator" in url:
            m.__enter__.return_value.read.return_value = aggregator_body.encode()
        else:
            m.__enter__.return_value.read.return_value = stall_body.encode()
        return m

    with patch("haywire.core.marketstall.cache._urlopen", side_effect=fake_urlopen):
        report = refresh(
            global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c"
        )

    assert report.sources_fetched == 2  # aggregator + the stall it referenced
    assert report.haybales_resolved == 2  # haybale-inline + haybale-from-stall
```

- [ ] **Step 20.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_refresh.py -v -k "test_refresh_"`
Expected: FAIL — `ImportError: cannot import name 'refresh'`.

- [ ] **Step 20.3: Implement the orchestrator**

Append to `packages/haywire-core/src/haywire/core/marketstall/refresh.py`:

```python
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
    ProjectMarketplaceFile,
    RefreshOutcome,
    RefreshReport,
    Subscription,
)


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
    active_urls: set[str] = {s.url for s in mf.markets} | {s.url for s in mf.stalls} | set(discovered_stall_urls)
    gc_orphans(active_urls, cache_dir=cache_dir)

    return report
```

- [ ] **Step 20.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_refresh.py -v`
Expected: 19 passed (12 + 7 new).

- [ ] **Step 20.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/refresh.py \
        tests/marketstall/test_refresh.py
git commit -m "feat(marketstall): add refresh() orchestrator with tri-state results and GC"
```

---

## Task 21: Helpers — `add_market_subscription_to_global`, `add_stall_subscription_to_global`

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/helpers.py`
- Create: `tests/marketstall/test_helpers.py`

- [ ] **Step 21.1: Write the failing tests**

Write to `tests/marketstall/test_helpers.py`:

```python
"""Helpers for adding/removing marketplace entries — spec §14."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_add_market_subscription_creates_file_if_missing(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import add_market_subscription_to_global
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(f, "https://x.example/marketplace.toml")
    mf = parse_global_marketplace(f)
    assert len(mf.markets) == 1
    assert mf.markets[0].url == "https://x.example/marketplace.toml"


@pytest.mark.unit
def test_add_market_subscription_is_idempotent(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import add_market_subscription_to_global
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(f, "https://x.example/m.toml")
    add_market_subscription_to_global(f, "https://x.example/m.toml")
    mf = parse_global_marketplace(f)
    assert len(mf.markets) == 1


@pytest.mark.unit
def test_add_stall_subscription_creates_file_if_missing(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import add_stall_subscription_to_global
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(f, "https://alice.example/marketstall.toml")
    mf = parse_global_marketplace(f)
    assert len(mf.stalls) == 1
    assert mf.stalls[0].blocked == []  # new field defaults to empty


@pytest.mark.unit
def test_add_stall_subscription_preserves_existing_sections(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import (
        add_market_subscription_to_global,
        add_stall_subscription_to_global,
    )
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(f, "https://m.example/m.toml")
    add_stall_subscription_to_global(f, "https://s.example/s.toml")
    mf = parse_global_marketplace(f)
    assert len(mf.markets) == 1
    assert len(mf.stalls) == 1
```

- [ ] **Step 21.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_helpers.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 21.3: Implement subscription helpers**

Write to `packages/haywire-core/src/haywire/core/marketstall/helpers.py`:

```python
"""Helpers for the marketplace file: subscriptions, heaps, ignores, cache removals.

Each helper reads the global (or project) file, mutates the parsed structure,
and writes back via the serializer. All operations are idempotent where it
makes sense; raise specific errors otherwise.
"""

from __future__ import annotations

from pathlib import Path

from haywire.core.marketstall.errors import DuplicateHeapNameError
from haywire.core.marketstall.parsing import (
    parse_global_marketplace,
    parse_project_marketplace,
    serialize_global_marketplace,
    serialize_project_marketplace,
)
from haywire.core.marketstall.types import (
    Haybale,
    MarketplaceFile,
    ProjectMarketplaceFile,
    Subscription,
)


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
```

- [ ] **Step 21.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_helpers.py -v`
Expected: 4 passed.

- [ ] **Step 21.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/helpers.py \
        tests/marketstall/test_helpers.py
git commit -m "feat(marketstall): add subscription helpers"
```

---

## Task 22: Helpers — `add_heap_to_project`, `remove_stale_haybale_from_project`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/helpers.py`
- Modify: `tests/marketstall/test_helpers.py`

- [ ] **Step 22.1: Write the failing tests**

Append to `tests/marketstall/test_helpers.py`:

```python
@pytest.mark.unit
def test_add_heap_to_project_creates_file(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import add_heap_to_project
    from haywire.core.marketstall.parsing import parse_project_marketplace

    f = tmp_path / "project.toml"
    add_heap_to_project(
        f, name="haybale-my-project", path=Path("/abs/path"), label="My Project"
    )
    pm = parse_project_marketplace(f)
    assert len(pm.heaps) == 1
    assert pm.heaps[0]["name"] == "haybale-my-project"
    assert pm.heaps[0]["path"] == "/abs/path"
    assert pm.heaps[0]["label"] == "My Project"


@pytest.mark.unit
def test_add_heap_to_project_raises_on_duplicate(tmp_path: Path) -> None:
    from haywire.core.marketstall.errors import DuplicateHeapNameError
    from haywire.core.marketstall.helpers import add_heap_to_project

    f = tmp_path / "project.toml"
    add_heap_to_project(f, name="haybale-x", path=Path("/p1"))
    with pytest.raises(DuplicateHeapNameError):
        add_heap_to_project(f, name="haybale-x", path=Path("/p2"))


@pytest.mark.unit
def test_remove_stale_haybale_removes_entry(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import remove_stale_haybale_from_project
    from haywire.core.marketstall.parsing import (
        parse_project_marketplace,
        serialize_project_marketplace,
    )
    from haywire.core.marketstall.types import Haybale, ProjectMarketplaceFile

    f = tmp_path / "project.toml"
    pm = ProjectMarketplaceFile(
        caches=[Haybale(name="haybale-gone", min_version="0.1.0", stale=True)]
    )
    f.write_text(serialize_project_marketplace(pm))

    removed = remove_stale_haybale_from_project(f, name="haybale-gone")
    assert removed is True

    reparsed = parse_project_marketplace(f)
    assert reparsed.caches == []


@pytest.mark.unit
def test_remove_stale_haybale_refuses_non_stale(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import remove_stale_haybale_from_project
    from haywire.core.marketstall.parsing import serialize_project_marketplace
    from haywire.core.marketstall.types import Haybale, ProjectMarketplaceFile

    f = tmp_path / "project.toml"
    pm = ProjectMarketplaceFile(
        caches=[Haybale(name="haybale-foo", min_version="0.1.0", stale=False)]
    )
    f.write_text(serialize_project_marketplace(pm))

    with pytest.raises(ValueError, match="non-stale"):
        remove_stale_haybale_from_project(f, name="haybale-foo")


@pytest.mark.unit
def test_remove_stale_haybale_returns_false_when_not_found(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import remove_stale_haybale_from_project

    f = tmp_path / "project.toml"
    f.write_text("")
    assert remove_stale_haybale_from_project(f, name="haybale-missing") is False
```

- [ ] **Step 22.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_helpers.py -v -k "heap or stale"`
Expected: FAIL — `ImportError`.

- [ ] **Step 22.3: Implement heap and stale-removal helpers**

Append to `packages/haywire-core/src/haywire/core/marketstall/helpers.py`:

```python
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
                f'at {existing.get("path")} in {project_path}.'
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
```

- [ ] **Step 22.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_helpers.py -v`
Expected: 9 passed (4 + 5 new).

- [ ] **Step 22.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/helpers.py \
        tests/marketstall/test_helpers.py
git commit -m "feat(marketstall): add add_heap_to_project and remove_stale_haybale_from_project"
```


---

## Task 23: Helpers — `record_ignore_on_source`, `record_block_on_source`, `detect_subscription_conflicts`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/helpers.py`
- Modify: `tests/marketstall/test_helpers.py`

- [ ] **Step 23.1: Write the failing tests**

Append to `tests/marketstall/test_helpers.py`:

```python
@pytest.mark.unit
def test_record_ignore_appends_to_subscription(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import (
        add_stall_subscription_to_global,
        record_ignore_on_source,
    )
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(f, "https://alice.example/marketstall.toml")
    record_ignore_on_source(
        f, source_url="https://alice.example/marketstall.toml", haybale_name="haybale-mesh"
    )

    mf = parse_global_marketplace(f)
    assert mf.stalls[0].ignores == ["haybale-mesh"]


@pytest.mark.unit
def test_record_ignore_is_idempotent(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import (
        add_stall_subscription_to_global,
        record_ignore_on_source,
    )
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(f, "https://alice.example/marketstall.toml")
    record_ignore_on_source(
        f, source_url="https://alice.example/marketstall.toml", haybale_name="haybale-mesh"
    )
    record_ignore_on_source(
        f, source_url="https://alice.example/marketstall.toml", haybale_name="haybale-mesh"
    )

    mf = parse_global_marketplace(f)
    assert mf.stalls[0].ignores == ["haybale-mesh"]


@pytest.mark.unit
def test_record_block_appends_to_subscription(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import (
        add_stall_subscription_to_global,
        record_block_on_source,
    )
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(f, "https://alice.example/marketstall.toml")
    record_block_on_source(
        f,
        source_url="https://alice.example/marketstall.toml",
        haybale_name="haybale-untrusted",
    )

    mf = parse_global_marketplace(f)
    assert mf.stalls[0].blocked == ["haybale-untrusted"]


@pytest.mark.unit
def test_record_block_works_on_market_subscription(tmp_path: Path) -> None:
    from haywire.core.marketstall.helpers import (
        add_market_subscription_to_global,
        record_block_on_source,
    )
    from haywire.core.marketstall.parsing import parse_global_marketplace

    f = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(f, "https://agg.example/marketplace.toml")
    record_block_on_source(
        f,
        source_url="https://agg.example/marketplace.toml",
        haybale_name="haybale-spam",
    )

    mf = parse_global_marketplace(f)
    assert mf.markets[0].blocked == ["haybale-spam"]


@pytest.mark.unit
def test_detect_subscription_conflicts_finds_name_collisions() -> None:
    from haywire.core.marketstall.helpers import detect_subscription_conflicts
    from haywire.core.marketstall.types import Haybale

    existing = [
        Haybale(name="haybale-foo", min_version="0.1.0", source_origin="https://a.example/m.toml"),
        Haybale(name="haybale-bar", min_version="0.1.0", source_origin="https://a.example/m.toml"),
    ]
    new = [
        Haybale(name="haybale-foo", min_version="0.2.0", source_origin="https://b.example/m.toml"),
        Haybale(name="haybale-new", min_version="0.1.0", source_origin="https://b.example/m.toml"),
    ]
    conflicts = detect_subscription_conflicts(existing, new)
    assert len(conflicts) == 1
    assert conflicts[0].name == "haybale-foo"
    assert conflicts[0].existing_source == "https://a.example/m.toml"
    assert conflicts[0].new_source == "https://b.example/m.toml"


@pytest.mark.unit
def test_detect_subscription_conflicts_no_collisions() -> None:
    from haywire.core.marketstall.helpers import detect_subscription_conflicts
    from haywire.core.marketstall.types import Haybale

    existing = [Haybale(name="haybale-a", min_version="0.1.0")]
    new = [Haybale(name="haybale-b", min_version="0.1.0")]
    assert detect_subscription_conflicts(existing, new) == []
```

- [ ] **Step 23.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_helpers.py -v -k "ignore or block or conflict"`
Expected: FAIL — `ImportError`.

- [ ] **Step 23.3: Implement the helpers**

Append to `packages/haywire-core/src/haywire/core/marketstall/helpers.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SubscriptionConflict:
    """A name collision between an already-resolved haybale and a new subscription's haybale."""

    name: str
    existing_source: str  # URL where the existing haybale was resolved from
    new_source: str  # URL where the new haybale is offered


def _replace_subscription_in_list(
    subs: list[Subscription], target_url: str, transform
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


def record_ignore_on_source(
    global_path: Path, *, source_url: str, haybale_name: str
) -> None:
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


def record_block_on_source(
    global_path: Path, *, source_url: str, haybale_name: str
) -> None:
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


def detect_subscription_conflicts(
    existing: list[Haybale], new: list[Haybale]
) -> list[SubscriptionConflict]:
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
```

- [ ] **Step 23.4: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_helpers.py -v`
Expected: 15 passed (9 + 6 new).

- [ ] **Step 23.5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/helpers.py \
        tests/marketstall/test_helpers.py
git commit -m "feat(marketstall): add record_ignore/block_on_source and detect_subscription_conflicts"
```

---

## Task 24: Public API — `marketstall/__init__.py` exports

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/__init__.py`

- [ ] **Step 24.1: Verify what currently exports**

Read the current file:

```bash
cat packages/haywire-core/src/haywire/core/marketstall/__init__.py
```

It should just have the module docstring (from Task 1) with no exports yet.

- [ ] **Step 24.2: Add a test that verifies the public surface**

Append to `tests/marketstall/test_haybale_dataclass.py`:

```python
@pytest.mark.unit
def test_public_surface_imports_from_marketstall_package() -> None:
    """All major types and functions are importable from haywire.core.marketstall."""
    from haywire.core import marketstall

    # Dataclasses
    assert hasattr(marketstall, "Haybale")
    assert hasattr(marketstall, "Subscription")
    assert hasattr(marketstall, "MarketplaceFile")
    assert hasattr(marketstall, "ProjectMarketplaceFile")
    assert hasattr(marketstall, "RefreshOutcome")
    assert hasattr(marketstall, "RefreshReport")
    assert hasattr(marketstall, "FetchResult")
    # Parsers
    assert hasattr(marketstall, "parse_global_marketplace")
    assert hasattr(marketstall, "parse_project_marketplace")
    assert hasattr(marketstall, "parse_marketstall_body")
    assert hasattr(marketstall, "parse_remote_marketplace_body")
    # Serializers
    assert hasattr(marketstall, "serialize_global_marketplace")
    assert hasattr(marketstall, "serialize_project_marketplace")
    # Refresh
    assert hasattr(marketstall, "refresh")
    # Helpers
    assert hasattr(marketstall, "add_market_subscription_to_global")
    assert hasattr(marketstall, "add_stall_subscription_to_global")
    assert hasattr(marketstall, "add_heap_to_project")
    assert hasattr(marketstall, "remove_stale_haybale_from_project")
    assert hasattr(marketstall, "record_ignore_on_source")
    assert hasattr(marketstall, "record_block_on_source")
    assert hasattr(marketstall, "detect_subscription_conflicts")
    # Errors
    assert hasattr(marketstall, "MalformedMarketplaceError")
    assert hasattr(marketstall, "DuplicateHeapNameError")
    assert hasattr(marketstall, "RemoteFetchError")
    # Platform
    assert hasattr(marketstall, "current_os")
    assert hasattr(marketstall, "haybale_supports_current_os")
    # URL resolution
    assert hasattr(marketstall, "classify_input")
    assert hasattr(marketstall, "InputForm")
    assert hasattr(marketstall, "BareRepoUrlRejectedError")
```

- [ ] **Step 24.3: Run the test to confirm it fails**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py::test_public_surface_imports_from_marketstall_package -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 24.4: Populate the `__init__.py`**

Replace the entire contents of `packages/haywire-core/src/haywire/core/marketstall/__init__.py` with:

```python
"""Marketstall distribution runtime — spec internals/specs/marketstall-distribution.md.

Replaces the legacy haywire.core.marketplace + marketplace_runtime + marketplace_errors
trio. The submodules here implement the new section vocabulary ([[markets]], [[stalls]],
[[haybales]], [[heaps]], [[caches]]), the host-provider abstraction, and the URL
resolution/refresh pipeline. The directory naming reflects the future haybale-marketplace
carve-out — see §3.1 of the spec.
"""

from haywire.core.marketstall.cache import (
    cache_read,
    cache_write,
    fetch_with_cache_fallback,
    gc_orphans,
)
from haywire.core.marketstall.errors import (
    DuplicateHeapNameError,
    MalformedMarketplaceError,
    RemoteFetchError,
)
from haywire.core.marketstall.helpers import (
    SubscriptionConflict,
    add_heap_to_project,
    add_market_subscription_to_global,
    add_stall_subscription_to_global,
    detect_subscription_conflicts,
    record_block_on_source,
    record_ignore_on_source,
    remove_stale_haybale_from_project,
)
from haywire.core.marketstall.parsing import (
    RemoteMarketplaceContents,
    parse_global_marketplace,
    parse_marketstall_body,
    parse_project_marketplace,
    parse_remote_marketplace_body,
    serialize_global_marketplace,
    serialize_project_marketplace,
)
from haywire.core.marketstall.platform import current_os, haybale_supports_current_os
from haywire.core.marketstall.refresh import (
    apply_blocked,
    apply_first_come_first_served,
    apply_heaps_shadow,
    apply_ignores,
    mark_stale_against_previous,
    refresh,
)
from haywire.core.marketstall.types import (
    FetchResult,
    Haybale,
    MarketplaceFile,
    ProjectMarketplaceFile,
    RefreshOutcome,
    RefreshReport,
    Subscription,
)
from haywire.core.marketstall.url_resolution import (
    BareRepoUrlRejectedError,
    ClassifiedInput,
    InputForm,
    classify_input,
)

__all__ = [
    # Dataclasses / enums
    "FetchResult",
    "Haybale",
    "MarketplaceFile",
    "ProjectMarketplaceFile",
    "RefreshOutcome",
    "RefreshReport",
    "Subscription",
    "RemoteMarketplaceContents",
    "SubscriptionConflict",
    "ClassifiedInput",
    "InputForm",
    # Parsers + serializers
    "parse_global_marketplace",
    "parse_project_marketplace",
    "parse_marketstall_body",
    "parse_remote_marketplace_body",
    "serialize_global_marketplace",
    "serialize_project_marketplace",
    # Cache
    "cache_read",
    "cache_write",
    "fetch_with_cache_fallback",
    "gc_orphans",
    # Refresh
    "refresh",
    "apply_ignores",
    "apply_blocked",
    "apply_heaps_shadow",
    "apply_first_come_first_served",
    "mark_stale_against_previous",
    # Helpers
    "add_market_subscription_to_global",
    "add_stall_subscription_to_global",
    "add_heap_to_project",
    "remove_stale_haybale_from_project",
    "record_ignore_on_source",
    "record_block_on_source",
    "detect_subscription_conflicts",
    # Errors
    "MalformedMarketplaceError",
    "DuplicateHeapNameError",
    "RemoteFetchError",
    "BareRepoUrlRejectedError",
    # Platform
    "current_os",
    "haybale_supports_current_os",
    # URL resolution
    "classify_input",
]
```

- [ ] **Step 24.5: Run the public-surface test**

Run: `uv run pytest tests/marketstall/test_haybale_dataclass.py::test_public_surface_imports_from_marketstall_package -v`
Expected: PASS.

- [ ] **Step 24.6: Run the full marketstall test suite to confirm everything still passes**

Run: `uv run pytest tests/marketstall/ -v`
Expected: all tests pass (foundation modules are now complete).

- [ ] **Step 24.7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/__init__.py \
        tests/marketstall/test_haybale_dataclass.py
git commit -m "feat(marketstall): export public API from package __init__"
```

---

## Task 25: Update `MarketplaceState` to use new module

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/state/marketplace_state.py`
- Modify: `tests/test_marketplace_state.py`

The studio `MarketplaceState` consumes the runtime via imports; it needs to point at the new module with renamed methods. UI behavior unchanged in this plan — slices 3-5 wire blocked/safety modal/provenance into the UI.

- [ ] **Step 25.1: Read current `MarketplaceState`**

Run: `cat barn/haybale-studio/haybale_studio/state/marketplace_state.py | head -160`

Note the current method names: `get_global`, `get_project_packages`, `remove_stale_package`. The §14 rename table changes these to `get_project_haybales`, `remove_stale_haybale`.

- [ ] **Step 25.2: Read the current `MarketplaceState` test to see the full method surface**

Run: `cat tests/test_marketplace_state.py`

Note which methods are exercised. The test file will be updated in step 25.4.

- [ ] **Step 25.3: Rewrite `MarketplaceState`**

Replace `barn/haybale-studio/haybale_studio/state/marketplace_state.py` with:

```python
"""MarketplaceState — AppState that owns marketplace orchestration.

Wraps haywire.core.marketstall. The UI editor calls methods on this state —
it doesn't know about marketstall internals directly. Dependencies are
resolved from the ambient DI context in on_enable, mirroring HaystackState's
pattern.

Per spec §3.1: file paths use the future haybale-marketplace subdirectory
(`~/.haywire/db/haybale-marketplace/`). The runtime code lives in
haywire.core.marketstall until the carve-out happens (out of scope here).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from haywire.core.marketstall import (
    Haybale,
    MalformedMarketplaceError,
    MarketplaceFile,
    RefreshReport,
    parse_global_marketplace,
    parse_project_marketplace,
    refresh as runtime_refresh,
    remove_stale_haybale_from_project,
)
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

logger = logging.getLogger(__name__)


@state(label="Marketplace State")
class MarketplaceState(AppState):
    """Owns marketplace orchestration for the studio library.

    Read API:
      - get_global(): MarketplaceFile | None (None when malformed; sets
        global_marketplace_error so the UI can render the Edit File banner).
      - get_project_haybales(): list[Haybale] from the project [[caches]].

    Orchestration API:
      - refresh(): RefreshReport, runs the refresh pipeline and caches the
        report on self.last_report for the UI to display.

    Path derivation (in on_enable):
      - workspace_root from haywire.core.di.context.get_workspace_root().
      - global_path = ~/.haywire/db/haybale-marketplace/marketplace.toml
        (per spec §3.1; placeholder for the future haybale-marketplace library).
      - project_path = <workspace_root>/.haywire/marketplace.toml.
    """

    def __init__(self) -> None:
        super().__init__()
        self._workspace_root: Optional[Path] = None
        self.last_report: Optional[RefreshReport] = None
        self.global_marketplace_error: Optional[str] = None

    def on_enable(self) -> None:
        from haywire.core.di.context import get_workspace_root

        self._workspace_root = get_workspace_root()

    def on_disable(self) -> None:
        self.last_report = None
        self.global_marketplace_error = None

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _global_path(self) -> Path:
        """~/.haywire/db/haybale-marketplace/marketplace.toml — spec §3.1.

        The `db/haybale-marketplace/` subdirectory is chosen now so the future
        haybale-marketplace carve-out doesn't require a migration. See spec §17
        for the non-goal "carve-out of haybale-marketplace as a separate library
        in this spec."
        """
        return Path.home() / ".haywire" / "db" / "haybale-marketplace" / "marketplace.toml"

    def _project_path(self) -> Optional[Path]:
        if self._workspace_root is None:
            return None
        return self._workspace_root / ".haywire" / "marketplace.toml"

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_global(self) -> Optional[MarketplaceFile]:
        """Parse the global marketplace file. None on malformed.

        On MalformedMarketplaceError, sets self.global_marketplace_error so the
        UI can render an Edit File banner. The error clears on the next
        successful get_global() call.
        """
        try:
            mf = parse_global_marketplace(self._global_path())
        except MalformedMarketplaceError as exc:
            self.global_marketplace_error = str(exc)
            return None
        self.global_marketplace_error = None
        return mf

    def get_project_haybales(self) -> list[Haybale]:
        """Parse <project>/.haywire/marketplace.toml and return its [[caches]] list."""
        project_path = self._project_path()
        if project_path is None:
            return []
        pm = parse_project_marketplace(project_path)
        return list(pm.caches)

    # ------------------------------------------------------------------
    # Orchestration API
    # ------------------------------------------------------------------

    def refresh(self) -> RefreshReport:
        """Run the refresh pipeline. Caches the result on self.last_report."""
        project_path = self._project_path()
        if project_path is None:
            self.last_report = RefreshReport()
            return self.last_report

        report = runtime_refresh(
            global_path=self._global_path(),
            project_path=project_path,
        )
        self.last_report = report
        return report

    def remove_stale_haybale(self, name: str) -> bool:
        """Remove a stale entry from the project [[caches]]. Returns True iff removed."""
        project_path = self._project_path()
        if project_path is None:
            return False
        return remove_stale_haybale_from_project(project_path, name=name)
```

- [ ] **Step 25.4: Update the `MarketplaceState` test file**

Open `tests/test_marketplace_state.py` and find every occurrence of:

- `from haywire.core.marketplace import MarketplaceEntry` → `from haywire.core.marketstall import Haybale`
- `from haywire.core.marketplace_runtime import ...` → `from haywire.core.marketstall import ...`
- `from haywire.core.marketplace_errors import ...` → `from haywire.core.marketstall import ...`
- `MarketplaceEntry(` → `Haybale(`
- `GlobalMarketplace(` → `MarketplaceFile(`
- `ProjectMarketplace(` → `ProjectMarketplaceFile(`
- `MalformedGlobalMarketplaceError` → `MalformedMarketplaceError`
- `.get_project_packages()` → `.get_project_haybales()`
- `.remove_stale_package(` → `.remove_stale_haybale(`
- `marketplaces=` → `markets=` (keyword arg)
- `marketstalls=` → `stalls=` (keyword arg)
- `packages=` (when on a `GlobalMarketplace`/`MarketplaceFile`) → `haybales=`
- `packages=` (when on a `ProjectMarketplace`/`ProjectMarketplaceFile`) → `caches=`
- `locals_=` (when on `ProjectMarketplace`) → `heaps=`

Adjust assertions for `MarketplaceFile.markets`, `.stalls`, `.haybales` (no `.locals_`, no `.packages`).

Also update the global-path expectation in the test: any reference to `~/.haywire/marketplace.toml` becomes `~/.haywire/db/haybale-marketplace/marketplace.toml`.

- [ ] **Step 25.5: Run the test to confirm it passes**

Run: `uv run pytest tests/test_marketplace_state.py -v`
Expected: PASS.

If it fails because the test is calling old method names you missed, fix in place; do not commit until green.

- [ ] **Step 25.6: Commit**

```bash
git add barn/haybale-studio/haybale_studio/state/marketplace_state.py \
        tests/test_marketplace_state.py
git commit -m "refactor(studio): port MarketplaceState to haywire.core.marketstall"
```


---

## Task 26: Repoint remaining studio imports — `library_manager.py`, `share.py`, editors

This task is bulk import-rewriting plus a careful check on share.py — we keep its section emission unchanged (slice 2 handles that) but it currently imports the old types. The file must compile and its tests pass after this task. No behavior changes here.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/library_manager.py`
- Modify: `packages/haywire-studio/src/haywire_studio/share.py`
- Modify: `barn/haybale-studio/haybale_studio/editors/library_browser_editor.py`
- Modify: `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py`

- [ ] **Step 26.1: Find every `MarketplaceEntry` and old-module reference in studio**

Run:
```bash
grep -rn "from haywire.core.marketplace\b\|from haywire.core.marketplace_runtime\|from haywire.core.marketplace_errors\|MarketplaceEntry\|GlobalMarketplace\|ProjectMarketplace\|MalformedGlobalMarketplaceError\|DuplicateLocalNameError\|DuplicatePackageNameError" \
    packages/haywire-studio/src barn/haybale-studio/haybale_studio --include="*.py"
```

This produces the worklist. For each match:
- `from haywire.core.marketplace import MarketplaceEntry` → `from haywire.core.marketstall import Haybale`
- `from haywire.core.marketplace_runtime import X` → `from haywire.core.marketstall import X` (with the renames in §14: `GlobalMarketplace` → `MarketplaceFile`, etc.)
- `from haywire.core.marketplace_errors import X` → `from haywire.core.marketstall import X` (`MalformedGlobalMarketplaceError` → `MalformedMarketplaceError`, `DuplicateLocalNameError` → `DuplicateHeapNameError`)
- `MarketplaceEntry(` → `Haybale(`
- `MarketplaceEntry` (as a type annotation) → `Haybale`

- [ ] **Step 26.2: Apply the rewrites to each file**

In each of:
- `packages/haywire-studio/src/haywire_studio/library_manager.py`
- `packages/haywire-studio/src/haywire_studio/share.py`
- `barn/haybale-studio/haybale_studio/editors/library_browser_editor.py`
- `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py`

apply the rewrites from step 26.1. Do not change any behavior — section names emitted by `share.py` (currently `[[packages]]`) stay as-is in this plan; slice 2 changes them.

`share.py` constructs `MarketplaceEntry` instances and serializes them to TOML; rename to `Haybale`. The `_TOML_FIELDS` order has changed (new `os` field) — share's emission goes through `Haybale.to_dict()` so it picks up the new order automatically.

For `share.py` specifically: keep the literal `[[packages]]` strings in the file write for now (slice 2 changes them to `[[haybales]]`). The dataclass rename is all that's needed here.

- [ ] **Step 26.3: Run the full unit test suite to catch any leftover references**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: PASS, or specific failures we then track down.

If there are failures, address each one — they will be either:
- A test file that still imports old names (update the imports the same way).
- A code file you missed in step 26.2 (grep again with the broader pattern, fix).

- [ ] **Step 26.4: Run ruff and mypy on the studio packages**

Run: `uv run ruff check packages/haywire-studio/src barn/haybale-studio`
Run: `uv run mypy packages/haywire-studio/src barn/haybale-studio`
Both must be clean. The pre-edit baseline (step 0.3) was clean; anything new is a regression to fix.

- [ ] **Step 26.5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/library_manager.py \
        packages/haywire-studio/src/haywire_studio/share.py \
        barn/haybale-studio/haybale_studio/editors/library_browser_editor.py \
        barn/haybale-studio/haybale_studio/editors/library_overview_editor.py
git commit -m "refactor(studio): repoint imports to haywire.core.marketstall"
```

---

## Task 27: Delete legacy migration function in `config.py`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/config.py`

Spec §13: the existing `_migrate_marketplace_schema_if_needed` is deleted outright — it was for the earlier `sources` → `[[marketplaces]]` transition, superseded by this rewrite.

- [ ] **Step 27.1: Read the current `config.py` to locate the function and its call site**

Run: `grep -n "_migrate_marketplace_schema_if_needed\|def _migrate" packages/haywire-studio/src/haywire_studio/config.py`

This gives the line numbers of (a) the function definition and (b) every call site.

- [ ] **Step 27.2: Delete the function and call sites**

Open `packages/haywire-studio/src/haywire_studio/config.py`. Remove:

- The `def _migrate_marketplace_schema_if_needed(marketplace_file: Path) -> None:` block and its body (including the docstring).
- Every line that calls `_migrate_marketplace_schema_if_needed(...)`.

After the edit, search the file for any remaining `_migrate_` reference. There should be none.

- [ ] **Step 27.3: Verify the file still compiles**

Run: `uv run python -c "import haywire_studio.config"`
Expected: no output (clean import).

- [ ] **Step 27.4: Delete the migration test file**

Run: `git rm tests/test_marketplace_migration.py`

- [ ] **Step 27.5: Run the unit test suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: PASS.

- [ ] **Step 27.6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/config.py
git commit -m "refactor(config): drop _migrate_marketplace_schema_if_needed and its test"
```

---

## Task 28: Delete legacy modules

**Files:**
- Delete: `packages/haywire-core/src/haywire/core/marketplace.py`
- Delete: `packages/haywire-core/src/haywire/core/marketplace_runtime.py`
- Delete: `packages/haywire-core/src/haywire/core/marketplace_errors.py`
- Delete: `tests/test_marketplace_runtime.py`
- Delete: `tests/test_marketplace_entry.py`

The new code at `haywire/core/marketstall/` fully replaces these. By this point every import has been repointed.

- [ ] **Step 28.1: Confirm no remaining references to the old modules**

Run:
```bash
grep -rn "haywire\.core\.marketplace\b\|haywire\.core\.marketplace_runtime\|haywire\.core\.marketplace_errors" \
    packages/ barn/ tests/ --include="*.py"
```
Expected: no matches.

If there are matches, fix them before deleting. They are bugs in Task 25 or Task 26.

- [ ] **Step 28.2: Delete the legacy files**

```bash
git rm packages/haywire-core/src/haywire/core/marketplace.py \
       packages/haywire-core/src/haywire/core/marketplace_runtime.py \
       packages/haywire-core/src/haywire/core/marketplace_errors.py \
       tests/test_marketplace_runtime.py \
       tests/test_marketplace_entry.py
```

- [ ] **Step 28.3: Run the full unit test suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: PASS. If anything fails, the missing-reference grep in step 28.1 missed something — restore the file (`git checkout HEAD -- <path>`), find and fix the leftover reference, then re-delete.

- [ ] **Step 28.4: Run ruff and mypy**

Run: `uv run ruff check packages/haywire-core/src/haywire/core/marketstall barn/haybale-studio packages/haywire-studio/src`
Run: `uv run mypy packages/haywire-core/src/haywire/core/marketstall barn/haybale-studio packages/haywire-studio/src`
Both must be clean.

- [ ] **Step 28.5: Commit**

```bash
git commit -m "refactor(core): delete legacy marketplace modules (superseded by marketstall package)"
```

---

## Task 29: Update glossary in lockstep

**Files:**
- Modify: `docs/reference/glossary.md`

Per the inquisition Q12 decision: the glossary lives in the same repo as the code and cannot be wrong for the duration of an implementation pass. The "Haybale — three distinct meanings" section was added in the inquisition. Now the marketplace-runtime section needs updating to reflect the new vocabulary.

- [ ] **Step 29.1: Read the current marketplace-runtime section**

Read `docs/reference/glossary.md`. The relevant blocks:

- Lines around 120-127 (the Marketstall, Marketplace, haybale-marketplace, README/OVERVIEW entries).
- The "Two-tier marketplace runtime *(new)*" section (around lines 131-157).
- The "Flagged ambiguities" entries near the end touching `[[marketplaces]]`, `[[marketstalls]]`, `[[packages]]`, `[[locals]]`, "marketplace vs marketstall," "locals location," etc.

- [ ] **Step 29.2: Rewrite the "Two-tier marketplace runtime" section header and entries**

Find the line `## Two-tier marketplace runtime *(new)*` in `docs/reference/glossary.md`. Replace the entire section (down to the next `---` separator) with:

```markdown
## Marketstall distribution runtime

The runtime that backs the Library Browser's Refresh / Add Source / Edit File flow. Spec: [`internals/specs/marketstall-distribution.md`](../speculatives/archive/marketstall-distribution.md). Code: `haywire.core.marketstall`.

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Global marketplace** | The user-scoped `~/.haywire/db/haybale-marketplace/marketplace.toml`. Holds the user's opt-in subscriptions (`[[markets]]`, `[[stalls]]`) and optionally inline `[[haybales]]`. Per-machine, never project-scoped. The `db/haybale-marketplace/` subdirectory is a forward reference to the planned **haybale-marketplace** library carve-out. | user marketplace |
| **Project marketplace** | The project-scoped `<project>/.haywire/marketplace.toml`. Holds the project's own `[[heaps]]` (written by `haywire init`, including dev-repo libraries under `--dev`) and the `[[caches]]` populated by refresh. Never has `[[markets]]` or `[[stalls]]`. | project file |
| **`[[markets]]`** | TOML section in the global marketplace declaring subscriptions to *remote marketplace feeds*. Each entry: `url`, `ignores`, `doubles`, `blocked`. Renamed from `[[marketplaces]]` (spec §14). | `[[marketplaces]]` (legacy schema) |
| **`[[stalls]]`** | TOML section declaring subscriptions to *remote marketstall feeds* (single-author publish files). Each entry: `url`, `ignores`, `doubles`, `blocked`. Renamed from `[[marketstalls]]`. | `[[marketstalls]]` (legacy schema) |
| **`[[haybales]]`** | TOML section listing one or more publishable library entries. Lives in `marketstall.toml` files; may also appear inline in `marketplace.toml` (PyPI-only / aggregator-publisher case). Replaces the older `[[packages]]` section name. | `[[packages]]` (legacy schema) |
| **`[[heaps]]`** | TOML section in the project marketplace declaring path-based libraries (always installed editably). Written by `haywire init`; manually editable. Renamed from `[[locals]]`. | `[[locals]]` (legacy schema) |
| **`[[caches]]`** | TOML section in the project marketplace holding the refresh result. Each entry is a fully-formed `Haybale` plus cache-only fields (`via`, `last_seen`, `stale`). Renamed from `[[packages]]` (project shape). | `[[packages]]` (project shape; legacy schema) |
| **Subscription** | A `[[markets]]` or `[[stalls]]` entry in the global marketplace — the user's opt-in to follow a remote feed. Identified by URL. Idempotent: re-adding the same URL is a no-op. | feed, source (overloaded) |
| **`ignores`** | Per-subscription array of names skipped from that source. Populated by the conflict-resolution prompt at Add Source time. Soft preference — the user picked another source. | skip list |
| **`blocked`** | Per-subscription array of names the user actively rejected via the first-install safety modal (§7.4). Stronger than `ignores`: blocked haybales are hidden from the Library Browser entirely. Un-blockable only by editing the marketplace file. | denylist (don't use — it's not a denylist, it's per-subscription) |
| **`doubles`** | Per-subscription array of names that two `[[markets]]` entries silently dedup to. Diagnostic only. | — |
| **Refresh** | The orchestrator (`haywire.core.marketstall.refresh`) that fetches every subscribed feed, resolves the candidate haybale list, applies `blocked`/`ignores`/heaps shadow/FCFS, and writes the result to the project `[[caches]]`. Triggered by Refresh button or auto-fires after Add Source. | sync, update |
| **One-level-deep resolution** | The hard limit on remote-marketplace chains: a remote marketplace's own `[[markets]]` entries are ignored — only its `[[stalls]]` URLs and inline `[[haybales]]` are consumed. Prevents infinite recursion and bounds the refresh blast radius. | recursive resolution |
| **Haybale (dataclass)** | The canonical dataclass for one entry available to install. Fields: `name`, `min_version`, `label`, `description`, `author`, `source` (`"pypi"` / `"git"` / `"local"`), `install_spec`, `tags`, `os`, `dependencies`, `source_url`, `docs_url`, plus cache-shape fields (`via`, `last_seen`, `stale`) and source-tagging fields. Code: `haywire.core.marketstall.types`. Renamed from `MarketplaceEntry`. | `MarketplaceEntry` (legacy name) |
| **Subscription (dataclass)** | The frozen dataclass for one `[[markets]]` or `[[stalls]]` entry: `url`, `ignores`, `doubles`, `blocked`. Renamed from `RemoteSubscription`; gained the `blocked` field. | `RemoteSubscription` (legacy name) |
| **Conflict resolution** | The four-filter rule applied during refresh: `blocked` per subscription, then `ignores` per subscription, then heaps shadow (heaps always win), then first-come-first-served as the final safety net. Spec §8.2. | — |
| **Stale** | Flag set on a project `[[caches]]` entry when a subsequent refresh did NOT re-resolve it. Renders as a red dot + "(stale)" suffix in the Library Browser. Stale + uninstalled entries are user-removable via the trash icon; stale + installed entries are locked until uninstalled. | outdated, expired |
| **`os` field** | Per-haybale list of supported platforms. Declarable values: `"macos"`, `"windows"`, `"linux"`. Source: each library's `pyproject.toml [tool.haywire].os`; copied into marketstalls by `haywire share`. Absent = "all platforms." `"other"` is the runtime sentinel for unmapped `platform.system()` results; never a declarable value. | — |
| **RefreshOutcome** | Tri-state per-subscription refresh result: `FRESH` (HTTP 200, cache overwritten), `CACHE_FALLBACK` (HTTP failed, served from cache), `UNAVAILABLE` (HTTP failed, no cache). | — |
| **RefreshReport** | Dataclass returned by `refresh()`: `sources_fetched`, `sources_from_cache`, `sources_unavailable`, `unavailable_urls`, `haybales_resolved`, `new_stale`, `updates_available`. The three `sources_*` counters partition the active subscription set. | — |
| **MarketplaceState** | The `AppState` that owns marketplace orchestration. The UI calls `state.refresh()`, `state.get_global()`, `state.get_project_haybales()`, `state.remove_stale_haybale()` — never `haywire.core.marketstall` functions directly. | — |
| **MalformedMarketplaceError** | Raised when a marketplace or marketstall file is invalid (TOML parse or schema violation). Library Manager surfaces this with an Edit File banner; the UI does not recover automatically. Renamed from `MalformedGlobalMarketplaceError`. | — |
| **HTTP cache** | `~/.haywire/cache/<url-hash>.toml`, one file per subscribed URL. Populated on successful fetch; consulted on fetch failure as a fallback. No TTL. Orphan cache files (no matching active subscription) are GC'd at end of each refresh. | — |
| **Host provider** | One git host's URL conventions. Protocol with `parse_blob_url` / `parse_raw_url` / `raw_url` / `blob_url` methods. GitHub and GitLab ship in the first cut; Bitbucket and Gitea are deferred. Self-hosted instances declare themselves in `~/.haywire/config.toml`. | — |
| **Blob URL** | The browser-friendly URL to a file on a git host (e.g. `https://github.com/alice/cool-libs/blob/main/marketstall.toml`). Canonical persisted form for `[[markets]]` and `[[stalls]]` subscriptions. | — |
| **Raw URL** | The fetch-friendly URL to a file's content (e.g. `https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml`). What the runtime actually HTTP-fetches. | — |
| **Marketstall** | A TOML file hosted by a library author that lists their published haybale packages; consumed as a remote feed by haywire projects. Produced by `haywire share`. Lives at `marketstall.toml` in the repo root (single-author) or `stalls/<dist-name>.toml` (aggregator layout). | marketplace snippet, package feed |
| **Marketplace** | The aggregated catalog of haybales visible in the Library Manager's AVAILABLE section. Built by merging the project's local `[[heaps]]` with all remote subscriptions (`[[markets]]` + `[[stalls]]`) resolved into `[[caches]]` by refresh. | package list, library catalog |
```

- [ ] **Step 29.3: Update flagged-ambiguities and other references**

In the "Flagged ambiguities" section of `docs/reference/glossary.md`:

- Update the `"marketplace" overloaded` entry to refer to the new section names (`[[markets]]` not `[[marketplaces]]`).
- Update the `"marketplace" vs "marketstall"` entry: now `[[markets]]` URL points at another `marketplace.toml`; `[[stalls]]` URL points at a `marketstall.toml`.
- Replace the `"locals" location` entry with: `"heaps" location — `haywire init` writes `[[heaps]]` to the **Project marketplace**, NOT the Global marketplace. The Global marketplace has no `[[heaps]]` section in the new schema (the legacy `[[locals]]` cross-project case is unsupported; users with that need declare each project's heaps in its own project marketplace).`

In the "stale" flagged-ambiguity entry, replace `[[packages]]` with `[[caches]]`.

In the existing `Marketstall` and `Marketplace` rows of the higher-level "Library & Plugin System" table, update the descriptions to mention the new section names where they currently say `[[packages]]`.

Update the `haybale-marketplace` row in the same "Library & Plugin System" table to note that the directory path `~/.haywire/db/haybale-marketplace/` is now used by the marketstall runtime as a forward reference.

- [ ] **Step 29.4: Verify the glossary renders correctly**

Run: `uv run mkdocs serve` in the background; visit http://127.0.0.1:8000/reference/glossary/ in a browser if a renderer is available, otherwise just verify no obvious markdown syntax errors:

Run: `python -c "import pathlib; t = pathlib.Path('docs/reference/glossary.md').read_text(); assert '[[markets]]' in t and '[[stalls]]' in t and '[[haybales]]' in t and '[[heaps]]' in t and '[[caches]]' in t"`
Expected: no output (assertions pass).

- [ ] **Step 29.5: Commit**

```bash
git add docs/reference/glossary.md
git commit -m "docs(glossary): update marketplace-runtime section for new vocabulary"
```

---

## Task 30: Final verification sweep

- [ ] **Step 30.1: Run the full test suite**

Run: `uv run pytest tests/ -q`
Expected: all pass (unit + integration if any are touched).

- [ ] **Step 30.2: Run ruff across all changed packages**

Run:
```bash
uv run ruff check \
    packages/haywire-core/src/haywire/core/marketstall \
    packages/haywire-studio/src \
    barn/haybale-studio/haybale_studio \
    tests/marketstall \
    tests/test_marketplace_state.py
```
Expected: clean.

- [ ] **Step 30.3: Run mypy across the same**

Run:
```bash
uv run mypy \
    packages/haywire-core/src/haywire/core/marketstall \
    packages/haywire-studio/src \
    barn/haybale-studio/haybale_studio
```
Expected: clean.

- [ ] **Step 30.4: Confirm the runtime starts**

Run: `uv run python -c "from haywire.core.marketstall import refresh, parse_global_marketplace, Haybale, MarketplaceFile; print('OK')"`
Expected: `OK`.

- [ ] **Step 30.5: Run the haywire CLI sanity check**

Run: `uv run haywire --help`
Expected: help text prints without error. Confirms the studio package still loads end-to-end after the rewrite.

- [ ] **Step 30.6: Review the diff and clean up any noise**

Run: `git log --oneline master..HEAD` to see the commit list.
Run: `git diff master --stat | tail -20` for a file-level summary.

Look for:
- Stray TODO comments
- `print()` debug statements
- Imports that are no longer needed in modified files

Fix any noise inline; commit a small cleanup commit if needed (`chore(marketstall): cleanup`).

- [ ] **Step 30.7: Push the branch (optional)**

Push only when the user explicitly asks. The foundation is now ready for slice 2 (author tooling).

---

## Spec coverage check

This plan covers the **Foundation slice (§16 step 1)** of the marketstall-distribution spec. Specifically:

| Spec §  | Covered by | Notes |
|---|---|---|
| §1 Vocabulary | Task 13-16, 29 | Parsers + serializers + glossary |
| §2 Marketstall format | Task 13, 15 | `_parse_haybale_entry` + `parse_marketstall_body` |
| §2.1 `os` field | Task 2, 7 | Dataclass field + `current_os()` + `haybale_supports_current_os` |
| §3.1 Consumer marketplace | Task 4, 14, 25 | `MarketplaceFile` + parser + `MarketplaceState._global_path` (uses `~/.haywire/db/haybale-marketplace/`) |
| §3.2 Project marketplace | Task 4, 14 | `ProjectMarketplaceFile` + parser |
| §3.3 Aggregator marketplace | Task 15 | `parse_remote_marketplace_body` accepts inline `[[haybales]]` |
| §4.2 Four input forms | Task 12 | `classify_input` |
| §4.3 Resolution | Task 12 | Bare repo URL rejection |
| §5 Host providers | Task 8-11 | Protocol, GitHub, GitLab, self-hosted config |
| §7.3 Caching | Task 17 | Tri-state, no TTL, GC |
| §7.4 Install safety (data layer only) | Task 3, 18, 23 | `blocked` field, `apply_blocked` filter, `record_block_on_source` |
| §8 Refresh pipeline | Task 18-20 | Filters + orchestrator |
| §8.1 One-level-deep | Task 15, 20 | `parse_remote_marketplace_body` ignores nested markets |
| §8.2 Conflict resolution | Task 18, 20 | All four filters wired in `refresh()` |
| §9 RefreshReport | Task 6, 20 | New fields (`sources_from_cache`, `updates_available`) |
| §13 Migration | Task 27 | `_migrate_marketplace_schema_if_needed` deleted |
| §14 Runtime renames | All tasks; final wiring Task 25-28 | Full §14 rename table |
| §15 Documentation | Task 29 | Glossary update in lockstep |

**Not covered (deferred to later slices):**

| Spec §  | Deferred to slice |
|---|---|
| §2.1 OS Edit dialog UI | 4 |
| §6 `haywire share` emission changes (`[[haybales]]` not `[[packages]]`) | 2 |
| §6.6 README marker handling | 2 |
| §7.1 Add Source dialog UI | 3 |
| §7.4 First-install safety modal UI | 5 |
| §10.3 Update-available UI | 7 |
| §11 Per-haybale stall generator | 8 |
| §12 Drift gate `min_version` lag | 6 |

---

## Self-Review notes (already applied)

- ✅ Every step has a complete code block; no "TBD" or "fill in details".
- ✅ Method names referenced in later tasks match earlier definitions (`get_project_haybales`, `remove_stale_haybale`, `apply_blocked`, `Subscription.blocked`).
- ✅ Import paths are explicit (`from haywire.core.marketstall import X`).
- ✅ Test fixtures use `tmp_path` consistently; the existing codebase pattern.
- ✅ Commits are small and frequent (one per task; some tasks split into multiple commits).
- ✅ The §14 rename table is fully exercised by tasks 2, 3, 5, 6, 13, 16, 21, 22, 23, 25, 26.
- ✅ Glossary updates happen in this plan (Task 29), not deferred — per inquisition Q12 decision.

---

## Execution Handoff

Plan complete and saved to `internals/plans/2026-05-21-marketstall-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
