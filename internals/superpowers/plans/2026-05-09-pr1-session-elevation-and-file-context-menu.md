# PR 1: Session Elevation + File Context Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevate `Session`, `SessionManager`, `SessionContext`, `WorkspaceManager`, `context_signals`, and `reactive` from `haywire.ui.*` to `haywire.core.*`; rewire shell ownership so `Session` no longer holds an `AppShell` back-reference; add `provide_session_manager()` to the DI module; add ambient globals for `SessionManager` and `workspace_root`; build a generic `FileBrowser` context-menu mechanism reusing the existing `@panel(action=, focus=, poll)` machinery (mirrors `SessionContextMenuProvider`).

**Architecture:** All cross-layer dependencies use the documented module-level-globals pattern in `haywire.core.di.context` (NOT `ContextVar` — see `.insights/project_di_context.md`). `Session` keeps its callback-slot pattern for `signal_orchestrator` and `lifecycle_orchestrator`; the `_shell` back-reference is replaced by `studio.app` owning a `_shells: dict[session_id, AppShell]` and calling `shell.cleanup()` upstream of `sm.remove_session(sid)`. The file-context-menu mirrors `SessionContextMenuProvider` ([context_menu.py](barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu.py)) as a focused copy: new `FileFocus`, `FileBrowserActions` Protocol (single method `reveal(editor_cls, binding_id, label)`), `FileBrowserState(SessionState)` with a transient `right_clicked_file: Reactive[Path|None]` (cleared on menu close), and a `SessionFileMenuProvider`. After both providers exist, opportunistically extract a shared `BaseContextMenuProvider` IF and only IF doing so does not require inventing a new shared dependency.

**Tech Stack:** Python 3.12, NiceGUI/Quasar, `injector` library (already used in `HaywireModule`), `pytest` (markers: `unit`, `integration`).

**Out of scope (deferred to PR 2):** Anything that touches `Haystack`, `HaystackEditor`, `GraphEditor`, or the `IProjectState.haystack` attribute. PR 1 is pure infrastructure — the `FileBrowser` keeps its current hardcoded `_open_graph_file()` routing through `app.haystack` until PR 2 deletes it.

---

## File Structure

### Files created

- `packages/haywire-core/src/haywire/core/session/__init__.py`
- `packages/haywire-core/src/haywire/core/session/session.py` — moved from `haywire.ui.session`
- `packages/haywire-core/src/haywire/core/session/session_manager.py` — moved from `haywire.ui.session_manager`
- `packages/haywire-core/src/haywire/core/session/context.py` — moved from `haywire.ui.context`
- `packages/haywire-core/src/haywire/core/session/context_signals.py` — moved from `haywire.ui.context_signals`
- `packages/haywire-core/src/haywire/core/session/protocols.py` — moved from `haywire.ui.protocols`
- `packages/haywire-core/src/haywire/core/session/reactive.py` — moved from `haywire.ui.reactive`
- `packages/haywire-core/src/haywire/core/session/workspace/__init__.py`
- `packages/haywire-core/src/haywire/core/session/workspace/manager.py` — moved from `haywire.ui.workspace.manager`
- `barn/haybale-studio/haybale_studio/state/file_browser_state.py` — `FileBrowserState(SessionState)`
- `barn/haybale-studio/haybale_studio/focuses/file_focus.py` — `FileFocus(Focus)` (extending the existing focuses module)
- `barn/haybale-studio/haybale_studio/editors/file_browser_menu/__init__.py`
- `barn/haybale-studio/haybale_studio/editors/file_browser_menu/actions.py` — `FileBrowserActions` Protocol
- `barn/haybale-studio/haybale_studio/editors/file_browser_menu/provider.py` — `SessionFileMenuProvider`
- `tests/core/test_session/__init__.py` (renames of moved tests below)

### Files modified

- `packages/haywire-core/src/haywire/ui/session.py` — replace contents with re-export shim from `haywire.core.session.session`
- `packages/haywire-core/src/haywire/ui/session_manager.py` — re-export shim
- `packages/haywire-core/src/haywire/ui/context.py` — re-export shim
- `packages/haywire-core/src/haywire/ui/context_signals.py` — re-export shim
- `packages/haywire-core/src/haywire/ui/protocols.py` — re-export shim
- `packages/haywire-core/src/haywire/ui/reactive.py` — re-export shim
- `packages/haywire-core/src/haywire/ui/workspace/manager.py` — re-export shim
- `packages/haywire-core/src/haywire/core/di/context.py` — add `_session_manager` + `_workspace_root` slots, setters, getters
- `packages/haywire-core/src/haywire/core/di/config.py` — add `provide_session_manager()`
- `packages/haywire-core/src/haywire/core/state/base.py` — `SessionState` import path stays (already in core)
- `packages/haywire-studio/src/haywire_studio/app.py` — call `set_session_manager()` and `set_workspace_root()`; add `_shells: dict[str, AppShell]`; rewrite `on_disconnect` and `main_page`
- `barn/haybale-studio/haybale_studio/focuses/__init__.py` — export `FileFocus`
- `barn/haybale-studio/haybale_studio/state/__init__.py` — export `FileBrowserState`
- `barn/haybale-studio/haybale_studio/editors/file_browser.py` — wire right-click → `SessionFileMenuProvider`; keep `_open_graph_file` routing intact (deletion is PR 2)
- `barn/haybale-studio/haybale_studio/__init__.py` (or wherever `register_components()` lives) — register `FileBrowserState` and `FileFocus`
- 53 import sites across `packages/` and `barn/` will eventually need updates from `from haywire.ui.X import Y` to `from haywire.core.session.X import Y`. **Strategy:** keep the `haywire.ui.*` shims working for the entire PR so import sites don't need to change yet. Cleanup of import sites is a separate follow-up commit at the end.

### Test files

- `tests/core/test_session/test_session.py` — renamed from `tests/ui/test_session.py`
- `tests/core/test_session/test_session_manager.py` — renamed from `tests/ui/test_session_manager.py`
- `tests/core/test_session/test_context.py` — renamed from `tests/ui/test_session_context.py`
- `tests/core/test_session/test_context_reactive.py` — renamed from `tests/ui/test_session_context_reactive.py`
- `tests/core/test_session/test_context_data.py` — renamed from `tests/ui/test_session_context_data.py`
- `tests/core/test_session/test_workspace_state.py` — renamed from `tests/ui/test_workspace_state.py`
- `tests/core/test_di/test_session_manager_provider.py` — new
- `tests/core/test_di/test_workspace_root_global.py` — new
- `tests/core/test_di/test_session_manager_global.py` — new
- `tests/ui/test_app/test_shell_cleanup_callback.py` — new
- `tests/studio/test_app/test_disconnect_flow.py` — new
- `tests/ui/test_file_browser_menu/test_file_focus.py` — new
- `tests/ui/test_file_browser_menu/test_file_browser_state.py` — new
- `tests/ui/test_file_browser_menu/test_session_file_menu_provider.py` — new
- `tests/ui/test_file_browser_menu/test_open_in_panel_smoke.py` — new

---

## Phase 1 — Elevate `reactive`, `context_signals`, `workspace.manager` (no dependencies on Session)

These three modules have the fewest dependencies — moving them first lets later moves rely on the new locations.

### Task 1: Move `reactive.py` to core, leave shim

**Files:**
- Create: `packages/haywire-core/src/haywire/core/session/__init__.py`
- Create: `packages/haywire-core/src/haywire/core/session/reactive.py`
- Modify: `packages/haywire-core/src/haywire/ui/reactive.py` (replace with shim)

- [ ] **Step 1: Create the empty session package**

```python
# packages/haywire-core/src/haywire/core/session/__init__.py
"""Session, SessionManager, SessionContext, signals — elevated from haywire.ui."""
```

- [ ] **Step 2: Verify the package is discoverable**

Run: `uv run python -c "import haywire.core.session"`
Expected: no output (success).

- [ ] **Step 3: Copy reactive.py contents verbatim to new location**

```bash
cp packages/haywire-core/src/haywire/ui/reactive.py \
   packages/haywire-core/src/haywire/core/session/reactive.py
```

- [ ] **Step 4: Replace the old location with a re-export shim**

Replace the entire contents of `packages/haywire-core/src/haywire/ui/reactive.py` with:

```python
"""Compatibility shim — Reactive lives in haywire.core.session.reactive.

This module re-exports for backwards compatibility. New code should import
from haywire.core.session.reactive directly.
"""

from haywire.core.session.reactive import *  # noqa: F401, F403
from haywire.core.session.reactive import (  # noqa: F401
    Reactive,
    iter_reactive_fields,
    reactive_field,
)
```

- [ ] **Step 5: Run reactive tests at the old import path to confirm shim works**

Run: `uv run pytest tests/ -k "reactive" -v`
Expected: all reactive-related tests pass (they import via `haywire.ui.reactive`).

- [ ] **Step 6: Run the full unit suite to confirm nothing broke**

Run: `uv run pytest -m "not integration" -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/__init__.py \
        packages/haywire-core/src/haywire/core/session/reactive.py \
        packages/haywire-core/src/haywire/ui/reactive.py
git commit -m "refactor(core): move haywire.ui.reactive to haywire.core.session

Drop-in shim left at the old location so import sites keep working.
Part of PR1 session elevation work."
```

---

### Task 2: Move `context_signals.py` to core

**Files:**
- Create: `packages/haywire-core/src/haywire/core/session/context_signals.py`
- Modify: `packages/haywire-core/src/haywire/ui/context_signals.py` (shim)

- [ ] **Step 1: Copy context_signals.py to new location**

```bash
cp packages/haywire-core/src/haywire/ui/context_signals.py \
   packages/haywire-core/src/haywire/core/session/context_signals.py
```

- [ ] **Step 2: Replace old location with shim**

Replace the entire contents of `packages/haywire-core/src/haywire/ui/context_signals.py` with:

```python
"""Compatibility shim — moved to haywire.core.session.context_signals."""

from haywire.core.session.context_signals import *  # noqa: F401, F403
```

If `__all__` is not defined upstream, add explicit re-exports for the symbols actually used. Inspect the original file's class/function names and add them to the shim:

```python
from haywire.core.session.context_signals import (  # noqa: F401
    ContextSignal,
    LifecycleCommand,
    Reveal,
    Close,
    ActiveFileMoved,
    Subject,
    # ... add every public name exported by the original file
)
```

- [ ] **Step 3: Verify the shim covers every name**

