# EditorWrapper Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the passive `EditorBinding` dataclass with a self-managing `EditorWrapper` class that owns editor lifecycle (registry subscription, instantiation, error capture per phase, cleanup), so `Slot` becomes a pure layout/routing layer mirroring `NodeWrapper`'s philosophy.

**Architecture:** `EditorWrapper` self-subscribes per-key to a new `EditorTypeRegistry.add_event_subscriber` API (mirrors `NodeFactory`). Wrapper holds session reference, captures errors into `EditorWrapperState` (`error_import`/`error_instantiate`/`error_runtime`), and exposes minimal-arg runtime methods (`draw(panel)`, `on_focus()`, `poll(event)`). Slot constructs wrappers internally via a single `add_binding(editor_key, editor_cls, ...)` path — used both by `populate_from_snapshot` (replacing the `from_snapshot` classmethod) and `TabSlot.open_tab`. On `CLASS_REMOVED` the wrapper keeps its instance alive (NodeWrapper-style); on recovery it clears the instance and lets the next `draw()` lazy-instantiate with the new class.

**Tech Stack:** Python, NiceGUI, pytest, ruff, mypy. Existing haywire DI/registry/lifecycle-event infrastructure.

---

## File Structure

**New files:**
- `packages/haywire-core/src/haywire/ui/editor/wrapper.py` — `EditorWrapper` + `EditorWrapperState`
- `tests/ui/test_editor_wrapper.py` — wrapper-scoped tests

**Modified files (haywire-core):**
- `packages/haywire-core/src/haywire/ui/editor/registry.py` — add per-key subscriber API
- `packages/haywire-core/src/haywire/ui/editor/base.py` — rename `binding` → `wrapper`
- `packages/haywire-core/src/haywire/ui/app/slot.py` — delete `EditorBinding` class + hot-reload methods; restructure constructor + add `populate_from_snapshot`; thin runtime methods
- `packages/haywire-core/src/haywire/ui/app/tab_slot.py` — adapt method bodies to new `add_binding` signature
- `packages/haywire-core/src/haywire/ui/app/icon_slot.py` — adapt if affected
- `packages/haywire-core/src/haywire/ui/app/shell.py` — adapt `_build_managed_slot` to two-phase pattern

**Modified files (haybale-studio editors):**
- `barn/haybale-studio/haybale_studio/editors/graph_editor.py` — `self.binding` → `self.wrapper`
- `barn/haybale-studio/haybale_studio/editors/file_viewer.py` — `self.binding` → `self.wrapper`
- Other `barn/haybale-studio/haybale_studio/editors/*.py` files using `self.binding`

**Modified files (tests):**
- `tests/ui/test_slot.py` — delete `replace_class`/`remove_bindings` tests; migrate construction
- `tests/ui/test_slot_on_focus.py` — migrate `EditorBinding(...)` literals
- `tests/ui/test_slot_tab.py` — migrate `EditorBinding(...)` literals
- `tests/ui/test_slot_icon.py` — migrate `EditorBinding(...)` literals
- `tests/studio/test_file_viewer_per_file.py` — comment update

---

### Task 0: Establish a clean baseline

**Why:** Before any code changes, confirm every existing test passes. This refactor touches editor lifecycle, slot construction, hot-reload, and a global rename across `barn/`. If a test fails after these changes, we need to know whether it's a regression we caused or a pre-existing failure unrelated to this work. Capture the baseline now so we can attribute failures correctly.

**Files:** none modified.

- [ ] **Step 0.1: Confirm clean working tree**

Run: `git status`
Expected: clean working tree, or only changes you've explicitly staged for this branch. If there are unrelated modifications, stash or commit them before proceeding — the baseline must reflect HEAD on this branch.

- [ ] **Step 0.2: Run the unit tests (fast suite)**

Run: `uv run pytest -m "not integration" -v 2>&1 | tee /tmp/baseline-unit.log`
Expected: all tests PASS.

If any test fails: STOP. Do not start the refactor. Investigate the failure first — either fix it on this branch (separate commit) or document it as a pre-existing failure (in which case the same test failing after the refactor is not a regression). Do not proceed to Task 1 until either (a) all unit tests pass on a clean baseline, or (b) the set of pre-existing failures is documented in `/tmp/baseline-unit.log` and the user has confirmed it.

- [ ] **Step 0.3: Run the integration tests (slow suite)**

Run: `uv run pytest -m integration -v 2>&1 | tee /tmp/baseline-integration.log`
Expected: all tests PASS.

Same protocol as 0.2: if anything fails, document or fix before proceeding.

- [ ] **Step 0.4: Run lint, format check, and mypy**

Run:

```bash
uv run ruff check . 2>&1 | tee /tmp/baseline-lint.log
uv run ruff format --check . 2>&1 | tee /tmp/baseline-format.log
uv run mypy packages/haywire-core/src/ 2>&1 | tee /tmp/baseline-mypy.log
```

Expected: all clean.

If any of these fail: same protocol — stop and resolve before starting the refactor. The point is to enter Task 1 with zero outstanding warnings on the touched packages so any new warning during the refactor is unambiguously caused by this work.

- [ ] **Step 0.5: Record the baseline**

The four log files in `/tmp/baseline-*.log` are your reference. If a regression appears in any later task, diff the failing test's output against the baseline log to confirm it's new.

No commit needed for this task — it's purely a verification gate. Proceed to Task 1 only after all five steps are clean.

---

### Task 1: Add per-key subscriber API to `EditorTypeRegistry`

**Why:** The wrapper self-subscribes per-key. `EditorTypeRegistry` only has the inherited batch API today — we need a per-key fan-out, mirroring `NodeFactory.factory.py:180-204` but localized to the editor registry (per Q3B decision).

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/registry.py`
- Test: `tests/ui/test_editor_registry.py` (new file or add to existing if present)

- [ ] **Step 1.1: Check for an existing editor registry test file**

Run: `ls tests/ui/test_editor_registry*.py 2>/dev/null; find tests -name "test*registry*.py" | head -5`
Expected: either a path is printed or no output. If a file exists, add tests to it. If not, create `tests/ui/test_editor_registry.py`.

- [ ] **Step 1.2: Write the failing test**

Create or append to `tests/ui/test_editor_registry.py`:

```python
"""Tests for EditorTypeRegistry per-key subscriber dispatch."""

from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType


class _Cls:
    pass


def test_per_key_subscriber_receives_event_for_its_key():
    reg = EditorTypeRegistry()
    received: list[LifeCycleEvent] = []
    reg.add_event_subscriber("a:editor:1", lambda evt: received.append(evt))

    # Manually queue an event and notify (mirrors how the registry's reload paths
    # populate _lifecycle_event_queue then call _notify_batch_event_subscribers)
    reg._lifecycle_event_queue.append(
        LifeCycleEvent(
            event_type=LifeCycleEventType.CLASS_RELOADED,
            registry_key="a:editor:1",
            affected_class=_Cls,
        )
    )
    reg._notify_batch_event_subscribers()

    assert len(received) == 1
    assert received[0].registry_key == "a:editor:1"


def test_per_key_subscriber_does_not_receive_other_keys():
    reg = EditorTypeRegistry()
    received: list[LifeCycleEvent] = []
    reg.add_event_subscriber("a:editor:1", lambda evt: received.append(evt))

    reg._lifecycle_event_queue.append(
        LifeCycleEvent(
            event_type=LifeCycleEventType.CLASS_RELOADED,
            registry_key="other:editor:99",
            affected_class=_Cls,
        )
    )
    reg._notify_batch_event_subscribers()

    assert received == []


def test_remove_event_subscriber_stops_callbacks():
    reg = EditorTypeRegistry()
    received: list[LifeCycleEvent] = []
    cb = lambda evt: received.append(evt)
    reg.add_event_subscriber("a:editor:1", cb)
    reg.remove_event_subscriber("a:editor:1", cb)

    reg._lifecycle_event_queue.append(
        LifeCycleEvent(
            event_type=LifeCycleEventType.CLASS_RELOADED,
            registry_key="a:editor:1",
            affected_class=_Cls,
        )
    )
    reg._notify_batch_event_subscribers()

    assert received == []
```

- [ ] **Step 1.3: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_editor_registry.py -v`
Expected: FAIL with `AttributeError: ... 'add_event_subscriber'`.

- [ ] **Step 1.4: Implement per-key dispatch**

Edit `packages/haywire-core/src/haywire/ui/editor/registry.py`. Add to `EditorTypeRegistry`:

```python
import inspect
import logging
from typing import Callable, Optional, Dict, List

logger = logging.getLogger(__name__)

from haywire.core.registry.base import BaseRegistry
from haywire.core.registry.lifecycle_event import LifeCycleEvent
from haywire.core.library.identity import LibraryIdentity

from .base import BaseEditor


class EditorTypeRegistry(BaseRegistry):
    """
    Registry of editor types.

    Extends BaseRegistry for hot-reload support, folder scanning, lifecycle
    events, dependency tracking, and snapshot rollback. Provided as a DI
    singleton by HaywireModule.

    Libraries register editors via add_folder() in register_components().
    Built-in framework editors are bootstrapped via register_builtin_editors()
    called from the DI provider, analogous to register_builtin_settings().
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._key_event_subscribers: Dict[str, List[Callable[[LifeCycleEvent], None]]] = {}

    def _class_filter(self, cls) -> bool:
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, BaseEditor)
                and cls is not BaseEditor
                and hasattr(cls, "class_identity")
            )
        except TypeError:
            return False

    def _register_class(self, cls: type, library_identity: Optional[LibraryIdentity] = None) -> "str | None":
        registry_key = cls.class_identity.registry_key
        logger.debug(f"EditorTypeRegistry: Registering '{registry_key}' ({cls.__name__})")
        return super()._register(registry_key, cls, library_identity)

    def _unregister_class(self, registry_key: str) -> "type | None":
        return super()._unregister(registry_key)

    def get_by_key(self, registry_key: str) -> "type | None":
        return self._classes.get(registry_key)

    def get_by_default_slot(self, slot: str) -> Dict[str, type]:
        return {k: v for k, v in self._classes.items() if v.class_identity.default_slot == slot}

    # ------------------------------------------------------------------
    # Per-key event subscription (mirrors NodeFactory.add_event_subscriber)
    # ------------------------------------------------------------------

    def add_event_subscriber(
        self, registry_key: str, callback: Callable[[LifeCycleEvent], None]
    ) -> None:
        """Register a callback for lifecycle events of a specific registry_key.

        Used by EditorWrapper to self-subscribe for hot-reload notifications
        without going through the slot. Mirrors NodeFactory's per-key API.
        """
        self._key_event_subscribers.setdefault(registry_key, []).append(callback)

    def remove_event_subscriber(
        self, registry_key: str, callback: Callable[[LifeCycleEvent], None]
    ) -> None:
        """Unregister a per-key callback."""
        if registry_key in self._key_event_subscribers:
            try:
                self._key_event_subscribers[registry_key].remove(callback)
            except ValueError:
                pass
            if not self._key_event_subscribers[registry_key]:
                del self._key_event_subscribers[registry_key]

    def _notify_batch_event_subscribers(self) -> None:
        """Override to dispatch per-key callbacks after batch fan-out.

        Order: batch subscribers first (preserving existing semantics), then
        per-key callbacks for every event in the queue. The queue is cleared
        by the super() call, so we copy events first.
        """
        events = list(self._lifecycle_event_queue)
        super()._notify_batch_event_subscribers()
        for event in events:
            callbacks = self._key_event_subscribers.get(event.registry_key, [])
            for cb in callbacks[:]:
                try:
                    cb(event)
                except Exception as exc:
                    logger.error(
                        f"EditorTypeRegistry: per-key subscriber for "
                        f"'{event.registry_key}' raised: {exc}",
                        exc_info=True,
                    )
```

Keep the docstrings on `get_by_key` and `get_by_default_slot` from the original file — copy them in if they were lost in the rewrite. Verify before saving.

- [ ] **Step 1.5: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_editor_registry.py -v`
Expected: PASS — 3 tests pass.

- [ ] **Step 1.6: Run lint + format + mypy**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/editor/registry.py && uv run ruff format packages/haywire-core/src/haywire/ui/editor/registry.py && uv run mypy packages/haywire-core/src/haywire/ui/editor/registry.py`
Expected: clean.

- [ ] **Step 1.7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/registry.py tests/ui/test_editor_registry.py
git commit -m "feat(editor-registry): add per-key event subscriber API

Mirrors NodeFactory's per-key dispatch so EditorWrapper can self-subscribe
for hot-reload events. Per-key callbacks fire after batch subscribers
preserving existing semantics."
```

---

### Task 2: Create `EditorWrapperState` dataclass

**Why:** Build the state container before the wrapper class. Dataclass-only — no behavior beyond `is_valid()` and `get_errors()`.

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Test: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 2.1: Write the failing tests**

Create `tests/ui/test_editor_wrapper.py`:

```python
"""Tests for EditorWrapper and EditorWrapperState."""

from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui.editor.wrapper import EditorWrapperState


def test_state_default_is_valid():
    state = EditorWrapperState()
    assert state.is_valid() is True
    assert state.get_errors() is None


def test_state_with_error_import_is_invalid():
    state = EditorWrapperState()
    state.error_import = HaywireException.create("import failed")
    state.is_imported = False
    assert state.is_valid() is False
    errs = state.get_errors()
    assert errs is not None and len(errs) == 1


def test_state_with_error_instantiate_is_invalid():
    state = EditorWrapperState()
    state.error_instantiate = HaywireException.create("instantiate failed")
    assert state.is_valid() is False


def test_state_get_errors_collects_all():
    state = EditorWrapperState()
    state.error_import = HaywireException.create("imp")
    state.error_instantiate = HaywireException.create("inst")
    state.error_runtime = HaywireException.create("rt")
    errs = state.get_errors()
    assert errs is not None and len(errs) == 3


def test_state_clear_errors_resets_runtime_and_instantiate():
    state = EditorWrapperState()
    state.error_import = HaywireException.create("imp")
    state.error_instantiate = HaywireException.create("inst")
    state.error_runtime = HaywireException.create("rt")
    state._clear_errors()
    # error_import is preserved (only cleared on hot-reload, mirroring NodeWrapperState)
    assert state.error_import is not None
    assert state.error_instantiate is None
    assert state.error_runtime is None
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.ui.editor.wrapper'`.

- [ ] **Step 2.3: Create the wrapper module with `EditorWrapperState` only**

Create `packages/haywire-core/src/haywire/ui/editor/wrapper.py`:

```python
"""
EditorWrapper — complete lifecycle management for Haywire editors.

Mirrors NodeWrapper's philosophy: the wrapper owns the editor instance,
captures errors per phase into EditorWrapperState, self-subscribes to the
editor registry for hot-reload events, and is the source of truth for
"is this editor healthy?".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from haywire.core.errors.haywire_exception import HaywireException

logger = logging.getLogger(__name__)


@dataclass
class EditorWrapperState:
    """Lifecycle state of an EditorWrapper and its editor instance.

    Mirrors the shape of NodeWrapperState but with editor-specific phases.
    Editors have no init/structural/test phases — only import, instantiate,
    and runtime (covering draw/on_focus/poll).
    """

    is_imported: bool = True
    """True when the editor class is available in the registry."""

    error_import: Optional[HaywireException] = None
    """Error from registry lookup (CLASS_REMOVED, CLASS_NOT_FOUND, reload failure)."""

    error_instantiate: Optional[HaywireException] = None
    """Error from constructing the editor instance."""

    error_runtime: Optional[HaywireException] = None
    """Error from a runtime call (draw, on_focus, poll, redraw)."""

    def is_valid(self) -> bool:
        """True iff the editor is imported and instantiation has not failed.

        Runtime errors do not invalidate the wrapper — the instance may still
        be usable on the next call (best-effort recovery).
        """
        return self.is_imported and self.error_instantiate is None

    def get_errors(self) -> Optional[list[HaywireException]]:
        """Return all populated error slots as a list, or None if no errors."""
        errors = []
        if self.error_import is not None:
            errors.append(self.error_import)
        if self.error_instantiate is not None:
            errors.append(self.error_instantiate)
        if self.error_runtime is not None:
            errors.append(self.error_runtime)
        return errors if errors else None

    def _clear_errors(self) -> None:
        """Clear runtime and instantiate errors. error_import is preserved
        and only cleared explicitly on successful hot-reload."""
        self.error_instantiate = None
        self.error_runtime = None
```

- [ ] **Step 2.4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v`
Expected: PASS — 5 tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py
git commit -m "feat(editor-wrapper): add EditorWrapperState dataclass

Captures per-phase errors (import/instantiate/runtime) and exposes
is_valid() and get_errors() — mirrors NodeWrapperState shape."
```

---

### Task 3: Implement `EditorWrapper` construction + import phase + cleanup

**Why:** The wrapper's most basic lifecycle — construction subscribes to the registry, sets `error_import` if the class is missing, and `cleanup()` unsubscribes. No instantiation yet, no runtime methods yet.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 3.1: Write the failing tests**

Append to `tests/ui/test_editor_wrapper.py`:

```python
from types import SimpleNamespace
from typing import Optional

from haywire.ui.editor.wrapper import EditorWrapper
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType


class _FakeEditorCls:
    class_identity = SimpleNamespace(
        registry_key="fake:editor:1",
        label="Fake",
        default_slot="main",
        opens=None,
    )


def _make_session():
    return SimpleNamespace(context=SimpleNamespace())


def test_wrapper_construction_with_class_sets_imported():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=session,
    )
    assert w.editor_key == "fake:editor:1"
    assert w.editor_cls is _FakeEditorCls
    assert w.payload is None
    assert w.state.is_imported is True
    assert w.state.error_import is None
    assert w.state.is_valid() is True


def test_wrapper_construction_with_none_class_sets_error_import():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="missing:editor:1",
        editor_cls=None,
        registry=reg,
        session=session,
    )
    assert w.editor_cls is None
    assert w.state.is_imported is False
    assert w.state.error_import is not None
    assert w.state.is_valid() is False


def test_wrapper_subscribes_to_registry_on_construction():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=session,
    )
    # Internal: the wrapper's _on_lifecycle_event should be in the per-key list
    assert "fake:editor:1" in reg._key_event_subscribers
    assert w._on_lifecycle_event in reg._key_event_subscribers["fake:editor:1"]


def test_wrapper_cleanup_unsubscribes_from_registry():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=session,
    )
    w.cleanup()
    assert "fake:editor:1" not in reg._key_event_subscribers


def test_wrapper_binding_id_without_payload():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    assert w.binding_id == "fake:editor:1"


def test_wrapper_binding_id_with_payload():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        payload="/tmp/x",
    )
    assert w.binding_id == "fake:editor:1::/tmp/x"


def test_wrapper_split_id_static():
    assert EditorWrapper.split_id("fake:editor:1") == ("fake:editor:1", None)
    assert EditorWrapper.split_id("fake:editor:1::/tmp/x") == ("fake:editor:1", "/tmp/x")
```

