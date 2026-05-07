# Cross-Session Event Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate cross-session event broadcasting into a single channel owned by `SessionManager`, move graph-validation side effects onto `Haystack`, and delete the vestigial `entry.sessions` bookkeeping.

**Architecture:** `Session` gains a new method `notify_cross_session_context_change(event)` that delegates to `SessionManager.broadcast(event)`, which fans the event unconditionally to every registered session. `Haystack` absorbs the app-level validation handler, owns its own `session_manager` reference, and subscribes to entry validation internally. `GraphEntry` stays a pure dataclass. `entry.sessions` bookkeeping is deleted entirely along with `session_attach`/`session_detach`.

**Tech Stack:** Python 3, pytest, NiceGUI. No new dependencies.

**Design spec:** [internals/superpowers/specs/2026-04-15-cross-session-event-channel-design.md](../specs/2026-04-15-cross-session-event-channel-design.md)

---

## File Inventory

**Modified (core):**
- `packages/haywire-core/src/haywire/ui/session.py` — constructor gains `session_manager`, add `notify_cross_session_context_change`
- `packages/haywire-core/src/haywire/ui/session_manager.py` — add `broadcast(event)`, inject `self` in `create_session`, delete `broadcast_data_mutation`

**Modified (studio):**
- `packages/haywire-studio/src/haywire_studio/haystack.py` — constructor gains `session_manager`, drop `validation_subscriber`, add `_on_entry_validation`, remove `entry.sessions` machinery, drop `session_id` params
- `packages/haywire-studio/src/haywire_studio/app.py` — delete `_subscribe_entry_validation`, `_on_graph_validation_for_entry`, `_result_mutates_data`; update `Haystack` construction; update `restore_persisted_tabs` call

**Modified (barn editors):**
- `barn/haybale-studio/haybale_studio/editors/graph_editor.py` — 5 producer migrations (undo/redo/save/save-as), remove `session_detach` call
- `barn/haybale-studio/haybale_studio/editors/haystack_editor.py` — 2 producer migrations, remove `session_detach` loop, drop `session_id` from `create_new` call
- `barn/haybale-studio/haybale_studio/editors/file_browser.py` — drop `session_id` from `open_graph` call

**Modified (tests):**
- `tests/studio/test_haystack.py` — rewrite fixtures for new signature, drop tests for deleted features (validation_subscriber, entry.sessions), add tests for new behavior
- `tests/studio/test_haystack_editor_remove.py` — update fixtures to account for cross-session routing of `DATA_MUTATED`
- `tests/ui/test_session_manager.py` (new) — tests for `SessionManager.broadcast`
- `tests/ui/test_session.py` (new) — tests for `Session.notify_cross_session_context_change`

---

## Task 1: Add `SessionManager.broadcast(event)` (TDD)

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/session_manager.py`
- Create: `tests/ui/test_session_manager.py`

- [ ] **Step 1: Write the failing test**

Create `tests/ui/test_session_manager.py`:

```python
"""Tests for SessionManager broadcast and session injection."""

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.ui.context_events import ContextChangedEvent, ContextChangeType
from haywire.ui.session_manager import SessionManager


def test_broadcast_fans_event_to_every_session():
    """broadcast() calls notify_context_changed on every registered session."""
    manager = SessionManager()
    s1 = MagicMock()
    s1.session_id = "s1"
    s2 = MagicMock()
    s2.session_id = "s2"
    manager._sessions = {"s1": s1, "s2": s2}

    event = ContextChangedEvent(change_type=ContextChangeType.DATA_MUTATED)
    manager.broadcast(event)

    s1.notify_context_changed.assert_called_once_with(event)
    s2.notify_context_changed.assert_called_once_with(event)


def test_broadcast_swallows_session_errors_and_continues():
    """If one session raises, broadcast still reaches the others."""
    manager = SessionManager()
    good = MagicMock()
    good.session_id = "good"
    bad = MagicMock()
    bad.session_id = "bad"
    bad.notify_context_changed.side_effect = RuntimeError("boom")
    manager._sessions = {"bad": bad, "good": good}

    event = ContextChangedEvent(change_type=ContextChangeType.DATA_MUTATED)
    manager.broadcast(event)  # must not raise

    good.notify_context_changed.assert_called_once_with(event)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_session_manager.py -v`
Expected: FAIL with `AttributeError: 'SessionManager' object has no attribute 'broadcast'`

- [ ] **Step 3: Implement `broadcast` and delete `broadcast_data_mutation`**

Edit `packages/haywire-core/src/haywire/ui/session_manager.py`:

Replace the `broadcast_data_mutation` method (lines 89–122) with:

```python
    def broadcast(self, event: ContextChangedEvent) -> None:
        """Fan an event out to every registered session.

        Used for cross-session notifications (e.g. DATA_MUTATED after a
        graph edit). Consumers already re-read their own ground-truth state
        when notified, so unconditional fan-out is safe — a session that
        doesn't care no-ops on receipt.
        """
        failed = []
        for session_id, session in list(self._sessions.items()):
            try:
                session.notify_context_changed(event)
            except Exception as e:
                logger.warning(f"SessionManager: broadcast failed for session {session_id[:8]}: {e}")
                failed.append(session_id)
        if failed:
            logger.warning(f"SessionManager: {len(failed)} session(s) failed during broadcast")