Run: `uv run pytest -m "not integration" -q`
Expected: all green. If any test fails with `ImportError: cannot import name X from haywire.ui.context_signals`, add `X` to the shim re-exports and re-run.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/context_signals.py \
        packages/haywire-core/src/haywire/ui/context_signals.py
git commit -m "refactor(core): move context_signals to haywire.core.session

Shim left at haywire.ui.context_signals for backwards compatibility."
```

---

### Task 3: Move `workspace/manager.py` to core

**Files:**
- Create: `packages/haywire-core/src/haywire/core/session/workspace/__init__.py`
- Create: `packages/haywire-core/src/haywire/core/session/workspace/manager.py`
- Modify: `packages/haywire-core/src/haywire/ui/workspace/manager.py` (shim)

- [ ] **Step 1: Create the workspace subpackage and move the file**

```bash
mkdir -p packages/haywire-core/src/haywire/core/session/workspace
touch packages/haywire-core/src/haywire/core/session/workspace/__init__.py
cp packages/haywire-core/src/haywire/ui/workspace/manager.py \
   packages/haywire-core/src/haywire/core/session/workspace/manager.py
```

- [ ] **Step 2: Replace old location with shim**

Replace `packages/haywire-core/src/haywire/ui/workspace/manager.py` with:

```python
"""Compatibility shim — moved to haywire.core.session.workspace.manager."""

from haywire.core.session.workspace.manager import WorkspaceManager  # noqa: F401
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/ -k "workspace" -v -m "not integration"`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/workspace/ \
        packages/haywire-core/src/haywire/ui/workspace/manager.py
git commit -m "refactor(core): move WorkspaceManager to haywire.core.session.workspace

Shim at haywire.ui.workspace.manager for backwards compatibility."
```

---

## Phase 2 — Elevate `protocols.py` (still has `haystack: IGraphManager` — kept as-is for PR 1; PR 2 will drop it)

### Task 4: Move `protocols.py` to core

**Files:**
- Create: `packages/haywire-core/src/haywire/core/session/protocols.py`
- Modify: `packages/haywire-core/src/haywire/ui/protocols.py` (shim)

- [ ] **Step 1: Copy protocols.py to new location**

```bash
cp packages/haywire-core/src/haywire/ui/protocols.py \
   packages/haywire-core/src/haywire/core/session/protocols.py
```

- [ ] **Step 2: Update the new file's TYPE_CHECKING import for `SessionManager`**

In `packages/haywire-core/src/haywire/core/session/protocols.py`, the `TYPE_CHECKING` block currently reads `from haywire.ui.session_manager import SessionManager`. Change it to anticipate the upcoming move:

```python
if TYPE_CHECKING:
    from haywire.core.di.config import LibrarySystemService
    from haywire.core.session.session_manager import SessionManager
    from haywire_studio.library_manager import LibraryManager  # type: ignore[import-untyped]
    from haywire.core.state import LibraryStateContainer
```

(The actual `SessionManager` move happens in Task 7. Until then, this is a forward reference that resolves correctly at runtime because `TYPE_CHECKING` is `False`.)

- [ ] **Step 3: Replace old location with shim**

Replace `packages/haywire-core/src/haywire/ui/protocols.py` with:

```python
"""Compatibility shim — moved to haywire.core.session.protocols."""

from haywire.core.session.protocols import IGraphManager, IProjectState  # noqa: F401
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest -m "not integration" -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/protocols.py \
        packages/haywire-core/src/haywire/ui/protocols.py
git commit -m "refactor(core): move IProjectState and IGraphManager to core.session

Shim at haywire.ui.protocols for backwards compatibility. The
IProjectState.haystack attribute stays for PR1; PR2 will drop it
when haystack moves into its own library."
```

---

## Phase 3 — Elevate `SessionContext`, `Session`, `SessionManager` (the actual subjects of the elevation)

### Task 5: Move `context.py` (SessionContext) to core

**Files:**
- Create: `packages/haywire-core/src/haywire/core/session/context.py`
- Modify: `packages/haywire-core/src/haywire/ui/context.py` (shim)

- [ ] **Step 1: Copy context.py to new location**

```bash
cp packages/haywire-core/src/haywire/ui/context.py \
   packages/haywire-core/src/haywire/core/session/context.py
```

- [ ] **Step 2: Update imports inside the new file**

Edit `packages/haywire-core/src/haywire/core/session/context.py` to import from the new locations:

Replace:
```python
from haywire.ui.reactive import Reactive, iter_reactive_fields, reactive_field
```
with:
```python
from haywire.core.session.reactive import Reactive, iter_reactive_fields, reactive_field
```

Update the `TYPE_CHECKING` block:
```python
if TYPE_CHECKING:
    from haywire.core.library.info import LibraryInfo
    from haywire.core.session.protocols import IProjectState
    from haywire.core.session.session import Session
```

- [ ] **Step 3: Replace old location with shim**

Replace `packages/haywire-core/src/haywire/ui/context.py` with:

```python
"""Compatibility shim — moved to haywire.core.session.context."""

from haywire.core.session.context import SessionContext  # noqa: F401
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest -m "not integration" -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/context.py \
        packages/haywire-core/src/haywire/ui/context.py
git commit -m "refactor(core): move SessionContext to haywire.core.session.context"
```

---

### Task 6: Move `session.py` (Session) to core AND drop the AppShell back-reference

**Files:**
- Create: `packages/haywire-core/src/haywire/core/session/session.py`
- Modify: `packages/haywire-core/src/haywire/ui/session.py` (shim)
- Test: `tests/core/test_session/test_session.py` (renamed)

This task is the load-bearing one: it both relocates `Session` and removes the `_shell` field that pinned it to `haywire.ui.app.shell.AppShell`. We test-drive the back-ref removal first, then move.

- [ ] **Step 1: Write the failing test for the new cleanup-callback API**

Create `tests/core/test_session/__init__.py` (empty) if it doesn't exist, then create `tests/core/test_session/test_session.py`:

```python
"""Tests for Session core wiring (post-elevation).

Replaces tests/ui/test_session.py. Verifies that Session has no
AppShell back-reference and instead invokes a generic cleanup callback.
"""

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.session.session import Session


def _make_session(session_manager=None):
    return Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=session_manager or MagicMock(),
    )


def test_session_stores_session_manager():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    assert session._session_manager is sm


def test_session_has_no_shell_attr():
    """The _shell back-reference and set_shell() are gone."""
    session = _make_session()
    assert not hasattr(session, "_shell")
    assert not hasattr(session, "set_shell")


def test_session_cleanup_callback_invoked_on_cleanup():
    """Session.cleanup() calls the registered cleanup callback if set."""
    session = _make_session()
    cb = MagicMock()
    session.set_cleanup_callback(cb)
    session.cleanup()
    cb.assert_called_once_with()


def test_session_cleanup_callback_optional():
    """Session.cleanup() is a no-op for the callback path when none is set."""
    session = _make_session()
    # Should not raise
    session.cleanup()


def test_session_cleanup_clears_callbacks():
    """After cleanup, the signal/lifecycle/cleanup callbacks are cleared."""
    session = _make_session()
    session.set_signal_orchestrator(MagicMock())
    session.set_lifecycle_orchestrator(MagicMock())
    session.set_cleanup_callback(MagicMock())
    session.cleanup()
    assert session._signal_callback is None
    assert session._lifecycle_callback is None
    assert session._cleanup_callback is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/core/test_session/test_session.py -v`
Expected: ImportError on `haywire.core.session.session` (the module doesn't exist yet).

- [ ] **Step 3: Copy session.py to new location and apply the AppShell-removal edits**

```bash
cp packages/haywire-core/src/haywire/ui/session.py \
   packages/haywire-core/src/haywire/core/session/session.py
```

Then edit `packages/haywire-core/src/haywire/core/session/session.py`:

a) Update imports at the top:
```python
from typing import Callable, Optional, TYPE_CHECKING
import uuid
import logging

from haywire.core.session.context import SessionContext
from haywire.core.session.context_signals import ContextSignal, LifecycleCommand
from haywire.core.session.workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from haywire.core.session.session_manager import SessionManager
```

(Note: the `from haywire.ui.app.shell import AppShell` line is REMOVED entirely.)

b) In `Session.__init__`, remove the `self._shell = None` line. The other field initializations stay.

c) Add a new field initialization in `__init__` after the `_lifecycle_callback` line:
```python
self._cleanup_callback: Optional[Callable[[], None]] = None
```

d) Delete the `set_shell` method entirely.

e) Add a `set_cleanup_callback` method, modeled on `set_signal_orchestrator`:
```python
def set_cleanup_callback(self, callback: Callable[[], None]) -> None:
    """Register a callback to be invoked first thing in cleanup().

    Used by AppShell to perform UI teardown before Session-state cleanup
    runs. The callback signature is intentionally generic — Session does
    not know what the callback does.
    """
    self._cleanup_callback = callback
```

f) Rewrite the `cleanup` method:
```python
def cleanup(self) -> None:
    """Tear down per-session state.

    Invokes the registered cleanup callback first (if any), then clears
    all callback slots. Called by SessionManager.remove_session OR by
    upstream callers (e.g. studio.app.on_disconnect calling shell.cleanup
    before sm.remove_session).
    """
    if self._cleanup_callback is not None:
        try:
            self._cleanup_callback()
        except Exception as e:
            logger.error(f"Session {self.session_id}: cleanup callback error: {e}")
    self._signal_callback = None
    self._lifecycle_callback = None
    self._cleanup_callback = None
    logger.info(f"Session cleaned up: {self.session_id}")
```

- [ ] **Step 4: Replace old location with shim**

Replace `packages/haywire-core/src/haywire/ui/session.py` with:

```python
"""Compatibility shim — moved to haywire.core.session.session."""

from haywire.core.session.session import Session  # noqa: F401
```

- [ ] **Step 5: Run the new tests**

Run: `uv run pytest tests/core/test_session/test_session.py -v`
Expected: all four tests pass.