- [ ] **Step 3.2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v`
Expected: FAIL with `ImportError: cannot import name 'EditorWrapper' from 'haywire.ui.editor.wrapper'`.

- [ ] **Step 3.3: Implement EditorWrapper construction, cleanup, and identity helpers**

Append to `packages/haywire-core/src/haywire/ui/editor/wrapper.py`:

```python
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.registry import EditorTypeRegistry
    from haywire.ui.session import Session
    from nicegui.element import Element


class EditorWrapper:
    """Manages the complete lifecycle of an editor instance.

    Responsibilities:
    - Self-subscribe to EditorTypeRegistry for per-key hot-reload events
    - Lazy-instantiate the editor class on first runtime call
    - Capture errors per phase (import/instantiate/runtime) into state
    - Notify the slot via redraw_callback when state changes require a redraw

    The wrapper holds a session reference for its lifetime — runtime methods
    read context via self._session.context internally so the slot can call
    them with minimal arguments.
    """

    def __init__(
        self,
        editor_key: str,
        editor_cls: "Optional[type[BaseEditor]]",
        registry: "EditorTypeRegistry",
        session: "Session",
        payload: Optional[str] = None,
        label: str = "",
    ):
        """
        Args:
            editor_key: Registry key of the editor class.
            editor_cls: The editor class. None when the registry has no entry
                for editor_key — error_import is populated and the wrapper
                renders a placeholder until a successful hot-reload arrives.
            registry: Editor registry for self-subscription.
            session: Owning session — held for the wrapper's lifetime.
            payload: Optional disambiguator (e.g., file path string for
                multi-instance editors). None for single-instance editors.
            label: Tab label for tabbed slots. Defaults to empty; resolved
                lazily at draw time when empty.
        """
        self.editor_key = editor_key
        self.editor_cls = editor_cls
        self.payload = payload
        self.label = label
        self._registry = registry
        self._session: "Optional[Session]" = session
        self._instance: "Optional[BaseEditor]" = None
        self._redraw_callback: Optional[Callable[["EditorWrapper"], None]] = None
        self._state = EditorWrapperState()

        # Subscribe per-key for hot-reload events
        self._registry.add_event_subscriber(self.editor_key, self._on_lifecycle_event)

        # Eager import phase: validate the class exists
        if self.editor_cls is None:
            self._state.is_imported = False
            self._state.error_import = HaywireException.create(
                f"Editor class '{self.editor_key}' is not available in the registry."
            ).enrich(
                operation="Editor Import",
                category="Editor Not Found",
                registry_key=self.editor_key,
                suggestions=[
                    "Ensure the providing library is installed and loaded.",
                    "Check for typos in the editor registry key.",
                ],
            )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def state(self) -> EditorWrapperState:
        return self._state

    @property
    def instance(self) -> "Optional[BaseEditor]":
        return self._instance

    @property
    def binding_id(self) -> str:
        """Stable identity. ``editor_key`` for single-instance bindings;
        ``editor_key::payload`` when a payload is present."""
        return f"{self.editor_key}::{self.payload}" if self.payload else self.editor_key

    @staticmethod
    def split_id(tab_id: str) -> tuple[str, Optional[str]]:
        """Inverse of :attr:`binding_id`."""
        if "::" in tab_id:
            editor_key, payload = tab_id.split("::", 1)
            return editor_key, payload
        return tab_id, None

    @property
    def can_close(self) -> bool:
        """Whether the host UI should render a close button.

        REQUIRED editors have no close button; everything else is closeable.
        Missing identity defaults to closeable. A wrapper with no editor_cls
        (broken state) is closeable so the user can dismiss it.
        """
        from haywire.ui.editor.identity import OpenBehavior

        if self.editor_cls is None:
            return True
        opens = getattr(self.editor_cls.class_identity, "opens", None)
        return opens is not OpenBehavior.REQUIRED

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def set_redraw_callback(
        self, callback: Optional[Callable[["EditorWrapper"], None]]
    ) -> None:
        """Set or clear the redraw callback.

        The slot calls this immediately after construction (in add_binding),
        and again with None during cleanup. The callback is invoked when
        wrapper state changes require a panel redraw — chiefly after a
        successful hot-reload that swaps the editor class.
        """
        self._redraw_callback = callback

    # ------------------------------------------------------------------
    # Lifecycle event handling (placeholder — implemented in a later task)
    # ------------------------------------------------------------------

    def _on_lifecycle_event(self, event: "LifeCycleEvent") -> None:
        """Handle a registry lifecycle event for our editor_key."""
        # Populated in Task 5.
        pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Tear down the wrapper. Idempotent."""
        try:
            self._registry.remove_event_subscriber(self.editor_key, self._on_lifecycle_event)
        except Exception:
            pass
        if self._instance is not None:
            try:
                self._instance.cleanup()
            except Exception as exc:
                logger.warning(
                    f"EditorWrapper '{self.editor_key}': instance.cleanup() raised: {exc}"
                )
            self._instance = None
        self._session = None
        self._redraw_callback = None
```

Add the missing imports at the top of the file (where `from typing import Optional` already is):

```python
from haywire.core.registry.lifecycle_event import LifeCycleEvent  # noqa: F401  (used in TYPE_CHECKING)
```

Actually — `LifeCycleEvent` is referenced in a string annotation under `TYPE_CHECKING`, so it must be inside the `if TYPE_CHECKING:` block. Adjust:

```python
if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.registry import EditorTypeRegistry
    from haywire.ui.session import Session
    from haywire.core.registry.lifecycle_event import LifeCycleEvent
    from nicegui.element import Element
```

- [ ] **Step 3.4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v`
Expected: PASS — all wrapper construction/cleanup/identity tests pass plus the earlier state tests.

- [ ] **Step 3.5: Run lint + format + mypy**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/editor/wrapper.py && uv run ruff format packages/haywire-core/src/haywire/ui/editor/wrapper.py && uv run mypy packages/haywire-core/src/haywire/ui/editor/wrapper.py`
Expected: clean.

- [ ] **Step 3.6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py
git commit -m "feat(editor-wrapper): construction, identity, cleanup

EditorWrapper self-subscribes per-key on construction, populates
error_import when editor_cls is None, and unsubscribes in cleanup().
Identity helpers (binding_id, split_id, can_close) match prior
EditorBinding behavior."
```

---

### Task 4: Implement `_instantiate` (lazy) — error capture into `error_instantiate`

**Why:** The next phase. `_instantiate()` is private; called by `draw()`/`on_focus()`/`poll()` lazily on first need. Captures `HaywireException.from_exception` on failure.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 4.1: Write the failing tests**

Append to `tests/ui/test_editor_wrapper.py`:

```python
class _RaisingEditorCls:
    class_identity = SimpleNamespace(
        registry_key="raising:editor:1",
        label="Raising",
        default_slot="main",
        opens=None,
    )

    def __init__(self):
        raise RuntimeError("constructor explodes")


def test_instantiate_creates_instance_and_assigns_wrapper():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    ok = w._instantiate()
    assert ok is True
    assert w.instance is not None
    assert w.instance.wrapper is w
    assert w.state.error_instantiate is None


def test_instantiate_captures_exception_into_error_instantiate():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="raising:editor:1",
        editor_cls=_RaisingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    ok = w._instantiate()
    assert ok is False
    assert w.instance is None
    assert w.state.error_instantiate is not None
    assert w.state.is_valid() is False


def test_instantiate_returns_false_when_editor_cls_is_none():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="missing:editor:1",
        editor_cls=None,
        registry=reg,
        session=_make_session(),
    )
    ok = w._instantiate()
    assert ok is False
    assert w.instance is None
```

- [ ] **Step 4.2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k instantiate`
Expected: FAIL — `_instantiate` does not exist or raises AttributeError on `instance.wrapper`.

- [ ] **Step 4.3: Implement `_instantiate`**

Add to `EditorWrapper` in `wrapper.py`, just before the `cleanup()` method:

```python
    # ------------------------------------------------------------------
    # Build phase
    # ------------------------------------------------------------------

    def _instantiate(self) -> bool:
        """Lazy-instantiate the editor instance from editor_cls.

        Called internally on first runtime entry point (draw/on_focus/poll).
        Captures construction errors into state.error_instantiate.

        Returns:
            True on success, False if editor_cls is None or construction raised.
        """
        if self.editor_cls is None:
            return False
        try:
            self._instance = self.editor_cls()
            self._instance.wrapper = self
            self._state.error_instantiate = None
            return True
        except Exception as exc:
            self._state.error_instantiate = HaywireException.from_exception(
                exception=exc,
                operation="Instantiate Editor",
                message=f"Failed to instantiate editor '{self.editor_key}'",
            ).enrich(
                editor_key=self.editor_key,
                class_name=self.editor_cls.__name__,
            )
            self._instance = None
            return False
```

Note: `instance.wrapper` is set here. The `BaseEditor` class still has `binding: Optional[EditorBinding]` today — assigning `wrapper` would fail with `AttributeError` only in strict mode, but in standard Python it just sets a new attribute. The assignment works for testing purposes. The proper rename of `binding` → `wrapper` on `BaseEditor` happens in Task 8.

- [ ] **Step 4.4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k instantiate`
Expected: PASS — 3 instantiate tests pass.

- [ ] **Step 4.5: Run full wrapper tests**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v`
Expected: PASS — all wrapper tests pass.

- [ ] **Step 4.6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py
git commit -m "feat(editor-wrapper): lazy _instantiate with error capture

Captures constructor exceptions into state.error_instantiate as a
HaywireException with editor context. Returns False when editor_cls
is None (already in error_import state)."
```

---

### Task 5: Implement `_on_lifecycle_event` — hot-reload state transitions

**Why:** Mirrors `NodeWrapper._on_node_lifecycle_event`. On warning events: keep instance + class alive, populate `error_import`, fire redraw callback. On successful events: update class, clear instance (lazy re-instantiate next draw), clear `error_import`, fire redraw callback.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 5.1: Write the failing tests**

Append to `tests/ui/test_editor_wrapper.py`:

```python
class _NewFakeEditorCls:
    class_identity = SimpleNamespace(
        registry_key="fake:editor:1",
        label="NewFake",
        default_slot="main",
        opens=None,
    )


def test_lifecycle_class_reloaded_updates_class_clears_instance_fires_redraw():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    redraw_calls: list[EditorWrapper] = []
    w.set_redraw_callback(lambda wr: redraw_calls.append(wr))
    # Force lazy instantiate so we have an instance to clear
    w._instantiate()
    assert w.instance is not None

    event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key="fake:editor:1",
        affected_class=_NewFakeEditorCls,
    )
    w._on_lifecycle_event(event)

    assert w.editor_cls is _NewFakeEditorCls
    assert w.instance is None  # cleared so next draw re-instantiates with new class
    assert w.state.error_import is None
    assert w.state.is_imported is True
    assert redraw_calls == [w]


def test_lifecycle_class_removed_keeps_instance_sets_error_import():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    redraw_calls: list[EditorWrapper] = []
    w.set_redraw_callback(lambda wr: redraw_calls.append(wr))
    w._instantiate()
    instance_before = w.instance
    assert instance_before is not None

    event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_REMOVED,
        registry_key="fake:editor:1",
        affected_class=None,
    )
    w._on_lifecycle_event(event)

    # NodeWrapper-style: instance and class kept alive
    assert w.instance is instance_before
    assert w.editor_cls is _FakeEditorCls
    # but error_import is set
    assert w.state.error_import is not None
    assert w.state.is_imported is False
    assert redraw_calls == [w]


def test_lifecycle_recovery_after_removal_clears_error_and_updates_class():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    # Force into removed state
    w._on_lifecycle_event(LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_REMOVED,
        registry_key="fake:editor:1",
        affected_class=None,
    ))
    assert w.state.error_import is not None

    redraw_calls: list[EditorWrapper] = []
    w.set_redraw_callback(lambda wr: redraw_calls.append(wr))

    # Now CLASS_ADDED brings it back
    w._on_lifecycle_event(LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_ADDED,
        registry_key="fake:editor:1",
        affected_class=_NewFakeEditorCls,
    ))
    assert w.editor_cls is _NewFakeEditorCls
    assert w.state.error_import is None
    assert w.state.is_imported is True
    assert redraw_calls == [w]


def test_lifecycle_redraw_callback_safe_when_unset():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
    )
    # No redraw_callback set; must not raise
    w._on_lifecycle_event(LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key="fake:editor:1",
        affected_class=_NewFakeEditorCls,
    ))
    assert w.editor_cls is _NewFakeEditorCls
```

- [ ] **Step 5.2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k lifecycle`
Expected: FAIL — `_on_lifecycle_event` is currently a `pass` stub.

- [ ] **Step 5.3: Implement `_on_lifecycle_event`**

Replace the placeholder `_on_lifecycle_event` in `wrapper.py` with:

```python
    def _on_lifecycle_event(self, event: "LifeCycleEvent") -> None:
        """Handle a registry lifecycle event for our editor_key.

        Mirrors NodeWrapper._on_node_lifecycle_event:
        - Warning events (CLASS_REMOVED, CLASS_NOT_FOUND, reload failures):
          keep instance + class reference alive; populate error_import.
        - Successful events (CLASS_RELOADED, CLASS_ADDED with affected_class):
          swap class, clear instance so next draw lazy-instantiates with
          the new class, clear error_import.

        Always fires the redraw callback (if set) so the slot can repaint
        any state-dependent UI (e.g. tab badges, error placeholders).
        """
        logger.info(
            f"EditorWrapper '{self.editor_key}': lifecycle event "
            f"{event.event_type.value}"
        )

        if event.is_warning_event():
            if event.is_removal():
                self._state.error_import = HaywireException.create(
                    message=(
                        f"Editor '{self.editor_key}' has been removed from "
                        f"the registry and can no longer be used."
                    ),
                ).enrich(
                    operation="Editor Removed",
                    registry_key=self.editor_key,
                    module_name=getattr(event, "module_name", None),
                    library_identity=getattr(event, "library_identity", None),
                    suggestions=[
                        "Re-add the editor class to the registry.",
                    ],
                )
            else:
                self._state.error_import = event.error
            self._state.is_imported = False
            # Keep self._instance and self.editor_cls alive (NodeWrapper-style)
            if self._redraw_callback is not None:
                self._redraw_callback(self)
            return

        # Successful event with new class
        if event.affected_class is not None:
            self.editor_cls = event.affected_class
            self._state.is_imported = True
            self._state.error_import = None
            # Clear instance so next draw lazy-instantiates with new class
            if self._instance is not None:
                try:
                    self._instance.cleanup()
                except Exception as exc:
                    logger.warning(
                        f"EditorWrapper '{self.editor_key}': "
                        f"instance.cleanup() raised during reload: {exc}"
                    )
                self._instance = None
            if self._redraw_callback is not None:
                self._redraw_callback(self)
```

- [ ] **Step 5.4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k lifecycle`
Expected: PASS — 4 lifecycle tests pass.

- [ ] **Step 5.5: Run full wrapper tests**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v`
Expected: PASS.

- [ ] **Step 5.6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py
git commit -m "feat(editor-wrapper): hot-reload lifecycle event handling

Mirrors NodeWrapper philosophy:
- CLASS_REMOVED keeps instance + class alive; sets error_import
- CLASS_RELOADED/ADDED swaps class, clears instance for lazy re-instantiate
- Redraw callback fires on every transition (None-safe)"
```

---

### Task 6: Implement runtime methods `draw`, `on_focus`, `poll`

**Why:** The runtime entry points the slot calls. Each delegates to the instance, captures errors into `error_runtime`. `draw()` lazy-instantiates and renders a placeholder if no instance can be created.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 6.1: Write the failing tests**

Append to `tests/ui/test_editor_wrapper.py`:

```python
class _RecordingEditorCls:
    """Editor stub that records calls to draw/on_focus/poll."""

    class_identity = SimpleNamespace(
        registry_key="rec:editor:1",
        label="Rec",
        default_slot="main",
        opens=None,
    )

    def __init__(self):
        self.draw_calls: list = []
        self.focus_calls: list = []
        self.poll_calls: list = []
        self.cleanup_calls = 0
        self.wrapper = None
        self.poll_returns = False

    def draw(self, context, container):
        self.draw_calls.append((context, container))

    def on_focus(self, context):
        self.focus_calls.append(context)

    def poll(self, context, event):
        self.poll_calls.append((context, event))
        return self.poll_returns

    def cleanup(self):
        self.cleanup_calls += 1


class _FakePanel:
    def __init__(self):
        self.cleared = 0
        self.children: list = []

    def clear(self):
        self.cleared += 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_draw_lazy_instantiates_and_delegates_to_instance():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="rec:editor:1",
        editor_cls=_RecordingEditorCls,
        registry=reg,
        session=session,
    )
    panel = _FakePanel()
    assert w.instance is None
    w.draw(panel)
    assert w.instance is not None
    assert panel.cleared == 1
    assert len(w.instance.draw_calls) == 1
    assert w.instance.draw_calls[0] == (session.context, panel)


def test_draw_renders_placeholder_when_instantiate_fails(monkeypatch):
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="raising:editor:1",
        editor_cls=_RaisingEditorCls,
        registry=reg,
        session=_make_session(),
    )
    panel = _FakePanel()
    placeholder_calls: list[str] = []

    # Stub ui.label so we can detect placeholder creation without a real NiceGUI client
    import haywire.ui.editor.wrapper as wrapper_mod

    class _FakeLabel:
        def classes(self, *a, **k):
            return self

    def _fake_label(text):
        placeholder_calls.append(text)
        return _FakeLabel()

    monkeypatch.setattr(wrapper_mod.ui, "label", _fake_label)

    w.draw(panel)
    assert w.instance is None
    assert panel.cleared == 1
    assert len(placeholder_calls) == 1
    assert "raising:editor:1" in placeholder_calls[0]


def test_draw_captures_runtime_exception_into_error_runtime():
    class _DrawRaisingCls:
        class_identity = SimpleNamespace(
            registry_key="dr:editor:1",
            label="DR",
            default_slot="main",
            opens=None,
        )

        def __init__(self):
            self.wrapper = None

        def draw(self, context, container):
            raise RuntimeError("draw boom")

    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="dr:editor:1",
        editor_cls=_DrawRaisingCls,
        registry=reg,
        session=_make_session(),
    )
    panel = _FakePanel()
    w.draw(panel)
    assert w.state.error_runtime is not None


def test_on_focus_delegates_to_instance():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="rec:editor:1",
        editor_cls=_RecordingEditorCls,
        registry=reg,
        session=session,
    )
    w._instantiate()
    w.on_focus()
    assert w.instance.focus_calls == [session.context]


def test_on_focus_no_op_without_instance():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="missing:editor:1",
        editor_cls=None,
        registry=reg,
        session=_make_session(),
    )
    # Must not raise
    w.on_focus()


def test_on_focus_captures_runtime_exception():
    class _FocusRaisingCls:
        class_identity = SimpleNamespace(
            registry_key="fr:editor:1",
            label="FR",
            default_slot="main",
            opens=None,
        )

        def __init__(self):
            self.wrapper = None

        def on_focus(self, context):
            raise RuntimeError("focus boom")

    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fr:editor:1",
        editor_cls=_FocusRaisingCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    w.on_focus()
    assert w.state.error_runtime is not None


def test_poll_delegates_and_returns_instance_value():
    reg = EditorTypeRegistry()
    session = _make_session()
    w = EditorWrapper(
        editor_key="rec:editor:1",
        editor_cls=_RecordingEditorCls,
        registry=reg,
        session=session,
    )
    w._instantiate()
    w.instance.poll_returns = True
    fake_event = SimpleNamespace()
    assert w.poll(fake_event) is True
    assert w.instance.poll_calls == [(session.context, fake_event)]


def test_poll_returns_false_without_instance():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="missing:editor:1",
        editor_cls=None,
        registry=reg,
        session=_make_session(),
    )
    fake_event = SimpleNamespace()
    assert w.poll(fake_event) is False


def test_poll_captures_runtime_exception_returns_false():
    class _PollRaisingCls:
        class_identity = SimpleNamespace(
            registry_key="pr:editor:1",
            label="PR",
            default_slot="main",
            opens=None,
        )

        def __init__(self):
            self.wrapper = None

        def poll(self, context, event):
            raise RuntimeError("poll boom")

    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="pr:editor:1",
        editor_cls=_PollRaisingCls,
        registry=reg,
        session=_make_session(),
    )
    w._instantiate()
    fake_event = SimpleNamespace()
    assert w.poll(fake_event) is False
    assert w.state.error_runtime is not None
```

- [ ] **Step 6.2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k "draw or focus or poll"`
Expected: FAIL — runtime methods don't exist yet.

- [ ] **Step 6.3: Add `nicegui.ui` import + implement runtime methods**

At the top of `wrapper.py`, add:

```python
from nicegui import ui
```

Add inside `EditorWrapper`, after `_instantiate`:

```python
    # ------------------------------------------------------------------
    # Runtime entry points (called by Slot)
    # ------------------------------------------------------------------

    def draw(self, panel: "Element") -> None:
        """Render the editor into ``panel``.

        Lazy-instantiates the editor if needed. If instantiation fails (or
        editor_cls is None), renders a minimal placeholder pointing the
        user to the error log; the rich error info is published via
        HaywireException's error queue.

        Runtime exceptions in the editor's draw() are captured into
        state.error_runtime; nothing is rendered after the exception.
        """
        try:
            panel.clear()
        except Exception as exc:
            logger.debug(
                f"EditorWrapper '{self.editor_key}': panel.clear() raised "
                f"(dead client?): {exc}"
            )
            return

        if self._instance is None:
            if not self._instantiate():
                with panel:
                    ui.label(
                        f"'{self.editor_key}' unavailable — see error log"
                    ).classes("hw-text-muted p-4")
                return

        try:
            self._instance.draw(self._session.context, panel)
        except Exception as exc:
            self._state.error_runtime = HaywireException.from_exception(
                exception=exc,
                operation="Editor Draw",
                message=f"draw() raised in editor '{self.editor_key}'",
            ).enrich(editor_key=self.editor_key)

    def on_focus(self) -> None:
        """Notify the editor that it became active. No-op if no instance."""
        if self._instance is None:
            return
        try:
            self._instance.on_focus(self._session.context)
        except Exception as exc:
            self._state.error_runtime = HaywireException.from_exception(
                exception=exc,
                operation="Editor Focus",
                message=f"on_focus() raised in editor '{self.editor_key}'",
            ).enrich(editor_key=self.editor_key)

    def poll(self, event: Any) -> bool:
        """Ask the editor whether it needs a redraw.

        Returns False if no instance exists or poll raised. Errors are
        captured into state.error_runtime.
        """
        if self._instance is None:
            return False
        try:
            return bool(self._instance.poll(self._session.context, event))
        except Exception as exc:
            self._state.error_runtime = HaywireException.from_exception(
                exception=exc,
                operation="Editor Poll",
                message=f"poll() raised in editor '{self.editor_key}'",
            ).enrich(editor_key=self.editor_key)
            return False
```

Note `Any` is already imported via `from typing import TYPE_CHECKING, Any, Callable` from Task 3.

- [ ] **Step 6.4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v`
Expected: PASS — all wrapper tests pass.

- [ ] **Step 6.5: Run lint + format + mypy**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/editor/wrapper.py && uv run ruff format packages/haywire-core/src/haywire/ui/editor/wrapper.py && uv run mypy packages/haywire-core/src/haywire/ui/editor/wrapper.py`
Expected: clean.

- [ ] **Step 6.6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py
git commit -m "feat(editor-wrapper): runtime methods draw/on_focus/poll

Each delegates to instance, captures exceptions into state.error_runtime.
draw() lazy-instantiates and renders a minimal hw-text-muted placeholder
when no instance can be created. Wrapper holds session reference; slot
calls these with minimal args."
```

---

### Task 7: Add `repayload` setter to `EditorWrapper`

**Why:** The slot mutates `wrapper.payload` during repayload. Q5C decided to keep this as a thin setter for symmetry. Single-line; primarily a future seam.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py`
- Modify: `tests/ui/test_editor_wrapper.py`

- [ ] **Step 7.1: Write the failing test**

Append to `tests/ui/test_editor_wrapper.py`:

```python
def test_repayload_updates_payload_and_binding_id():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        payload="__unsaved_3__",
    )
    assert w.binding_id == "fake:editor:1::__unsaved_3__"
    w.repayload("/tmp/saved.haywire")
    assert w.payload == "/tmp/saved.haywire"
    assert w.binding_id == "fake:editor:1::/tmp/saved.haywire"


def test_repayload_to_none_removes_suffix():
    reg = EditorTypeRegistry()
    w = EditorWrapper(
        editor_key="fake:editor:1",
        editor_cls=_FakeEditorCls,
        registry=reg,
        session=_make_session(),
        payload="x",
    )
    w.repayload(None)
    assert w.payload is None
    assert w.binding_id == "fake:editor:1"
```

- [ ] **Step 7.2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k repayload`
Expected: FAIL — `repayload` does not exist.

- [ ] **Step 7.3: Implement `repayload`**

Add to `EditorWrapper` after the runtime methods, before `cleanup`:

```python
    def repayload(self, new_payload: Optional[str]) -> None:
        """Update the payload in place. Slot is responsible for collision
        check and DOM-side housekeeping (panel name, set_value)."""
        self.payload = new_payload
```

- [ ] **Step 7.4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_editor_wrapper.py -v -k repayload`
Expected: PASS.

- [ ] **Step 7.5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/wrapper.py tests/ui/test_editor_wrapper.py
git commit -m "feat(editor-wrapper): repayload setter

Single-line setter for save-as flow. Slot owns collision detection
and DOM updates."
```

---

### Task 8: Rename `BaseEditor.binding` → `BaseEditor.wrapper` + update barn editors

**Why:** With `EditorWrapper` in place, the editor-side reference name should match. Hard rename across `BaseEditor` and all `barn/haybale-studio/` editors that reference `self.binding`.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/base.py`
- Modify: `barn/haybale-studio/haybale_studio/editors/graph_editor.py`
- Modify: `barn/haybale-studio/haybale_studio/editors/file_viewer.py`
- Modify: any other `barn/haybale-studio/haybale_studio/editors/*.py` that uses `self.binding`
- Modify: `tests/studio/test_file_viewer_per_file.py` (comment only)

- [ ] **Step 8.1: List every file that references `self.binding` in barn editors**

Run:

```bash
grep -rln "self\.binding" /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/barn/haybale-studio/haybale_studio/editors/
```

Note the list of files — these all need updating in this task.

- [ ] **Step 8.2: Update `BaseEditor`**

Edit `packages/haywire-core/src/haywire/ui/editor/base.py`:

Replace the `binding` attribute and its docstring with:

```python
    #: The runtime wrapper this instance belongs to. Assigned by
    #: :meth:`EditorWrapper._instantiate` right after construction so the
    #: editor can read its own ``editor_key`` / ``payload`` at any point
    #: (draw, poll, event handlers) without the slot having to pass it
    #: through each entry point. Stays ``None`` only for instances created
    #: outside a wrapper (e.g. in direct unit tests).
    wrapper: "Optional[EditorWrapper]" = None
```

Update the `TYPE_CHECKING` import:

```python
if TYPE_CHECKING:
    from haywire.ui.editor.wrapper import EditorWrapper
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent
    from nicegui.element import Element
```

(Remove the `from haywire.ui.app.slot import EditorBinding` line.)

In the `on_focus` docstring, update the line `Read self.binding.payload for this instance's identity.` to `Read self.wrapper.payload for this instance's identity.`

In the `draw` docstring, update `:attr:\`binding\`` references to `:attr:\`wrapper\``.

- [ ] **Step 8.3: Update each barn editor**

For each file from step 8.1, run a global replace `self.binding` → `self.wrapper` in that file. Verify the replacements visually before saving — the only legitimate uses are reading wrapper attributes (`.payload`, `.editor_key`, etc.) or comparing to `None`.

Example edits for `barn/haybale-studio/haybale_studio/editors/graph_editor.py`:

```python
# Before
if self.binding is None or self.binding.payload is None:
    ...
payload = self.binding.payload
# After
if self.wrapper is None or self.wrapper.payload is None:
    ...
payload = self.wrapper.payload
```

Apply identical mechanical replacements in `file_viewer.py` and any other file from step 8.1.

Also update docstring references like `"Resolves self.binding.payload"` → `"Resolves self.wrapper.payload"`.

- [ ] **Step 8.4: Update test comment**

Edit `tests/studio/test_file_viewer_per_file.py`:

Change the comment `# Simulate binding attachment the way EditorBinding.ensure_instance does.` to `# Simulate wrapper attachment the way EditorWrapper._instantiate does.`

If the test body assigns `editor.binding = ...`, update that to `editor.wrapper = ...`.

- [ ] **Step 8.5: Run targeted tests for each barn editor and the studio test**

Run: `uv run pytest tests/studio/ -v`
Expected: PASS.

- [ ] **Step 8.6: Run full barn tests**

Run: `uv run pytest -k "graph_editor or file_viewer or haybale_studio" -v`
Expected: PASS.

- [ ] **Step 8.7: Run lint**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/editor/base.py barn/haybale-studio/`
Expected: clean.

- [ ] **Step 8.8: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/base.py barn/haybale-studio/haybale_studio/editors/ tests/studio/test_file_viewer_per_file.py
git commit -m "refactor(editor): rename BaseEditor.binding -> wrapper

Hard rename across BaseEditor and all barn/haybale-studio editors.
Type now points to haywire.ui.editor.wrapper.EditorWrapper."
```

---

### Task 9: Update `Slot.__init__` signature, add `populate_from_snapshot`, internal `add_binding` rewrite

**Why:** This is the largest single change. `Slot.__init__` drops `initial_bindings` and `active_key`; new method `populate_from_snapshot(data)` handles snapshot deserialization (replacing the deleted `from_snapshot` classmethod). `add_binding` becomes the single wrapper-construction path with a new signature `(editor_key, editor_cls, payload=None, label="", activate=False)`. The slot's batch registry subscription is removed.

**Note:** This task touches a *lot* of `slot.py` lines. Do it in a tight loop: change, run tests, see failures, adapt.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/slot.py`
- Modify: `tests/ui/test_slot.py`, `test_slot_on_focus.py`, `test_slot_tab.py`, `test_slot_icon.py`
- Modify: `packages/haywire-core/src/haywire/ui/app/tab_slot.py` (signature compatibility)
- Modify: `packages/haywire-core/src/haywire/ui/app/icon_slot.py` (signature compatibility)
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py` (`_build_managed_slot`)

- [ ] **Step 9.1: Read tab_slot.py and icon_slot.py to understand subclass overrides**

Run:

```bash
cat packages/haywire-core/src/haywire/ui/app/tab_slot.py | head -100
cat packages/haywire-core/src/haywire/ui/app/icon_slot.py | head -100
```

Note any methods that touch `self._bindings`, `add_binding`, or construct `EditorBinding`.

- [ ] **Step 9.2: Delete the `EditorBinding` class from `slot.py`**

Edit `packages/haywire-core/src/haywire/ui/app/slot.py`:

Delete the entire `@dataclass class EditorBinding:` block (lines ~50-116 in current state — verify by reading the file first).

Replace the module docstring's reference to `:class:\`EditorBinding\`` with `:class:\`EditorWrapper\`` (keep the rest of the docstring).

Add the import at the top (with other haywire imports):

```python
from haywire.ui.editor.wrapper import EditorWrapper
```

Replace every occurrence of `EditorBinding` (in type hints, isinstance checks, etc.) inside `slot.py` with `EditorWrapper`. Use editor's "find and replace in current file" — verify each match is a class reference, not a string in a docstring describing past behavior.

- [ ] **Step 9.3: Restructure `Slot.__init__`**

Replace `Slot.__init__` body. New signature and body:

```python
    def __init__(
        self,
        session: "Session",
        name: str,
        registry: EditorTypeRegistry,
        on_visibility_change: Optional[Callable[[bool], None]] = None,
        bar_place: Literal["left", "right", "top", "bottom"] = "left",
        show_fold_toggle: bool = False,
        visible: bool = True,
        size: int = 300,
    ):
        """
        Args:
            session: The owning session.
            name: Slot identifier — one of "left", "right", "main", "bottom".
            registry: Editor type registry; passed through to wrappers
                constructed via add_binding / populate_from_snapshot.
            on_visibility_change: Optional callback fired when the slot's
                visibility changes.
            bar_place: Where the bar renders relative to the area.
            show_fold_toggle: Render a fold toggle on the bar.
            visible: Initial visibility of the slot's area container.
            size: Initial pixel size.

        After construction, callers must populate the slot via
        :meth:`populate_from_snapshot` or :meth:`add_binding` before any
        rendering. The slot is empty (no bindings, no active wrapper) until
        populated.
        """
        self._session = session
        self.name = name
        self._registry: EditorTypeRegistry = registry
        self._bindings: list[EditorWrapper] = []
        self._active: Optional[EditorWrapper] = None
        self._visible: bool = visible
        self._size: int = size
        self._area_panel_container: Optional[ui.element] = None
        self._area_parent_box: Optional[ui.element] = None
        self._panels: dict[str, ui.element] = {}
        self._drawn: set[str] = set()
        self._on_visibility_change = on_visibility_change
        self._bar_place = bar_place
        self._show_fold_toggle = show_fold_toggle
        self._bar_container: Optional[ui.element] = None
        self._fold_button: Optional[ui.element] = None
```

Note: the line `self._registry.add_batch_event_subscriber(self._on_editor_lifecycle)` is **gone**. The slot no longer subscribes.

- [ ] **Step 9.4: Add `populate_from_snapshot` method**

Add after `__init__`, replacing the deleted `to_snapshot`/`from_snapshot` block (`to_snapshot` is kept; `from_snapshot` classmethod is deleted).

Keep `to_snapshot` exactly as-is — it reads wrapper fields (`binding.editor_key`, `binding.payload`, `binding.label`) which still exist on `EditorWrapper`. Confirm it reads via `binding.editor_cls` etc. (only attribute name changes are local).

Delete the `from_snapshot` classmethod entirely.

Add a new instance method:

```python
    def populate_from_snapshot(self, data: dict) -> None:
        """Populate the slot's bindings from a snapshot dict.

        Injects all REQUIRED editors for this slot from the registry first,
        then appends snapshot entries (ON_PAYLOAD / ON_CONTEXT). Resolves
        the active binding from data["active_key"]. Unknown editor keys
        in the snapshot are skipped with a log warning (Q9A).

        Idempotent only on a fresh slot — call exactly once after __init__,
        before any rendering.
        """
        from haywire.ui.editor.identity import OpenBehavior

        # REQUIRED editors are always re-injected from the registry
        for key, editor_cls in self._registry.get_by_default_slot(self.name).items():
            opens = getattr(editor_cls.class_identity, "opens", OpenBehavior.REQUIRED)
            if opens is OpenBehavior.REQUIRED:
                self.add_binding(
                    editor_key=key,
                    editor_cls=editor_cls,
                    payload=None,
                    label=getattr(editor_cls.class_identity, "label", key),
                    activate=False,
                )

        # Snapshot entries
        for entry in data.get("editors", []):
            key = entry.get("key")
            if not key:
                continue
            editor_cls = self._registry.get_by_key(key)
            if editor_cls is None:
                logger.warning(
                    f"Slot '{self.name}': snapshot editor '{key}' not in registry — skipping"
                )
                continue
            self.add_binding(
                editor_key=key,
                editor_cls=editor_cls,
                payload=entry.get("payload"),
                label=entry.get("label", key),
                activate=False,
            )

        # Apply visibility/size from snapshot if present
        if "visible" in data:
            self._visible = bool(data["visible"])
        if "size" in data:
            self._size = int(data["size"])

        # Resolve initial active binding
        active_key = data.get("active_key")
        if active_key is not None:
            key, payload = EditorWrapper.split_id(active_key)
            match = self.find_binding(key, payload)
            if match is not None:
                self._active = match
                return
        if self._bindings:
            self._active = self._bindings[0]
```

- [ ] **Step 9.5: Rewrite `add_binding` with new signature**

Replace `add_binding` method:

```python
    def add_binding(
        self,
        editor_key: str,
        editor_cls: type["BaseEditor"],
        payload: Optional[str] = None,
        label: str = "",
        activate: bool = False,
    ) -> EditorWrapper:
        """Construct a wrapper, attach the redraw callback, and add it.

        Single wrapper-construction path — used by both populate_from_snapshot
        and TabSlot.open_tab. Creates the panel if the area has been
        rendered. Activates the new wrapper if requested.

        Returns the newly-constructed wrapper.
        """
        wrapper = EditorWrapper(
            editor_key=editor_key,
            editor_cls=editor_cls,
            registry=self._registry,
            session=self._session,
            payload=payload,
            label=label,
        )
        wrapper.set_redraw_callback(lambda w=wrapper: self._redraw(w))
        self._bindings.append(wrapper)
        if self._area_panel_container is not None:
            self._create_panel(wrapper)
        if activate:
            if self._active is None:
                self._activate(wrapper)
            else:
                self.switch_to(wrapper.editor_key, wrapper.payload)
        return wrapper
```

Note `lambda w=wrapper:` — the default-arg trick captures the current wrapper (necessary inside loops, harmless here).

- [ ] **Step 9.6: Thin out runtime methods**

Replace `_ensure_drawn`:

```python
    def _ensure_drawn(self, wrapper: EditorWrapper) -> None:
        """Trigger first-time draw of the wrapper's panel."""
        bid = wrapper.binding_id
        if bid in self._drawn:
            return
        panel = self._panels.get(bid)
        if panel is None:
            return
        wrapper.draw(panel)
        self._drawn.add(bid)
