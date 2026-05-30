# Marketstall First-Install Safety Modal — Slice 5 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Interpose a first-install safety modal between the user clicking Install and the actual `uv pip install`. The modal surfaces the haybale's source URL, lets the user verify before committing, and offers Block as a stronger alternative to Cancel — Block writes to the subscription's `blocked = []` array (already supported in foundation) and triggers a refresh, after which the apply_blocked filter (already wired in foundation) hides the haybale from AVAILABLE entirely.

**Architecture:** The foundation already does most of the heavy lifting: `record_block_on_source` writes the blocked field, `apply_blocked` filters during refresh, the `via` cache field records each haybale's source URL. Slice 5 ties the threads together: (1) a new `install_safety_modal` helper in `haywire.ui.modals`, (2) a `seen.toml` tracker for first-install scoping, (3) a wrapper around `_install_package` that consults seen.toml and gates the install on user confirmation, (4) a small "resolve via URL to subscription URL" helper for the Block button.

**Tech Stack:** Python 3.12, NiceGUI (UI), `haywire.core.marketstall` foundation API (`record_block_on_source`, `refresh`), `haywire.ui.modals` (`Popup`-based new helper). No new third-party deps.

**Spec reference:** [`internals/specs/marketstall-distribution.md`](../../speculatives/archive/marketstall-distribution.md) §7.4 (first-install safety modal). Inquisition Q9 + Q10a (blocked-list semantics; hide blocked from AVAILABLE; per-source blocking).