- [ ] **Step 6: Delete the old test file (it's been replaced)**

```bash
git rm tests/ui/test_session.py
```

- [ ] **Step 7: Run the full unit suite — there will be failures from callers that called `set_shell` or read `session._shell`**

Run: `uv run pytest -m "not integration" -q`
Expected: failures in `packages/haywire-core/src/haywire/ui/app/shell.py` and `packages/haywire-studio/src/haywire_studio/app.py` (callers of `session.set_shell`). Note them.

- [ ] **Step 8: Find and remove `set_shell` call sites; defer the disconnect rewrite to Task 9**

Search:
```bash
grep -rn "set_shell\|session\._shell" packages/ barn/ --include="*.py"
```

For each call site, **delete the `session.set_shell(...)` call** but leave the rest of the surrounding code untouched. The disconnect dance (Task 9) will handle the new wiring.

Specifically, in `packages/haywire-studio/src/haywire_studio/app.py:246`, delete the `haywire_session.set_shell(app_shell)` line. The shell is created and rendered as before, but Session no longer holds a reference to it.

In `packages/haywire-core/src/haywire/ui/app/shell.py`, search for any code that reads `session._shell`. There should be none — `_shell` was only ever written by `set_shell` and read by `Session.cleanup`. Verify.

- [ ] **Step 9: Run unit tests again**

Run: `uv run pytest -m "not integration" -q`
Expected: all green. Note: actual disconnect cleanup of AppShell is broken at this point — that's intentional and gets fixed in Task 9.

- [ ] **Step 10: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/session.py \
        packages/haywire-core/src/haywire/ui/session.py \
        tests/core/test_session/test_session.py \
        tests/ui/test_session.py \
        packages/haywire-studio/src/haywire_studio/app.py
git commit -m "refactor(core): elevate Session to core.session, drop AppShell back-ref

Session no longer holds a typed AppShell reference. set_shell() is
removed; replaced with a generic set_cleanup_callback(). AppShell
cleanup is rewired in the disconnect-flow task (PR1 Task 9)."
```

---

### Task 7: Move `SessionManager` to core

**Files:**
- Create: `packages/haywire-core/src/haywire/core/session/session_manager.py`
- Modify: `packages/haywire-core/src/haywire/ui/session_manager.py` (shim)
- Test: `tests/core/test_session/test_session_manager.py`

- [ ] **Step 1: Copy session_manager.py to new location**

```bash
cp packages/haywire-core/src/haywire/ui/session_manager.py \
   packages/haywire-core/src/haywire/core/session/session_manager.py
```

- [ ] **Step 2: Update imports inside the new file**

In `packages/haywire-core/src/haywire/core/session/session_manager.py`:

Replace:
```python
from haywire.ui.context_signals import ContextSignal, Subject
```
with:
```python
from haywire.core.session.context_signals import ContextSignal, Subject
```

Update the `TYPE_CHECKING` block:
```python
if TYPE_CHECKING:
    from haywire.core.session.session import Session
```

Update the in-method import in `create_session`:
```python
def create_session(self, **session_kwargs) -> "Session":
    ...
    from haywire.core.session.session import Session
    ...
```

- [ ] **Step 3: Replace old location with shim**

Replace `packages/haywire-core/src/haywire/ui/session_manager.py` with:

```python
"""Compatibility shim — moved to haywire.core.session.session_manager."""

from haywire.core.session.session_manager import SessionManager  # noqa: F401
```

- [ ] **Step 4: Move and rename the existing tests**

```bash
mkdir -p tests/core/test_session
git mv tests/ui/test_session_manager.py tests/core/test_session/test_session_manager.py
```

In the moved test file, update imports from `from haywire.ui.session_manager import SessionManager` to `from haywire.core.session.session_manager import SessionManager`.

- [ ] **Step 5: Run the moved tests**

Run: `uv run pytest tests/core/test_session/test_session_manager.py -v`
Expected: all pass.

- [ ] **Step 6: Run the full unit suite**

Run: `uv run pytest -m "not integration" -q`
Expected: all green (the shim covers callers).

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/session_manager.py \
        packages/haywire-core/src/haywire/ui/session_manager.py \
        tests/core/test_session/test_session_manager.py
git commit -m "refactor(core): move SessionManager to haywire.core.session

Shim at haywire.ui.session_manager for backwards compatibility."
```

---

### Task 8: Move remaining session-related tests under tests/core/test_session/

- [ ] **Step 1: Move tests with git mv to preserve history**

```bash
git mv tests/ui/test_session_context.py tests/core/test_session/test_context.py
git mv tests/ui/test_session_context_reactive.py tests/core/test_session/test_context_reactive.py
git mv tests/ui/test_session_context_data.py tests/core/test_session/test_context_data.py
git mv tests/ui/test_workspace_state.py tests/core/test_session/test_workspace_state.py
```

- [ ] **Step 2: Update imports in each moved test file**

In each moved file, replace `from haywire.ui.context import` with `from haywire.core.session.context import`, `from haywire.ui.reactive import` with `from haywire.core.session.reactive import`, and `from haywire.ui.workspace.manager import` with `from haywire.core.session.workspace.manager import`.

Search to confirm no `haywire.ui.context` / `haywire.ui.reactive` / `haywire.ui.workspace.manager` imports remain in the moved files:

```bash
grep -n "from haywire.ui.context\|from haywire.ui.reactive\|from haywire.ui.workspace" tests/core/test_session/
```
Expected: no output.

- [ ] **Step 3: Run the moved tests**

Run: `uv run pytest tests/core/test_session/ -v`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test(core): move session-related tests under tests/core/test_session/

Updates imports to point at the new haywire.core.session.* locations.
The old haywire.ui.* shims still work but tests assert on the canonical
locations."
```

---

## Phase 4 — Add ambient globals for `SessionManager` and `workspace_root`; add DI provider for `SessionManager`

### Task 9: Add `_session_manager` ambient slot to `core/di/context.py`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/di/context.py`
- Test: `tests/core/test_di/test_session_manager_global.py` (new)

- [ ] **Step 1: Write failing test**

Create `tests/core/test_di/__init__.py` (empty) if missing, then create `tests/core/test_di/test_session_manager_global.py`:

```python
"""Test that the ambient SessionManager global behaves like its peers."""

from unittest.mock import MagicMock

import pytest


def test_get_raises_before_set():
    # Reset global so the test is independent of test order
    import haywire.core.di.context as ctx_mod
    ctx_mod._session_manager = None

    from haywire.core.di.context import get_session_manager
    with pytest.raises(RuntimeError, match="SessionManager not set"):
        get_session_manager()


def test_set_then_get_returns_same_instance():
    from haywire.core.di.context import set_session_manager, get_session_manager

    sm = MagicMock()
    set_session_manager(sm)
    assert get_session_manager() is sm


def test_set_overwrites_previous():
    from haywire.core.di.context import set_session_manager, get_session_manager

    sm1 = MagicMock()
    sm2 = MagicMock()
    set_session_manager(sm1)
    set_session_manager(sm2)
    assert get_session_manager() is sm2
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest tests/core/test_di/test_session_manager_global.py -v`
Expected: ImportError on `set_session_manager` / `get_session_manager`.

- [ ] **Step 3: Add the slot, setter, and getter to `core/di/context.py`**

Open `packages/haywire-core/src/haywire/core/di/context.py`. Inside the `TYPE_CHECKING` block, add:

```python
    from haywire.core.session.session_manager import SessionManager
```

After `_settings_registry: Optional["SettingsRegistry"] = None`, add:

```python
_session_manager: Optional["SessionManager"] = None
```

In the setters section (after `set_settings_registry`), add:

```python
def set_session_manager(manager: "SessionManager") -> None:
    global _session_manager
    _session_manager = manager
```

In the getters section (after `get_settings_registry`), add:

```python
def get_session_manager() -> "SessionManager":
    if _session_manager is None:
        raise RuntimeError(
            "SessionManager not set in ambient context. "
            "Ensure HaywireApp has been initialised before requesting it."
        )
    return _session_manager
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/core/test_di/test_session_manager_global.py -v`
Expected: all three tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/di/context.py \
        tests/core/test_di/test_session_manager_global.py
git commit -m "feat(di): add SessionManager ambient global

Module-level set_session_manager/get_session_manager mirror the
existing pattern (see .insights/project_di_context.md). Will be
populated by HaywireApp in studio.app and by the new
provide_session_manager() in HaywireModule."
```

---

### Task 10: Add `_workspace_root` ambient slot

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/di/context.py`
- Test: `tests/core/test_di/test_workspace_root_global.py`

- [ ] **Step 1: Write failing test**

Create `tests/core/test_di/test_workspace_root_global.py`:

```python
"""Test that the ambient workspace_root global behaves like its peers."""

from pathlib import Path

import pytest


def test_get_raises_before_set():
    import haywire.core.di.context as ctx_mod
    ctx_mod._workspace_root = None

    from haywire.core.di.context import get_workspace_root
    with pytest.raises(RuntimeError, match="workspace_root not set"):
        get_workspace_root()


def test_set_then_get_returns_path():
    from haywire.core.di.context import set_workspace_root, get_workspace_root

    p = Path("/tmp/some-workspace")
    set_workspace_root(p)
    assert get_workspace_root() == p


def test_set_str_path_normalises_to_path():
    """Accepts str OR Path; always returns Path."""
    from haywire.core.di.context import set_workspace_root, get_workspace_root

    set_workspace_root("/tmp/another")
    assert get_workspace_root() == Path("/tmp/another")
    assert isinstance(get_workspace_root(), Path)
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest tests/core/test_di/test_workspace_root_global.py -v`
Expected: ImportError on `set_workspace_root` / `get_workspace_root`.

- [ ] **Step 3: Add the slot, setter, and getter**

In `packages/haywire-core/src/haywire/core/di/context.py`, add at the top (outside `TYPE_CHECKING`):

```python
from pathlib import Path
```

After `_session_manager: Optional["SessionManager"] = None`, add:

```python
_workspace_root: Optional[Path] = None
```

In the setters section:

```python
def set_workspace_root(path) -> None:
    """Set the ambient workspace root. Accepts str or Path."""
    global _workspace_root
    _workspace_root = Path(path)
```

In the getters section:

```python
def get_workspace_root() -> Path:
    if _workspace_root is None:
        raise RuntimeError(
            "workspace_root not set in ambient context. "
            "Ensure HaywireApp has been initialised before requesting it."
        )
    return _workspace_root
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/core/test_di/test_workspace_root_global.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/di/context.py \
        tests/core/test_di/test_workspace_root_global.py
git commit -m "feat(di): add workspace_root ambient global

Mirrors set_session_manager/get_session_manager. Populated by
HaywireApp.__init__."
```

---

### Task 11: Add `provide_session_manager()` to `HaywireModule`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/di/config.py`
- Test: `tests/core/test_di/test_session_manager_provider.py`

- [ ] **Step 1: Write failing test**

Create `tests/core/test_di/test_session_manager_provider.py`:

```python
"""Test that provide_session_manager wires SessionManager via DI and ambient context."""

from unittest.mock import MagicMock

import pytest


def test_provider_returns_session_manager():
    """The provider returns a SessionManager configured with the container."""
    import haywire.core.di.context as ctx_mod
    ctx_mod._session_manager = None

    from haywire.core.di.config import HaywireModule
    from haywire.core.session.session_manager import SessionManager
    from haywire.core.state import LibraryStateContainer

    container = LibraryStateContainer()
    module = HaywireModule(workspace_root="/tmp/test")  # adjust kwargs to match real signature
    sm = module.provide_session_manager(container)

    assert isinstance(sm, SessionManager)
    assert sm._container is container


def test_provider_publishes_to_ambient_context():
    """The provider also publishes the instance via set_session_manager."""
    import haywire.core.di.context as ctx_mod
    ctx_mod._session_manager = None

    from haywire.core.di.config import HaywireModule
    from haywire.core.di.context import get_session_manager
    from haywire.core.state import LibraryStateContainer

    container = LibraryStateContainer()
    module = HaywireModule(workspace_root="/tmp/test")
    sm = module.provide_session_manager(container)

    assert get_session_manager() is sm
```

Note: inspect `HaywireModule.__init__` in `packages/haywire-core/src/haywire/core/di/config.py` for the actual constructor signature; adjust `HaywireModule(...)` accordingly.

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest tests/core/test_di/test_session_manager_provider.py -v`
Expected: AttributeError or method-not-found on `provide_session_manager`.

- [ ] **Step 3: Add the provider to `HaywireModule`**

In `packages/haywire-core/src/haywire/core/di/config.py`, find the existing `provide_X` methods (around line 80–200). Add the import at the top:

```python
from haywire.core.di.context import (
    set_node_factory,
    set_adapter_factory,
    set_type_registry,
    set_settings_registry,
    set_session_manager,  # NEW
)
```

And add a new provider method alongside the others:

```python
@provider
@singleton
def provide_session_manager(
    self, container: LibraryStateContainer
) -> SessionManager:
    """Provide singleton SessionManager.

    Also publishes the instance to the ambient DI context so deep callers
    (AppState.on_enable) can read it without constructor injection.
    """
    manager = SessionManager(container=container)
    set_session_manager(manager)
    return manager
```

You may need to add `from haywire.core.session.session_manager import SessionManager` at the top of the file if not already imported.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/core/test_di/test_session_manager_provider.py -v`
Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/di/config.py \
        tests/core/test_di/test_session_manager_provider.py
git commit -m "feat(di): add provide_session_manager() to HaywireModule

The provider constructs a SessionManager bound to the container and
publishes it via set_session_manager(). HaywireApp will pull it via
the injector instead of constructing it directly."
```

---

### Task 12: Update `HaywireApp` to pull SessionManager from DI and set ambient globals

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py`

- [ ] **Step 1: In `HaywireApp.__init__`, set `workspace_root` ambient global**

Open `packages/haywire-studio/src/haywire_studio/app.py`. Find `__init__` (around line 36).

Add the import at the top:
```python
from haywire.core.di.context import set_workspace_root
```

Then in `__init__`, just after `self.workspace_root = workspace_root or os.getcwd()`, add:

```python
set_workspace_root(self.workspace_root)
```

- [ ] **Step 2: In `setup_shared_services`, pull SessionManager from the injector**

Replace the lines (currently around line 122–134):

```python
from haywire.core.state import LibraryStateContainer
from haywire.ui.session_manager import SessionManager

# ... (registries / factories / container setup unchanged)

# SessionManager needs the container to drive attach/detach.
self.session_manager = SessionManager(container=self.library_state_container)
```

with:

```python
from haywire.core.state import LibraryStateContainer
from haywire.core.session.session_manager import SessionManager

# ... (registries / factories / container setup unchanged)

# SessionManager comes from the DI container; provide_session_manager()
# also publishes it via set_session_manager() into the ambient context.
self.session_manager = self.library_service.injector.get(SessionManager)
```

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest -m "not integration" -q`
Expected: all green.

- [ ] **Step 4: Smoke-test the app boots**

Run: `uv run haywire` in a separate terminal. Watch the startup logs. Expected: `"Haywire workspace: ..."`, `"Library system initialized."`, `"Shared services configured successfully."`. The app reaches the "ready to serve" state without error.

If the app fails to boot due to ambient-context order (e.g. `provide_session_manager` runs before the container is created), check the order of provider declarations in `HaywireModule` — `provide_library_state_container` must be declared as a dependency in the `provide_session_manager` signature so injector resolves it first (it is, via the `container: LibraryStateContainer` parameter). If the failure is "set_workspace_root not called yet," verify the `set_workspace_root` call in `__init__` runs before any code path that reads it.

Stop the app (Ctrl-C). Note: the integration tests exercise more thoroughly, so you can also run:

Run: `uv run pytest -m integration -q -k "startup or boot"`
Expected: pass (if such tests exist).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/app.py
git commit -m "feat(studio): wire SessionManager via DI; set workspace_root ambient global

HaywireApp now pulls SessionManager from the injector (provided by
provide_session_manager()) instead of constructing it directly. The
workspace_root is published via set_workspace_root() so future AppStates
can read it from ambient context."
```

---

## Phase 5 — Rewire disconnect flow: shell-upstream model (Q7A)

### Task 13: Add a `_shells: dict[session_id, AppShell]` to `HaywireApp` and rewrite `on_disconnect`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py`
- Test: `tests/studio/test_app/test_disconnect_flow.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/studio/__init__.py` and `tests/studio/test_app/__init__.py` (empty) if missing, then create `tests/studio/test_app/test_disconnect_flow.py`:

```python
"""Test the shell-upstream disconnect flow.

Per Q7A in the design discussion: studio.app owns a shells dict
keyed by session_id. on_disconnect calls shell.cleanup() FIRST,
then sm.remove_session(sid). Session.cleanup() never reaches into
AppShell (it has no _shell field anymore — see PR1 Task 6).
"""

from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture
def app_under_test():
    """Construct a minimal HaywireApp-like object for disconnect testing.

    Avoids HaywireApp.__init__ (which boots the library system); we only
    need the disconnect-flow attributes.
    """
    from haywire_studio.app import HaywireApp
    app = HaywireApp.__new__(HaywireApp)
    app._is_shutting_down = False
    app._shells = {}
    app.session_manager = MagicMock()
    return app


def test_disconnect_calls_shell_cleanup_then_remove_session(app_under_test):
    sid = "abc12345"
    shell = MagicMock()
    app_under_test._shells[sid] = shell

    client = MagicMock()
    client._haywire_session_id = sid
    app_under_test.on_disconnect(client)

    # Shell cleanup runs first
    shell.cleanup.assert_called_once()
    # Then SessionManager removes the session
    app_under_test.session_manager.remove_session.assert_called_once_with(sid)
    # And the shell entry is gone from the dict
    assert sid not in app_under_test._shells


def test_disconnect_with_no_shell_still_removes_session(app_under_test):
    """If there's no shell (race or buggy state), still detach the session."""
    sid = "noshell0"
    client = MagicMock()
    client._haywire_session_id = sid
    app_under_test.on_disconnect(client)

    app_under_test.session_manager.remove_session.assert_called_once_with(sid)


def test_disconnect_without_session_id_is_noop(app_under_test):
    """A client with no _haywire_session_id (e.g. failed handshake) is skipped."""
    client = MagicMock()
    client._haywire_session_id = None
    app_under_test.on_disconnect(client)

    app_under_test.session_manager.remove_session.assert_not_called()


def test_disconnect_during_shutdown_skips(app_under_test):
    app_under_test._is_shutting_down = True
    sid = "shutdown"
    shell = MagicMock()
    app_under_test._shells[sid] = shell

    client = MagicMock()
    client._haywire_session_id = sid
    app_under_test.on_disconnect(client)

    shell.cleanup.assert_not_called()
    app_under_test.session_manager.remove_session.assert_not_called()
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest tests/studio/test_app/test_disconnect_flow.py -v`
Expected: failures — `_shells` doesn't exist on `HaywireApp`, and `on_disconnect` doesn't yet call `shell.cleanup()`.

- [ ] **Step 3: Add `_shells` dict to `HaywireApp.__init__`**

In `packages/haywire-studio/src/haywire_studio/app.py`, in `__init__`, just after `set_workspace_root(...)`, add:

```python
self._shells: dict[str, "AppShell"] = {}
```

Add the TYPE_CHECKING import at the top of the file:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from haywire.ui.app.shell import AppShell
```

(If TYPE_CHECKING is already imported, just add the AppShell line.)

- [ ] **Step 4: Rewrite `on_disconnect`**

Replace the body of `on_disconnect` (currently around line 88–95):

```python
def on_disconnect(self, client):
    """Handle client disconnect.

    Shell-upstream model (Q7A): tear down the AppShell first, then
    detach the session. SessionManager.remove_session does only state
    cleanup now — UI cleanup is the shell's responsibility.
    """
    if self._is_shutting_down:
        return
    session_id = getattr(client, "_haywire_session_id", None)
    if not session_id:
        return
    print(f"Client disconnected, cleaning up session {session_id[:8]}")

    shell = self._shells.pop(session_id, None)
    if shell is not None:
        try:
            shell.cleanup()
        except Exception as e:
            print(f"  Error cleaning up shell for session {session_id[:8]}: {e}")

    self.session_manager.remove_session(session_id)
```

- [ ] **Step 5: Register/unregister shells in `main_page`**

Find `main_page` in app.py (around line 220). After `app_shell = AppShell(haywire_session, editor_registry=editor_registry)`, add:

```python
self._shells[haywire_session.session_id] = app_shell
```

(The shell entry is removed in `on_disconnect` — see Step 4.)

- [ ] **Step 6: Run the disconnect tests**

Run: `uv run pytest tests/studio/test_app/test_disconnect_flow.py -v`
Expected: all four pass.

- [ ] **Step 7: Run the full unit suite**

Run: `uv run pytest -m "not integration" -q`
Expected: all green.

- [ ] **Step 8: Smoke-test the app: open a browser, close the tab, verify clean disconnect logs**

Run: `uv run haywire` in one terminal. In a browser, open `http://localhost:8082`. Wait for the UI to render. Close the tab. Watch the server logs — expected: `"Client disconnected, cleaning up session ..."` followed by `"SessionManager: removed session ..."`. No exceptions. Stop the app.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/app.py \
        tests/studio/test_app/test_disconnect_flow.py
git commit -m "refactor(studio): shell-upstream disconnect flow (Q7A)

studio.app now owns _shells dict keyed by session_id. on_disconnect
calls shell.cleanup() first, then sm.remove_session(sid). Session
itself is no longer involved in shell teardown.

SessionManager.remove_session() is unchanged but its session.cleanup()
call is now a no-op for the AppShell concern (Session.cleanup just
clears callback slots — see PR1 Task 6).

The previous design where SessionManager invoked session.cleanup() ->
shell.cleanup() via a back-reference is gone."
```

---

## Phase 6 — Build the `FileBrowser` context-menu infrastructure

This phase adds the new `FileFocus`, `FileBrowserActions`, `FileBrowserState`, and `SessionFileMenuProvider`. The `FileBrowser` itself is wired to open the menu on right-click but **keeps its existing left-click `_open_graph_file` routing** through `app.haystack` until PR 2 deletes it.

### Task 14: Add `FileBrowserState(SessionState)` with `right_clicked_file`

**Files:**
- Create: `barn/haybale-studio/haybale_studio/state/file_browser_state.py`
- Modify: `barn/haybale-studio/haybale_studio/state/__init__.py`
- Test: `tests/ui/test_file_browser_menu/test_file_browser_state.py`

- [ ] **Step 1: Write the failing test**

Create `tests/ui/test_file_browser_menu/__init__.py` (empty), then create `tests/ui/test_file_browser_menu/test_file_browser_state.py`:

```python
"""FileBrowserState — per-session, holds transient right-clicked file."""

from pathlib import Path

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_file_browser_state_starts_empty():
    from haybale_studio.state.file_browser_state import FileBrowserState
    state = FileBrowserState()
    assert state.right_clicked_file.value is None


def test_right_clicked_file_can_be_set_and_cleared():
    from haybale_studio.state.file_browser_state import FileBrowserState
    state = FileBrowserState()
    p = Path("/tmp/foo.haywire")
    state.right_clicked_file.value = p
    assert state.right_clicked_file.value == p
    state.right_clicked_file.value = None
    assert state.right_clicked_file.value is None


def test_state_class_is_a_session_state():
    from haybale_studio.state.file_browser_state import FileBrowserState
    from haywire.core.state.base import SessionState
    assert issubclass(FileBrowserState, SessionState)
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest tests/ui/test_file_browser_menu/test_file_browser_state.py -v`
Expected: ImportError on `haybale_studio.state.file_browser_state`.

- [ ] **Step 3: Implement `FileBrowserState`**

Create `barn/haybale-studio/haybale_studio/state/file_browser_state.py`:

```python
"""FileBrowserState — per-session state for the FileBrowser editor.

Holds transient context for the right-click context menu. Contracts:

  - ``right_clicked_file`` is set by SessionFileMenuProvider when the
    user right-clicks a file in the tree.
  - Cleared back to None when the menu closes (any dismissal path).
  - Panels with focus=FileFocus may read this in their poll() to
    decide whether they appear in the menu (e.g. extension-based
    filtering).

Mirrors the EditState.active_port / active_edge pattern: pure menu
state, NOT a persistent selection. ``active_file`` (which IS
persistent) lives on SessionContext, not here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from haywire.core.session.reactive import Reactive, reactive_field
from haywire.core.state.base import SessionState
from haywire.core.state.decorator import state


@state(label="File Browser State")
class FileBrowserState(SessionState):
    """Per-session state for the FileBrowser editor."""

    right_clicked_file: Reactive[Optional[Path]] = reactive_field(None)

    def __init__(self) -> None:
        super().__init__()
        # Initialize per-instance Reactive container
        from copy import copy
        from haywire.core.session.reactive import iter_reactive_fields

        for name, initial in iter_reactive_fields(type(self)):
            self.__dict__[name] = Reactive(copy(initial))
```

- [ ] **Step 4: Export from the state package**

Open `barn/haybale-studio/haybale_studio/state/__init__.py` and add:

```python
from .file_browser_state import FileBrowserState  # noqa: F401
```

(If the file does not exist, create it with that single line.)

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/ui/test_file_browser_menu/test_file_browser_state.py -v`
Expected: all three pass.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-studio/haybale_studio/state/file_browser_state.py \
        barn/haybale-studio/haybale_studio/state/__init__.py \
        tests/ui/test_file_browser_menu/__init__.py \
        tests/ui/test_file_browser_menu/test_file_browser_state.py
git commit -m "feat(state): add FileBrowserState for file context menu

Per-session state. Holds right_clicked_file: Reactive[Path|None],
set when the user right-clicks a file in FileBrowser, cleared on
menu close. Panels with focus=FileFocus poll on this to decide
visibility."
```

---

### Task 15: Add `FileFocus` (Focus subclass)

**Files:**
- Create: `barn/haybale-studio/haybale_studio/focuses/file_focus.py`
- Modify: `barn/haybale-studio/haybale_studio/focuses/__init__.py`
- Test: `tests/ui/test_file_browser_menu/test_file_focus.py`

- [ ] **Step 1: Write the failing test**

Create `tests/ui/test_file_browser_menu/test_file_focus.py`:

```python
"""FileFocus — Focus subclass discriminating panels for the file context menu."""

from pathlib import Path
from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_file_focus_id():
    from haybale_studio.file_focus import FileFocus
    assert FileFocus.id == "file"


def test_file_focus_unavailable_when_no_right_click():
    from haybale_studio.file_focus import FileFocus
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state_inst = FileBrowserState()
    ctx.data = {FileBrowserState: state_inst}
    # right_clicked_file starts None
    assert FileFocus.available(ctx) is False


def test_file_focus_available_when_right_clicked():
    from haybale_studio.file_focus import FileFocus
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state_inst = FileBrowserState()
    state_inst.right_clicked_file.value = Path("/tmp/x.haywire")
    ctx.data = {FileBrowserState: state_inst}
    assert FileFocus.available(ctx) is True


def test_file_focus_registered_in_focus_map():
    """Focus.__init_subclass__ should have registered FileFocus by id."""
    from haywire.ui.panel.focus import focus_by_id  # focus module path
    from haybale_studio.file_focus import FileFocus  # noqa: F401 — triggers registration

    assert focus_by_id("file") is FileFocus
```

(Note: the `from haywire.ui.panel.focus` import — check if Focus has been moved or stays in `haywire.ui`. Per PR 1 scope, `haywire.ui.panel.*` is NOT being moved, so this path is correct.)

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest tests/ui/test_file_browser_menu/test_file_focus.py -v`
Expected: ImportError on `haybale_studio.focuses`.

- [ ] **Step 3: Implement `FileFocus`**

Create `barn/haybale-studio/haybale_studio/focuses/file_focus.py`:

```python
"""FileFocus — discriminator for panels that appear in the file context menu.

When the user right-clicks a file in FileBrowser, SessionFileMenuProvider
sets FileBrowserState.right_clicked_file; FileFocus.available(ctx) returns
True; PanelRegistry then yields panels declared with focus=FileFocus, which
are filtered through poll(ctx) and rendered in the menu popup.

Mirrors NodeFocus / EdgeFocus / etc. in the same focuses package.
"""

from __future__ import annotations

from typing import Any, ClassVar

from haywire.ui.panel.focus import Focus
from haywire.ui import elements as hui


class FileFocus(Focus):
    """Active when the user has just right-clicked a file in FileBrowser."""

    id: ClassVar[str] = "file"
    label: ClassVar[str] = "File"
    icon: ClassVar[str] = hui.icon.file if hasattr(hui.icon, "file") else "description"
    order: ClassVar[int] = 200  # library-ish, below built-ins (0–99)

    @classmethod
    def available(cls, ctx: Any) -> bool:
        # Lazy import to avoid module-load ordering with state classes
        from haybale_studio.state.file_browser_state import FileBrowserState
        try:
            return ctx.data[FileBrowserState].right_clicked_file.value is not None
        except KeyError:
            return False
```

If `hui.icon.file` does not exist (verify with `grep -n "file\b" packages/haywire-core/src/haywire/ui/elements/icon.py`), use the literal string `"description"` (Material Symbols name).

- [ ] **Step 4: Export from the focuses package**

Open `barn/haybale-studio/haybale_studio/focuses/__init__.py` and add:

```python
from .file_focus import FileFocus  # noqa: F401
```

If the existing file uses a different export style (e.g. `__all__`), match it.

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/ui/test_file_browser_menu/test_file_focus.py -v`
Expected: all four pass.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-studio/haybale_studio/focuses/file_focus.py \
        barn/haybale-studio/haybale_studio/focuses/__init__.py \
        tests/ui/test_file_browser_menu/test_file_focus.py
git commit -m "feat(focuses): add FileFocus for the file context menu

Focus.available(ctx) returns True when FileBrowserState.right_clicked_file
is non-None. PanelRegistry uses this to gate file-context-menu panels."
```

---

### Task 16: Add `FileBrowserActions` Protocol

**Files:**
- Create: `barn/haybale-studio/haybale_studio/editors/file_browser_menu/__init__.py`
- Create: `barn/haybale-studio/haybale_studio/editors/file_browser_menu/actions.py`

- [ ] **Step 1: Create the package**

```bash
mkdir -p barn/haybale-studio/haybale_studio/editors/file_browser_menu
touch barn/haybale-studio/haybale_studio/editors/file_browser_menu/__init__.py
```

- [ ] **Step 2: Create `actions.py` with the Protocol**

Create `barn/haybale-studio/haybale_studio/editors/file_browser_menu/actions.py`:

```python
"""FileBrowserActions — Protocol implemented by SessionFileMenuProvider.

Per Q11B: a single method, ``reveal``. Each panel resolves its own
binding_id (e.g. the "Open in Haystack" panel calls
HaystackState.open_graph(path) to derive an entry_id, then calls
actions.reveal(GraphEditor, entry_id, display_name)).

Protocol matching is structural — SessionFileMenuProvider satisfies
this without inheriting from it.
"""

from __future__ import annotations

from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor


class FileBrowserActions(Protocol):
    """Action contract for panels declared with action=FileBrowserActions."""

    def reveal(
        self,
        editor_cls: "type[BaseEditor]",
        binding_id: Any,
        label: str,
    ) -> None:
        """Issue a Reveal lifecycle command and close the menu popup."""
        ...
```

- [ ] **Step 3: Verify import**

Run: `uv run python -c "from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions; print(FileBrowserActions)"`
Expected: `<class 'haybale_studio.editors.file_browser_menu.actions.FileBrowserActions'>`.

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/file_browser_menu/
git commit -m "feat(file-browser): add FileBrowserActions Protocol

Single method reveal(editor_cls, binding_id, label). Panels with
action=FileBrowserActions call actions.reveal(...) to open an editor;
the provider implements it as session.lifecycle(Reveal(...)) plus
popup close."
```

---

### Task 17: Implement `SessionFileMenuProvider`

**Files:**
- Create: `barn/haybale-studio/haybale_studio/editors/file_browser_menu/provider.py`
- Test: `tests/ui/test_file_browser_menu/test_session_file_menu_provider.py`

This is a focused copy of `SessionContextMenuProvider` ([context_menu.py:144-222](barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu.py#L144)) — same Popup + PanelRegistry + poll() loop, simpler intent (no `_OpenMenuContext`, no canvas concerns).

- [ ] **Step 1: Write the failing test**

Create `tests/ui/test_file_browser_menu/test_session_file_menu_provider.py`:

```python
"""SessionFileMenuProvider — tests for the file context menu provider.

Mirrors the test pattern in tests/ui/test_canvas_handlers/test_session_context_menu_provider.py.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def _make_provider_under_test(panels=None):
    """Build a provider with mocked dependencies."""
    from haybale_studio.editors.file_browser_menu.provider import SessionFileMenuProvider
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state_inst = FileBrowserState()
    ctx.data = {FileBrowserState: state_inst}
    session = MagicMock()
    panel_registry = MagicMock()
    panel_registry.get_panels_for.return_value = panels or []

    provider = SessionFileMenuProvider(
        context=ctx, session=session, panel_registry=panel_registry
    )
    return provider, ctx, session, panel_registry, state_inst


def test_on_file_context_sets_right_clicked_file():
    provider, ctx, session, panel_registry, state = _make_provider_under_test()
    p = Path("/tmp/foo.haywire")
    with patch.object(provider, "_build_popup") as mock_popup_factory:
        mock_popup_factory.return_value = MagicMock()
        provider.on_file_context(pos=(10, 20), path=p)

    assert state.right_clicked_file.value == p


def test_on_close_clears_right_clicked_file():
    provider, ctx, session, panel_registry, state = _make_provider_under_test()
    p = Path("/tmp/foo.haywire")

    captured_on_close = {}
    def _capture(cb):
        captured_on_close["cb"] = cb

    popup = MagicMock()
    popup.on_close = _capture

    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=p)

    assert state.right_clicked_file.value == p
    captured_on_close["cb"]()  # Simulate menu close
    assert state.right_clicked_file.value is None


