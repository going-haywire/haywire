# Marketstall URL Distribution UI — Slice 3 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the Add Source dialog into a single input field that accepts all four input forms from spec §4.2 (blob URL, raw URL, plain TOML URL, pasted TOML block), rejects bare repo URLs, body-shape-detects to write the subscription into the correct list (`[[markets]]` vs `[[stalls]]`), auto-refreshes after subscribe. Surface provenance in the Library Browser rows so users can see whether a haybale arrived directly from a `[[stalls]]` subscription or transitively "via aggregator" from a `[[markets]]`.

**Architecture:** The §4.3 resolution algorithm (classify → fetch → parse → decide subscription type → write) lives in `haywire.core.marketstall` as a pure helper (`resolve_and_subscribe`). The dialog becomes a thin UI wrapper that calls the helper, renders errors as `ui.notify`, and chains into the existing conflict-resolution prompt. The Library Browser reads each haybale's `via` cache field to render the provenance affordance.

**Tech Stack:** Python 3.12, NiceGUI (UI framework — see [.insights/feedback_nicegui_*](../../.insights/) for traps), `haywire.core.marketstall` foundation API, `pytest`. No new third-party deps.

**Spec reference:** [`internals/specs/marketstall-distribution.md`](../speculatives/archive/marketstall-distribution.md). §4.2 (four input forms), §4.3 (resolution algorithm), §7.1 (Add Source dialog), §7.4 (provenance display in Library Browser — the install-safety modal IS slice 5; only the provenance label is in scope here).

**Inquisition decisions this slice implements:** Q4 (drop bare repo URL form 3 — already in url_resolution.py from foundation), Q9 (provenance display — the "via aggregator" affordance; install-safety modal is slice 5).

---

## Scope Boundary