```

Also remove the now-unused `Optional` from imports if nothing else needs it — scan the file.

Update the module docstring at the top of the file (lines 2–8): replace the `broadcast_data_mutation()` mention with `broadcast()`:

```python
"""
SessionManager — manages the lifecycle of all active browser sessions.

Each browser connection gets its own Session. The SessionManager creates,
tracks, and removes sessions. It also provides broadcast() to fan a
ContextChangedEvent to every session — used for cross-session updates.
"""
```

Update the class docstring usage example (around line 22–31):

```python
    """
    Manages all active Sessions across browser connections.

    Usage:
        manager = SessionManager()
        session = manager.create_session(project_state=app, workspace_manager=ws)
        manager.remove_session(session.session_id)
        manager.broadcast(event)
    """
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_session_manager.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/session_manager.py tests/ui/test_session_manager.py
git commit -m "feat(session_manager): add broadcast(event), remove broadcast_data_mutation"
```

---

## Task 2: Add `session_manager` injection to `Session` (TDD)

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/session.py`
- Modify: `packages/haywire-core/src/haywire/ui/session_manager.py`
- Create: `tests/ui/test_session.py`

- [ ] **Step 1: Write the failing test**

Create `tests/ui/test_session.py`:

```python
"""Tests for Session cross-session notifications."""

from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.ui.context_events import ContextChangedEvent, ContextChangeType
from haywire.ui.session import Session


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


def test_notify_cross_session_delegates_to_session_manager():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    event = ContextChangedEvent(change_type=ContextChangeType.DATA_MUTATED)

    session.notify_cross_session_context_change(event)

    sm.broadcast.assert_called_once_with(event)


def test_notify_context_changed_stays_local_only():
    """Local notify does NOT go through session_manager."""
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    orchestrator = MagicMock()
    session.set_orchestrator(orchestrator)

    event = ContextChangedEvent(change_type=ContextChangeType.SELECTION_CHANGED)
    session.notify_context_changed(event)

    orchestrator.assert_called_once_with(event, session.context)
    sm.broadcast.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_session.py -v`
Expected: FAIL — `Session.__init__()` doesn't accept `session_manager`

- [ ] **Step 3: Add `session_manager` to `Session.__init__`**

Edit `packages/haywire-core/src/haywire/ui/session.py`:

Change the constructor signature and body. Replace:

```python
    def __init__(self, project_state, workspace_manager: WorkspaceManager):
        """
        Create a new session.

        Args:
            project_state: The shared project state (graph data, settings, etc.).
            workspace_manager: Pre-configured WorkspaceManager for this session.
        """
        self.session_id = str(uuid.uuid4())
        self.project_state = project_state
        self.context = SessionContext(session_id=self.session_id, app=project_state)
        self.context.session = self
        self.workspace_manager = workspace_manager
```

With:

```python
    def __init__(self, project_state, workspace_manager: WorkspaceManager, session_manager: "SessionManager"):
        """
        Create a new session.

        Args:
            project_state: The shared project state (graph data, settings, etc.).
            workspace_manager: Pre-configured WorkspaceManager for this session.
            session_manager: The SessionManager that owns this session, used for
                cross-session event broadcasting.
        """
        self.session_id = str(uuid.uuid4())
        self.project_state = project_state
        self.context = SessionContext(session_id=self.session_id, app=project_state)
        self.context.session = self
        self.workspace_manager = workspace_manager
        self._session_manager = session_manager
```

Add the import at the top of the file under the existing `TYPE_CHECKING` block:

```python
if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.session_manager import SessionManager
```

- [ ] **Step 4: Add `notify_cross_session_context_change`**

After `notify_context_changed` (around line 84), add:

```python
    def notify_cross_session_context_change(self, event: ContextChangedEvent) -> None:
        """
        Fan a context change out to every session (including self).

        Used for events that peer sessions care about — graph data mutations,
        haystack changes. Delegates to SessionManager.broadcast, which calls
        notify_context_changed on every registered session.

        Args:
            event: The ContextChangedEvent describing what changed.
        """
        self._session_manager.broadcast(event)
```

Update the class docstring to document the two notify flows. Replace the existing "Context change flow:" section (around lines 32–36) with:

```python
    Two context change flows:
        Local (single session):
            component → session.notify_context_changed(event) → orchestrator
        Cross-session (all sessions including origin):
            component → session.notify_cross_session_context_change(event)
                      → SessionManager.broadcast(event)
                      → every session.notify_context_changed(event) → orchestrator
```

- [ ] **Step 5: Inject `session_manager` in `SessionManager.create_session`**

Edit `packages/haywire-core/src/haywire/ui/session_manager.py`, replace the `create_session` method (around line 40–54):

```python
    def create_session(self, **session_kwargs) -> "Session":
        """
        Create a new Session and register it.

        All keyword arguments are forwarded to the Session constructor.
        ``session_manager=self`` is injected automatically so callers do
        not pass it.

        Returns:
            The newly created Session.
        """
        from haywire.ui.session import Session

        session = Session(session_manager=self, **session_kwargs)
        self._sessions[session.session_id] = session
        logger.info(f"SessionManager: created session {session.session_id[:8]}")
        return session
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_session.py tests/ui/test_session_manager.py -v`
Expected: PASS (5 tests total)

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/session.py packages/haywire-core/src/haywire/ui/session_manager.py tests/ui/test_session.py
git commit -m "feat(session): add notify_cross_session_context_change + session_manager injection"
```

---

## Task 3: Remove `entry.sessions` bookkeeping from `Haystack`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/haystack.py`

This task deletes dead code. The tests that cover the removed behavior are deleted in Task 6.

- [ ] **Step 1: Remove `sessions` field from `GraphEntry`**

Edit `packages/haywire-studio/src/haywire_studio/haystack.py`:

In the `GraphEntry` dataclass (around line 57–76), remove the `sessions` line. Also update the docstring:

```python
@dataclass
class GraphEntry:
    """
    Holds all runtime state for a single open graph.

    Attributes:
        graph:    The BaseGraph instance.
        editor:   Editor wrapping the graph for undo/redo and mutations.
        path:     Absolute Path to the .haywire file, or None for untitled.
        unsaved:  True if the graph has in-memory changes not yet written to disk.
        interpreter:  Per-graph Interpreter instance (created on execution start).
    """

    graph: "HaywireGraph"
    editor: "Editor"
    path: Optional[Path] = None
    unsaved: bool = False
    interpreter: Optional["Interpreter"] = field(default=None, repr=False)
```

Also remove the now-unused `Set` from the import at the top of the file — check the `typing` import line and remove `Set` if unreferenced.

- [ ] **Step 2: Remove `session_id` parameters from `create_new` and `open_graph`**

Around lines 150–201, change both signatures and bodies.

Replace `create_new`:

```python
    def create_new(self) -> GraphEntry:
        """
        Create a new unnamed graph.

        Each call produces a fresh entry keyed as ``'__new_1__'``, ``'__new_2__'``, …
        and named ``'Untitled 1'``, ``'Untitled 2'``, …

        Returns:
            The new GraphEntry.
        """
        self._new_counter += 1
        key = f"__new_{self._new_counter}__"
        name = f"Untitled {self._new_counter}"
        graph, editor = self._graph_factory(key, name)
        entry = GraphEntry(graph=graph, editor=editor, path=None)
        self._entries[key] = entry
        self._validation_subscriber(entry)
        return entry
```

Replace `open_graph`:

```python
    def open_graph(self, path: Path) -> GraphEntry:
        """
        Open a .haywire file, reusing the existing entry if already loaded.

        On first-time open, subscribes the validation callback.

        Args:
            path: Absolute path to the .haywire file.

        Returns:
            The (existing or newly-loaded) GraphEntry.
        """
        key = str(path)
        entry = self._entries.get(key)
        if entry is None:
            graph, editor = self._graph_factory(path.stem, str(path))
            graph.load_from_file(str(path))
            graph.force_validation()
            entry = GraphEntry(graph=graph, editor=editor, path=path)
            self._entries[key] = entry
            self._validation_subscriber(entry)
        return entry
```