def test_reveal_issues_lifecycle_and_closes_popup():
    provider, ctx, session, panel_registry, state = _make_provider_under_test()
    popup = MagicMock()
    provider._open_popup = popup

    editor_cls = MagicMock()
    provider.reveal(editor_cls, binding_id="binding_id-x", label="My Editor")

    # session.lifecycle was called with a Reveal command
    session.lifecycle.assert_called_once()
    call = session.lifecycle.call_args[0][0]
    assert call.editor is editor_cls
    assert call.binding_id == "binding_id-x"
    assert call.label == "My Editor"
    # And the popup got closed
    popup.close.assert_called_once()


def test_panels_filtered_by_poll():
    """Only panels whose poll() returns True are drawn."""
    visible_panel_cls = MagicMock()
    visible_panel_cls.poll.return_value = True
    hidden_panel_cls = MagicMock()
    hidden_panel_cls.poll.return_value = False

    provider, ctx, session, panel_registry, state = _make_provider_under_test(
        panels=[visible_panel_cls, hidden_panel_cls]
    )

    popup = MagicMock()
    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=Path("/tmp/foo"))

    visible_panel_cls.assert_called_once()  # instantiated
    hidden_panel_cls.assert_not_called()    # never instantiated


def test_no_panels_no_popup_open():
    """If no panel polls True, the popup is not opened."""
    panel_cls = MagicMock()
    panel_cls.poll.return_value = False
    provider, ctx, session, panel_registry, state = _make_provider_under_test(panels=[panel_cls])
    popup = MagicMock()

    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=Path("/tmp/foo"))

    popup.open.assert_not_called()
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest tests/ui/test_file_browser_menu/test_session_file_menu_provider.py -v`
Expected: ImportError on `haybale_studio.editors.file_browser_menu.provider`.

- [ ] **Step 3: Implement `SessionFileMenuProvider`**

Create `barn/haybale-studio/haybale_studio/editors/file_browser_menu/provider.py`:

```python
"""SessionFileMenuProvider — panel-driven file context menu provider.

Mirrors SessionContextMenuProvider in graph_canvas/handlers/context_menu.py:
- on_file_context updates FileBrowserState.right_clicked_file
- queries PanelRegistry for panels with action=FileBrowserActions, focus=FileFocus
- filters by poll(), draws into a Popup
- on_close clears right_clicked_file (Q8A: transient menu state)

Implements FileBrowserActions structurally — reveal(editor_cls, binding_id, label).

This file is a focused copy of the canvas provider. PR1 Task 18
(opportunistic) considers extracting a BaseContextMenuProvider IF the
extraction does not require a synthetic shared dependency.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Tuple, TYPE_CHECKING

from haywire.ui.panel.layout import PanelLayout
from haywire.ui.components.popup import Popup
from haywire.core.session.context_signals import Reveal

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.core.session.session import Session
    from haywire.ui.panel.registry import PanelRegistry
    from haywire.ui.editor.base import BaseEditor

logger = logging.getLogger(__name__)


class SessionFileMenuProvider:
    """Panel-driven file-context-menu provider, satisfies FileBrowserActions."""

    def __init__(
        self,
        context: "SessionContext",
        session: "Session",
        panel_registry: "PanelRegistry",
    ):
        self._context = context
        self._session = session
        self._panel_registry = panel_registry
        self._open_popup: Optional[Popup] = None

    def _build_popup(self, pos: Tuple[float, float]) -> Popup:
        """Build a Popup at the given position. Extracted for testability."""
        return Popup(position_x=pos[0], position_y=pos[1], backdrop_click_close=True)

    # ------------------------------------------------------------------
    # Intent
    # ------------------------------------------------------------------

    def on_file_context(self, pos: Tuple[float, float], path: Path) -> None:
        """User right-clicked a file at screen position ``pos``."""
        from haybale_studio.state.file_browser_state import FileBrowserState
        from haybale_studio.file_focus import FileFocus
        from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions

        # Set transient menu state
        self._context.data[FileBrowserState].right_clicked_file.value = path

        popup = self._build_popup(pos)
        self._open_popup = popup

        def _on_close():
            # Q8A: clear right_clicked_file on dismissal
            try:
                self._context.data[FileBrowserState].right_clicked_file.value = None
            except KeyError:
                pass
            self._open_popup = None

        popup.on_close(_on_close)

        panel_classes = self._panel_registry.get_panels_for(
            actions_provider=self, focus=FileFocus
        )

        visible = [cls for cls in panel_classes if cls.poll(self._context)]
        if not visible:
            # Nothing to show — clear right_clicked_file immediately and skip
            _on_close()
            return

        layout = PanelLayout(popup.content)
        for cls in visible:
            try:
                cls().draw(self._context, layout, self)
            except Exception as exc:
                logger.exception(
                    f"Error drawing file menu panel {cls.__name__}: {exc}"
                )
        popup.open()

    # ------------------------------------------------------------------
    # FileBrowserActions Protocol implementation
    # ------------------------------------------------------------------

    def reveal(
        self,
        editor_cls: "type[BaseEditor]",
        binding_id: Any,
        label: str,
    ) -> None:
        """Issue a Reveal lifecycle command and close the popup."""
        self._session.lifecycle(
            Reveal(editor=editor_cls, binding_id=binding_id, label=label)
        )
        if self._open_popup is not None:
            self._open_popup.close()
```

Note on the `_on_close()` early-return: when no panel polls True we still want `right_clicked_file` cleared (otherwise it persists despite no visible menu). The test `test_no_panels_no_popup_open` covers the popup-open path; we add the explicit `_on_close()` call to handle the cleanup-without-popup case.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/ui/test_file_browser_menu/test_session_file_menu_provider.py -v`
Expected: all five pass.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/file_browser_menu/provider.py \
        tests/ui/test_file_browser_menu/test_session_file_menu_provider.py
git commit -m "feat(file-browser): add SessionFileMenuProvider

Mirrors SessionContextMenuProvider — Popup + PanelRegistry + poll()
+ Reveal. Single intent on_file_context(pos, path); satisfies
FileBrowserActions Protocol structurally. Per Q8A, clears
FileBrowserState.right_clicked_file on menu close."
```

---

### Task 18: Wire FileBrowser to open the menu on right-click

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/file_browser.py`

The FileBrowser already constructs a Quasar `q-tree` with a click handler. We add a `contextmenu.prevent` handler on each tree node that calls into a session-scoped `SessionFileMenuProvider`. **The existing `_open_graph_file` left-click routing stays intact** — PR 2 deletes it.

- [ ] **Step 1: Inspect the current FileBrowser tree wiring**

Read [file_browser.py:264-298](barn/haybale-studio/haybale_studio/editors/file_browser.py#L264). The `_on_select` handler is bound to left-click only. We need to add a right-click handler.

The file uses NiceGUI's `ui.tree` (Quasar `q-tree` underneath). To add a right-click handler at the tree level, we listen to the `node-clicked` event variant for context — actually, q-tree doesn't expose node-level contextmenu. Instead, we attach `contextmenu.prevent` to the slot template via a custom slot rendering, which q-tree supports through `body` slots.

The simplest robust path: render each tree node via a custom body slot that wraps its label in a `ui.element` with `.on("contextmenu.prevent", ...)`. See [node_menu_builder.py:128](barn/haybale-studio/haybale_studio/editors/graph_canvas/node_menu_builder.py#L128) for how the canvas wires `contextmenu.prevent`.

- [ ] **Step 2: Add the provider-construction helper**

In the `LazyFileBrowserEditor` class (or whatever class owns the tree), find `draw()` and the place where `self._tree = ui.tree(...)` is set up. Add a helper method:

```python
def _ensure_menu_provider(self, context: "SessionContext"):
    """Lazily construct the menu provider for this session."""
    if getattr(self, "_menu_provider", None) is None:
        from haybale_studio.editors.file_browser_menu.provider import SessionFileMenuProvider
        # PanelRegistry resolution: SessionContext.app exposes panel_registry
        # via the IProjectState protocol.
        panel_registry = context.app.panel_registry
        self._menu_provider = SessionFileMenuProvider(
            context=context,
            session=context.session,
            panel_registry=panel_registry,
        )
    return self._menu_provider
```

(Note: `context.app.panel_registry` — verify this exists by checking `IProjectState`. From the protocols file we read earlier, `IProjectState` does NOT yet expose `panel_registry`. Quick check:)

```bash
grep -n "panel_registry" packages/haywire-core/src/haywire/core/session/protocols.py
```

If it's not there, add `panel_registry: Any` to the IProjectState protocol (HaywireApp already has it as `self.panel_registry`).

- [ ] **Step 3: Add the right-click handler method**

In the same class, add:

```python
def _on_node_context(self, node_id: str, screen_x: float, screen_y: float, context: "SessionContext") -> None:
    """User right-clicked a tree node."""
    if not node_id or node_id.endswith(_LOAD_MORE_ID):
        return
    path = Path(node_id)
    if not path.is_file():
        return  # Folders don't get a context menu (yet)
    provider = self._ensure_menu_provider(context)
    provider.on_file_context(pos=(screen_x, screen_y), path=path)
```

- [ ] **Step 4: Wire `contextmenu.prevent` to each tree node**

This is the trickiest piece because q-tree's slot model is limited. The robust approach: after `self._tree = ui.tree(...)`, iterate `self._tree._props["nodes"]` (the eager-loaded tree) and attach a JS-level event handler via the underlying Vue component slot. Concretely, q-tree supports a `default-header` scoped slot in Vue. NiceGUI exposes Vue slots via `add_slot(name, content)`.

Given the eager-then-lazy strategy, the simpler path is to render the tree **inside an outer element that intercepts contextmenu globally and dispatches to whatever node is under the cursor**:

```python
# In draw(), wrap the tree in an outer element:
with ui.element("div").classes("file-browser-root").on(
    "contextmenu.prevent",
    lambda e: self._dispatch_contextmenu(e, context),
) as outer:
    self._tree = ui.tree(...)
```

And add the dispatch method:

```python
def _dispatch_contextmenu(self, event, context: "SessionContext") -> None:
    """Resolve the tree node under the cursor and open the menu.

    NiceGUI passes the original DOM event in event.args; we read
    the q-tree's 'selected' or hover state from props if available.
    Fall back to a JS-side helper that walks up event.target.
    """
    args = event.args or {}
    # The browser event includes clientX/clientY, target, etc.
    # The q-tree renders each node in a div with data-key=<node_id>.
    # We can't access event.target here directly — it's on the JS side.
    # Use a small JS shim that the tree's contextmenu dispatches:
    from nicegui import ui as _ui
    _ui.run_javascript(f"""
        (function() {{
            const e = window.__last_contextmenu_event || null;
            if (!e || !e.target) return;
            let n = e.target;
            while (n && !(n.getAttribute && n.getAttribute('data-key'))) {{
                n = n.parentElement;
            }}
            if (!n) return;
            const key = n.getAttribute('data-key');
            window.emitEvent('haywire_file_contextmenu', {{
                key: key,
                x: e.clientX,
                y: e.clientY,
            }});
        }})();
    """)
```

**This wiring path is fragile** — and given the inquisition wasn't asked about it, the implementing engineer should verify by trial and revisit if simpler. A cleaner alternative if q-tree's body slot is workable:

```python
self._tree.add_slot("default-header", """
    <div :data-file-key="props.key"
         @contextmenu.prevent="$emit('node-context', { key: props.key, x: $event.clientX, y: $event.clientY })">
        {{ props.node.label }}
    </div>
