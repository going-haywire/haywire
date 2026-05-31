# Post-Install Requirements (`needs_refresh` / `needs_restart`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface to the user, at the end of a library install or uninstall, whether they need to reload the browser tab or restart the Studio process before the library can be used (or before the process is safe to continue using).

**Architecture:** Two author-declared flags on `LibraryIdentity` (`needs_refresh`, `needs_restart`) are unioned by `LibraryManager.install()` / `uninstall_streaming()` across newly-imported + evicted libraries and returned as a small `PostInstallHints` dataclass. The renamed `LibraryOperationProgressModal.finish()` reads the hints and renders one of three terminal states: `Done` / `Reload the page` (calls `ui.navigate.reload()`) / `How to restart Studio` (reveals a manual-restart instructions panel; no auto-quit). Trust-the-author model — no auto-detection, no lint, no publish-time check; both flags default to `False`.

**Tech Stack:** Python 3.12, NiceGUI 3.12+, pytest with `pytest.mark.unit` + `pytest.mark.anyio`, `MagicMock`-based registry stubs (see `tests/test_library_manager_dry_run.py` for the pattern).

**Glossary entry:** [docs/reference/glossary.md](../../docs/reference/glossary.md) — "Post-install requirements" (already landed).

**Layering rule (must be honored):** `haywire.core` → `haywire.ui` → `haybale-*`. `PostInstallHints` lives in `haywire.ui` (sibling of the modal); haybale-marketplace imports it from there.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `packages/haywire-core/src/haywire/core/library/identity.py` | Modify | Add `needs_refresh: bool = False` and `needs_restart: bool = False` fields to `LibraryIdentity`. |
| `packages/haywire-core/src/haywire/core/library/decorator.py` | Modify (docstring only) | Document the two new optional kwargs accepted via the kwargs pass-through. |
| `packages/haywire-core/src/haywire/ui/modals/install_progress_modal.py` | Replace | Define `PostInstallHints` dataclass; rename `InstallProgressModal` → `LibraryOperationProgressModal` and `install_progress_modal` → `library_operation_progress_modal`; extend `finish()` to accept `hints` and render three terminal states. |
| `packages/haywire-core/src/haywire/ui/modals/__init__.py` | Modify | Re-export the renamed class/function and the new `PostInstallHints` dataclass. |
| `barn/haybale-marketplace/haybale_marketplace/library_manager.py` | Modify | Change `install()` and `uninstall_streaming()` return signatures to `(success, message, hints)`; add private `_compute_hints(...)` helper that ORs flags across (newly-imported + evicted). Update `install_streaming` deprecated alias. |
| `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py` | Modify | Update the two call sites (`_do_install`, `_do_uninstall`) to unpack the new 3-tuple and pass `hints` to `progress.finish(...)`. Convert `_do_uninstall` from the inline log card to the renamed progress modal. |
| `tests/test_library_identity_flags.py` | Create | Unit tests for the two new `LibraryIdentity` fields + `@library` decorator pass-through. |
| `tests/test_post_install_hints.py` | Create | Unit tests for the `PostInstallHints` dataclass (frozen, defaults, OR semantics via helper). |
| `tests/test_library_manager_hints.py` | Create | Unit tests for `LibraryManager.install()` / `uninstall_streaming()` returning correctly unioned `PostInstallHints` across success, failure-with-eviction, and uninstall paths. |
| `tests/test_library_operation_progress_modal.py` | Create | Unit tests for `LibraryOperationProgressModal.finish()` terminal-state branching. Smoke-level (the modal is UI; assert visibility flags + button label + reload-callback wiring, not full rendering). |

---

## Task 1: Add `needs_refresh` / `needs_restart` fields to `LibraryIdentity`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/identity.py`
- Test: `tests/test_library_identity_flags.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_library_identity_flags.py` with this content:

```python
"""Tests for the post-install requirement flags on LibraryIdentity."""

from __future__ import annotations

import pytest

from haywire.core.library.identity import LibraryIdentity


def _make_identity(**overrides) -> LibraryIdentity:
    """Build a LibraryIdentity with minimal-but-complete required fields."""
    base = dict(
        label="test",
        version="1.0.0",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path="/tmp/test",
        module_name="test_module",
        id="test",
    )
    base.update(overrides)
    return LibraryIdentity(**base)


@pytest.mark.unit
def test_needs_refresh_defaults_to_false():
    """LibraryIdentity.needs_refresh must default to False when not specified."""
    identity = _make_identity()
    assert identity.needs_refresh is False


@pytest.mark.unit
def test_needs_restart_defaults_to_false():
    """LibraryIdentity.needs_restart must default to False when not specified."""
    identity = _make_identity()
    assert identity.needs_restart is False


@pytest.mark.unit
def test_needs_refresh_explicit_true_preserved():
    """An explicit needs_refresh=True must round-trip through the dataclass."""
    identity = _make_identity(needs_refresh=True)
    assert identity.needs_refresh is True


@pytest.mark.unit
def test_needs_restart_explicit_true_preserved():
    """An explicit needs_restart=True must round-trip through the dataclass."""
    identity = _make_identity(needs_restart=True)
    assert identity.needs_restart is True


@pytest.mark.unit
def test_both_flags_can_be_set_together():
    """Both flags can be True simultaneously."""
    identity = _make_identity(needs_refresh=True, needs_restart=True)
    assert identity.needs_refresh is True
    assert identity.needs_restart is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_library_identity_flags.py -v`
Expected: All five tests FAIL with `TypeError: LibraryIdentity.__init__() got an unexpected keyword argument 'needs_refresh'` (or default-True tests fail with `AttributeError` if you read the attribute pre-add).

- [ ] **Step 3: Add the two fields to `LibraryIdentity`**

Open `packages/haywire-core/src/haywire/core/library/identity.py`. The current file is:

```python
from dataclasses import dataclass


@dataclass
class LibraryIdentity:
    """Metadata for a Haywire library"""

    label: str
    version: str
    description: str
    url: str
    help_url: str
    author: str
    author_url: str
    folder_path: str  # Path to the library folder
    module_name: str  # Python module name
    id: str  # Unique identifier for the library
    # List of referenced haywire libraries.
    # For hot reloading to work, the dependencies must be specified.
    # ... (existing docstring)
    dependencies: list[str] | None = None
    tags: list[str] | None = None  # Searchable tags for marketplace/discovery
    file_watcher: bool = False  # Whether to watch for file changes

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.tags is None:
            self.tags = []
```

Add the two flags after `file_watcher`. Replace the existing line:

```python
    file_watcher: bool = False  # Whether to watch for file changes
```

with:

```python
    file_watcher: bool = False  # Whether to watch for file changes
    # Post-install requirements (author-declared; default False).
    # See: docs/reference/glossary.md → "Post-install requirements".
    needs_refresh: bool = False
    needs_restart: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_library_identity_flags.py -v`
Expected: All five tests PASS.

- [ ] **Step 5: Type check the module**

Run: `uv run mypy packages/haywire-core/src/haywire/core/library/identity.py`
Expected: `Success: no issues found in 1 source file` (or whatever the pre-edit baseline showed, with no new errors).

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/identity.py tests/test_library_identity_flags.py
git commit -m "feat(library): add needs_refresh / needs_restart flags to LibraryIdentity

Two author-declared flags surfaced post-install by LibraryManager. Both default
to False; trust-the-author model (no auto-detection). See docs/reference/glossary.md
'Post-install requirements'."
```

---

## Task 2: Update `@library` decorator docstring to document the new kwargs

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/library/decorator.py:24-41`

The decorator passes kwargs straight through to `LibraryIdentity(**kwargs)`, so no code change is needed — only docstring. The end-to-end behavior is already covered by Task 1's `_make_identity(needs_refresh=True)` (which exercises the same kwargs path); no new test required.

- [ ] **Step 1: Update the docstring**

Open `packages/haywire-core/src/haywire/core/library/decorator.py`. Locate the `Args:` section (lines 24-41). After the `file_watcher` paragraph, add:

```python
        needs_refresh (bool, optional): Declares that installing this library registers
            new Vue components or JS resources that an already-open browser tab cannot
            pick up; install completion prompts the user to reload the page. Defaults
            to False. See docs/reference/glossary.md → "Post-install requirements".
        needs_restart (bool, optional): Declares that installing or uninstalling this
            library leaves the Python process in a state requiring a Studio restart
            (typically C-extension modules, haywire-core upgrades, or import-time
            global mutation). Symmetric — applied on uninstall too. Defaults to False.
```

- [ ] **Step 2: Verify the decorator accepts the new kwargs end-to-end**

Run: `uv run python -c "
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library

@library(label='t', needs_refresh=True, needs_restart=True)
class L(BaseLibrary):
    def register_components(self): pass

print('refresh:', L.class_identity.needs_refresh)
print('restart:', L.class_identity.needs_restart)
"`
Expected:
```
refresh: True
restart: True
```

- [ ] **Step 3: Commit**

```bash
git add packages/haywire-core/src/haywire/core/library/decorator.py
git commit -m "docs(library): document needs_refresh / needs_restart in @library decorator"
```

---

## Task 3: Create `PostInstallHints` dataclass and OR-merge helper

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/modals/install_progress_modal.py` (add dataclass at top)
- Test: `tests/test_post_install_hints.py`

`PostInstallHints` is the install-flow projection of the two `LibraryIdentity` flags. It's `frozen=True` so callers can't mutate it post-creation, and it has a `merge(other)` method that returns a new hints with each flag OR'd. The merge helper is what `LibraryManager` will use to union over multiple libraries.

- [ ] **Step 1: Write the failing test**

Create `tests/test_post_install_hints.py`:

```python
"""Tests for the PostInstallHints dataclass used by the post-install UX."""

from __future__ import annotations

import pytest

from haywire.ui.modals.install_progress_modal import PostInstallHints


@pytest.mark.unit
def test_defaults_to_no_requirements():
    """A bare PostInstallHints() must have both flags False."""
    h = PostInstallHints()
    assert h.needs_refresh is False
    assert h.needs_restart is False


@pytest.mark.unit
def test_is_frozen():
    """PostInstallHints must be frozen (immutable after construction)."""
    h = PostInstallHints()
    with pytest.raises((AttributeError, Exception)):  # FrozenInstanceError
        h.needs_refresh = True  # type: ignore[misc]


@pytest.mark.unit
def test_merge_ors_both_flags():
    """merge() must OR each flag and return a new instance."""
    a = PostInstallHints(needs_refresh=True, needs_restart=False)
    b = PostInstallHints(needs_refresh=False, needs_restart=True)
    out = a.merge(b)
    assert out.needs_refresh is True
    assert out.needs_restart is True


@pytest.mark.unit
def test_merge_with_empty_is_identity():
    """Merging with PostInstallHints() must return an equivalent value."""
    a = PostInstallHints(needs_refresh=True, needs_restart=False)
    out = a.merge(PostInstallHints())
    assert out.needs_refresh is True
    assert out.needs_restart is False