```

Replace `_redraw`:

```python
    def _redraw(self, wrapper: EditorWrapper) -> None:
        """Full redraw of one wrapper's panel."""
        bid = wrapper.binding_id
        panel = self._panels.get(bid)
        if panel is None:
            return
        try:
            panel.clear()
        except RuntimeError as exc:
            logger.debug(f"Slot '{self.name}': skipping redraw of '{bid}' on dead client: {exc}")
            self._panels.pop(bid, None)
            self._drawn.discard(bid)
            return
        self._drawn.discard(bid)
        wrapper.draw(panel)
        self._drawn.add(bid)
```

Replace `_activate`:

```python
    def _activate(self, wrapper: EditorWrapper) -> None:
        """Make ``wrapper`` the active one and run its on_focus hook."""
        self._active = wrapper
        wrapper.on_focus()
        self._ensure_drawn(wrapper)
        if self._area_panel_container is not None:
            self._area_panel_container.set_value(wrapper.binding_id)
```

Replace `handle_context_event`:

```python
    def handle_context_event(self, event: "ContextChangedEvent") -> None:
        """Forward the event to the active wrapper's poll/redraw gate."""
        if self._active is None or self._area_panel_container is None:
            return
        if self._active.poll(event):
            self._redraw(self._active)
```

- [ ] **Step 9.7: Update `repayload_binding` (if it currently exists in slot.py) to mutate via the wrapper**

Replace the body that mutates `target.payload = new_payload`. Use the existing wrapper attribute:

```python
    def repayload_binding(
        self,
        editor_key: str,
        old_payload: Optional[str],
        new_payload: Optional[str],
    ) -> bool:
        """Re-key an existing wrapper's payload in place.

        Slot owns collision detection and DOM-side housekeeping; the
        wrapper just exposes its payload as a mutable field.
        """
        target = self.find_binding(editor_key, old_payload)
        if target is None:
            return False
        if target.payload == new_payload:
            return True

        new_id = f"{editor_key}::{new_payload}" if new_payload else editor_key
        if any(b is not target and b.binding_id == new_id for b in self._bindings):
            logger.warning(
                f"Slot '{self.name}': repayload collision — '{new_id}' already exists"
            )
            return False

        old_id = target.binding_id
        target.repayload(new_payload)

        panel = self._panels.pop(old_id, None)
        if panel is not None:
            panel._props["name"] = new_id
            self._panels[new_id] = panel
        drawn = old_id in self._drawn
        self._drawn.discard(old_id)
        if drawn:
            self._drawn.add(new_id)
        if self._active is target and self._area_panel_container is not None:
            self._area_panel_container.set_value(new_id)
        return True