""")
self._tree.on("node-context", lambda e: self._on_node_context(
    e.args.get("key"), e.args.get("x"), e.args.get("y"), context
))
```

Use the slot approach if it works; otherwise fall back to the global-listener approach. Test interactively.

- [ ] **Step 5: Smoke-test in the browser**

Run: `uv run haywire`. Open the browser. Right-click a file in the tree. Expected:
- Either a popup appears (if any panels register against `FileFocus`) OR no popup but no error in the console (no panels yet exist for FileFocus — that's fine for PR 1).
- No errors in server logs.
- The default browser context menu does NOT appear (`contextmenu.prevent` worked).

If the right-click does nothing AND nothing logs, the slot wiring failed silently — switch to the alternative approach in Step 4.

- [ ] **Step 6: Run the unit suite**

Run: `uv run pytest -m "not integration" -q`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/file_browser.py \
        packages/haywire-core/src/haywire/core/session/protocols.py
git commit -m "feat(file-browser): wire contextmenu to SessionFileMenuProvider

Right-click on a file dispatches to provider.on_file_context.
Left-click routing (_open_graph_file) stays intact for PR1; PR2
deletes it once HaystackState owns graph opening.

IProjectState gains panel_registry attribute (already present on
HaywireApp, just exposed on the protocol now)."
```

---

### Task 19: Smoke-test "Open in <X>" with a placeholder panel (verification only — placeholder is reverted at the end)

This step is non-load-bearing; it verifies that the entire chain works end-to-end before PR 2 builds the real "Open in Haystack" panel.

**Files:**
- Create (temporarily): `tests/ui/test_file_browser_menu/test_open_in_panel_smoke.py`

- [ ] **Step 1: Write a smoke test that registers a temporary FileFocus panel and asserts the round-trip**

Create `tests/ui/test_file_browser_menu/test_open_in_panel_smoke.py`:

```python
"""End-to-end smoke: a panel with focus=FileFocus appears in the menu
when right_clicked_file is set, and reveal() fires."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_panel_appears_and_reveal_fires():
    from haywire.ui.panel.base import BasePanel
    from haywire.ui.panel.decorator import panel
    from haywire.ui.panel.registry import PanelRegistry
    from haybale_studio.file_focus import FileFocus
    from haybale_studio.state.file_browser_state import FileBrowserState
    from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions
    from haybale_studio.editors.file_browser_menu.provider import SessionFileMenuProvider

    @panel(action=FileBrowserActions, focus=FileFocus, label="Smoke Open")
    class SmokeOpenPanel(BasePanel):
        @classmethod
        def poll(cls, ctx) -> bool:
            f = ctx.data[FileBrowserState].right_clicked_file.value
            return f is not None and f.suffix == ".smoke"

        def draw(self, ctx, layout, actions):
            f = ctx.data[FileBrowserState].right_clicked_file.value
            # Simulate user clicking the menu item
            actions.reveal(MagicMock(), binding_id=str(f), label=f.name)

    # Build a fake context + registry
    registry = PanelRegistry()
    registry.register(SmokeOpenPanel)

    ctx = MagicMock()
    state = FileBrowserState()
    ctx.data = {FileBrowserState: state}
    session = MagicMock()
    provider = SessionFileMenuProvider(
        context=ctx, session=session, panel_registry=registry
    )

    popup = MagicMock()
    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=Path("/tmp/foo.smoke"))

    # The panel was drawn (which calls reveal), so session.lifecycle was invoked
    session.lifecycle.assert_called_once()
    # And the popup was opened (visible panel(s) existed)
    popup.open.assert_called_once()