@pytest.mark.unit
def test_merge_does_not_mutate_inputs():
    """merge() must not modify either operand."""
    a = PostInstallHints(needs_refresh=True)
    b = PostInstallHints(needs_restart=True)
    a.merge(b)
    assert a == PostInstallHints(needs_refresh=True, needs_restart=False)
    assert b == PostInstallHints(needs_refresh=False, needs_restart=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_post_install_hints.py -v`
Expected: All five tests FAIL with `ImportError: cannot import name 'PostInstallHints'`.

- [ ] **Step 3: Add `PostInstallHints` to the modal module**

Open `packages/haywire-core/src/haywire/ui/modals/install_progress_modal.py`. The current top of the file is:

```python
"""Install progress modal — streaming log with spinner, success, and error states.

Opens immediately with a spinner and a live ``ui.log`` feed. The caller drives
state transitions via the returned :class:`InstallProgressModal` handle:
... (existing docstring)
"""

from __future__ import annotations

from typing import Optional

from nicegui import ui

from haywire.ui.components.popup import Popup
```

Insert the dataclass after the imports, before the `class InstallProgressModal:` line. Add:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class PostInstallHints:
    """Post-install user-action requirements computed by ``LibraryManager``.

    Author-declared on ``LibraryIdentity`` via ``@library(needs_refresh=True,
    needs_restart=True)``. Unioned across newly-imported and evicted libraries
    by the install/uninstall flow and consumed by
    :meth:`LibraryOperationProgressModal.finish` to render the terminal state.

    See docs/reference/glossary.md → "Post-install requirements".
    """

    needs_refresh: bool = False
    needs_restart: bool = False

    def merge(self, other: "PostInstallHints") -> "PostInstallHints":
        """Return a new hints with each flag OR'd between self and other."""
        return PostInstallHints(
            needs_refresh=self.needs_refresh or other.needs_refresh,
            needs_restart=self.needs_restart or other.needs_restart,
        )
```

Also add the import to the existing `from dataclasses import dataclass` (if not already present — it isn't in this file yet, so the line above adds it).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_post_install_hints.py -v`
Expected: All five tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/modals/install_progress_modal.py tests/test_post_install_hints.py
git commit -m "feat(modals): add PostInstallHints dataclass with merge helper

Frozen value type returned by LibraryManager.install/uninstall to drive the
post-install modal's terminal state. merge() ORs flags so callers can union
across multiple libraries."
```

---

## Task 4: Rename `InstallProgressModal` → `LibraryOperationProgressModal`; extend `finish()` to accept hints

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/modals/install_progress_modal.py`
- Test: `tests/test_library_operation_progress_modal.py`

Three terminal states (per design Q3):
- No flags → button text `Done`, no notice.
- `needs_refresh=True`, restart not set → button text `Reload the page`, button click calls `ui.navigate.reload()`, notice text `Reload the page to use the new library.`
- `needs_restart=True` (regardless of refresh) → button text `How to restart Studio`, button click reveals an instructions panel containing `Quit Studio in your terminal (Ctrl+C) and run \`uv run haywire\` again.`, no auto-quit.

The class/function rename touches one definition file, one re-export in `__init__.py`, and one caller (handled in Task 5).

- [ ] **Step 1: Write the failing test**

Create `tests/test_library_operation_progress_modal.py`:

```python
"""Smoke tests for LibraryOperationProgressModal.finish() terminal-state branching.

These exercise the visibility / label / callback wiring rather than full DOM
rendering. The modal is constructed inside a NiceGUI page context using the
standard nicegui.testing harness.
"""

from __future__ import annotations

import pytest
from nicegui import ui
from nicegui.testing import User

from haywire.ui.modals.install_progress_modal import (
    LibraryOperationProgressModal,
    PostInstallHints,
    library_operation_progress_modal,
)


pytestmark = pytest.mark.module_under_test  # placeholder; replace with project's marker if any


@pytest.mark.unit
async def test_finish_no_flags_shows_done_button(user: User) -> None:
    """No flags → button label 'Done', no notice, no reload callback."""

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints())
        # Stash on the page for assertion
        page.modal = modal  # type: ignore[attr-defined]

    await user.open("/")
    modal = page.modal  # type: ignore[attr-defined]

    # Spinner is hidden, terminal row is visible, button label is "Done".
    assert modal._spinner_row.visible is False
    assert modal._done_row[0].visible is True
    assert modal._done_row[1].text == "Done"
    # Restart instructions panel is hidden.
    assert modal._restart_instructions.visible is False
    # Reload notice is hidden.
    assert modal._reload_notice.visible is False


@pytest.mark.unit
async def test_finish_needs_refresh_shows_reload_button(user: User) -> None:
    """needs_refresh=True → button 'Reload the page' and the reload notice is visible."""

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints(needs_refresh=True))
        page.modal = modal  # type: ignore[attr-defined]

    await user.open("/")
    modal = page.modal  # type: ignore[attr-defined]

    assert modal._done_row[1].text == "Reload the page"
    assert modal._reload_notice.visible is True
    assert modal._restart_instructions.visible is False


@pytest.mark.unit
async def test_finish_needs_restart_shows_restart_button(user: User) -> None:
    """needs_restart=True → button 'How to restart Studio'; click reveals instructions."""

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints(needs_restart=True))
        page.modal = modal  # type: ignore[attr-defined]

    await user.open("/")
    modal = page.modal  # type: ignore[attr-defined]

    assert modal._done_row[1].text == "How to restart Studio"
    # Instructions panel starts hidden (revealed on click).
    assert modal._restart_instructions.visible is False
    # Refresh notice is hidden — restart subsumes refresh.
    assert modal._reload_notice.visible is False


@pytest.mark.unit
async def test_finish_restart_subsumes_refresh(user: User) -> None:
    """Both flags True → restart UX wins; refresh notice stays hidden."""

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints(needs_refresh=True, needs_restart=True))
        page.modal = modal  # type: ignore[attr-defined]

    await user.open("/")
    modal = page.modal  # type: ignore[attr-defined]

    assert modal._done_row[1].text == "How to restart Studio"
    assert modal._reload_notice.visible is False


@pytest.mark.unit
async def test_finish_with_error_shows_close_and_keeps_banner(user: User) -> None:
    """error=<msg> → banner visible, label 'Close', no reload/restart wiring."""

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(error="Install failed: out of disk")
        page.modal = modal  # type: ignore[attr-defined]

    await user.open("/")
    modal = page.modal  # type: ignore[attr-defined]

    assert modal._error_banner[1].visible is True
    assert modal._error_banner[0].text == "Install failed: out of disk"
    assert modal._done_row[1].text == "Close"


@pytest.mark.unit
async def test_finish_with_error_and_restart_shows_both(user: User) -> None:
    """error + needs_restart → banner visible AND restart button (per Q12.A)."""

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(error="Install failed: pip exit 1",
                     hints=PostInstallHints(needs_restart=True))
        page.modal = modal  # type: ignore[attr-defined]

    await user.open("/")
    modal = page.modal  # type: ignore[attr-defined]

    assert modal._error_banner[1].visible is True
    assert modal._done_row[1].text == "How to restart Studio"
```

If the `pytest.mark.module_under_test` line generates a warning (no such marker registered), delete that line — it's a placeholder noted in the docstring; the per-test `@pytest.mark.unit` markers are what matter.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_library_operation_progress_modal.py -v`
Expected: All six tests FAIL with `ImportError: cannot import name 'LibraryOperationProgressModal'`.

- [ ] **Step 3: Replace the modal module contents**

Open `packages/haywire-core/src/haywire/ui/modals/install_progress_modal.py`. After Task 3, it contains `PostInstallHints` plus the legacy `InstallProgressModal` class and `install_progress_modal()` factory. Replace the legacy class + factory with the renamed, extended versions. The full replacement file should be:

```python
"""Library operation progress modal — streaming log with spinner, success, and error states.

Opens immediately with a spinner and a live ``ui.log`` feed. The caller drives
state transitions via the returned :class:`LibraryOperationProgressModal` handle:

  modal = library_operation_progress_modal(title="Installing haybale-foo")
  modal.push("Resolving dependencies…")
  modal.finish(hints=PostInstallHints(needs_refresh=True))
  modal.finish(error="Install failed: …", hints=PostInstallHints(needs_restart=True))

The terminal state is driven by ``hints`` (and optionally ``error``):
  * No flags, no error → "Done" button, closes popup.
  * ``needs_refresh=True``, no error → "Reload the page" button that calls
    ``ui.navigate.reload()``.
  * ``needs_restart=True`` → "How to restart Studio" button that reveals a
    manual-restart instructions panel (no auto-quit; restart subsumes refresh).
  * ``error=…`` → red banner stays visible; button label becomes "Close" unless
    ``needs_restart`` is also set, in which case the restart button takes over.

See docs/reference/glossary.md → "Post-install requirements".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from nicegui import ui

from haywire.ui.components.popup import Popup


@dataclass(frozen=True)
class PostInstallHints:
    """Post-install user-action requirements computed by ``LibraryManager``.

    Author-declared on ``LibraryIdentity`` via ``@library(needs_refresh=True,
    needs_restart=True)``. Unioned across newly-imported and evicted libraries
    by the install/uninstall flow and consumed by
    :meth:`LibraryOperationProgressModal.finish` to render the terminal state.

    See docs/reference/glossary.md → "Post-install requirements".
    """

    needs_refresh: bool = False
    needs_restart: bool = False

    def merge(self, other: "PostInstallHints") -> "PostInstallHints":
        """Return a new hints with each flag OR'd between self and other."""
        return PostInstallHints(
            needs_refresh=self.needs_refresh or other.needs_refresh,
            needs_restart=self.needs_restart or other.needs_restart,
        )


_RESTART_INSTRUCTIONS = (
    "Quit Studio in your terminal (Ctrl+C) and run `uv run haywire` again."
)


class LibraryOperationProgressModal:
    """Handle returned by :func:`library_operation_progress_modal`.

    Use :meth:`push` to stream log lines and :meth:`finish` to transition
    from spinner to the terminal state (success or failure, possibly with
    post-install requirements).
    """

    def __init__(
        self,
        popup: Popup,
        log: "ui.log",
        spinner_row,
        done_row,
        error_banner,
        reload_notice,
        restart_instructions,
    ):
        self._popup = popup
        self._log = log
        self._spinner_row = spinner_row
        self._done_row = done_row  # (row_element, button_element)
        self._error_banner = error_banner  # (text_label, container_row)
        self._reload_notice = reload_notice  # ui.label
        self._restart_instructions = restart_instructions  # ui.label

    def push(self, line: str) -> None:
        """Append a line to the streaming log."""
        self._log.push(line)

    def finish(
        self,
        *,
        error: Optional[str] = None,
        hints: Optional[PostInstallHints] = None,
    ) -> None:
        """Transition to the terminal state.

        Args:
            error: When supplied, shows the error banner. Combines with ``hints``:
                if ``hints.needs_restart`` is True, the restart button still
                appears alongside the error banner (per Q12.A).
            hints: Post-install requirements that drive button label + extra
                notice / instructions. When None, treated as ``PostInstallHints()``.
        """
        hints = hints or PostInstallHints()
        self._spinner_row.set_visibility(False)

        if error:
            self._error_banner[0].set_text(error)
            self._error_banner[1].set_visibility(True)

        button = self._done_row[1]

        # Restart subsumes refresh: check restart first.
        if hints.needs_restart:
            button.set_text("How to restart Studio")
            button.on("click", lambda: self._restart_instructions.set_visibility(True))
        elif hints.needs_refresh:
            button.set_text("Reload the page")
            self._reload_notice.set_visibility(True)
            button.on("click", lambda: ui.navigate.reload())
        elif error:
            button.set_text("Close")
        # else: default "Done" label set at construction; closes popup.

        self._done_row[0].set_visibility(True)

    def close(self) -> None:
        """Close the popup programmatically."""
        self._popup.close()


def library_operation_progress_modal(
    *,
    title: str,
    width: str = "520px",
    log_max_lines: int = 200,
) -> LibraryOperationProgressModal:
    """Open a library-operation progress modal and return a handle.

    The modal shows a spinner and a live log feed. Call
    :meth:`~LibraryOperationProgressModal.push` to stream output lines and
    :meth:`~LibraryOperationProgressModal.finish` when the operation completes.

    Args:
        title: Popup title (e.g. "Installing haybale-foo").
        width: CSS width of the popup card.
        log_max_lines: Maximum lines kept in the log widget.

    Returns:
        A :class:`LibraryOperationProgressModal` handle for driving state transitions.
    """
    popup = Popup(
        title=title,
        width=width,
        closable=False,
        backdrop_click_close=False,
        escape_close=False,
    )

    with popup:
        with ui.column().classes("w-full gap-2 p-1"):
            # Spinner row — visible during the operation
            spinner_row = ui.row().classes("items-center gap-2")
            with spinner_row:
                ui.spinner(size="sm")
                ui.label("Working…").classes("text-xs hw-text-dim")

            # Error banner — hidden until finish(error=…) is called
            error_text = ui.label("").classes("text-xs hw-text-danger")
            error_container = (
                ui.row()
                .classes("w-full items-start gap-2 p-2 rounded")
                .style("border-left: 3px solid var(--hw-danger); background: var(--hw-danger-bg);")
            )
            with error_container:
                ui.icon("error", size="16px").classes("hw-text-danger flex-shrink-0 mt-0.5")
                error_text.move(error_container)
            error_container.set_visibility(False)

            # Streaming log
            log = (
                ui.log(max_lines=log_max_lines)
                .classes("w-full text-xs")
                .style("height: 200px; font-family: monospace;")
            )

            # Refresh-required notice — hidden unless needs_refresh fires
            reload_notice = ui.label(
                "Reload the page to use the new library."
            ).classes("text-xs hw-text-muted")
            reload_notice.set_visibility(False)

            # Restart instructions panel — hidden until the restart button is clicked
            restart_instructions = (
                ui.label(_RESTART_INSTRUCTIONS)
                .classes("text-xs hw-text-muted p-2 rounded")
                .style("background: var(--hw-bg-surface); font-family: monospace;")
            )
            restart_instructions.set_visibility(False)

            # Done/Close/Reload/Restart button row — hidden until finish() is called
            done_row = ui.row().classes("w-full justify-end")
            with done_row:
                done_btn = ui.button("Done", on_click=popup.close).props("flat dense")
            done_row.set_visibility(False)

    popup.open()

    return LibraryOperationProgressModal(
        popup=popup,
        log=log,
        spinner_row=spinner_row,
        done_row=(done_row, done_btn),
        error_banner=(error_text, error_container),
        reload_notice=reload_notice,
        restart_instructions=restart_instructions,
    )
```

Important detail on the rename: do **not** keep the old `InstallProgressModal` / `install_progress_modal` names as deprecated aliases. There is exactly one caller (handled in Task 5), and per the project CLAUDE.md guidance, backwards-compat shims for in-repo renames are an anti-pattern.

- [ ] **Step 4: Update the modals package re-export**

Open `packages/haywire-core/src/haywire/ui/modals/__init__.py`. Currently:

```python
from .install_progress_modal import InstallProgressModal, install_progress_modal
```

Change that import line to:

```python
from .install_progress_modal import (
    LibraryOperationProgressModal,
    PostInstallHints,
    library_operation_progress_modal,
)
```

In the `__all__` list, replace:

```python
    "InstallProgressModal",
    ...
    "install_progress_modal",
```

with:

```python
    "LibraryOperationProgressModal",
    "PostInstallHints",
    ...
    "library_operation_progress_modal",
```

(Keep the rest of `__all__` alphabetized as it already is.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_library_operation_progress_modal.py -v`
Expected: All six tests PASS.

If a test fails because the NiceGUI testing harness uses different attribute names than `.visible` / `.text`, adapt the assertion mechanics to match what the project's other modal tests use. Look at `tests/marketstall/test_install_safety_modal_logic.py` for the established pattern.

- [ ] **Step 6: Type check the module**

Run: `uv run mypy packages/haywire-core/src/haywire/ui/modals/install_progress_modal.py packages/haywire-core/src/haywire/ui/modals/__init__.py`
Expected: no new errors beyond the pre-edit baseline.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/modals/install_progress_modal.py packages/haywire-core/src/haywire/ui/modals/__init__.py tests/test_library_operation_progress_modal.py
git commit -m "feat(modals): rename install modal, add hints-driven terminal states

InstallProgressModal → LibraryOperationProgressModal (the modal now serves
uninstall too). finish() takes a PostInstallHints and renders one of: Done /
Reload the page (calls ui.navigate.reload) / How to restart Studio (reveals
instructions; no auto-quit). Restart subsumes refresh. Failure-with-restart
shows error banner alongside the restart button."
```

---

## Task 5: `LibraryManager.install()` / `.uninstall_streaming()` — return `PostInstallHints`

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/library_manager.py`
- Test: `tests/test_library_manager_hints.py`

This task does three things:
1. Adds a private `_compute_install_hints(...)` helper.
2. Changes `install()`'s return type from `tuple[bool, str]` to `tuple[bool, str, PostInstallHints]`.
3. Changes `uninstall_streaming()`'s return type from `tuple[bool, str]` to `tuple[bool, str, PostInstallHints]`.

Per the design:
- **install success** hints = OR of `needs_refresh`/`needs_restart` over (post-scan library_ids that were not present before install) ∪ (evicted library_ids' previously-known flags).
- **install failure** hints = `needs_refresh=False`, `needs_restart` = OR over evicted library_ids' previously-known flags (the eviction already happened before pip failed).
- **uninstall** hints = `needs_refresh=False`, `needs_restart` = the removed library's `needs_restart` flag (captured before disable).

The "evicted library's previously-known flags" requires reading `LibraryIdentity` *before* `remove_library()` is called. Capture them into a list while iterating the eviction loop.

The `install_streaming()` deprecated alias also has to update to forward the new return tuple.

- [ ] **Step 1: Write the failing test**

Create `tests/test_library_manager_hints.py`:

```python
"""Tests for LibraryManager.install / .uninstall_streaming returning PostInstallHints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.ui.modals.install_progress_modal import PostInstallHints

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _identity(lib_id: str, *, needs_refresh: bool = False, needs_restart: bool = False) -> LibraryIdentity:
    return LibraryIdentity(
        label=lib_id,
        version="0.0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path=f"/tmp/{lib_id}",
        module_name=lib_id,
        id=lib_id,
        needs_refresh=needs_refresh,
        needs_restart=needs_restart,
    )


def _make_manager(*, libraries_before: dict, libraries_after: dict):
    """Build a LibraryManager whose registry returns `libraries_before` until
    scan_for_libraries() is called, after which it returns `libraries_after`.
    """
    from haybale_marketplace.library_manager import LibraryManager
    from haywire.core.library.install_type import InstallType

    registry = MagicMock()
    state = {"libs": dict(libraries_before)}

    registry.list_names.side_effect = lambda: list(state["libs"].keys())
    registry.get_library_identity.side_effect = lambda lid: state["libs"][lid]
    registry.get_library_install_type.return_value = InstallType.REGULAR
    registry.find_library_by_distribution_name.side_effect = lambda dn: dn.replace("-", "_")
    registry.get_library_distribution_name.side_effect = lambda lid: lid.replace("_", "-")

    def _scan() -> None:
        state["libs"] = dict(libraries_after)

    registry.scan_for_libraries.side_effect = _scan
    registry.enable_all_libraries.return_value = None

    def _remove(lid: str) -> bool:
        state["libs"].pop(lid, None)
        return True

    registry.remove_library.side_effect = _remove
    registry.disable_library.return_value = None

    mgr = LibraryManager(library_registry=registry)
    return mgr, registry


@pytest.mark.unit
async def test_install_success_no_flags_returns_empty_hints():
    """A fresh install of a library declaring neither flag → empty hints."""
    new_lib = _identity("new_lib")
    mgr, _ = _make_manager(libraries_before={}, libraries_after={"new_lib": new_lib})

    with patch.object(mgr, "dry_run", new=AsyncMock(return_value=[])), \
         patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))), \
         patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())):
        success, _msg, hints = await mgr.install("new-lib", on_output=lambda _l: None)

    assert success is True
    assert hints == PostInstallHints()


@pytest.mark.unit
async def test_install_success_new_lib_needs_refresh_propagates():
    """A fresh install of a library declaring needs_refresh=True → hints.needs_refresh=True."""
    new_lib = _identity("graph_editor", needs_refresh=True)
    mgr, _ = _make_manager(libraries_before={}, libraries_after={"graph_editor": new_lib})

    with patch.object(mgr, "dry_run", new=AsyncMock(return_value=[])), \
         patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))), \
         patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())):
        success, _msg, hints = await mgr.install("haybale-graph-editor", on_output=lambda _l: None)

    assert success is True
    assert hints.needs_refresh is True
    assert hints.needs_restart is False


@pytest.mark.unit
async def test_install_failure_with_evicted_restart_lib_returns_restart_hint():
    """Per Q12.A: if eviction removed a needs_restart library and then pip failed,
    hints.needs_restart must be True."""
    evicted = _identity("haybale_ext", needs_restart=True)
    mgr, _ = _make_manager(libraries_before={"haybale_ext": evicted}, libraries_after={"haybale_ext": evicted})

    with patch.object(mgr, "dry_run", new=AsyncMock(return_value=["haybale-ext"])), \
         patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(False, "pip exit 1"))):
        success, _msg, hints = await mgr.install("haybale-ext==2.0", on_output=lambda _l: None)

    assert success is False
    assert hints.needs_refresh is False  # failure never sets refresh
    assert hints.needs_restart is True


@pytest.mark.unit
async def test_install_upgrade_unions_new_and_evicted_flags():
    """Per Q6.A: install hints = OR over (newly-imported + evicted) for restart;
    OR over (newly-imported only) for refresh."""
    old_v = _identity("haybale_x", needs_restart=True, needs_refresh=False)
    new_v = _identity("haybale_x", needs_restart=False, needs_refresh=True)
    mgr, _ = _make_manager(libraries_before={"haybale_x": old_v},
                           libraries_after={"haybale_x": new_v})

    with patch.object(mgr, "dry_run", new=AsyncMock(return_value=["haybale-x"])), \
         patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))), \
         patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())):
        success, _msg, hints = await mgr.install("haybale-x==2.0", on_output=lambda _l: None)

    assert success is True
    # refresh: True (new version declares it)
    assert hints.needs_refresh is True
    # restart: True (old version declared it; OR'd in from evicted set)
    assert hints.needs_restart is True


@pytest.mark.unit
async def test_uninstall_propagates_needs_restart_only():
    """Per Q5/B: uninstall hints.needs_refresh is always False; needs_restart
    comes from the removed library."""
    target = _identity("haybale_ext", needs_restart=True, needs_refresh=True)
    mgr, _ = _make_manager(libraries_before={"haybale_ext": target},
                           libraries_after={})

    with patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))), \
         patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())):
        success, _msg, hints = await mgr.uninstall_streaming("haybale_ext", on_output=lambda _l: None)

    assert success is True
    assert hints.needs_refresh is False  # uninstall never sets refresh
    assert hints.needs_restart is True


@pytest.mark.unit
async def test_uninstall_with_no_restart_flag_returns_empty_hints():
    """Uninstalling a library that didn't declare needs_restart → empty hints."""
    target = _identity("haybale_plain")
    mgr, _ = _make_manager(libraries_before={"haybale_plain": target},
                           libraries_after={})

    with patch.object(mgr, "_run_uv_streaming", new=AsyncMock(return_value=(True, ""))), \
         patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda fn: fn())):
        success, _msg, hints = await mgr.uninstall_streaming("haybale_plain", on_output=lambda _l: None)

    assert success is True
    assert hints == PostInstallHints()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_library_manager_hints.py -v`
Expected: All six tests FAIL — install() and uninstall_streaming() currently return 2-tuples, so unpacking into 3 names raises `ValueError: not enough values to unpack`.

- [ ] **Step 3: Modify `library_manager.py` — add import and `_compute_install_hints` helper**

Open `barn/haybale-marketplace/haybale_marketplace/library_manager.py`. Locate the import block near the top. Add (next to the existing imports of `LibraryRegistry`, `InstallType`, etc. — find the natural location for a `haywire.ui` import):

```python
from haywire.ui.modals.install_progress_modal import PostInstallHints
```

Then, locate the `LibraryManager` class. After `_parse_dry_run_removals` and before `dry_run`, add the helper:

```python
    def _hints_for_library(self, library_id: str) -> PostInstallHints:
        """Read the post-install flags off a library's identity.

        Returns an empty PostInstallHints if the library is no longer registered
        (e.g. we're querying after it's been evicted).
        """
        try:
            identity = self.registry.get_library_identity(library_id)
        except KeyError:
            return PostInstallHints()
        return PostInstallHints(
            needs_refresh=identity.needs_refresh,
            needs_restart=identity.needs_restart,
        )
```

- [ ] **Step 4: Modify `install()` to compute and return hints**

Replace the body of `install()` (currently lines ~292-350). The new body:

```python
    async def install(
        self,
        install_spec: str,
        on_output: Callable[[str], None],
        source_pkg: "Haybale | None" = None,
    ) -> tuple[bool, str, PostInstallHints]:
        """Install a package with live output streaming.

        Returns ``(success, message, hints)`` where ``hints`` is a
        :class:`PostInstallHints` unioned across newly-imported libraries
        (success path) and any evicted libraries (success OR failure path,
        for ``needs_restart`` only).
        """
        if Path(install_spec).is_dir():
            args = ["install", "-e", install_spec]
        else:
            args = ["install", "--no-sources", install_spec]

        # Capture pre-install registered library_ids so we can compute the
        # newly-imported set post-scan.
        pre_install_ids = set(self.registry.list_names())

        # Pre-evict libraries that pip is about to upgrade. Capture each
        # evicted library's hints BEFORE remove_library() drops the identity.
        try:
            to_remove = await self.dry_run(install_spec)
        except RuntimeError:
            to_remove = []

        evicted_restart_hint = PostInstallHints()
        evicted: list[str] = []
        for dist_name in to_remove:
            lib_id = self.registry.find_library_by_distribution_name(dist_name)
            if lib_id and self.registry.get_library_install_type(lib_id) == InstallType.REGULAR:
                # Capture needs_restart only (per Q5/B: refresh is install-only,
                # and Q12.A: a failed install with an evicted restart-lib should
                # still surface the restart hint).
                lib_hints = self._hints_for_library(lib_id)
                evicted_restart_hint = evicted_restart_hint.merge(
                    PostInstallHints(needs_restart=lib_hints.needs_restart)
                )
                self.registry.remove_library(lib_id)
                evicted.append(dist_name)

        if evicted:
            on_output(f"Preparing upgrade: removing {', '.join(evicted)} from registry…")

        success, stderr = await self._run_uv_streaming(args, on_output)
        if not success:
            # Failure path: needs_refresh always False; needs_restart from evictions only.
            return False, f"Install failed: {stderr}", evicted_restart_hint

        on_output("Invalidating caches...")
        self._invalidate_caches()

        on_output("Scanning for libraries...")
        await asyncio.to_thread(self.registry.scan_for_libraries)

        on_output("Enabling libraries...")
        self.registry.enable_all_libraries()

        if source_pkg is not None:
            self._sync_install_to_pyproject(source_pkg, on_output)

        # Success path: union evicted-restart with the freshly-imported set.
        post_install_ids = set(self.registry.list_names())
        new_ids = post_install_ids - pre_install_ids
        hints = evicted_restart_hint
        for lid in new_ids:
            hints = hints.merge(self._hints_for_library(lid))

        return True, f"Installed: {install_spec}", hints
```

- [ ] **Step 5: Modify `install_streaming()` deprecated alias to forward the 3-tuple**

Replace its body:

```python
    async def install_streaming(
        self,
        install_spec: str,
        on_output: Callable[[str], None],
        source_pkg: "Haybale | None" = None,
    ) -> tuple[bool, str, PostInstallHints]:
        """Deprecated alias for install(). Use install() directly."""
        return await self.install(install_spec, on_output, source_pkg)
```

- [ ] **Step 6: Modify `uninstall_streaming()` to compute and return hints**

Replace its body:

```python
    async def uninstall_streaming(
        self,
        library_id: str,
        on_output: Callable[[str], None],
    ) -> tuple[bool, str, PostInstallHints]:
        """Uninstall a library with live output streaming.

        Returns ``(success, message, hints)`` where ``hints.needs_refresh`` is
        always False (per Q5/B) and ``hints.needs_restart`` reflects the
        removed library's declared flag, captured before disable.
        """
        dist_name = self.registry.get_library_distribution_name(library_id)
        if not dist_name:
            return False, f"Cannot find pip package name for library '{library_id}'", PostInstallHints()

        # Capture the library's hints before disabling — registry may drop the identity.
        lib_hints = self._hints_for_library(library_id)
        # Per Q5/B: refresh is install-only for uninstall.
        hints = PostInstallHints(needs_restart=lib_hints.needs_restart)

        self.registry.disable_library(library_id)

        success, stderr = await self._run_uv_streaming(
            ["uninstall", dist_name],
            on_output,
        )
        if not success:
            return False, f"Uninstall failed: {stderr}", hints

        on_output("Invalidating caches...")
        self._invalidate_caches()

        on_output("Scanning for libraries...")
        await asyncio.to_thread(self.registry.scan_for_libraries)

        self._sync_uninstall_from_pyproject(dist_name, on_output)

        return True, f"Uninstalled: {dist_name}", hints
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_library_manager_hints.py -v`
Expected: All six tests PASS.

If `_hints_for_library` raises because `get_library_identity` raises a non-KeyError exception type in the mock, adjust the mock's `side_effect` to raise `KeyError`. If the mock signature is different from what the test assumes, debug the call vs. the real registry's method signatures.

- [ ] **Step 8: Sanity-check the existing dry_run tests still pass**

Run: `uv run pytest tests/test_library_manager_dry_run.py tests/test_library_manager_marketplace_writes.py -v`
Expected: All existing tests still PASS (nothing about dry_run / pyproject writes changed).

- [ ] **Step 9: Type check the module**

Run: `uv run mypy barn/haybale-marketplace/haybale_marketplace/library_manager.py`
Expected: no new errors beyond the pre-edit baseline.

- [ ] **Step 10: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/library_manager.py tests/test_library_manager_hints.py
git commit -m "feat(library-manager): return PostInstallHints from install/uninstall

install() and uninstall_streaming() now return (success, message, hints).
Hints are unioned across newly-imported (success) and evicted (success/failure)
libraries per the design rules:
  - install success: refresh|restart OR over newly-imported; restart OR over evicted.
  - install failure: refresh=False; restart OR over evicted (per Q12.A).
  - uninstall: refresh=False (per Q5/B); restart from the removed library.

install_streaming() deprecated alias forwards the 3-tuple unchanged."
```

---

## Task 6: Update `_do_install` and `_do_uninstall` call sites in `library_overview_editor.py`

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`

Two call sites:
1. `_do_install` (around lines 1490, 1551, 1553): unpacks `manager.install(...)` 3-tuple; passes `hints` to `progress.finish(...)`. Also: rename import from `install_progress_modal` → `library_operation_progress_modal`.
2. `_do_uninstall` (around lines 855-878): currently uses the inline `_create_log_in_card` log card. Convert to the renamed modal (per Q14.A — uninstall reuses the same modal). Pass `hints` to `finish()`.

No automated test for this file — it's UI orchestration tightly coupled to NiceGUI page context and the surrounding editor. The terminal-state correctness is covered by Task 4's tests on the modal itself, and Task 5's tests on the hints computation. This task is wiring.

- [ ] **Step 1: Update the `_do_install` import line**

Open `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`. Locate the import inside `_do_install` (around line 1490):

```python
        from haywire.ui.modals import install_progress_modal, upgrade_impact_modal
```

Change to:

```python
        from haywire.ui.modals import library_operation_progress_modal, upgrade_impact_modal
```

- [ ] **Step 2: Update the `_do_install` modal-construction and finish() calls**

Locate the modal construction (around line 1551):

```python
        progress = install_progress_modal(title=f"Installing {name}…")

        success, message = await manager.install(install_spec, progress.push, source_pkg)

        if success:
            progress.push(f"--- {name} installed successfully ---")
            progress.finish()
            ui.notify(f"Installed: {name}", type="positive")
            installed = self._find_installed_by_dist_name(name, manager)
            if installed:
                context.active_library = installed
            self._notify_library_changed(context)
        else:
            progress.push(f"--- ERROR: {message} ---")
            progress.finish(error=message)
            ui.notify(message, type="negative")
```

Replace with:

```python
        progress = library_operation_progress_modal(title=f"Installing {name}…")

        success, message, hints = await manager.install(install_spec, progress.push, source_pkg)

        if success:
            progress.push(f"--- {name} installed successfully ---")
            progress.finish(hints=hints)
            ui.notify(f"Installed: {name}", type="positive")
            installed = self._find_installed_by_dist_name(name, manager)
            if installed:
                context.active_library = installed
            self._notify_library_changed(context)
        else:
            progress.push(f"--- ERROR: {message} ---")
            progress.finish(error=message, hints=hints)
            ui.notify(message, type="negative")
```

- [ ] **Step 3: Convert `_do_uninstall` to use the renamed modal**

Locate `_do_uninstall` (around line 856). Current body:

```python
    async def _do_uninstall(
        self,
        library_id: str,
        label: str,
        manager,
        context: "SessionContext",
    ):
        """Perform uninstall with streaming log output."""
        ui.notify(f"Uninstalling {label}…", type="info")
        log = self._create_log_in_card(self._fixed, f"Uninstalling {label}…")

        success, message = await manager.uninstall_streaming(library_id, log.push)

        if success:
            log.push(f"--- {label} uninstalled successfully ---")
            ui.notify(f"Uninstalled: {label}", type="positive")
        else:
            log.push(f"--- ERROR: {message} ---")
            ui.notify(message, type="negative")

        # Clear the active library and notify all editors
        context.active_library = None
        self._notify_library_changed(context)
```

Replace with:

```python
    async def _do_uninstall(
        self,
        library_id: str,
        label: str,
        manager,
        context: "SessionContext",
    ):
        """Perform uninstall with streaming log output, surfacing post-uninstall hints."""
        from haywire.ui.modals import library_operation_progress_modal

        ui.notify(f"Uninstalling {label}…", type="info")
        progress = library_operation_progress_modal(title=f"Uninstalling {label}…")

        success, message, hints = await manager.uninstall_streaming(library_id, progress.push)

        if success:
            progress.push(f"--- {label} uninstalled successfully ---")
            progress.finish(hints=hints)
            ui.notify(f"Uninstalled: {label}", type="positive")
        else:
            progress.push(f"--- ERROR: {message} ---")
            progress.finish(error=message, hints=hints)
            ui.notify(message, type="negative")

        # Clear the active library and notify all editors
        context.active_library = None
        self._notify_library_changed(context)
```

- [ ] **Step 4: Search for any remaining references to the old names**

Run: `grep -rn "install_progress_modal\|InstallProgressModal" /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo --include="*.py" | grep -v __pycache__`
Expected: zero matches. If any appear (other than the historical commit messages), update them.

- [ ] **Step 5: Type check the modified modules**

Run: `uv run mypy barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`
Expected: no new errors beyond the pre-edit baseline.

- [ ] **Step 6: Smoke-run the studio**

Run: `uv run haywire` (start the studio process).
Manually verify in the browser:
  1. Open the Library Browser → AVAILABLE filter.
  2. Pick a small library, click Install.
  3. Confirm the progress modal opens, streams `uv pip install` output.
  4. On success, terminal-state button text should be `Done` (since no in-repo haybale currently declares `needs_refresh=True` until a follow-up commit).
  5. Click Done. Modal closes.

If a library declared `needs_refresh=True` for testing, the button should read "Reload the page" and clicking it should reload the tab.

If you can't smoke-test interactively, run the existing integration tests:
`uv run pytest -m integration tests/marketstall/ -v`
Expected: all existing integration tests PASS (no regressions in the install pipeline).

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py
git commit -m "feat(library-overview): wire PostInstallHints through install/uninstall UX

_do_install and _do_uninstall now unpack the 3-tuple from LibraryManager and
pass hints to progress.finish(). _do_uninstall converted from the inline log
card to the renamed library_operation_progress_modal — uninstall now uses the
same modal as install, with needs_restart surfaced via the 'How to restart
Studio' terminal state when applicable."
```

---

## Task 7: Full-suite regression sanity check

**Files:** none modified — verification only.

- [ ] **Step 1: Run the full unit suite**

Run: `uv run pytest -m unit -v`
Expected: all tests PASS. New tests from Tasks 1, 3, 4, 5 are included; pre-existing tests are unchanged.

- [ ] **Step 2: Run the full ruff lint**

Run: `uv run ruff check .`
Expected: clean (or no new warnings beyond the pre-edit baseline).

- [ ] **Step 3: Run mypy on all the modules this plan touched**

Run:
```sh
uv run mypy \
  packages/haywire-core/src/haywire/core/library/identity.py \
  packages/haywire-core/src/haywire/core/library/decorator.py \
  packages/haywire-core/src/haywire/ui/modals/install_progress_modal.py \
  packages/haywire-core/src/haywire/ui/modals/__init__.py \
  barn/haybale-marketplace/haybale_marketplace/library_manager.py \
  barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py
```
Expected: no new errors beyond the pre-edit baseline. If any appear, fix them now — do not commit with new type errors.

- [ ] **Step 4: Run ruff format check**

Run: `uv run ruff format --check .`
Expected: no formatting drift in any of the touched files. If drift exists, run `uv run ruff format <touched files>` and amend the last commit (or make a new formatting commit).

- [ ] **Step 5: Final commit (only if a fix was needed in steps 1-4)**

```bash
git add <files-fixed>
git commit -m "chore: post-implementation cleanup for post-install requirements"
```

If steps 1-4 were all clean, skip this step — there's nothing to commit.

---

## Out of scope (separate follow-up work)

These are deliberate omissions, captured per the design summary:

- **Auditing in-monorepo haybales for correct `needs_refresh` / `needs_restart` values** (per Q13.A). The framework lands here; haybale-graph-editor and other haybales update at their own pace. Today's "graph-editor renders bunched in upper-left after install" bug persists until haybale-graph-editor is republished with `needs_refresh=True` — that's a separate change to that library's `@library(...)` call.

- **Real restart implementation** (per Q4 follow-up note). The "How to restart Studio" button reveals instructions but does not actually quit the process. Investigating a real auto-restart button (across launch contexts: terminal, packaged app, systemd, Docker) is deferred.

- **Auto-detection or publish-time / import-time lint of missing flags** (rejected per Q2, Q7). The trust-the-author model is explicit; do not add cross-checks at any layer.

- **Changes to the upgrade-impact-modal flow** ([library_overview_editor.py:1490-1548](../../barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py)). That modal already handles its concern (warn about collateral upgrades before install runs). It is upstream of the install-progress modal and unaffected by hints.

---

## Self-review notes

- **Spec coverage:** Each numbered item in the inquisition summary maps to a task:
  - Decorator flags + LibraryIdentity → Tasks 1-2.
  - `PostInstallHints` dataclass in `haywire.ui` → Task 3.
  - Modal rename + three terminal states → Task 4.
  - Install/uninstall return hints with Q5/Q6/Q12 union → Task 5.
  - Caller updates → Task 6.
  - "How to restart Studio" reveal-instructions UX (no auto-quit) → Task 4 (Step 3, in the `library_operation_progress_modal` factory and `finish()` body).
  - Regression sanity check → Task 7.
- **Placeholder scan:** No "TBD" / "add appropriate" / "similar to" left in code or commands. Every test contains real assertions; every replacement shows the actual replacement text.
- **Type consistency:** `PostInstallHints` field names (`needs_refresh`, `needs_restart`) and method name (`merge`) are identical across Tasks 1, 3, 4, 5. The modal class name `LibraryOperationProgressModal` and factory `library_operation_progress_modal` are identical across Tasks 4, 6. The `LibraryIdentity` field names match between Tasks 1 and 5's test helper. The 3-tuple return order is `(success, message, hints)` everywhere.