```

- [ ] **Step 9.8: Update `remove_binding` to call wrapper cleanup**

Edit `remove_binding`:

```python
    def remove_binding(
        self,
        editor_key: str,
        payload: Optional[str] = None,
        cleanup: Optional[Callable[["BaseEditor"], None]] = None,
    ) -> Optional[EditorWrapper]:
        """Remove a single wrapper matching (editor_key, payload).

        Calls wrapper.cleanup() (which unsubscribes from the registry and
        cleans the editor instance). The optional ``cleanup`` callback is
        invoked on the editor instance before wrapper.cleanup() — kept for
        callers that want to inject extra teardown.
        """
        target = self.find_binding(editor_key, payload)
        if target is None:
            return None

        if target.instance is not None and cleanup is not None:
            try:
                cleanup(target.instance)
            except Exception as exc:
                logger.warning(
                    f"Slot '{self.name}': extra cleanup for '{target.binding_id}' raised: {exc}"
                )

        target.set_redraw_callback(None)
        target.cleanup()

        panel = self._panels.pop(target.binding_id, None)
        if panel is not None:
            panel.delete()
        self._drawn.discard(target.binding_id)

        was_active = self._active is target
        idx = self._bindings.index(target)
        self._bindings.remove(target)

        if was_active:
            if self._bindings:
                next_idx = min(idx, len(self._bindings) - 1)
                sibling = self._bindings[next_idx]
                self._active = None
                self._activate(sibling)
            else:
                self._active = None
        return target