def test_panel_skipped_when_extension_doesnt_match():
    from haywire.ui.panel.base import BasePanel
    from haywire.ui.panel.decorator import panel
    from haywire.ui.panel.registry import PanelRegistry
    from haybale_studio.file_focus import FileFocus
    from haybale_studio.state.file_browser_state import FileBrowserState
    from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions
    from haybale_studio.editors.file_browser_menu.provider import SessionFileMenuProvider

    @panel(action=FileBrowserActions, focus=FileFocus, label="Smoke OnlySmokeExt")
    class SmokeOnlyPanel(BasePanel):
        @classmethod
        def poll(cls, ctx) -> bool:
            f = ctx.data[FileBrowserState].right_clicked_file.value
            return f is not None and f.suffix == ".smoke"

        def draw(self, ctx, layout, actions):
            actions.reveal(MagicMock(), binding_id="", label="x")

    registry = PanelRegistry()
    registry.register(SmokeOnlyPanel)

    ctx = MagicMock()
    state = FileBrowserState()
    ctx.data = {FileBrowserState: state}
    session = MagicMock()
    provider = SessionFileMenuProvider(
        context=ctx, session=session, panel_registry=registry
    )

    popup = MagicMock()
    with patch.object(provider, "_build_popup", return_value=popup):
        # Right-click a file with a DIFFERENT extension
        provider.on_file_context(pos=(0, 0), path=Path("/tmp/foo.txt"))

    popup.open.assert_not_called()
    session.lifecycle.assert_not_called()