(We keep `_validation_subscriber` alive for now — it's deleted in Task 4.)

- [ ] **Step 3: Delete `session_attach`, `session_detach`, `sessions_for_entry`**

Around lines 311–325, delete the "Session tracking" section entirely:

```python
    # ------------------------------------------------------------------
    # Session tracking
    # ------------------------------------------------------------------

    def session_attach(self, entry: GraphEntry, session_id: str) -> None:
        ...
    def session_detach(self, entry: GraphEntry, session_id: str) -> None:
        ...
    def sessions_for_entry(self, entry: GraphEntry) -> Set[str]:
        ...
```

- [ ] **Step 4: Update `Haystack` module-level docstring**

Edit the usage example (around lines 11–33) — remove `session_id` args and the `session_detach` line. Also the class docstring's "Sessions attach/detach" point (around lines 126–127). Final versions:

Module docstring usage example:

```python
Usage in app.py::

    haystack = Haystack(
        workspace_root=Path(...),
        graph_factory=app._graph_factory,
        validation_subscriber=app._subscribe_entry_validation,
    )

    # When a file is opened:
    entry = haystack.open_graph(path)

    # When the user creates a new unnamed graph:
    entry = haystack.create_new()

    # On save:
    haystack.save_graph(entry)

    # Save/load haystacks:
    haystack.save_haystack("default")
    haystack.load_haystack("default")
```

Class docstring key-design-points:

```python
    Key design points:
    - One GraphEntry per unique file path; untitled graphs use key '__untitled__'.
    - New unnamed graphs get auto-keyed as '__new_1__', '__new_2__', etc.
    - Haystacks: named selections of open graphs persisted as TOML in
      ``<workspace>/haystacks/*.toml``.
```

- [ ] **Step 5: Verify — intentionally break by running module import**

Run: `uv run python -c "from haywire_studio.haystack import Haystack, GraphEntry; print(Haystack, GraphEntry)"`
Expected: OK (module imports cleanly)

Run: `uv run pytest tests/studio/test_haystack.py -v`
Expected: FAIL — tests reference `entry.sessions`, `session_attach`, removed `session_id` kwargs. This is expected and fixed in Task 6.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/haystack.py
git commit -m "refactor(haystack): delete entry.sessions bookkeeping and session_id params"
```

---

## Task 4: Absorb validation handler into `Haystack`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/haystack.py`
- Modify: `packages/haywire-studio/src/haywire_studio/app.py`

This task replaces the `validation_subscriber` injection with a `session_manager` dependency and an internal `_on_entry_validation` method.

- [ ] **Step 1: Update `Haystack.__init__` — swap `validation_subscriber` for `session_manager`**

Edit `packages/haywire-studio/src/haywire_studio/haystack.py`:

Replace the `__init__` and the `ValidationSubscriber` type alias (around lines 50–54, 134–144):

Delete the type alias line:

```python
# Subscriber signature: called once per newly-created GraphEntry
ValidationSubscriber = Callable[["GraphEntry"], None]
```

Replace the `__init__`:

```python
    def __init__(
        self,
        workspace_root: Path,
        graph_factory: GraphFactory,
        session_manager: "SessionManager",
    ):
        self._entries: Dict[str, GraphEntry] = {}
        self._new_counter: int = 0
        self._workspace_root: Path = workspace_root
        self._graph_factory: GraphFactory = graph_factory
        self._session_manager = session_manager
```

Add `SessionManager` to the `TYPE_CHECKING` block at the top of the file:

```python
if TYPE_CHECKING:
    from haywire.core.graph.base import HaywireGraph
    from haywire.core.execution.interpreter import Interpreter
    from haywire.core.graph.editor import Editor
    from haywire.core.graph.validation import ValidationResult
    from haywire.ui.session_manager import SessionManager
```

- [ ] **Step 2: Add `_on_entry_validation` method**

After the `__init__` (around where the old comment block for graph lifecycle starts), insert:

```python
    # ------------------------------------------------------------------
    # Validation → entry lifecycle + cross-session broadcast
    # ------------------------------------------------------------------

    def _on_entry_validation(self, entry: GraphEntry, result: "ValidationResult") -> None:
        """Handle a validation result on one of this haystack's entries.

        Three concerns, all rooted in the fact that a graph under this
        haystack's ownership just validated:

        1. Stop execution if the result requires graph reassembly.
        2. Mark the entry unsaved if the result mutated data.
        3. Broadcast DATA_MUTATED so peer sessions refresh.
        """
        from haywire.ui.context_events import ContextChangedEvent, ContextChangeType

        if entry.is_executing and result.has_changes() and result.graph is not None:
            if result.graph.requires_graph_reassembly():
                entry.stop_execution()

        if bool(result.nodes or result.edges):
            entry.unsaved = True
            event = ContextChangedEvent(change_type=ContextChangeType.DATA_MUTATED)
            self._session_manager.broadcast(event)
```

- [ ] **Step 3: Replace `_validation_subscriber(entry)` calls with inline subscription**

In `create_new`, `open_graph`, and the `load_haystack` graph loop, replace the `self._validation_subscriber(entry)` lines with:

```python
            entry.graph.subscribe_to_validation(
                lambda result, _entry=entry: self._on_entry_validation(_entry, result)
            )
```

Specifically — in `create_new` (around line 169), the line becomes:

```python
        entry = GraphEntry(graph=graph, editor=editor, path=None)
        self._entries[key] = entry
        entry.graph.subscribe_to_validation(
            lambda result, _entry=entry: self._on_entry_validation(_entry, result)
        )
        return entry
```

In `open_graph` (around line 199):

```python
            entry = GraphEntry(graph=graph, editor=editor, path=path)
            self._entries[key] = entry
            entry.graph.subscribe_to_validation(
                lambda result, _entry=entry: self._on_entry_validation(_entry, result)
            )
        return entry
```

In `load_haystack` (around line 466):

```python
            entry = GraphEntry(graph=graph, editor=editor, path=abs_path)
            self._entries[key] = entry
            entry.graph.subscribe_to_validation(
                lambda result, _entry=entry: self._on_entry_validation(_entry, result)
            )
            opened.append(entry)
```

- [ ] **Step 4: Update `Haystack` module docstring usage example**

Edit lines 11–33 to replace the `validation_subscriber=` kwarg with `session_manager=`:

```python
Usage in app.py::

    haystack = Haystack(
        workspace_root=Path(...),
        graph_factory=app._graph_factory,
        session_manager=app.session_manager,
    )

    # When a file is opened:
    entry = haystack.open_graph(path)

    # When the user creates a new unnamed graph:
    entry = haystack.create_new()

    # On save:
    haystack.save_graph(entry)

    # Save/load haystacks:
    haystack.save_haystack("default")
    haystack.load_haystack("default")
```

- [ ] **Step 5: Rewire `Haystack` construction in `app.py`**

Edit `packages/haywire-studio/src/haywire_studio/app.py`:

In `setup_shared_services` (around line 147–151), replace:

```python
        self.haystack = Haystack(
            workspace_root=Path(self.workspace_root),
            graph_factory=self._graph_factory,
            validation_subscriber=self._subscribe_entry_validation,
        )
```

With:

```python
        self.haystack = Haystack(
            workspace_root=Path(self.workspace_root),
            graph_factory=self._graph_factory,
            session_manager=self.session_manager,
        )
```

- [ ] **Step 6: Delete obsolete helpers from `app.py`**

In `packages/haywire-studio/src/haywire_studio/app.py`, delete the following (exact lines as they stand today):

1. The `_result_mutates_data` top-level function (lines 34–40).
2. The `_on_graph_validation_for_entry` staticmethod (lines 169–175) and its preceding comment block header (lines 165–168):

```python
    # ------------------------------------------------------------------
    # Per-graph execution
    # ------------------------------------------------------------------
```

3. The `_subscribe_entry_validation` method (lines 252–265).

Also scan the `app.py` imports at the top of the file — remove `ValidationResult` from the `from haywire.core.graph.validation import ...` line if it's no longer referenced (it was only used by the deleted helpers).

- [ ] **Step 7: Update `restore_persisted_tabs` in `app.py`**

Around line 239, the call is:

```python
                self.haystack.open_graph(path, session_id)
```

Change to:

```python
                self.haystack.open_graph(path)
```

The `session_id` parameter on `restore_persisted_tabs` becomes unused — either remove it from the signature or leave for a follow-up. **Leave it for now** — other call sites pass it, and cleaning up the signature is out of scope for this refactor.

- [ ] **Step 8: Run a smoke import to verify `app.py` and `haystack.py` still import cleanly**

Run: `uv run python -c "from haywire_studio.app import HaywireApp; print('ok')"`
Expected: `ok`

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/haystack.py packages/haywire-studio/src/haywire_studio/app.py
git commit -m "refactor(haystack): absorb validation handler, drop validation_subscriber"
```

---

## Task 5: Migrate producers to `notify_cross_session_context_change`

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/graph_editor.py`
- Modify: `barn/haybale-studio/haybale_studio/editors/haystack_editor.py`
- Modify: `barn/haybale-studio/haybale_studio/editors/file_browser.py`

This task moves all cross-session broadcasts to the new API and removes session_detach calls.

- [ ] **Step 1: Update `graph_editor.py` — undo (line 235–248)**

Edit `barn/haybale-studio/haybale_studio/editors/graph_editor.py`:

Replace the `_do_undo` method body tail (lines 241–248):

```python
        entry.editor.undo()
        session = context.session
        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.DATA_MUTATED,
                    source_editor="graph_editor",
                )
            )
```

With:

```python
        entry.editor.undo()
        session = context.session
        if session is not None:
            session.notify_cross_session_context_change(
                ContextChangedEvent(
                    change_type=ContextChangeType.DATA_MUTATED,
                    source_editor="graph_editor",
                )
            )
```

- [ ] **Step 2: Update `graph_editor.py` — redo (line 250–263)**

Same change for `_do_redo`:

```python
        entry.editor.redo()
        session = context.session
        if session is not None:
            session.notify_cross_session_context_change(
                ContextChangedEvent(
                    change_type=ContextChangeType.DATA_MUTATED,
                    source_editor="graph_editor",
                )
            )
```

- [ ] **Step 3: Update `graph_editor.py` — save path (line 287–302)**

Replace (lines 287–302):

```python
        if entry.path is not None:
            # Already has a path — just overwrite it
            success = app.haystack.save_graph(entry)
            if success:
                ui.notify(f"Saved: {entry.path.name}", type="positive", position="top-right")
                self._update_header(context)
                # Notify all sessions viewing this graph so GraphManagerEditor
                # and other headers clear their dirty indicators.
                if hasattr(app, "session_manager"):
                    try:
                        app.session_manager.broadcast_data_mutation(graph_path=entry.path)
                    except Exception:
                        pass
            else:
                ui.notify("Save failed", type="negative", position="top-right")
            return
```

With:

```python
        if entry.path is not None:
            # Already has a path — just overwrite it
            success = app.haystack.save_graph(entry)
            if success:
                ui.notify(f"Saved: {entry.path.name}", type="positive", position="top-right")
                self._update_header(context)
                session = context.session
                if session is not None:
                    session.notify_cross_session_context_change(
                        ContextChangedEvent(
                            change_type=ContextChangeType.DATA_MUTATED,
                            source_editor="graph_editor",
                        )
                    )
            else:
                ui.notify("Save failed", type="negative", position="top-right")
            return
```

- [ ] **Step 4: Update `graph_editor.py` — save-as path (around line 439–455)**

Locate the save-as success block. Replace the broadcast call:

```python
            if session:
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                        source_editor="graph_editor",
                        detail=entry,
                    )
                )
            # Broadcast to all sessions so their GraphManagerEditor and header
            # also clear the dirty indicator.
            if hasattr(app, "session_manager"):
                try:
                    app.session_manager.broadcast_data_mutation(graph_path=save_path)
                except Exception:
                    pass
```

With:

```python
            if session:
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                        source_editor="graph_editor",
                        detail=entry,
                    )
                )
                session.notify_cross_session_context_change(
                    ContextChangedEvent(
                        change_type=ContextChangeType.DATA_MUTATED,
                        source_editor="graph_editor",
                    )
                )
```

(`ACTIVE_GRAPH_CHANGED` is legitimately local — it tells *this* session which tab to focus. `DATA_MUTATED` is cross-session.)

- [ ] **Step 5: Update `graph_editor.py` — cleanup (remove `session_detach` call)**

Replace the `cleanup` method body head (lines 463–477):

```python
    def cleanup(self) -> None:
        # Detach this session from its graph entry so the haystack can tell
        # when no session is still viewing the graph. Running here covers
        # both the close-× path (Slot calls cleanup during remove_binding)
        # and full-session teardown.
        context = self._context
        app = self._project_state
        if context is not None and app is not None and hasattr(app, "haystack"):
            entry = self._get_entry(context)
            if entry is not None and context.session is not None:
                try:
                    app.haystack.session_detach(entry, context.session.session_id)
                except Exception as exc:
                    logger.warning(f"GraphEditor.cleanup(): haystack detach failed: {exc}")

        if self._canvas_manager:
```

With:

```python
    def cleanup(self) -> None:
        if self._canvas_manager:
```

- [ ] **Step 6: Update `haystack_editor.py` — `_broadcast_mutation` helper (line 940–946)**

Edit `barn/haybale-studio/haybale_studio/editors/haystack_editor.py`.

Replace:

```python
    def _broadcast_mutation(self, app, entry: "GraphEntry") -> None:
        """Broadcast a DATA_MUTATED event to all sessions viewing this graph."""
        if hasattr(app, "session_manager"):
            try:
                app.session_manager.broadcast_data_mutation(graph_path=entry.path)
            except Exception:
                pass
```

With a delete of the helper entirely — nothing uses it after producer migration. Also search the file for `_broadcast_mutation(` calls and replace them with the proper cross-session notify at each call site. Use:

```bash
uv run python -c "import re; txt = open('barn/haybale-studio/haybale_studio/editors/haystack_editor.py').read(); print([i for i, l in enumerate(txt.splitlines(), 1) if '_broadcast_mutation' in l])"
```

to find exact lines before editing. Each call site becomes:

```python
        session = context.session
        if session is not None:
            session.notify_cross_session_context_change(
                ContextChangedEvent(
                    change_type=ContextChangeType.DATA_MUTATED,
                    source_editor="haystack",
                )
            )
```

If there are no call sites (the helper is dead), just delete the helper.

- [ ] **Step 7: Update `haystack_editor.py` — `_notify_data_mutated` (line 918–927)**

Replace:

```python
    def _notify_data_mutated(self, context: "SessionContext") -> None:
        """Fire DATA_MUTATED to refresh the graph list."""
        session = context.session
        if session:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.DATA_MUTATED,
                    source_editor="haystack",
                )
            )
```

With:

```python
    def _notify_data_mutated(self, context: "SessionContext") -> None:
        """Fire DATA_MUTATED to refresh the graph list across all sessions."""
        session = context.session
        if session:
            session.notify_cross_session_context_change(
                ContextChangedEvent(
                    change_type=ContextChangeType.DATA_MUTATED,
                    source_editor="haystack",
                )
            )
```

- [ ] **Step 8: Update `haystack_editor.py` — remove `session_detach` loop (line 328–330) and `session_id` arg on `create_new`**

Replace (around lines 325–333):

```python
        # Stop execution if running (defensive — should already be stopped)
        entry.stop_execution()

        # Detach all sessions
        for sid in list(entry.sessions):
            app.haystack.session_detach(entry, sid)

        # Remove from haystack
        app.haystack.remove_entry(entry)
```

With:

```python
        # Stop execution if running (defensive — should already be stopped)
        entry.stop_execution()

        # Remove from haystack
        app.haystack.remove_entry(entry)
```

Around line 603, replace:

```python
        entry = app.haystack.create_new(session.session_id)
```

With:

```python
        entry = app.haystack.create_new()
```

Around line 828, replace:

```python
                entry = app.haystack.open_graph(path, session.session_id)
```

With:

```python
                entry = app.haystack.open_graph(path)
```

- [ ] **Step 9: Update `file_browser.py` — drop `session_id` arg**

Edit `barn/haybale-studio/haybale_studio/editors/file_browser.py`.

Around line 175, replace:

```python
        entry = app.haystack.open_graph(path, session.session_id)
```

With:

```python
        entry = app.haystack.open_graph(path)
```

- [ ] **Step 10: Run smoke import check**

Run: `uv run python -c "from haybale_studio.editors.graph_editor import GraphEditor; from haybale_studio.editors.haystack_editor import HaystackEditor; from haybale_studio.editors.file_browser import FileBrowserEditor; print('ok')"`
Expected: `ok`

- [ ] **Step 11: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/graph_editor.py barn/haybale-studio/haybale_studio/editors/haystack_editor.py barn/haybale-studio/haybale_studio/editors/file_browser.py
git commit -m "refactor(editors): migrate producers to notify_cross_session_context_change"
```

---

## Task 6: Update `tests/studio/test_haystack.py`

**Files:**
- Modify: `tests/studio/test_haystack.py`

Rewrites fixtures for the new `Haystack` signature, drops tests for deleted features, adds new tests.

- [ ] **Step 1: Read the current test file**

Read the file to confirm line numbers and existing test names.

Run: `cat tests/studio/test_haystack.py | head -120`

- [ ] **Step 2: Rewrite fixtures and expectations**

Replace the entire test file with:

```python
"""Unit tests for Haystack entry lifecycle + validation wiring."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.ui.context_events import ContextChangeType
from haywire_studio.haystack import GraphEntry, Haystack


def _fake_factory():
    def _factory(graph_id: str, name: str):
        graph = BaseGraph(graph_id, name)
        editor = Editor(graph, node_factory=MagicMock(), undo_config=MagicMock())
        return graph, editor

    return _factory


def _make_haystack(tmp_path: Path, session_manager=None):
    return Haystack(
        workspace_root=tmp_path,
        graph_factory=_fake_factory(),
        session_manager=session_manager or MagicMock(),
    )


# --- create_new / open_graph ------------------------------------------------

def test_create_new_returns_entry(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)

    entry = haystack.create_new()

    assert isinstance(entry, GraphEntry)
    assert entry.path is None


def test_create_new_keys_each_entry_uniquely(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)

    a = haystack.create_new()
    b = haystack.create_new()

    assert a is not b
    assert a.key != b.key


def test_open_graph_reuses_entry_for_same_path(tmp_path: Path) -> None:
    path = tmp_path / "g.haywire"
    # Seed a valid graph file via BaseGraph.save_to_file
    seed = BaseGraph("seed", "seed")
    assert seed.save_to_file(str(path)) is True

    haystack = _make_haystack(tmp_path)

    first = haystack.open_graph(path)
    second = haystack.open_graph(path)

    assert first is second


# --- validation wiring ------------------------------------------------------

def test_new_entry_subscribes_validation_callback(tmp_path: Path) -> None:
    """Creating an entry wires its graph to Haystack._on_entry_validation."""
    haystack = _make_haystack(tmp_path)
    entry = haystack.create_new()

    # The graph should have at least one validation callback subscribed
    # (BaseGraph exposes this via internal bookkeeping — assert subscription
    # happened by firing a data-mutating validation and observing side effects).
    sm = haystack._session_manager
    # Construct a fake ValidationResult that flips the unsaved flag.
    result = MagicMock()
    result.nodes = [object()]  # truthy → data-mutating
    result.edges = []
    result.has_changes.return_value = True
    result.graph = None

    # Fire validation through the graph's normal subscription channel.
    # BaseGraph.subscribe_to_validation callbacks receive a ValidationResult
    # on each validation pass — invoke them via _on_entry_validation directly
    # rather than trying to drive the whole validation pipeline.
    haystack._on_entry_validation(entry, result)

    assert entry.unsaved is True
    sm.broadcast.assert_called_once()


def test_on_entry_validation_stops_execution_on_reassembly(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)
    entry = haystack.create_new()

    entry.stop_execution = MagicMock()
    # Simulate: execution is running
    entry.is_executing_mock = True
    type(entry).is_executing = property(lambda self: True)

    inner_graph = MagicMock()
    inner_graph.requires_graph_reassembly.return_value = True

    result = MagicMock()
    result.nodes = []
    result.edges = []
    result.has_changes.return_value = True
    result.graph = inner_graph

    haystack._on_entry_validation(entry, result)

    entry.stop_execution.assert_called_once()


def test_on_entry_validation_non_mutating_does_not_broadcast(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)
    entry = haystack.create_new()
    # create_new already broadcasts 0 times so far; reset the counter
    sm = haystack._session_manager
    sm.broadcast.reset_mock()

    result = MagicMock()
    result.nodes = []
    result.edges = []
    result.has_changes.return_value = False
    result.graph = None

    haystack._on_entry_validation(entry, result)

    assert entry.unsaved is False
    sm.broadcast.assert_not_called()


# --- removed signatures -----------------------------------------------------

def test_graph_entry_has_no_sessions_field(tmp_path: Path) -> None:
    """entry.sessions was deleted; accessing it should raise."""
    haystack = _make_haystack(tmp_path)
    entry = haystack.create_new()

    with pytest.raises(AttributeError):
        _ = entry.sessions


def test_haystack_has_no_session_attach(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)
    assert not hasattr(haystack, "session_attach")
    assert not hasattr(haystack, "session_detach")
    assert not hasattr(haystack, "sessions_for_entry")
```

**Note on `test_open_graph_reuses_entry_for_same_path`:** if `BaseGraph.load_from_file` rejects empty files, adjust the test to either write a minimal valid graph file or skip that test pending a proper fixture. The TDD discipline here is: *if the test can't be made to pass with a reasonable fixture in 5 minutes, mark it `@pytest.mark.skip(reason="needs BaseGraph.save_to_file seed fixture")` and open a follow-up — the rest of this file covers the refactor's actual semantics.*

- [ ] **Step 3: Run the updated tests**

Run: `uv run pytest tests/studio/test_haystack.py -v`
Expected: PASS (or the one `open_graph_reuses_entry` test skipped with a fixture note). All other tests in the file must pass.

- [ ] **Step 4: Commit**

```bash
git add tests/studio/test_haystack.py
git commit -m "test(haystack): rewrite for new signature, drop entry.sessions tests, add validation tests"
```

---

## Task 7: Fix `tests/studio/test_haystack_editor_remove.py`

**Files:**
- Modify: `tests/studio/test_haystack_editor_remove.py`

The existing `test_remove_entry_helper_fires_graph_removed` asserts `DATA_MUTATED` arrives via `context.session.notify_context_changed`. After migration, the producer calls `notify_cross_session_context_change` instead — so the assertion must either target that method OR the test fixture must wire `notify_cross_session_context_change` to also hit `notify_context_changed` (simulating fan-out).

The simpler, honest change: target `notify_cross_session_context_change` for the `DATA_MUTATED` assertion, keep `notify_context_changed` for `GRAPH_REMOVED` and `ACTIVE_GRAPH_CHANGED`.

- [ ] **Step 1: Update the `editor_and_context` fixture**

Edit `tests/studio/test_haystack_editor_remove.py` around lines 13–42:

Replace the fixture body to add `notify_cross_session_context_change` on the session mock, and drop the obsolete `haystack.session_detach`:

```python
@pytest.fixture
def editor_and_context():
    """Return (editor, context, app, haystack) with a real HaystackEditor."""
    from haybale_studio.editors.haystack_editor import HaystackEditor

    editor = HaystackEditor()
    haystack = MagicMock()
    haystack.save_graph = MagicMock(return_value=True)
    haystack.remove_entry = MagicMock(return_value=True)

    session = SimpleNamespace(
        session_id="sess-1",
        workspace_manager=None,
        notify_context_changed=MagicMock(),
        notify_cross_session_context_change=MagicMock(),
    )

    app = SimpleNamespace(
        haystack=haystack,
        workspace_root="/tmp/ws",
        session_manager=None,
    )

    context = SimpleNamespace(
        app=app,
        session=session,
        active_graph=None,
        active_graph_path=None,
    )
    return editor, context, app, haystack
```

- [ ] **Step 2: Drop `sessions` from `_make_entry`**

Around lines 45–56, replace:

```python
def _make_entry(path=None, unsaved: bool = False, is_executing: bool = False, key: str = "/tmp/a.haywire"):
    graph = object()
    return SimpleNamespace(
        graph=graph,
        path=path,
        unsaved=unsaved,
        is_executing=is_executing,
        sessions=set(),
        key=key,
        display_name="a.haywire",
        stop_execution=MagicMock(),
    )
```

With:

```python
def _make_entry(path=None, unsaved: bool = False, is_executing: bool = False, key: str = "/tmp/a.haywire"):
    graph = object()
    return SimpleNamespace(
        graph=graph,
        path=path,
        unsaved=unsaved,
        is_executing=is_executing,
        key=key,
        display_name="a.haywire",
        stop_execution=MagicMock(),
    )
```

- [ ] **Step 3: Fix `test_remove_entry_helper_fires_graph_removed`**

Around lines 107–118, replace:

```python
def test_remove_entry_helper_fires_graph_removed(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)

    with patch("haybale_studio.editors.haystack_editor.ui.notify"):
        editor._remove_entry(entry, context)

    event_types = [
        call.args[0].change_type for call in context.session.notify_context_changed.call_args_list
    ]
    assert ContextChangeType.GRAPH_REMOVED in event_types
    assert ContextChangeType.DATA_MUTATED in event_types
```

With:

```python
def test_remove_entry_helper_fires_graph_removed(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)

    with patch("haybale_studio.editors.haystack_editor.ui.notify"):
        editor._remove_entry(entry, context)

    local_event_types = [
        call.args[0].change_type for call in context.session.notify_context_changed.call_args_list
    ]
    cross_event_types = [
        call.args[0].change_type
        for call in context.session.notify_cross_session_context_change.call_args_list
    ]
    # GRAPH_REMOVED stays local — tells this session's shell to close the tab
    assert ContextChangeType.GRAPH_REMOVED in local_event_types
    # DATA_MUTATED is now cross-session — peer sessions refresh haystack list
    assert ContextChangeType.DATA_MUTATED in cross_event_types
```

- [ ] **Step 4: Run the updated tests**

Run: `uv run pytest tests/studio/test_haystack_editor_remove.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add tests/studio/test_haystack_editor_remove.py
git commit -m "test(haystack_editor): route DATA_MUTATED through cross-session channel"
```

---

## Task 8: Full test suite sweep

**Files:**
- Modify: any test file that breaks due to removed `broadcast_data_mutation`, `session_attach`, `validation_subscriber`, or `entry.sessions`.

This is a search-and-repair task. Expected survivors of the search: the four files modified in Tasks 6 and 7, plus possibly integration tests.

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest 2>&1 | tee /tmp/haywire-test-sweep.log`
Expected: A number of failures related to the refactored APIs.

- [ ] **Step 2: Search for remaining references to removed APIs**

Run:

```bash
uv run python - <<'PY'
import subprocess
patterns = [
    r"broadcast_data_mutation",
    r"validation_subscriber",
    r"session_attach",
    r"session_detach",
    r"entry\.sessions",
    r"sessions_for_entry",
]
for p in patterns:
    print(f"=== {p} ===")
    r = subprocess.run(
        ["grep", "-rn", "-E", p,
         "tests/", "packages/", "barn/"],
        capture_output=True, text=True,
    )
    print(r.stdout or "(no matches)")
PY
```

Expected: NO matches in `tests/`, `packages/`, or `barn/`. Any hits indicate missed migration sites — return to the relevant earlier task and fix.

(Matches in `internals/` are acceptable — those are historical design docs, not code.)

- [ ] **Step 3: Fix each failing test**

For each failure in `/tmp/haywire-test-sweep.log`:
- If it references a removed API: update to the new API per the pattern in Tasks 5–7.
- If it's a genuine regression: debug and fix.

- [ ] **Step 4: Re-run full suite**

Run: `uv run pytest`
Expected: all green.

- [ ] **Step 5: Run quality checks**

Run in parallel (or sequentially):

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/
```

Expected: all clean. If `ruff format --check` fails, run `uv run ruff format .` and re-commit.

- [ ] **Step 6: Commit any fixes made during sweep**

```bash
git add -A
git commit -m "test: finish cross-session channel migration test fixes"
```

(Skip this commit if no changes were needed in this task.)

---

## Task 9: Manual smoke test

**Files:** none modified.

- [ ] **Step 1: Launch the app**

Run: `uv run haywire`
Expected: app launches without exceptions.

- [ ] **Step 2: Open two browser tabs to the same URL**

Open two tabs on `http://localhost:8080` (or whatever port `haywire` reports). Open the same graph file in both.

- [ ] **Step 3: Verify cross-session propagation**

- In tab A, add a node. Expected: tab B's canvas shows the node (already worked via direct graph subscription). Tab B's haystack list / header updates its dirty indicator — this is the path that now goes through `notify_cross_session_context_change`.
- In tab A, save the graph. Expected: tab B's dirty indicator clears.
- In tab A, undo the node addition. Expected: tab B's canvas reverts and its dirty indicator updates. **This is new behavior** — before this refactor, undo/redo fired local-only.

- [ ] **Step 4: Verify no regressions**

- Selection in tab A does NOT move selection in tab B (SELECTION_CHANGED stays local).
- Workspace layout changes in tab A do NOT affect tab B.
- Execution start/stop in tab A correctly updates tab B's execution indicator (already worked pre-refactor).

- [ ] **Step 5: No commit needed — manual test only**

---

## Task 10: Delete the design spec's broadcast note

The class docstring in `haystack.py` had a now-incorrect comment:

> `broadcast_data_mutation() in SessionManager uses graph_path to selectively notify only the sessions that are viewing the changed graph.`

This was deleted as part of Task 3 (Step 4). Confirm by grep:

- [ ] **Step 1: Verify docstring is clean**

Run: `uv run python -c "import haywire_studio.haystack as h; assert 'broadcast_data_mutation' not in h.Haystack.__doc__, 'stale ref'"`
Expected: no `AssertionError`.

- [ ] **Step 2: Grep for any other stale mentions in source files**

Run:

```bash
uv run python - <<'PY'
import subprocess
r = subprocess.run(
    ["grep", "-rn", "broadcast_data_mutation",
     "packages/", "barn/", "tests/"],
    capture_output=True, text=True,
)
print(r.stdout or "CLEAN")
PY
```

Expected: `CLEAN`.

(Again, matches in `internals/` are acceptable — historical specs.)

- [ ] **Step 3: No commit needed — verification only**

---

## Acceptance criteria

- `uv run pytest` — all green
- `uv run ruff check .` — clean
- `uv run ruff format --check .` — clean
- `uv run mypy packages/haywire-core/src/` — clean
- Grep returns no matches outside `internals/` for: `broadcast_data_mutation`, `validation_subscriber`, `session_attach`, `session_detach`, `entry.sessions`, `sessions_for_entry`
- Manual smoke test (Task 9) passes
- All commits in order, each task is a single coherent commit