```

- [ ] **Step 9.9: Delete `replace_class`, `remove_bindings`, `_on_editor_lifecycle`**

Delete the three methods entirely. Their lines are roughly 705-737, 831-865, and 871-892 in the current `slot.py` — verify by grep before deleting:

```bash
grep -n "def replace_class\|def remove_bindings\|def _on_editor_lifecycle" packages/haywire-core/src/haywire/ui/app/slot.py
```

- [ ] **Step 9.10: Update `cleanup`**

Replace:

```python
    def cleanup(self) -> None:
        """Tear down all wrappers. Idempotent."""
        for wrapper in list(self._bindings):
            wrapper.set_redraw_callback(None)
            wrapper.cleanup()
        self._bindings.clear()
        self._active = None
```

(Removed: `self._registry.remove_batch_event_subscriber(self._on_editor_lifecycle)`.)

- [ ] **Step 9.11: Update `find_binding` typing**

`find_binding` already returns `Optional[EditorWrapper]` after the rename. Verify by reading the method body:

```bash
grep -A 20 "def find_binding" packages/haywire-core/src/haywire/ui/app/slot.py
```

Type annotation should be `-> Optional[EditorWrapper]:`. Adjust if needed.

- [ ] **Step 9.12: Adapt `tab_slot.py` and `icon_slot.py`**

For `tab_slot.py`, find any place that constructs `EditorBinding(...)` (e.g. inside `open_tab`). Replace:

Before:
```python
self.add_binding(
    EditorBinding(editor_key=editor_key, editor_cls=editor_cls, payload=payload),
    activate=True,
)
```

After:
```python
self.add_binding(
    editor_key=editor_key,
    editor_cls=editor_cls,
    payload=payload,
    label=label,
    activate=True,
)
```

The `label` argument is new — `open_tab` already receives it ([tab_slot.py:138](packages/haywire-core/src/haywire/ui/app/tab_slot.py#L138)).

Same scan for `icon_slot.py` — likely has no `add_binding` calls but verify.

- [ ] **Step 9.13: Update `shell.py` `_build_managed_slot`**

Edit `packages/haywire-core/src/haywire/ui/app/shell.py:481-509`:

Replace:

```python
        slot = cls.from_snapshot(
            data=data,
            registry=self._editor_registry,
            session=self.session,
            name=slot_name,
            bar_place=bar_place,
            show_fold_toggle=show_fold_toggle,
            on_visibility_change=on_visibility_change,
        )