```

Note: the panel registration above uses `registry.register(SmokeOpenPanel)` — verify the actual PanelRegistry API by inspecting `packages/haywire-core/src/haywire/ui/panel/registry.py`. If the method is different (e.g. `add_class`), use that.

- [ ] **Step 2: Run the smoke test**

Run: `uv run pytest tests/ui/test_file_browser_menu/test_open_in_panel_smoke.py -v`
Expected: both tests pass.

If they fail because of PanelRegistry API mismatch, fix the test accordingly. If they fail because `registry.get_panels_for(actions_provider=self, focus=FileFocus)` doesn't return the registered panel, inspect the structural matching logic — `actions_provider=self` means the provider must structurally satisfy `FileBrowserActions`. Verify by checking `isinstance(provider, FileBrowserActions)` returns True (it should, since FileBrowserActions is a `@runtime_checkable` Protocol — if not, add `@runtime_checkable` to the Protocol declaration).

- [ ] **Step 3: Commit**

```bash
git add tests/ui/test_file_browser_menu/test_open_in_panel_smoke.py
git commit -m "test: smoke test for the file context menu round-trip

Registers a temporary panel with focus=FileFocus, action=FileBrowserActions,
and verifies that on_file_context → poll() → draw() → actions.reveal()
all wire together correctly."
```

---

## Phase 7 — Opportunistic base extraction (Q3C)

### Task 20: Decide whether to extract `BaseContextMenuProvider`

Per Q3C: extraction happens **if and only if it does not require inventing a new shared dependency**. Since `SessionContextMenuProvider` lives in `haybale-studio` and `SessionFileMenuProvider` also lives in `haybale-studio` (both in the same library), a shared base in `haybale-studio` adds no cross-library coupling. So extraction is on the table.

- [ ] **Step 1: Open both providers side by side and identify identical code**

Files to compare:
- `barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu.py` (lines 144-222 — the `SessionContextMenuProvider` class structure)
- `barn/haybale-studio/haybale_studio/editors/file_browser_menu/provider.py` (the new `SessionFileMenuProvider`)

Identify methods/state that are byte-for-byte identical:
- `_build_popup(pos)` — identical
- The `_open_popup` field — identical pattern
- The popup-close lambda + `panel_registry.get_panels_for` + `[cls for cls in panel_classes if cls.poll(...)]` filter + `PanelLayout(popup.content) + cls().draw(...)` loop — same shape but called from different "intent" methods

- [ ] **Step 2: Extract `BaseContextMenuProvider`**

Create `barn/haybale-studio/haybale_studio/editors/_context_menu_base.py`:

```python
"""BaseContextMenuProvider — shared infrastructure for panel-driven
context menus. Used by:
  - SessionContextMenuProvider (graph canvas)
  - SessionFileMenuProvider (file browser)

Concrete subclasses define their own intent methods (e.g. on_node_context,
on_file_context); the base provides _build_popup, the panel iteration
loop, and shared bookkeeping.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple, TYPE_CHECKING

from haywire.ui.panel.layout import PanelLayout
from haywire.ui.components.popup import Popup

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.core.session.session import Session
    from haywire.ui.panel.registry import PanelRegistry

logger = logging.getLogger(__name__)


class BaseContextMenuProvider:
    """Shared base for panel-driven context menu providers.

    Subclasses provide intent methods (e.g. on_node_context) and the
    actions Protocol implementation. They call _open_menu(action, focus,
    pos, on_close=...) to surface the menu.
    """

    def __init__(
        self,
        context: "SessionContext",
        session: "Session",
        panel_registry: "PanelRegistry",
    ):
        self._context = context
        self._session = session
        self._panel_registry = panel_registry
        self._open_popup: Optional[Popup] = None

    def _build_popup(self, pos: Tuple[float, float]) -> Popup:
        return Popup(position_x=pos[0], position_y=pos[1], backdrop_click_close=True)

    def _open_menu(
        self,
        action: type,
        focus: type,
        pos: Tuple[float, float],
        on_close=None,
    ) -> None:
        """Build popup, query panels for (action, focus), draw matched ones.

        on_close: subclass-supplied additional cleanup, called when the
        popup closes (after the base clears _open_popup).
        """
        popup = self._build_popup(pos)
        self._open_popup = popup

        def _wrapped_on_close():
            self._open_popup = None
            if on_close is not None:
                try:
                    on_close()
                except Exception as exc:
                    logger.exception(f"on_close handler raised: {exc}")

        popup.on_close(_wrapped_on_close)

        panel_classes = self._panel_registry.get_panels_for(
            actions_provider=self, focus=focus
        )
        visible = [cls for cls in panel_classes if cls.poll(self._context)]
        if not visible:
            _wrapped_on_close()
            return

        layout = PanelLayout(popup.content)
        for cls in visible:
            try:
                cls().draw(self._context, layout, self)
            except Exception as exc:
                logger.exception(
                    f"Error drawing context menu panel {cls.__name__}: {exc}"
                )
        popup.open()
```

- [ ] **Step 3: Refactor `SessionFileMenuProvider` to use the base**

Edit `barn/haybale-studio/haybale_studio/editors/file_browser_menu/provider.py`:

```python
"""SessionFileMenuProvider — file context menu provider.