**In scope:**
- One-field Add Source dialog with four input forms.
- Body-shape detection (markets-or-stalls subscription).
- Pasted TOML block → write file to `~/.haywire/db/haybale-marketplace/stalls/<dist-name>.toml`, reference as `file://`.
- Bare-repo-URL rejection with the §4.2 error message in the UI.
- Provenance label in Library Browser rows showing `from {host}` (direct stall) or `via {host}` (transitive market).
- Auto-refresh after successful subscribe (already wired via existing `on_added` callback — verify, don't reimplement).

**Out of scope (deferred):**
- First-install safety modal with Cancel/Block/Install buttons — slice 5.
- OS multi-select dialog + Install button OS gating — slice 4.
- Update-available signal (▲ + Update button) — slice 7.
- Drift gate `min_version` lag check — slice 6.

---

## File Structure

### New files (created)

- `packages/haywire-core/src/haywire/core/marketstall/subscribe.py` — `resolve_and_subscribe(global_path, user_input, *, paste_dir)` orchestration; `SubscribeResult` dataclass; `SubscribeError` exception class hierarchy.
- `tests/marketstall/test_subscribe.py` — unit tests for `resolve_and_subscribe` across all four input forms + error cases.
- `tests/test_library_browser_provenance.py` — tests for the provenance label derivation helper.

### Modified files

- `packages/haywire-core/src/haywire/core/marketstall/__init__.py` — export `resolve_and_subscribe`, `SubscribeResult`, `SubscribeError`, `subscribe_kind`.
- `barn/haybale-studio/haybale_studio/editors/library_marketplace_dialog.py` — rewrite to single-field dialog; remove the dual-tab `_handle_add_marketplace` / `_handle_add_marketstall` split; route through `resolve_and_subscribe`.
- `barn/haybale-studio/haybale_studio/editors/library_browser_editor.py` — extend `_library_item` to render provenance label from `via` field.

### Files NOT touched in this slice (deferred)

- `library_overview_editor.py` — slice 4 (OS multi-select).
- `host_providers/`, `url_resolution.py`, `parsing.py`, `refresh.py` — foundation already complete; no changes.

---

## Pre-flight Baseline

- [ ] **Step 0.1: Confirm worktree state**

Run from worktree:
```sh
git status
git rev-parse --short HEAD
git branch --show-current
```
Expected: clean tree on `feat/marketstall-url-distribution` at HEAD `c16ec01c`.

- [ ] **Step 0.2: Run the existing test suite as the baseline**

Run from worktree: `uv run pytest tests/ -m "not integration" -q`
Expected: `1377 passed, 1 skipped`. Record any deviation.

- [ ] **Step 0.3: Run ruff and mypy as baseline**

Run from worktree:
```sh
uv run ruff check barn/haybale-studio/haybale_studio/editors/library_marketplace_dialog.py barn/haybale-studio/haybale_studio/editors/library_browser_editor.py packages/haywire-core/src/haywire/core/marketstall
uv run mypy barn/haybale-studio/haybale_studio packages/haywire-core/src/haywire/core/marketstall
```
Both must be clean.

---

## Task 1: `subscribe.py` — `resolve_and_subscribe` orchestrator

**Files:**
- Create: `packages/haywire-core/src/haywire/core/marketstall/subscribe.py`
- Create: `tests/marketstall/test_subscribe.py`

The §4.3 algorithm currently lives in two places: `classify_input` (foundation) does steps 1-2; the rest (fetch, parse, decide subscription type, write) is duplicated piecemeal in the dialog handlers and in tests. This task moves the full algorithm into one pure function that the UI can call thinly.

**Algorithm (spec §4.3, post-inquisition):**
1. Call `classify_input(user_input)` → `ClassifiedInput`.
2. If form is `PASTED_BLOCK`: parse the body, require `[[haybales]]`, extract the first haybale's `name` to derive `<dist-name>`, write the block to `<paste_dir>/<dist-name>.toml`, reset `ClassifiedInput` to `PLAIN_TOML_URL` with `fetch_url=persist_url="file://<absolute path>"`.
3. Fetch via `fetch_with_cache_fallback(fetch_url)`. `RemoteFetchError` → wrap as `SubscribeError`.
4. Parse the body shape:
   - Contains `[[markets]]` or `[[stalls]]` (with/without inline `[[haybales]]`) → it's a marketplace. Add via `add_market_subscription_to_global`.
   - Contains `[[haybales]]` only → it's a marketstall. Add via `add_stall_subscription_to_global`.
   - Contains neither → `SubscribeError("Body is neither a marketplace nor a marketstall")`.
5. Return `SubscribeResult(kind: Literal["market", "stall"], persist_url, body)`.

The caller (dialog) handles conflict-resolution prompt + auto-refresh after `resolve_and_subscribe` returns.

`SubscribeError` is a thin wrapper. The existing `BareRepoUrlRejectedError` propagates as-is; callers can catch both `BareRepoUrlRejectedError` and `SubscribeError` to render distinct messages.

- [ ] **Step 1.1: Write failing tests**

Write to `tests/marketstall/test_subscribe.py`:

```python
"""resolve_and_subscribe — spec §4.3 orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_subscribe_marketstall_blob_url(tmp_path: Path) -> None:
    """A blob URL pointing at a marketstall (haybales only) → [[stalls]] entry."""
    from haywire.core.marketstall import resolve_and_subscribe
    from haywire.core.marketstall.parsing import parse_global_marketplace

    global_path = tmp_path / "marketplace.toml"
    paste_dir = tmp_path / "stalls"

    body = '[[haybales]]\nname = "haybale-foo"\nmin_version = "0.1.0"\n'
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = body.encode()
        result = resolve_and_subscribe(
            global_path,
            "https://github.com/alice/cool-libs/blob/main/marketstall.toml",
            paste_dir=paste_dir,
            cache_dir=tmp_path / "cache",
        )

    assert result.kind == "stall"
    assert result.persist_url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"

    mf = parse_global_marketplace(global_path)
    assert len(mf.stalls) == 1
    assert mf.stalls[0].url == result.persist_url


@pytest.mark.unit
def test_subscribe_marketplace_with_inline_haybales(tmp_path: Path) -> None:
    """A body with [[markets]] (or [[stalls]]) is a marketplace → [[markets]] entry."""
    from haywire.core.marketstall import resolve_and_subscribe
    from haywire.core.marketstall.parsing import parse_global_marketplace

    global_path = tmp_path / "marketplace.toml"

    body = (
        '[[stalls]]\n'
        'url = "https://other.example/marketstall.toml"\n'
        'ignores = []\n'
        'doubles = []\n'
        'blocked = []\n'
        '\n'
        '[[haybales]]\n'
        'name = "haybale-inline"\n'
        'min_version = "0.1.0"\n'
    )
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = body.encode()
        result = resolve_and_subscribe(
            global_path,
            "https://aggregator.example/marketplace.toml",
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )

    assert result.kind == "market"

    mf = parse_global_marketplace(global_path)
    assert len(mf.markets) == 1


@pytest.mark.unit
def test_subscribe_marketplace_with_markets_only(tmp_path: Path) -> None:
    """A body with only [[markets]] (no [[stalls]], no [[haybales]]) is still a marketplace."""
    from haywire.core.marketstall import resolve_and_subscribe
    from haywire.core.marketstall.parsing import parse_global_marketplace

    global_path = tmp_path / "marketplace.toml"

    body = '[[markets]]\nurl = "https://x.example/m.toml"\nignores = []\ndoubles = []\nblocked = []\n'
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = body.encode()
        result = resolve_and_subscribe(
            global_path,
            "https://aggregator.example/marketplace.toml",
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )

    assert result.kind == "market"

    mf = parse_global_marketplace(global_path)
    assert len(mf.markets) == 1


@pytest.mark.unit
def test_subscribe_raw_url_persists_canonical_blob(tmp_path: Path) -> None:
    """A raw URL is fetched as-is but persisted in canonical blob form."""
    from haywire.core.marketstall import resolve_and_subscribe
    from haywire.core.marketstall.parsing import parse_global_marketplace

    global_path = tmp_path / "marketplace.toml"

    body = '[[haybales]]\nname = "haybale-foo"\nmin_version = "0.1.0"\n'
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = body.encode()
        result = resolve_and_subscribe(
            global_path,
            "https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml",
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )

    assert result.persist_url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    mf = parse_global_marketplace(global_path)
    assert mf.stalls[0].url == result.persist_url


@pytest.mark.unit
def test_subscribe_plain_toml_url(tmp_path: Path) -> None:
    """A plain TOML URL is fetched as-is and persisted as-is."""
    from haywire.core.marketstall import resolve_and_subscribe

    global_path = tmp_path / "marketplace.toml"

    body = '[[haybales]]\nname = "haybale-foo"\nmin_version = "0.1.0"\n'
    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = body.encode()
        result = resolve_and_subscribe(
            global_path,
            "https://going-haywire.github.io/haywire/marketplace.toml",
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )

    assert result.kind == "stall"
    assert result.persist_url == "https://going-haywire.github.io/haywire/marketplace.toml"


@pytest.mark.unit
def test_subscribe_pasted_toml_block_writes_file(tmp_path: Path) -> None:
    """Pasted TOML block is written to paste_dir/<dist-name>.toml and referenced as file://."""
    from haywire.core.marketstall import resolve_and_subscribe
    from haywire.core.marketstall.parsing import parse_global_marketplace

    global_path = tmp_path / "marketplace.toml"
    paste_dir = tmp_path / "stalls"

    block = '[[haybales]]\nname = "haybale-pasted"\nmin_version = "0.1.0"\n'
    result = resolve_and_subscribe(
        global_path,
        block,
        paste_dir=paste_dir,
        cache_dir=tmp_path / "cache",
    )

    assert result.kind == "stall"
    assert result.persist_url.startswith("file://")
    assert "haybale-pasted.toml" in result.persist_url

    # The file should exist on disk.
    written_file = paste_dir / "haybale-pasted.toml"
    assert written_file.is_file()
    assert "haybale-pasted" in written_file.read_text()

    # The subscription points at the file:// URL.
    mf = parse_global_marketplace(global_path)
    assert mf.stalls[0].url == result.persist_url


@pytest.mark.unit
def test_subscribe_bare_repo_url_rejected(tmp_path: Path) -> None:
    """Bare repo URLs raise BareRepoUrlRejectedError per §4.2."""
    from haywire.core.marketstall import BareRepoUrlRejectedError, resolve_and_subscribe

    with pytest.raises(BareRepoUrlRejectedError):
        resolve_and_subscribe(
            tmp_path / "marketplace.toml",
            "https://github.com/alice/cool-libs",
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )


@pytest.mark.unit
def test_subscribe_fetch_failure_raises_subscribe_error(tmp_path: Path) -> None:
    """RemoteFetchError → SubscribeError."""
    from haywire.core.marketstall import SubscribeError, resolve_and_subscribe

    with patch("haywire.core.marketstall.cache._urlopen", side_effect=OSError):
        with pytest.raises(SubscribeError) as exc_info:
            resolve_and_subscribe(
                tmp_path / "marketplace.toml",
                "https://gone.example/marketstall.toml",
                paste_dir=tmp_path / "stalls",
                cache_dir=tmp_path / "cache",
            )
    assert "fetch" in str(exc_info.value).lower() or "unreachable" in str(exc_info.value).lower()


@pytest.mark.unit
def test_subscribe_empty_body_raises_subscribe_error(tmp_path: Path) -> None:
    """A body with neither [[markets]]/[[stalls]] nor [[haybales]] is malformed."""
    from haywire.core.marketstall import SubscribeError, resolve_and_subscribe

    with patch("haywire.core.marketstall.cache._urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"# empty\n"
        with pytest.raises(SubscribeError) as exc_info:
            resolve_and_subscribe(
                tmp_path / "marketplace.toml",
                "https://x.example/feed.toml",
                paste_dir=tmp_path / "stalls",
                cache_dir=tmp_path / "cache",
            )
    assert "marketplace" in str(exc_info.value).lower() or "marketstall" in str(exc_info.value).lower()


@pytest.mark.unit
def test_subscribe_pasted_block_without_haybales_raises(tmp_path: Path) -> None:
    """A pasted TOML block must contain [[haybales]] (it's a marketstall by definition)."""
    from haywire.core.marketstall import SubscribeError, resolve_and_subscribe

    block = '[[markets]]\nurl = "https://x.example/m.toml"\nignores = []\ndoubles = []\nblocked = []\n'
    with pytest.raises(SubscribeError):
        resolve_and_subscribe(
            tmp_path / "marketplace.toml",
            block,
            paste_dir=tmp_path / "stalls",
            cache_dir=tmp_path / "cache",
        )
```

- [ ] **Step 1.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/marketstall/test_subscribe.py -v`
Expected: FAIL — `ModuleNotFoundError: haywire.core.marketstall.subscribe`.

- [ ] **Step 1.3: Implement `subscribe.py`**

Write to `packages/haywire-core/src/haywire/core/marketstall/subscribe.py`:

```python
"""Add Source orchestrator — spec §4.3.

The §4.3 resolution algorithm composes the foundation's classify_input,
fetch_with_cache_fallback, parsers, and helpers into one pure function.
The UI dialog calls this; the function has no I/O beyond what the underlying
foundation primitives already do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import toml

from haywire.core.marketstall.cache import fetch_with_cache_fallback
from haywire.core.marketstall.errors import RemoteFetchError
from haywire.core.marketstall.helpers import (
    add_market_subscription_to_global,
    add_stall_subscription_to_global,
)
from haywire.core.marketstall.url_resolution import (
    ClassifiedInput,
    InputForm,
    classify_input,
)


class SubscribeError(RuntimeError):
    """Raised by resolve_and_subscribe on fetch failure, malformed body, or unwriteable paste file.

    Distinct from BareRepoUrlRejectedError (which propagates separately from
    classify_input). Callers should catch both to render distinct UI messages.
    """


SubscriptionKind = Literal["market", "stall"]


@dataclass(frozen=True)
class SubscribeResult:
    """Outcome of a successful resolve_and_subscribe call.

    `kind` reports which section the subscription was written to:
      - "market" → [[markets]]
      - "stall"  → [[stalls]]
    """

    kind: SubscriptionKind
    persist_url: str
    body: str


def _derive_dist_name(toml_body: str) -> str:
    """Extract the first haybale's `name` from a pasted TOML block.

    Raises SubscribeError if no [[haybales]] section is present, or the first
    entry has no `name` field.
    """
    try:
        data = toml.loads(toml_body)
    except toml.TomlDecodeError as exc:
        raise SubscribeError(f"Pasted TOML is malformed: {exc}") from exc

    haybales = data.get("haybales", [])
    if not haybales:
        raise SubscribeError(
            "Pasted TOML block has no [[haybales]] section. A pasted block must be a marketstall."
        )
    first = haybales[0]
    name = first.get("name")
    if not isinstance(name, str) or not name:
        raise SubscribeError("First [[haybales]] entry in pasted block has no `name` field.")
    return name


_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _save_pasted_block(toml_body: str, paste_dir: Path) -> tuple[str, str]:
    """Write a pasted TOML block to paste_dir/<dist-name>.toml, return (fetch_url, persist_url)."""
    dist_name = _derive_dist_name(toml_body)
    if not _SAFE_NAME.match(dist_name):
        raise SubscribeError(
            f"Unsafe dist name {dist_name!r}; can only contain ASCII letters, digits, dot, dash, underscore."
        )

    paste_dir.mkdir(parents=True, exist_ok=True)
    out_path = paste_dir / f"{dist_name}.toml"
    out_path.write_text(toml_body, encoding="utf-8")
    file_url = f"file://{out_path.resolve()}"
    return file_url, file_url


def resolve_and_subscribe(
    global_path: Path,
    user_input: str,
    *,
    paste_dir: Path,
    cache_dir: Path | None = None,
) -> SubscribeResult:
    """Run the full §4.3 Add Source algorithm.

    Raises BareRepoUrlRejectedError (propagates from classify_input) on form-3
    bare repo URLs. Raises SubscribeError on fetch failure, malformed body,
    or unwriteable paste file.
    """
    classified = classify_input(user_input)

    if classified.form is InputForm.PASTED_BLOCK:
        assert classified.toml_body is not None  # invariant of classify_input
        fetch_url, persist_url = _save_pasted_block(classified.toml_body, paste_dir)
    else:
        assert classified.fetch_url is not None and classified.persist_url is not None
        fetch_url = classified.fetch_url
        persist_url = classified.persist_url

    try:
        result = fetch_with_cache_fallback(fetch_url, cache_dir=cache_dir)
    except RemoteFetchError as exc:
        raise SubscribeError(f"Could not fetch {fetch_url}: {exc}") from exc

    body = result.body
    try:
        data = toml.loads(body)
    except toml.TomlDecodeError as exc:
        raise SubscribeError(f"Fetched body is malformed TOML: {exc}") from exc

    has_markets_or_stalls = bool(data.get("markets")) or bool(data.get("stalls"))
    has_haybales = bool(data.get("haybales"))

    if has_markets_or_stalls:
        add_market_subscription_to_global(global_path, persist_url)
        return SubscribeResult(kind="market", persist_url=persist_url, body=body)

    if has_haybales:
        add_stall_subscription_to_global(global_path, persist_url)
        return SubscribeResult(kind="stall", persist_url=persist_url, body=body)

    raise SubscribeError(
        "Body is neither a marketplace (no [[markets]] or [[stalls]]) nor a marketstall (no [[haybales]])."
    )
```

- [ ] **Step 1.4: Export from the package**

Edit `packages/haywire-core/src/haywire/core/marketstall/__init__.py`. Add these imports and exports:

```python
# Add to the existing imports block:
from haywire.core.marketstall.subscribe import (
    SubscribeError,
    SubscribeResult,
    SubscriptionKind,
    resolve_and_subscribe,
)
```

And to the `__all__` list:

```python
    # Add Source orchestration
    "resolve_and_subscribe",
    "SubscribeResult",
    "SubscribeError",
```

(`SubscriptionKind` is a `Literal` type alias; export it for type-annotation users but it's not strictly necessary to add to `__all__`.)

- [ ] **Step 1.5: Run the tests to confirm they pass**

Run: `uv run pytest tests/marketstall/test_subscribe.py -v`
Expected: 10 passed.

- [ ] **Step 1.6: Run the full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all pass (1377 + 10 = 1387).

- [ ] **Step 1.7: Lint check**

Run:
```sh
uv run ruff check packages/haywire-core/src/haywire/core/marketstall/subscribe.py tests/marketstall/test_subscribe.py
uv run mypy packages/haywire-core/src/haywire/core/marketstall/subscribe.py
```
Both clean.

- [ ] **Step 1.8: Commit**

```sh
git add packages/haywire-core/src/haywire/core/marketstall/subscribe.py \
        packages/haywire-core/src/haywire/core/marketstall/__init__.py \
        tests/marketstall/test_subscribe.py
git commit -m "feat(marketstall): add resolve_and_subscribe orchestrator (spec §4.3)"
```

---

## Task 2: Rewrite Add Source dialog as single-field input

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/library_marketplace_dialog.py`

The existing dialog has two tabs ("Marketplace URL" / "Marketstall URL") each with its own input field + handler. Replace both with a single input field that accepts any of the four forms, calls `resolve_and_subscribe`, and routes the existing conflict-resolution prompt (`_check_and_prompt_conflicts`) on success.

UI shape per spec §7.1:
- One input labeled "URL or pasted TOML".
- Helper text under the input enumerates the accepted forms.
- "Add source" button calls the handler.
- "Cancel" button closes.

Error paths:
- `BareRepoUrlRejectedError` → `ui.notify` with the rejection message (already friendly text from foundation).
- `SubscribeError` → `ui.notify` with the error string.

Success path:
- `ui.notify("Subscribed to {persist_url}", type="positive")`.
- Close dialog.
- Call existing `_check_and_prompt_conflicts(new_source_url=result.persist_url, new_source_is_marketstall=(result.kind == "stall"), on_done=on_added)`.

Note: `_check_and_prompt_conflicts` already exists and works for both kinds. Keep it.

- [ ] **Step 2.1: Read current dialog to understand the shape**

Run: `cat barn/haybale-studio/haybale_studio/editors/library_marketplace_dialog.py | head -130`

Confirm the file imports, the existing helper functions, and the NiceGUI patterns (`ui.dialog`, `hui.dialog_card`, `hui.input_field`, `ui.button`).

- [ ] **Step 2.2: Replace `show_add_source_dialog` and remove the per-tab handlers**

Edit `barn/haybale-studio/haybale_studio/editors/library_marketplace_dialog.py`:

Replace the docstring at the top:

```python
"""Add Source dialog for the Library Manager.

Single input field accepting four forms per spec §4.2:
  - Blob URL  (github.com/.../blob/{ref}/marketstall.toml)
  - Raw URL   (raw.githubusercontent.com/.../...)
  - Plain TOML URL  (anything else)
  - Pasted TOML block (not a URL)

The body-shape decides whether the subscription writes to [[markets]] or [[stalls]].
"""
```

Replace the entire `show_add_source_dialog` function (lines 25-68) with:

```python
def show_add_source_dialog(on_added: Callable[[], None]) -> None:
    """Open the single-field Add Source dialog.

    `on_added` is called after a successful add (and after any conflict-
    resolution prompt resolves). The caller typically refreshes the
    marketplace and re-renders the library list.
    """
    with ui.dialog() as dialog, hui.dialog_card():
        with ui.column().classes("p-4 gap-3 w-[28rem]"):
            ui.label("Add a marketplace source").classes("text-sm font-medium")
            ui.label(
                "Paste a marketstall URL, a marketplace URL, or a [[haybales]] TOML block."
            ).classes("text-xs hw-text-dim")

            input_field = hui.input_field(
                placeholder="https://github.com/.../blob/main/marketstall.toml",
            )

            with ui.column().classes("gap-0 text-xs hw-text-dim"):
                ui.label("Accepted forms:")
                ui.label("• Blob URL (github.com/.../blob/{ref}/marketstall.toml)")
                ui.label("• Raw URL (raw.githubusercontent.com/...)")
                ui.label("• Any URL that serves a TOML file (GitHub Pages, GitLab Pages, etc.)")
                ui.label("• A [[haybales]] TOML block pasted directly")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Add source",
                    on_click=lambda: _handle_add_source(input_field.value, dialog, on_added),
                ).props("flat color=primary")

    dialog.open()


def _handle_add_source(user_input: str, dialog: "ui.dialog", on_added: Callable[[], None]) -> None:
    """Validate input, run the §4.3 algorithm, route the conflict prompt on success."""
    from pathlib import Path

    from haywire.core.marketstall import (
        BareRepoUrlRejectedError,
        SubscribeError,
        resolve_and_subscribe,
    )

    from haywire_studio.config import GLOBAL_CONFIG_DIR, ensure_global_config

    if not (user_input or "").strip():
        ui.notify("Please paste a URL or TOML block.", type="warning")
        return

    try:
        ensure_global_config()
        result = resolve_and_subscribe(
            GLOBAL_CONFIG_DIR / "marketplace.toml",
            user_input,
            paste_dir=GLOBAL_CONFIG_DIR / "stalls",
        )
    except BareRepoUrlRejectedError as exc:
        ui.notify(str(exc), type="warning")
        return
    except SubscribeError as exc:
        logger.warning(f"Add Source failed: {exc}")
        ui.notify(f"Failed to add source: {exc}", type="negative")
        return
    except Exception as exc:
        logger.exception("Unexpected error in Add Source")
        ui.notify(f"Unexpected error: {exc}", type="negative")
        return

    ui.notify(f"Subscribed to {result.persist_url}", type="positive")
    dialog.close()
    _check_and_prompt_conflicts(
        new_source_url=result.persist_url,
        new_source_is_marketstall=(result.kind == "stall"),
        on_done=on_added,
    )
```

Then DELETE the now-unused `_handle_add_marketplace` and `_handle_add_marketstall` functions (the old per-tab handlers).

Keep `_check_and_prompt_conflicts` and `_show_conflict_resolution_dialog` exactly as they are — they're called by the new `_handle_add_source` and are already kind-agnostic.

- [ ] **Step 2.3: Verify the file imports are tidy**

After the rewrite, run `grep "^import\|^from" barn/haybale-studio/haybale_studio/editors/library_marketplace_dialog.py | head -10` and confirm:
- `nicegui.ui`, `hui` are imported at the top.
- `logging` is imported.
- Lazy imports of `haywire.core.marketstall.*` are inside the handler functions (matches the existing pattern).
- No imports for the removed handlers' helpers (`add_market_subscription_to_global`, `add_stall_subscription_to_global`) at top-level.

- [ ] **Step 2.4: Run full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all pass.

There are no direct unit tests for the dialog itself (NiceGUI dialogs aren't easily unit-testable). The slice 3 functional verification step (manual run) covers it.

- [ ] **Step 2.5: Lint check**

Run:
```sh
uv run ruff check barn/haybale-studio/haybale_studio/editors/library_marketplace_dialog.py
uv run mypy barn/haybale-studio/haybale_studio/editors/library_marketplace_dialog.py
```
Both clean.

- [ ] **Step 2.6: Commit**

```sh
git add barn/haybale-studio/haybale_studio/editors/library_marketplace_dialog.py
git commit -m "feat(library-manager): single-field Add Source dialog (spec §7.1)"
```

---

## Task 3: Provenance affordance in Library Browser rows

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/library_browser_editor.py`
- Create: `tests/test_library_browser_provenance.py`

Per spec §7.4 (provenance display) and inquisition Q9: each haybale in the Library Browser shows where it came from, using the `via` cache field already recorded during refresh. The plan-language:

- **Direct `[[stalls]]` subscription**: row shows "from {host}" sub-label (e.g. "from github.com/alice").
- **Transitive via `[[markets]]`**: row shows "via {host}" with the aggregator's hostname.

The `via` cache field is set by `refresh.py` to the URL that supplied each haybale. Distinguishing "direct" from "transitive" requires comparing `via` against the user's `[[stalls]]` subscriptions — if `via == sub.url` for some `sub in mf.stalls`, it's direct; otherwise it came through a `[[markets]]` subscription.

The provenance label is a small helper function (`derive_provenance_label`) that takes a haybale and the parsed `MarketplaceFile`, returns `str | None` (None if `via` is empty — e.g. inline haybales from the global file).

The label is appended to the existing sublabel string in `_library_item`. Existing sublabel is `f"v{version}" + " (stale)" if stale else ""`. Add the provenance prefix: e.g. `"via github.com — v0.2.0"`.

- [ ] **Step 3.1: Write failing tests**

Write to `tests/test_library_browser_provenance.py`:

```python
"""Provenance label derivation for the Library Browser — spec §7.4."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_provenance_label_for_direct_stall_subscription() -> None:
    """Haybale fetched from a [[stalls]] subscription shows 'from {host}'."""
    from haybale_studio.editors.library_browser_editor import derive_provenance_label
    from haywire.core.marketstall import Haybale, MarketplaceFile, Subscription

    haybale = Haybale(
        name="haybale-foo",
        min_version="0.1.0",
        via="https://alice.example/marketstall.toml",
    )
    mf = MarketplaceFile(
        stalls=[Subscription(url="https://alice.example/marketstall.toml")]
    )

    label = derive_provenance_label(haybale, mf)
    assert label is not None
    assert "from" in label.lower()
    assert "alice.example" in label


@pytest.mark.unit
def test_provenance_label_for_transitive_via_market() -> None:
    """Haybale via [[markets]] (not directly in [[stalls]]) shows 'via {host}'."""
    from haybale_studio.editors.library_browser_editor import derive_provenance_label
    from haywire.core.marketstall import Haybale, MarketplaceFile, Subscription

    # User subscribed to an aggregator; haybale arrived via the aggregator's listed stall.
    haybale = Haybale(
        name="haybale-foo",
        min_version="0.1.0",
        via="https://going-haywire.github.io/haywire/stalls/haybale-foo.toml",
    )
    mf = MarketplaceFile(
        markets=[Subscription(url="https://going-haywire.github.io/haywire/marketplace.toml")],
        # No matching [[stalls]] entry for the haybale's via URL.
    )

    label = derive_provenance_label(haybale, mf)
    assert label is not None
    assert "via" in label.lower()
    assert "going-haywire.github.io" in label


@pytest.mark.unit
def test_provenance_label_empty_via_returns_none() -> None:
    """A haybale with no `via` (e.g. inline in global file) returns None."""
    from haybale_studio.editors.library_browser_editor import derive_provenance_label
    from haywire.core.marketstall import Haybale, MarketplaceFile

    haybale = Haybale(name="haybale-foo", min_version="0.1.0", via="")
    mf = MarketplaceFile()

    assert derive_provenance_label(haybale, mf) is None


@pytest.mark.unit
def test_provenance_label_strips_user_paths_from_file_urls() -> None:
    """For file:// pasted-block subscriptions, the label uses 'pasted' instead of a path."""
    from haybale_studio.editors.library_browser_editor import derive_provenance_label
    from haywire.core.marketstall import Haybale, MarketplaceFile, Subscription

    haybale = Haybale(
        name="haybale-foo",
        min_version="0.1.0",
        via="file:///Users/me/.haywire/db/haybale-marketplace/stalls/haybale-foo.toml",
    )
    mf = MarketplaceFile(
        stalls=[Subscription(url="file:///Users/me/.haywire/db/haybale-marketplace/stalls/haybale-foo.toml")]
    )

    label = derive_provenance_label(haybale, mf)
    assert label is not None
    assert "pasted" in label.lower()
```

- [ ] **Step 3.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/test_library_browser_provenance.py -v`
Expected: FAIL — `ImportError: cannot import name 'derive_provenance_label'`.

- [ ] **Step 3.3: Implement `derive_provenance_label`**

Add to `barn/haybale-studio/haybale_studio/editors/library_browser_editor.py` (top of the file, after the existing imports — make sure to use `from __future__ import annotations`):

```python
from urllib.parse import urlsplit


def derive_provenance_label(haybale, mf) -> str | None:
    """Return a short provenance label for a haybale.

    Spec §7.4: shows direct subscriptions as 'from {host}' and transitive
    aggregator routing as 'via {host}'. Inline haybales (no `via`) return None.

    `mf` is the parsed MarketplaceFile (global). `haybale.via` is the URL that
    supplied this haybale during the most recent refresh.
    """
    via = getattr(haybale, "via", "") or ""
    if not via:
        return None

    if via.startswith("file://"):
        # Pasted TOML block — don't surface the user's filesystem path.
        return "from pasted"

    hostname = (urlsplit(via).hostname or via).lower()

    # Is this URL one of the user's direct [[stalls]] subscriptions?
    stall_urls = {sub.url for sub in getattr(mf, "stalls", [])}
    if via in stall_urls:
        return f"from {hostname}"

    # Otherwise it arrived via a [[markets]] aggregator.
    return f"via {hostname}"
```

- [ ] **Step 3.4: Wire the label into `_library_item`'s sublabel**

Edit `_library_item` (around line 446). Currently the sublabel logic is:

```python
sublabel = f"v{version}" if version else None
if is_stale:
    sublabel = f"{sublabel} (stale)" if sublabel else "(stale)"
```

Extend it to include the provenance label. Insert after the stale handling:

```python
        # Provenance label per spec §7.4 — only for entries that have a `via` URL
        # (i.e. came from a refresh; skip heaps and inline-in-global haybales).
        provenance = self._provenance_label_for(lib, context)
        if provenance:
            sublabel = f"{provenance} — {sublabel}" if sublabel else provenance
```

And add the helper method:

```python
    def _provenance_label_for(self, lib, context: "SessionContext") -> str | None:
        """Look up the user's [[stalls]] list to derive 'from {host}' vs 'via {host}'."""
        from haybale_studio.state.marketplace_state import MarketplaceState

        if context.app_data is None or MarketplaceState not in context.app_data:
            return None
        state = context.app_data[MarketplaceState]
        mf = state.get_global()
        if mf is None:
            return None
        return derive_provenance_label(lib, mf)
```

- [ ] **Step 3.5: Run the tests**

Run: `uv run pytest tests/test_library_browser_provenance.py -v`
Expected: 4 passed.

- [ ] **Step 3.6: Run the full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all pass (1387 + 4 = 1391).

- [ ] **Step 3.7: Lint check**

Run:
```sh
uv run ruff check barn/haybale-studio/haybale_studio/editors/library_browser_editor.py tests/test_library_browser_provenance.py
uv run mypy barn/haybale-studio/haybale_studio
```
Both clean.

- [ ] **Step 3.8: Commit**

```sh
git add barn/haybale-studio/haybale_studio/editors/library_browser_editor.py tests/test_library_browser_provenance.py
git commit -m "feat(library-browser): show provenance label on each haybale row (spec §7.4)"
```

---

## Task 4: Final verification sweep + functional smoke

- [ ] **Step 4.1: Run the full test suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: 1391 passed.

- [ ] **Step 4.2: Run ruff across all changed paths**

Run:
```sh
uv run ruff check \
    packages/haywire-core/src/haywire/core/marketstall \
    barn/haybale-studio/haybale_studio/editors/library_marketplace_dialog.py \
    barn/haybale-studio/haybale_studio/editors/library_browser_editor.py \
    tests/marketstall/test_subscribe.py \
    tests/test_library_browser_provenance.py
```
Expected: clean.

- [ ] **Step 4.3: Run mypy on the modified source files**

Run:
```sh
uv run mypy packages/haywire-core/src/haywire/core/marketstall barn/haybale-studio/haybale_studio
```
Expected: clean.

- [ ] **Step 4.4: Functional smoke (manual — requires the haywire app)**

Launch the haywire app: `uv run haywire`. In a fresh test project (use `haywire init verify-slice3 --no-sync` from a tmp dir; cd in; `uv sync; uv run haywire`):

Verify the Add Source dialog:
- Opens with ONE input field (not two tabs).
- Helper text lists the four accepted forms.
- Pasting a GitHub blob URL to a real marketstall (e.g. `https://github.com/going-haywire/haywire/blob/main/marketstall.toml` if one exists) successfully subscribes.
- Pasting a bare repo URL (e.g. `https://github.com/alice/cool-libs`) shows the rejection notification.
- Pasting a TOML block `[[haybales]]\nname = "haybale-test"\nmin_version = "0.0.1"\n` saves the file to `~/.haywire/db/haybale-marketplace/stalls/haybale-test.toml` and subscribes via `file://`.

Verify the Library Browser:
- After a successful subscribe + refresh, the new haybale row shows a `from {host}` (or `via {host}`) sublabel prefix.

If anything fails the smoke test, fix in place and re-run.

- [ ] **Step 4.5: Review the diff and tidy up**

Run: `git log --oneline c16ec01c..HEAD` for the slice 3 commit list.
Run: `git diff c16ec01c --stat` for the file-level summary.

Expected: 3 commits, ~5 files modified/created, ~600-800 line delta.

---

## Spec coverage check

This plan covers the **URL Distribution UI slice** of the marketstall spec:

| Spec § | Covered by | Notes |
|---|---|---|
| §4.2 four input forms | Task 1 (algorithm) + Task 2 (UI) | classify_input + resolve_and_subscribe + single-field dialog |
| §4.3 resolution algorithm | Task 1 | resolve_and_subscribe orchestrates the full pipeline |
| §7.1 single-field Add Source | Task 2 | Dialog rewrite |
| §7.4 provenance display | Task 3 | derive_provenance_label + Library Browser sublabel |

**Not covered (deferred):**

| Spec § | Deferred to slice |
|---|---|
| §7.4 first-install safety modal (block/cancel/install buttons) | 5 |
| §2.1 OS multi-select UI in Edit dialog | 4 |
| §10 update-available signal UI | 7 |
| §12 drift gate lag check | 6 |
| §11 per-haybale stall generator | 8 |

---

## Self-Review notes

- ✅ Every step has complete code; no "TBD".
- ✅ Names referenced across tasks: `resolve_and_subscribe`, `SubscribeResult`, `SubscribeError`, `derive_provenance_label`, `_handle_add_source`, `_provenance_label_for` — all defined where first used.
- ✅ `_check_and_prompt_conflicts` is REUSED from the existing dialog, not rewritten. It's already kind-agnostic.
- ✅ TDD discipline: failing test before implementation in tasks 1 and 3.
- ✅ Commits are feature-focused (algorithm / dialog UI / browser UI).
- ✅ Task 2 has no unit tests because NiceGUI dialogs aren't easily testable; functional verification in Task 4.4 covers it.
- ✅ The provenance label uses `getattr` defensively in case the input lib is a runtime LibraryWrapper (with `.identity.via`) vs a cache Haybale (with `.via` direct).

Note on the LibraryWrapper case: `_library_item` accepts both `LibraryWrapper` (for installed libraries, with `.identity`) and `Haybale` (for available-but-not-installed entries, with `.via` direct). `derive_provenance_label` should handle both — for `LibraryWrapper`, the `via` attribute is usually missing, in which case the function returns None (no provenance shown). Verify this during step 3.3 implementation.

---

## Execution Handoff

Plan saved to `internals/plans/2026-05-22-marketstall-url-distribution.md`. Three execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task, quiet-mode reporting, batched reviews. Estimated 3-5 subagent dispatches.

**2. Inline Execution** — Execute in this session.

**3. Inquisition first** — If the algorithm-vs-UI boundary in `resolve_and_subscribe` (Task 1) feels unsettled, an inquisition pass before code might be worth it.

Which approach?