```

With:

```python
        slot = cls(
            session=self.session,
            name=slot_name,
            registry=self._editor_registry,
            bar_place=bar_place,
            show_fold_toggle=show_fold_toggle,
            on_visibility_change=on_visibility_change,
        )
        slot.populate_from_snapshot(data)
```

- [ ] **Step 9.14: Migrate slot tests to new API**

The slot tests construct slots and bindings in patterns that no longer compile. Update each test file.

For `tests/ui/test_slot.py`:
- Delete the `replace_class` test cases (lines ~441-501).
- Delete the `remove_bindings` test cases (lines ~503-560).
- For tests that build a slot, change the construction pattern:

Before:
```python
slot = TabSlot(
    session=fake_session,
    name="main",
    registry=_REGISTRY,
    initial_bindings=[EditorBinding(editor_key="a", editor_cls=cls)],
)
```

After:
```python
slot = TabSlot(
    session=fake_session,
    name="main",
    registry=_REGISTRY,
)
slot.add_binding(editor_key="a", editor_cls=cls)
```

For `tests/ui/test_slot_on_focus.py`, `test_slot_tab.py`, `test_slot_icon.py`: same mechanical migration. The `_FakeRegistry` stub from these test files needs to grow `add_event_subscriber` and `remove_event_subscriber` since wrappers self-subscribe. Add:

```python
class _FakeRegistry:
    def __init__(self):
        self._subscribers = {}

    def add_batch_event_subscriber(self, _cb):
        pass

    def remove_batch_event_subscriber(self, _cb):
        pass

    def add_event_subscriber(self, key, cb):
        self._subscribers.setdefault(key, []).append(cb)

    def remove_event_subscriber(self, key, cb):
        if key in self._subscribers:
            try:
                self._subscribers[key].remove(cb)
            except ValueError:
                pass
            if not self._subscribers[key]:
                del self._subscribers[key]