Inherits popup/panel infrastructure from BaseContextMenuProvider.
Adds: on_file_context intent, FileBrowserActions implementation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Tuple, TYPE_CHECKING

from haybale_studio.editors._context_menu_base import BaseContextMenuProvider
from haywire.core.session.context_signals import Reveal

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor

logger = logging.getLogger(__name__)


class SessionFileMenuProvider(BaseContextMenuProvider):
    """Panel-driven file-context-menu provider, satisfies FileBrowserActions."""

    def on_file_context(self, pos: Tuple[float, float], path: Path) -> None:
        from haybale_studio.state.file_browser_state import FileBrowserState
        from haybale_studio.file_focus import FileFocus
        from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions

        # Set transient menu state
        self._context.data[FileBrowserState].right_clicked_file.value = path

        def _on_close():
            try:
                self._context.data[FileBrowserState].right_clicked_file.value = None
            except KeyError:
                pass

        self._open_menu(FileBrowserActions, FileFocus, pos, on_close=_on_close)

    def reveal(
        self,
        editor_cls: "type[BaseEditor]",
        binding_id: Any,
        label: str,
    ) -> None:
        self._session.lifecycle(
            Reveal(editor=editor_cls, binding_id=binding_id, label=label)
        )
        if self._open_popup is not None:
            self._open_popup.close()
```

- [ ] **Step 4: Refactor `SessionContextMenuProvider` to use the base**

In `barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu.py`:

a) Add the import at the top:
```python
from haybale_studio.editors._context_menu_base import BaseContextMenuProvider
```

b) Change the class declaration:
```python
class SessionContextMenuProvider(IContextMenuProvider, BaseContextMenuProvider):
    ...
```

c) Delete `__init__` (the base provides it). If the canvas needs extra fields (e.g. `_on_emit_event`, `_on_emit_sync_event`, `_open_ctx`), keep a custom `__init__` that calls `super().__init__(context, session, panel_registry)` then sets the extras.

d) Delete `_build_popup` (the base provides it).

e) Replace each `_open_menu` body with calls to the base's `_open_menu`. Each canvas intent method (e.g. `on_node_context`) currently builds its popup inline; refactor each to call `self._open_menu(action_cls, focus_cls, pos, on_close=lambda: ...)` where the on_close handles the canvas-specific cleanup currently in `_on_close` (clearing `active_port`/`active_edge`, resuming pending connections).

This is mechanical but touchy. **If at any point the refactor stalls or breaks tests in non-obvious ways, revert this task entirely (Q3C explicitly permits leaving the duplication).** The base extraction is a nice-to-have, not load-bearing.

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -m "not integration" -q`
Expected: all green. Pay particular attention to `tests/ui/test_canvas_handlers/test_session_context_menu_provider.py`.

- [ ] **Step 6: Smoke-test the canvas context menu still works**

Run: `uv run haywire`. Open a graph. Right-click a node → expected: node context menu appears (Delete Node, Copy Node, etc.). Right-click an edge → edge menu. Right-click empty canvas → canvas menu.

- [ ] **Step 7: Commit (or revert)**

If everything works:
```bash
git add barn/haybale-studio/haybale_studio/editors/_context_menu_base.py \
        barn/haybale-studio/haybale_studio/editors/file_browser_menu/provider.py \
        barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu.py
git commit -m "refactor(panels): extract BaseContextMenuProvider

Pulls the popup/registry/poll/draw machinery shared between
SessionContextMenuProvider (canvas) and SessionFileMenuProvider
(file browser) into a common base. Both providers now implement
only their intent methods and actions Protocol.

Per Q3C: extraction was opportunistic — done because both providers
live in haybale-studio so no synthetic shared dependency was needed."
```

If it doesn't work cleanly:
```bash
git checkout barn/haybale-studio/haybale_studio/editors/file_browser_menu/provider.py
git checkout barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu.py
rm barn/haybale-studio/haybale_studio/editors/_context_menu_base.py
git status  # verify clean
echo "Skipping base extraction per Q3C — duplication is acceptable."
```

---

## Phase 8 — Cleanup pass: update import sites, delete shims (NEXT PR; not PR 1)

This phase is **deferred to a follow-up PR**, not PR 1. The shims at `haywire.ui.session`, `haywire.ui.session_manager`, etc., stay in place for the duration of PR 1 and PR 2. A third "import-cleanup" PR can land later — once both PR 1 and PR 2 are merged and stable, sweep through all 53 import sites (`grep -rn "from haywire.ui.session\|from haywire.ui.session_manager\|from haywire.ui.context\b\|from haywire.ui.context_signals\|from haywire.ui.workspace\|from haywire.ui.reactive\|from haywire.ui.protocols" packages/ barn/`) and update each to the canonical `haywire.core.session.*` path. Then delete the shims.

This explicitly is NOT part of PR 1's scope — listed here only so the next person knows it exists.

---

## Final verification

### Task 21: Run the full test suite + smoke-test

- [ ] **Step 1: Run unit tests**

Run: `uv run pytest -m "not integration" -q`
Expected: all green.

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest -m integration -q`
Expected: all green.

- [ ] **Step 3: Run the linter and type checker**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-visiongraph/haybale_visiongraph/ barn/haybale-TEST_A/haybale_test_a/`
Expected: clean.

- [ ] **Step 4: Smoke-test in the browser**

Run: `uv run haywire`. Open the browser to `http://localhost:8082`. Verify:
- App loads, file tree renders
- Click a `.haywire` file → opens in graph editor (existing behavior, unchanged)
- Right-click a file → either nothing happens (no FileFocus panels yet) OR an empty popup briefly flashes and closes (depends on whether any panel has registered for FileFocus)
- Close the browser tab → server log shows "Client disconnected, cleaning up session ..." and "SessionManager: removed session ..."
- No errors in either browser console or server logs

Stop the app.

- [ ] **Step 5: Final commit (if needed)**

If anything trivial was found and fixed during smoke-testing, commit it now:
```bash
git status  # check for stragglers
git add <files>
git commit -m "fix: small cleanups from PR1 smoke testing"
```

PR 1 is complete. Open the PR.

---

## Self-review checklist

Before opening the PR, verify against the design decisions:

- [ ] All session-related modules moved to `haywire.core.session.*`; shims at old `haywire.ui.*` locations
- [ ] `Session._shell` field and `set_shell` method are gone; `set_cleanup_callback` exists
- [ ] `provide_session_manager()` exists in `HaywireModule` and calls `set_session_manager()`
- [ ] `set_workspace_root` and `set_session_manager` exist in `core/di/context.py` mirroring the existing `set_node_factory` pattern
- [ ] `HaywireApp.__init__` calls `set_workspace_root(self.workspace_root)`
- [ ] `HaywireApp.setup_shared_services` pulls SessionManager via `injector.get(SessionManager)`
- [ ] `HaywireApp._shells: dict[str, AppShell]` exists
- [ ] `HaywireApp.on_disconnect` does `shell.cleanup()` first, then `sm.remove_session(sid)`
- [ ] `FileBrowserState(SessionState)` with `right_clicked_file: Reactive[Path|None]` exists
- [ ] `FileFocus(Focus)` exists with `id="file"` and reads `FileBrowserState.right_clicked_file`
- [ ] `FileBrowserActions` Protocol exists with single method `reveal(editor_cls, binding_id, label)`
- [ ] `SessionFileMenuProvider` exists and on menu close clears `right_clicked_file` (Q8A)
- [ ] FileBrowser wires right-click to `provider.on_file_context(pos, path)`
- [ ] FileBrowser left-click `_open_graph_file` routing is **untouched** (PR 2 deletes it)
- [ ] No code in `haywire.core.*` imports from `haywire.ui.*` (except via TYPE_CHECKING + forward references where unavoidable)
- [ ] `BaseContextMenuProvider` extraction is either done cleanly OR reverted with the duplication accepted (Q3C)

If any item is unchecked, address before opening the PR.