**Inquisition decisions this slice implements:** Q9 (the install-safety modal addition to the spec); Q10a (blocked haybales fully hidden from AVAILABLE — already done by foundation's `apply_blocked`); Q10b (per-source blocking — already enforced by foundation).

---

## Scope Boundary

**In scope:**
- New `install_safety_modal` helper in `haywire.ui.modals` — three-button modal (Cancel / Block / Install) with safety copy + source-URL link button.
- New `seen.toml` tracker module (`haywire.core.marketstall.seen`) — `is_seen(name) -> bool`, `mark_seen(name) -> None`. Lives at `~/.haywire/db/haybale-marketplace/seen.toml`.
- Wrap `_install_package` in the Library Overview Editor with a "should we show the safety modal?" check. Show modal when `not is_seen(name)`; skip when already seen.
- "Resolve via URL to subscription URL" helper — for the Block button, determine which `[[markets]]` or `[[stalls]]` entry owns this haybale, so `record_block_on_source` knows where to write.
- After Block: write the block + refresh the marketplace + re-render the Library Browser. The haybale should vanish from AVAILABLE on the next render (foundation's `apply_blocked` handles the hide).

**Out of scope (deferred):**
- Drift gate `min_version` lag check — slice 6.
- Update-available signal — slice 7.
- Per-haybale stall generator — slice 8.
- Glossary update for `seen.toml` — bundle into slice 8's docs sweep or a standalone glossary commit.

---

## File Structure

### New files (created)

- `packages/haywire-core/src/haywire/core/marketstall/seen.py` — `is_seen(name, *, seen_path=None)`, `mark_seen(name, *, seen_path=None)`. Simple TOML-backed set of haybale names.
- `packages/haywire-core/src/haywire/ui/modals/install_safety_modal.py` — `install_safety_modal(*, haybale_name, source_url, on_cancel, on_block, on_install)`. Three-button modal with safety copy.
- `tests/marketstall/test_seen.py` — unit tests for the seen.toml tracker.
- `tests/marketstall/test_install_safety_modal_logic.py` — unit tests for the "resolve via URL to subscription URL" helper (the modal UI itself isn't unit-testable, but the supporting logic is).

### Modified files

- `packages/haywire-core/src/haywire/core/marketstall/__init__.py` — export `is_seen`, `mark_seen`, and the new resolver helper.
- `packages/haywire-core/src/haywire/core/marketstall/helpers.py` — add `resolve_block_target(global_path, via_url) -> str | None`. Returns the URL of the subscription that owns a haybale, given its `via` field. Falls back to the parent aggregator's URL if no direct match (transitive case).
- `packages/haywire-core/src/haywire/ui/modals/__init__.py` — export `install_safety_modal`.
- `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py` — wrap the `_install_package` callsites in a `_install_with_safety_check` wrapper that shows the modal on first install.

### Files NOT touched in this slice (deferred)

- `library_browser_editor.py` — the blocked filter happens during refresh (foundation), no browser-side filtering needed.
- `refresh.py` — already applies `apply_blocked` per subscription.
- `helpers.py` `record_block_on_source` — already exists from foundation.

---

## Pre-flight Baseline

- [ ] **Step 0.1: Confirm worktree state**

Run from worktree:
```sh
git status
git rev-parse --short HEAD
git branch --show-current
```
Expected: clean tree on `feat/marketstall-install-safety` at HEAD `f10c1ac9`.

- [ ] **Step 0.2: Run the test suite as the baseline**

Run from worktree: `uv run pytest tests/ -m "not integration" -q`
Expected: `1403 passed, 1 skipped`.

- [ ] **Step 0.3: Run ruff and mypy as baseline**

```sh
uv run ruff check packages/haywire-core/src/haywire/core/marketstall packages/haywire-core/src/haywire/ui/modals barn/haybale-studio/haybale_studio/editors/library_overview_editor.py
uv run mypy packages/haywire-core/src/haywire/core/marketstall packages/haywire-core/src/haywire/ui barn/haybale-studio/haybale_studio
```
Both must be clean.

---

## Task 1: `seen.toml` tracker

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/seen.py`
- Create: `tests/marketstall/test_seen.py`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/__init__.py` (export)

Lightweight set-of-names tracker, TOML-backed. The file lives at `~/.haywire/db/haybale-marketplace/seen.toml` (under the same forward-reference path as the global marketplace). One section:

```toml
seen = ["haybale-foo", "haybale-bar"]
```

API:
- `is_seen(name: str, *, seen_path: Path | None = None) -> bool`
- `mark_seen(name: str, *, seen_path: Path | None = None) -> None`

The `seen_path` keyword arg is for tests (override the default path). Production code uses the default, which resolves to `~/.haywire/db/haybale-marketplace/seen.toml`.

- [ ] **Step 1.1: Write failing tests**

Write to `tests/marketstall/test_seen.py`:

```python
"""seen.toml tracker — spec §7.4 first-install scoping."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_is_seen_returns_false_when_file_missing(tmp_path: Path) -> None:
    from haywire.core.marketstall.seen import is_seen

    seen_path = tmp_path / "seen.toml"
    assert is_seen("haybale-foo", seen_path=seen_path) is False


@pytest.mark.unit
def test_mark_seen_creates_file(tmp_path: Path) -> None:
    from haywire.core.marketstall.seen import mark_seen, is_seen

    seen_path = tmp_path / "seen.toml"
    mark_seen("haybale-foo", seen_path=seen_path)

    assert seen_path.is_file()
    assert is_seen("haybale-foo", seen_path=seen_path) is True


@pytest.mark.unit
def test_mark_seen_is_idempotent(tmp_path: Path) -> None:
    from haywire.core.marketstall.seen import mark_seen, is_seen

    seen_path = tmp_path / "seen.toml"
    mark_seen("haybale-foo", seen_path=seen_path)
    mark_seen("haybale-foo", seen_path=seen_path)
    mark_seen("haybale-foo", seen_path=seen_path)

    # No duplicates.
    import toml
    data = toml.loads(seen_path.read_text())
    assert data.get("seen", []).count("haybale-foo") == 1


@pytest.mark.unit
def test_is_seen_distinguishes_names(tmp_path: Path) -> None:
    from haywire.core.marketstall.seen import mark_seen, is_seen

    seen_path = tmp_path / "seen.toml"
    mark_seen("haybale-foo", seen_path=seen_path)

    assert is_seen("haybale-foo", seen_path=seen_path) is True
    assert is_seen("haybale-bar", seen_path=seen_path) is False


@pytest.mark.unit
def test_mark_seen_preserves_existing_entries(tmp_path: Path) -> None:
    from haywire.core.marketstall.seen import mark_seen, is_seen

    seen_path = tmp_path / "seen.toml"
    mark_seen("haybale-foo", seen_path=seen_path)
    mark_seen("haybale-bar", seen_path=seen_path)
    mark_seen("haybale-baz", seen_path=seen_path)

    assert is_seen("haybale-foo", seen_path=seen_path) is True
    assert is_seen("haybale-bar", seen_path=seen_path) is True
    assert is_seen("haybale-baz", seen_path=seen_path) is True


@pytest.mark.unit
def test_is_seen_returns_false_on_malformed_file(tmp_path: Path) -> None:
    """A corrupt seen.toml fails closed: returns False (rather than crashing).

    Rationale: showing the safety modal once extra is harmless; crashing
    Install is not.
    """
    from haywire.core.marketstall.seen import is_seen

    seen_path = tmp_path / "seen.toml"
    seen_path.write_text("this is = not valid TOML [[")

    assert is_seen("haybale-foo", seen_path=seen_path) is False
```

- [ ] **Step 1.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_seen.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 1.3: Implement `seen.py`**

Write to `packages/haywire-core/src/haywire/core/marketstall/seen.py`:

```python
"""seen.toml tracker — spec §7.4 first-install scoping.

Records which haybale names the user has previously seen-and-installed on
this machine. Used by the Library Overview Editor's Install button to decide
whether to show the first-install safety modal.

File lives at ~/.haywire/db/haybale-marketplace/seen.toml. Schema:

    seen = ["haybale-foo", "haybale-bar"]

Per spec §7.4: scoped per-haybale-name (not per-version, not per-source).
Reinstall of a previously-installed-and-uninstalled haybale skips the modal
(the user already decided once).
"""

from __future__ import annotations

from pathlib import Path

import toml


def _default_seen_path() -> Path:
    """Production seen.toml location: ~/.haywire/db/haybale-marketplace/seen.toml."""
    return Path.home() / ".haywire" / "db" / "haybale-marketplace" / "seen.toml"


def _load(seen_path: Path) -> list[str]:
    """Return the seen list, or [] if file missing or malformed (fail closed)."""
    if not seen_path.is_file():
        return []
    try:
        data = toml.loads(seen_path.read_text(encoding="utf-8"))
    except toml.TomlDecodeError:
        return []
    seen = data.get("seen", [])
    if not isinstance(seen, list):
        return []
    return [s for s in seen if isinstance(s, str)]


def is_seen(name: str, *, seen_path: Path | None = None) -> bool:
    """True if `name` has been previously marked as seen on this machine."""
    path = seen_path if seen_path is not None else _default_seen_path()
    return name in _load(path)


def mark_seen(name: str, *, seen_path: Path | None = None) -> None:
    """Append `name` to the seen list. Idempotent (no duplicates)."""
    path = seen_path if seen_path is not None else _default_seen_path()
    seen = _load(path)
    if name in seen:
        return
    seen.append(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(toml.dumps({"seen": seen}), encoding="utf-8")
```

- [ ] **Step 1.4: Export from the package**

Edit `packages/haywire-core/src/haywire/core/marketstall/__init__.py`. Add to the existing imports block:

```python
from haywire.core.marketstall.seen import is_seen, mark_seen
```

And to the `__all__` list (anywhere in the install-safety / seen section):

```python
    # Install-safety scoping
    "is_seen",
    "mark_seen",
```

- [ ] **Step 1.5: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_seen.py -v`
Expected: 6 passed.

- [ ] **Step 1.6: Run the full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: 1403 baseline + 6 new = 1409.

- [ ] **Step 1.7: Lint check**

Run:
```sh
uv run ruff check packages/haywire-core/src/haywire/core/marketstall/seen.py tests/marketstall/test_seen.py packages/haywire-core/src/haywire/core/marketstall/__init__.py
uv run mypy packages/haywire-core/src/haywire/core/marketstall/seen.py packages/haywire-core/src/haywire/core/marketstall/__init__.py
```
Both clean.

- [ ] **Step 1.8: Commit**

```sh
git add packages/haywire-core/src/haywire/core/marketstall/seen.py \
        packages/haywire-core/src/haywire/core/marketstall/__init__.py \
        tests/marketstall/test_seen.py
git commit -m "feat(marketstall): add seen.toml tracker for first-install scoping (spec §7.4)"
```

---

## Task 2: `resolve_block_target` helper

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/marketstall/helpers.py`
- Modify: `packages/haywire-core/src/haywire/core/marketstall/__init__.py` (export)
- Create: `tests/marketstall/test_resolve_block_target.py`

The Block button needs to know which subscription's `blocked` array to write to. The haybale's `via` field is the URL it was fetched from:
- **Direct stall case**: `via == stall.url` for some `[[stalls]]` entry → block goes on that stall.
- **Transitive market case**: `via` is a discovered stall URL (not directly subscribed). Falls back to the parent `[[markets]]` URL — the only entry the user controls.
- **Inline haybale case**: `via` is empty (haybale was inline in the global file, not from any subscription). Cannot block; return None.

`record_block_on_source` (existing foundation helper) takes a `source_url` and searches both lists; if there's no match, it silently no-ops. We need a smarter helper that returns the correct URL to block on, so the UI can either block successfully OR surface a clear error.

API:
```python
def resolve_block_target(global_path: Path, via_url: str) -> str | None:
    """Return the URL of the subscription that should receive a block for `via_url`.

    - If via_url matches a [[stalls]] entry → return that stall.url (direct).
    - If via_url matches a [[markets]] entry → return that market.url (rare).
    - If no direct match, return the FIRST [[markets]].url (transitive — the
      user only controls the aggregator).
    - If no [[markets]] subscriptions exist, return None (cannot block).
    """
```

- [ ] **Step 2.1: Write failing tests**

Write to `tests/marketstall/test_resolve_block_target.py`:

```python
"""resolve_block_target — pick the right subscription URL for Block."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_resolve_block_target_returns_stall_for_direct(tmp_path: Path) -> None:
    """When via matches a [[stalls]] URL, block goes on that stall."""
    from haywire.core.marketstall import (
        add_stall_subscription_to_global,
        resolve_block_target,
    )

    global_path = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(global_path, "https://alice.example/marketstall.toml")

    target = resolve_block_target(global_path, "https://alice.example/marketstall.toml")
    assert target == "https://alice.example/marketstall.toml"


@pytest.mark.unit
def test_resolve_block_target_returns_market_for_direct_market(tmp_path: Path) -> None:
    """If via somehow matches a [[markets]] entry directly, block goes there."""
    from haywire.core.marketstall import (
        add_market_subscription_to_global,
        resolve_block_target,
    )

    global_path = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(global_path, "https://agg.example/marketplace.toml")

    target = resolve_block_target(global_path, "https://agg.example/marketplace.toml")
    assert target == "https://agg.example/marketplace.toml"


@pytest.mark.unit
def test_resolve_block_target_falls_back_to_aggregator_for_transitive(tmp_path: Path) -> None:
    """Transitive: via is a discovered stall, not a direct subscription.
    Fallback to the aggregator's [[markets]] URL (the only one the user controls)."""
    from haywire.core.marketstall import (
        add_market_subscription_to_global,
        resolve_block_target,
    )

    global_path = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(global_path, "https://agg.example/marketplace.toml")

    # via is a stall the user didn't directly subscribe to.
    target = resolve_block_target(
        global_path, "https://going-haywire.github.io/haywire/stalls/haybale-foo.toml"
    )
    assert target == "https://agg.example/marketplace.toml"


@pytest.mark.unit
def test_resolve_block_target_returns_none_when_no_subscriptions(tmp_path: Path) -> None:
    """With no [[markets]] or [[stalls]] entries, no block can be recorded."""
    from haywire.core.marketstall import resolve_block_target

    global_path = tmp_path / "marketplace.toml"
    # Don't write anything — file is missing.

    target = resolve_block_target(global_path, "https://x.example/stall.toml")
    assert target is None


@pytest.mark.unit
def test_resolve_block_target_returns_none_for_empty_via(tmp_path: Path) -> None:
    """Empty via (inline haybale from global file) returns None."""
    from haywire.core.marketstall import (
        add_market_subscription_to_global,
        resolve_block_target,
    )

    global_path = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(global_path, "https://agg.example/marketplace.toml")

    target = resolve_block_target(global_path, "")
    assert target is None


@pytest.mark.unit
def test_resolve_block_target_prefers_direct_stall_over_aggregator(tmp_path: Path) -> None:
    """Direct stall subscription wins over fallback to aggregator."""
    from haywire.core.marketstall import (
        add_market_subscription_to_global,
        add_stall_subscription_to_global,
        resolve_block_target,
    )

    global_path = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(global_path, "https://agg.example/marketplace.toml")
    add_stall_subscription_to_global(global_path, "https://alice.example/marketstall.toml")

    target = resolve_block_target(global_path, "https://alice.example/marketstall.toml")
    assert target == "https://alice.example/marketstall.toml"
```

- [ ] **Step 2.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_resolve_block_target.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_block_target'`.

- [ ] **Step 2.3: Implement `resolve_block_target`**

In `packages/haywire-core/src/haywire/core/marketstall/helpers.py`, add at the end:

```python
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
```

- [ ] **Step 2.4: Export from the package**

Edit `packages/haywire-core/src/haywire/core/marketstall/__init__.py`. Add `resolve_block_target` to both the imports from `.helpers` and the `__all__` list.

- [ ] **Step 2.5: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_resolve_block_target.py -v`
Expected: 6 passed.

- [ ] **Step 2.6: Run the full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: 1409 + 6 = 1415.

- [ ] **Step 2.7: Lint check**

```sh
uv run ruff check packages/haywire-core/src/haywire/core/marketstall/helpers.py packages/haywire-core/src/haywire/core/marketstall/__init__.py tests/marketstall/test_resolve_block_target.py
uv run mypy packages/haywire-core/src/haywire/core/marketstall/helpers.py
```
Both clean.

- [ ] **Step 2.8: Commit**

```sh
git add packages/haywire-core/src/haywire/core/marketstall/helpers.py packages/haywire-core/src/haywire/core/marketstall/__init__.py tests/marketstall/test_resolve_block_target.py
git commit -m "feat(marketstall): add resolve_block_target helper for Block button (spec §7.4)"
```

---

## Task 3: `install_safety_modal` UI helper

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/modals/install_safety_modal.py`
- Modify: `packages/haywire-core/src/haywire/ui/modals/__init__.py` (export)

A new modal helper that mirrors `confirm_modal`'s shape but adds:
- A source-URL link button (opens `source_url` in a new tab; disabled if `source_url` is empty).
- A third button (`Block`) between Cancel and Install.
- Safety copy from spec §7.4.

Title: `f"Install {haybale_name}?"`.

Callbacks:
- `on_cancel: Callable[[], None] | None = None` — Cancel button or backdrop/escape close.
- `on_block: Callable[[], None]` — Block button.
- `on_install: Callable[[], None]` — Install button.

The modal IS unit-testable to a limited extent (importable, instantiable), but the click handlers and visual layout aren't easily testable in the conventional sense. The UI is validated by functional smoke testing.

- [ ] **Step 3.1: Write the modal**

Write to `packages/haywire-core/src/haywire/ui/modals/install_safety_modal.py`:

```python
"""Install safety modal — spec §7.4 first-install confirmation.

Three-button modal interposing between Install click and actual `uv pip install`.
Cancel / Block / Install. Includes safety copy and a source-URL link button.
"""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.ui.components.popup import Popup


_SAFETY_COPY = (
    "You are about to install third-party code. You are responsible for "
    "verifying this library is safe before installing. Review the source "
    "first if you don't recognize the author."
)


def install_safety_modal(
    *,
    haybale_name: str,
    source_url: str,
    on_install: Callable[[], None],
    on_block: Callable[[], None],
    on_cancel: Callable[[], None] | None = None,
) -> Popup:
    """Open the first-install safety modal and return the opened Popup.

    Args:
        haybale_name: The haybale's distribution name (e.g. "haybale-foo").
        source_url: The haybale's source_url field. If empty, the source-link
            button is disabled with explanatory text.
        on_install: Called when the user clicks Install. Popup closes after.
        on_block: Called when the user clicks Block. Popup closes after.
        on_cancel: Called when the user cancels (Cancel button, backdrop click,
            escape). Optional.
    """
    popup = Popup(
        title=f"Install {haybale_name}?",
        width="420px",
        closable=True,
        backdrop_click_close=True,
        escape_close=True,
        backdrop_color="transparent",
    )

    decided = {"value": False}

    if on_cancel is not None:

        def _maybe_cancel() -> None:
            if not decided["value"]:
                on_cancel()

        popup.on_close(_maybe_cancel)

    with popup:
        ui.label(_SAFETY_COPY).classes("text-sm")

        # Source link row.
        with ui.row().classes("w-full items-center mt-3 gap-2"):
            if source_url:
                ui.button(
                    "Review source",
                    icon="open_in_new",
                    on_click=lambda: ui.run_javascript(f"window.open({source_url!r}, '_blank')"),
                ).props("flat dense size=sm")
                ui.label(source_url).classes("text-xs hw-text-dim font-mono truncate")
            else:
                ui.button(
                    "Review source",
                    icon="open_in_new",
                ).props("flat dense size=sm disable").tooltip("No source URL provided")
                ui.label("(no source URL provided)").classes("text-xs hw-text-dim italic")

        # Action buttons.
        def _do_install() -> None:
            decided["value"] = True
            on_install()
            popup.close()

        def _do_block() -> None:
            decided["value"] = True
            on_block()
            popup.close()

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            ui.button("Block", on_click=_do_block).props("flat dense").style(
                "color: var(--hw-warning);"
            )
            ui.button("Install", on_click=_do_install).props("flat dense").style(
                "color: var(--hw-positive);"
            )

    popup.open()
    return popup
```

- [ ] **Step 3.2: Export from the modals package**

Edit `packages/haywire-core/src/haywire/ui/modals/__init__.py`. Add:

```python
from haywire.ui.modals.install_safety_modal import install_safety_modal
```

And to `__all__`:

```python
    "install_safety_modal",
```

- [ ] **Step 3.3: Write a smoke import test**

Append to `tests/marketstall/test_install_safety_modal_logic.py` (will be created in Task 4 — for now, just write the file with this single test):

```python
"""Install safety modal — integration logic + smoke import."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_install_safety_modal_is_importable() -> None:
    """The modal helper must be importable from haywire.ui.modals."""
    from haywire.ui.modals import install_safety_modal

    assert callable(install_safety_modal)
```

- [ ] **Step 3.4: Run the test**

Run: `uv run pytest tests/marketstall/test_install_safety_modal_logic.py -v`
Expected: 1 passed.

- [ ] **Step 3.5: Lint check**

```sh
uv run ruff check packages/haywire-core/src/haywire/ui/modals/install_safety_modal.py packages/haywire-core/src/haywire/ui/modals/__init__.py
uv run mypy packages/haywire-core/src/haywire/ui/modals/install_safety_modal.py
```
Both clean.

- [ ] **Step 3.6: Commit**

```sh
git add packages/haywire-core/src/haywire/ui/modals/install_safety_modal.py packages/haywire-core/src/haywire/ui/modals/__init__.py tests/marketstall/test_install_safety_modal_logic.py
git commit -m "feat(modals): add install_safety_modal (Cancel/Block/Install with safety copy)"
```

## Discipline

- The modal uses `ui.run_javascript("window.open(...)")` for the source-URL link, NOT a plain anchor — anchors don't reliably open in new tabs in NiceGUI. JS `window.open` works.
- The "disable" prop on the Source button when `source_url == ""` uses Quasar's `disable` prop (different from `disabled` attribute). The tooltip explains the disabled state.
- The `decided` dict pattern guards against the on_close handler double-firing when on_install or on_block also explicitly close the popup. Mirrors the existing `confirm_modal` pattern.

---

## Task 4: Wrap Install in the safety check

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py`
- Modify: `tests/marketstall/test_install_safety_modal_logic.py`

The Library Overview Editor's `_install_package` method is called from two sites:
- Line ~489 (main Install button)
- Line ~1439 (`install_selected` inside `_open_version_picker`)

We need to interpose a "should we show the safety modal?" check at BOTH sites. Create a new method `_install_with_safety_check` that:
1. Looks up `is_seen(haybale_name)`. If True, call `_install_package` directly (skip modal).
2. If False, open `install_safety_modal` with three callbacks:
   - `on_cancel` → notify, no change.
   - `on_block` → call `resolve_block_target(global_path, via_url)`; if returns a URL, call `record_block_on_source(global_path, source_url=url, haybale_name=name)`; trigger a refresh; re-render the Library Browser.
   - `on_install` → call `mark_seen(name)`; then call `_install_package` to proceed.

The Block button needs access to the marketplace state (for `record_block_on_source` and refresh trigger). Use `context.app_data[MarketplaceState]`.

The `via_url` comes from `marketplace_pkg.via` — the cache field set during refresh. For inline haybales (no via), `resolve_block_target` returns None and Block notifies "Cannot block: this haybale is not from a subscription."

- [ ] **Step 4.1: Write the wrapper integration test**

Append to `tests/marketstall/test_install_safety_modal_logic.py`:

```python
@pytest.mark.unit
def test_record_block_via_resolve_target(tmp_path) -> None:
    """End-to-end: resolve_block_target + record_block_on_source writes the block."""
    from pathlib import Path
    from haywire.core.marketstall import (
        add_stall_subscription_to_global,
        record_block_on_source,
        resolve_block_target,
        parse_global_marketplace,
    )

    global_path = tmp_path / "marketplace.toml"
    add_stall_subscription_to_global(global_path, "https://alice.example/marketstall.toml")

    via = "https://alice.example/marketstall.toml"  # direct subscription
    target = resolve_block_target(global_path, via)
    assert target is not None
    record_block_on_source(global_path, source_url=target, haybale_name="haybale-untrusted")

    mf = parse_global_marketplace(global_path)
    assert mf.stalls[0].blocked == ["haybale-untrusted"]


@pytest.mark.unit
def test_record_block_via_aggregator_fallback(tmp_path) -> None:
    """Transitive case: via doesn't match any subscription; fallback to aggregator."""
    from haywire.core.marketstall import (
        add_market_subscription_to_global,
        record_block_on_source,
        resolve_block_target,
        parse_global_marketplace,
    )

    global_path = tmp_path / "marketplace.toml"
    add_market_subscription_to_global(global_path, "https://agg.example/marketplace.toml")

    via = "https://going-haywire.github.io/haywire/stalls/haybale-foo.toml"  # discovered, not subscribed
    target = resolve_block_target(global_path, via)
    assert target == "https://agg.example/marketplace.toml"

    record_block_on_source(global_path, source_url=target, haybale_name="haybale-foo")

    mf = parse_global_marketplace(global_path)
    assert mf.markets[0].blocked == ["haybale-foo"]
```

- [ ] **Step 4.2: Run the tests to confirm they pass**

These compose existing helpers, so they should pass immediately. Run: `uv run pytest tests/marketstall/test_install_safety_modal_logic.py -v`
Expected: 3 passed (the smoke test from Task 3 + these 2).

- [ ] **Step 4.3: Wrap the install button**

In `barn/haybale-studio/haybale_studio/editors/library_overview_editor.py`, find the clean-install button (the `else` branch of the Install button dispatch, around line 482-494):

```python
                            else:
                                ui.button(
                                    "Install",
                                    icon=hui.icon.download,
                                    on_click=lambda e,
                                    spec=marketplace_pkg.install_spec,
                                    n=marketplace_pkg.name,
                                    m=manager,
                                    ctx=context: (self._install_package(spec, n, e.sender, m, ctx)),
                                ).props("color=positive size=sm")
```

Change the `on_click` to use the wrapper:

```python
                            else:
                                ui.button(
                                    "Install",
                                    icon=hui.icon.download,
                                    on_click=lambda e,
                                    pkg=marketplace_pkg,
                                    m=manager,
                                    ctx=context: (self._install_with_safety_check(pkg, e.sender, m, ctx)),
                                ).props("color=positive size=sm")
```

Then add `_install_with_safety_check` to `LibraryOverviewEditor` (near `_install_package`):

```python
    def _install_with_safety_check(
        self,
        pkg: Haybale,
        button,
        manager,
        context: "SessionContext",
    ):
        """Interpose the spec §7.4 safety modal before _install_package.

        Skip the modal when the haybale name is already in seen.toml
        (the user previously decided to install it, possibly later uninstalled,
        so re-install doesn't re-prompt).
        """
        from haywire.core.marketstall import (
            is_seen,
            mark_seen,
            record_block_on_source,
            resolve_block_target,
        )
        from haywire.ui.modals import install_safety_modal

        from haybale_studio.state.marketplace_state import MarketplaceState

        # Skip the modal if we've already shown it for this haybale name once.
        if is_seen(pkg.name):
            asyncio.ensure_future(
                self._install_package(pkg.install_spec, pkg.name, button, manager, context)
            )
            return

        # Build callbacks that capture the necessary state.
        def _on_install() -> None:
            mark_seen(pkg.name)
            asyncio.ensure_future(
                self._install_package(pkg.install_spec, pkg.name, button, manager, context)
            )

        def _on_block() -> None:
            # Resolve which subscription owns this haybale, then record the block.
            state = context.app_data.get(MarketplaceState) if context.app_data else None
            if state is None:
                ui.notify("Marketplace state not available", type="warning")
                return
            global_path = state._global_path()
            target = resolve_block_target(global_path, pkg.via)
            if target is None:
                ui.notify(
                    f"Cannot block {pkg.name}: not from a subscription you can edit.",
                    type="warning",
                )
                return
            try:
                record_block_on_source(global_path, source_url=target, haybale_name=pkg.name)
            except Exception as exc:
                logger.exception("Failed to record block")
                ui.notify(f"Failed to block: {exc}", type="negative")
                return
            ui.notify(f"Blocked {pkg.name} from {target}", type="positive")
            # Trigger refresh so the apply_blocked filter hides the haybale immediately.
            state.refresh()
            self._notify_library_changed(context)

        def _on_cancel() -> None:
            ui.notify(f"Install of {pkg.name} cancelled", type="info")

        install_safety_modal(
            haybale_name=pkg.name,
            source_url=pkg.source_url or "",
            on_install=_on_install,
            on_block=_on_block,
            on_cancel=_on_cancel,
        )
```

Note the `asyncio.ensure_future(...)` wrapper around `_install_package` — that method is `async`, so we have to schedule it explicitly when calling from a sync callback.

- [ ] **Step 4.4: Wrap the version-picker Install button too**

Find `_open_version_picker` (around line 1407) and its `install_selected` async function (around line 1433):

```python
            async def install_selected(e):
                selected = version_select.value
                if not selected or selected in ("Loading…", "(unavailable)"):
                    return
                dialog.close()
                spec = manager.build_versioned_spec(pkg, selected)
                await self._install_package(spec, pkg.name, None, manager, context)
```

Add the safety check before the install call:

```python
            async def install_selected(e):
                selected = version_select.value
                if not selected or selected in ("Loading…", "(unavailable)"):
                    return
                dialog.close()
                spec = manager.build_versioned_spec(pkg, selected)
                # Reuse the safety wrapper but with the versioned spec.
                # We pass a synthetic Haybale-like copy to avoid mutating pkg.
                # Note: pkg keeps its original install_spec for the safety modal
                # context; the actual install uses the versioned spec.
                from dataclasses import replace
                versioned_pkg = replace(pkg, install_spec=spec)
                self._install_with_safety_check(versioned_pkg, None, manager, context)
```

The `dataclasses.replace` is needed because `Haybale` is a frozen dataclass — we can't just mutate `pkg.install_spec` in place. Verify the Haybale's frozen status: it's actually **NOT** frozen (`@dataclass` without `frozen=True` per the foundation). But `replace()` works fine on both frozen and non-frozen dataclasses, and it's clearer.

Actually re-checking — `Haybale` is `@dataclass` (mutable). So we COULD mutate, but `replace()` is cleaner. Keep using `replace()`.

- [ ] **Step 4.5: Run the full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: 1415 + 0 new = 1415 (the integration tests in test_install_safety_modal_logic.py were already counted in Task 4.2).

- [ ] **Step 4.6: Lint check**

```sh
uv run ruff check barn/haybale-studio/haybale_studio/editors/library_overview_editor.py
uv run mypy barn/haybale-studio/haybale_studio
```
Both clean.

- [ ] **Step 4.7: Verify the file still imports cleanly**

Run: `uv run python -c "import haybale_studio.editors.library_overview_editor; print('OK')"`
Expected: `OK`.

- [ ] **Step 4.8: Commit**

```sh
git add barn/haybale-studio/haybale_studio/editors/library_overview_editor.py tests/marketstall/test_install_safety_modal_logic.py
git commit -m "feat(library-overview): show install_safety_modal on first install (spec §7.4)"
```

## Discipline

- The `_install_with_safety_check` wrapper is sync (returns None); it schedules `_install_package` (async) via `asyncio.ensure_future` when needed.
- `is_seen` / `mark_seen` use the default `~/.haywire/db/haybale-marketplace/seen.toml` location (no path override in production).
- Block triggers `state.refresh()` synchronously — this is fast for empty/small marketplaces; for large ones it might briefly block the UI. Acceptable for now.
- `pkg.source_url or ""` defends against haybales with no source declaration. The modal shows "(no source URL provided)" in that case.

---

## Task 5: Final verification sweep + smoke test instructions

- [ ] **Step 5.1: Run the full test suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: 1415 passed.

- [ ] **Step 5.2: Run ruff and mypy**

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-studio/haybale_studio
```
All clean.

- [ ] **Step 5.3: Smoke test (manual — requires `uv run haywire` + a haybale to install)**

```sh
# Start the app from the worktree-aware project:
cd /Users/mfroehli/Desktop/test/slice4-smoke   # or create a fresh slice5-smoke project
uv run haywire

# To trigger the safety modal, you need a haybale in AVAILABLE that isn't installed yet.
# The easiest way: subscribe to a real marketstall via Add Source, then see the haybales appear.
# For testing, you can paste a TOML block via Add Source:

# 1. Library Browser → "Add source"
# 2. Paste this TOML block:
#    [[haybales]]
#    name = "haybale-smoketest"
#    min_version = "0.0.1"
#    source = "git"
#    install_spec = "haybale-smoketest @ git+https://example.com/fake.git"
#    source_url = "https://github.com/example/haybale-smoketest"

# 3. After subscribe + auto-refresh, haybale-smoketest appears in AVAILABLE.
# 4. Click haybale-smoketest → Library Overview Editor opens.
# 5. Click "Install" → SAFETY MODAL should appear with:
#    - Title: "Install haybale-smoketest?"
#    - Safety copy
#    - "Review source" button (enabled, links to github.com/example/haybale-smoketest)
#    - Three buttons: Cancel, Block, Install
# 6. Click Cancel → modal closes, info notification "Install of haybale-smoketest cancelled".
# 7. Click Install again → modal reappears (still first install).
# 8. Click Install → mark_seen happens, real uv pip install runs (will fail because git URL is fake, but that's expected).
# 9. Click the SAME haybale's Install button again → modal does NOT appear (seen.toml records it).
# 10. Verify: cat ~/.haywire/db/haybale-marketplace/seen.toml
#     Expected: seen = ["haybale-smoketest"]

# Block flow:
# 11. Add a different test haybale (e.g. haybale-testblock).
# 12. Click Install → modal appears.
# 13. Click Block → notification "Blocked haybale-testblock from ...", haybale vanishes from AVAILABLE.
# 14. Verify: cat ~/.haywire/db/haybale-marketplace/marketplace.toml
#     Expected: the matching [[stalls]] entry has blocked = ["haybale-testblock"].
```

- [ ] **Step 5.4: Review the diff and commit summary**

Run: `git log --oneline f10c1ac9..HEAD`
Run: `git diff f10c1ac9 --shortstat`

Expected: 4 commits (Tasks 1-4), ~6 files changed, ~400-500 line delta.

---

## Spec coverage check

| Spec § | Covered by | Notes |
|---|---|---|
| §7.4 first-install safety modal | Tasks 3, 4 | Three-button modal interposes Install |
| §7.4 source link button | Task 3 | `ui.run_javascript("window.open(...)")` |
| §7.4 Block writes to `blocked = []` | Tasks 2, 4 | resolve_block_target + record_block_on_source |
| §7.4 seen.toml first-install scoping | Task 1 | is_seen + mark_seen |
| §7.4 hide blocked from AVAILABLE | (foundation already) | apply_blocked runs during refresh |

**Not covered (deferred):**

| Spec § | Deferred to slice |
|---|---|
| §10 Update-available signal | 7 |
| §12 Drift gate lag check | 6 |
| §11 Per-haybale stall generator | 8 |

---

## Self-Review notes

- ✅ Every step has complete code; no "TBD".
- ✅ Names referenced across tasks: `is_seen`, `mark_seen`, `resolve_block_target`, `install_safety_modal`, `_install_with_safety_check`. All defined where first used and referenced consistently.
- ✅ TDD discipline: failing tests before implementation in Tasks 1, 2.
- ✅ Task 3's modal has a smoke-import test only; full behavior tested via Task 5 manual smoke.
- ✅ Foundation work reused: `record_block_on_source` (slice 1), `apply_blocked` filter in `refresh()` (slice 1), `Haybale.via` and `Haybale.source_url` fields (slice 1).
- ✅ Tasks 1 and 2 commit in either order (independent). Tasks 3 then 4 depend on them.

---

## Execution Handoff

Plan saved to `internals/plans/2026-05-23-marketstall-install-safety.md`. Three execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task, quiet-mode reporting. Estimated 4-5 dispatches.

**2. Inline Execution** — Execute Tasks 1-4 in this session.

**3. Inquisition first** — If the `resolve_block_target` transitive fallback (Task 2) or the seen.toml fail-closed semantic feels under-defined.

Which approach?