```

For `test_slot_on_focus.py:200`, the `EditorBinding(editor_key="e1", editor_cls=_RaisingEditor, payload=None)` line constructs a binding outside `add_binding`. Migrate to use the slot's `add_binding`. Same for any other `EditorBinding(...)` literal in the tests.

For tests that previously asserted on `binding.payload == "old"` etc., the wrapper attribute names are unchanged.

For `tests/ui/test_slot_on_focus.py:253` (`slot.remove_bindings("e1")`): the method is deleted. The test was asserting sibling promotion — replace the trigger with `slot.close_tab("e1")` (TabSlot public API) and verify the test still exercises the same promotion logic. If the test uses a generic `Slot` (not `TabSlot`), use `slot.remove_binding("e1")` (note: singular — the per-key bulk removal is gone).

- [ ] **Step 9.15: Run the full slot test suite**

Run: `uv run pytest tests/ui/test_slot.py tests/ui/test_slot_on_focus.py tests/ui/test_slot_tab.py tests/ui/test_slot_icon.py -v`
Expected: PASS. Iterate until green — most failures will be construction-pattern mismatches.

- [ ] **Step 9.16: Run wrapper tests still pass**

Run: `uv run pytest tests/ui/test_editor_wrapper.py tests/ui/test_editor_registry.py -v`
Expected: PASS.

- [ ] **Step 9.17: Run lint + format + mypy**

Run:

```bash
uv run ruff check packages/haywire-core/src/haywire/ui/app/slot.py packages/haywire-core/src/haywire/ui/app/tab_slot.py packages/haywire-core/src/haywire/ui/app/icon_slot.py packages/haywire-core/src/haywire/ui/app/shell.py
uv run ruff format packages/haywire-core/src/haywire/ui/app/slot.py packages/haywire-core/src/haywire/ui/app/tab_slot.py packages/haywire-core/src/haywire/ui/app/icon_slot.py packages/haywire-core/src/haywire/ui/app/shell.py
uv run mypy packages/haywire-core/src/haywire/ui/app/
```

Expected: clean.

- [ ] **Step 9.18: Run the full test suite**

Run: `uv run pytest -m "not integration"`
Expected: PASS.

- [ ] **Step 9.19: Run integration tests**

Run: `uv run pytest -m integration`
Expected: PASS. These exercise full library loading + slot rendering — most likely to surface any missed migration.

- [ ] **Step 9.20: Smoke test the running app**

Run: `uv run haywire`

In the browser:
1. Open multiple tabs (graph editor with at least 2 different graphs, file viewer)
2. Switch between tabs — verify each renders correctly
3. Save-as a graph (rename the unsaved tab) — verify the tab id updates
4. Close a tab — verify sibling activation works
5. Open browser dev tools console — verify no warnings/errors

Document any UI regressions before proceeding.

- [ ] **Step 9.21: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/slot.py packages/haywire-core/src/haywire/ui/app/tab_slot.py packages/haywire-core/src/haywire/ui/app/icon_slot.py packages/haywire-core/src/haywire/ui/app/shell.py tests/ui/
git commit -m "refactor(slot): adopt EditorWrapper, drop hot-reload fan-out

- Slot.__init__ now bare config; populate_from_snapshot replaces
  the from_snapshot classmethod
- add_binding takes (editor_key, editor_cls, payload, label, activate)
  as the single wrapper-construction path
- Wrapper self-subscribes to the registry; replace_class /
  remove_bindings / _on_editor_lifecycle deleted
- Runtime methods (handle_context_event, _activate, _ensure_drawn,
  _redraw) collapse to thin wrapper-method delegation
- Tests migrated: EditorBinding literals replaced with add_binding"
```

---

### Task 10: Final verification

**Why:** Confirm everything still works end-to-end after the multi-file change.

- [ ] **Step 10.1: Full quality suite**

Run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/
uv run pytest --cov
```

Expected: clean lint/format, no new mypy errors, all tests pass, coverage stable or improved on the touched modules.

- [ ] **Step 10.2: Search for residual `EditorBinding` references**

Run:

```bash
grep -rn "EditorBinding" packages/ barn/ tests/ docs/ 2>/dev/null
```

Expected: no matches in production code; possibly some matches in `docs/` describing past architecture (acceptable). If any production code still references `EditorBinding`, fix it.

- [ ] **Step 10.3: Search for residual `self.binding` references**

Run:

```bash
grep -rn "self\.binding" packages/ barn/ 2>/dev/null
```

Expected: no matches in editor code (any matches in `node_wrapper.py`, `edge_wrapper.py`, port code are unrelated and correct — those are not editor `self.binding`).

- [ ] **Step 10.4: Smoke test app one more time**

Run: `uv run haywire`

Verify:
1. Cold start loads without errors
2. Open + switch + close a tab works
3. Hot-reload an editor file (save a `.py` in `barn/haybale-studio/haybale_studio/editors/`) and verify the editor reloads in-place without a page refresh
4. Console clean

- [ ] **Step 10.5: Commit any final cleanup**

If steps 10.2–10.4 surfaced anything:

```bash
git add -p
git commit -m "chore: cleanup after EditorWrapper refactor"
```

If nothing to clean, skip.

---

## Self-Review

**Spec coverage check:**
- Q1 (slot-injected redraw callback) → Task 3 (`set_redraw_callback`), Task 5 (callback fires), Task 9 (slot wires it in `add_binding`). ✓
- Q2 (`haywire/ui/editor/wrapper.py`) → Task 2/3. ✓
- Q3 (per-key on `EditorTypeRegistry`) → Task 1. ✓
- Q4 (eager import + lazy instantiate, unified `error_runtime`) → Task 3 (eager import), Task 4 (lazy `_instantiate`), Task 6 (single `error_runtime`). ✓
- Q5 (slot owns collision; mutates wrapper.payload) → Task 9.7. ✓
- Q6 (`set_redraw_callback`) → Task 3, Task 9.5. ✓
- Q7/Q13 (placeholder when no instance; healthy delegates) → Task 6. ✓
- Q8 (two-phase + `populate_from_snapshot`) → Task 9.4, 9.13. ✓
- Q9 (skip unknown editors silently) → Task 9.4 (log warning + skip). ✓
- Q10 (wrapper holds session) → Task 3 + Task 6 (calls `self._session.context`). ✓
- Q11 (delete `replace_class`/`remove_bindings`/`_on_editor_lifecycle`) → Task 9.9. ✓
- Q12 (NodeWrapper-style: keep instance on REMOVED) → Task 5. ✓
- Q14 (error queue out of scope; `HaywireException` self-publishes) → no task; Tasks 4/6 just write to state. ✓
- Q15 (rename `binding` → `wrapper`) → Task 8. ✓
- Q16 (new `test_editor_wrapper.py`) → Tasks 2-7 build it; Task 9 migrates slot tests. ✓
- Q17 (`add_binding(editor_key, editor_cls, ...)`) → Task 9.5. ✓

**Placeholder scan:** No "TBD"/"TODO"/"add appropriate error handling" patterns. Each step has actual code or commands.

**Type/method consistency:** `EditorWrapper` constructor signature consistent across Task 3 and Task 9.5. `add_binding` signature consistent between Task 9.5 (definition), Task 9.4 (called from `populate_from_snapshot`), and Task 9.12 (called from `tab_slot.open_tab`). `set_redraw_callback` defined in Task 3, used in Task 5 (test), Task 9.5 (slot wires it), Task 9.8 (slot clears it on remove), Task 9.10 (slot clears it on cleanup).

**Coverage gaps:** None. All 17 inquisition decisions are mapped.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-25-editor-wrapper-refactor.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
