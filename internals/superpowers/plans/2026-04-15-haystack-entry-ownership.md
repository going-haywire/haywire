# Haystack entry ownership + dirty-removal confirmation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move graph-entry creation onto `Haystack`, move tab orchestration onto `AppShell` via a new `OPEN_GRAPH_REQUESTED` event, and add a Save/Save-As/Discard/Cancel confirmation dialog when removing a dirty entry in `HaystackEditor`.

**Architecture:** Breaking refactor — three `HaywireApp` helper methods (`open_graph_file`, `create_new_graph`, `open_graph_in_tab`) get deleted. `Haystack` takes graph factory + validation subscriber at construction; callers pass `session_id`, not factory. `AppShell` handles the new `OPEN_GRAPH_REQUESTED` event to do the detach/attach/context-update dance that was on `HaywireApp`. `HaystackEditor._on_entry_delete` prompts before discarding unsaved work.

**Tech Stack:** Python 3.12+, NiceGUI, pytest. Follows existing haywire reactive-events + Popup patterns.

**Spec:** `internals/superpowers/specs/2026-04-15-haystack-entry-ownership-design.md` (commit `0e5d06e`).

---

## File Structure

**Modified:**

- `packages/haywire-studio/src/haywire_studio/haystack.py` — constructor signature tightened to require `workspace_root`, `graph_factory`, `validation_subscriber`; `open_graph` / `create_new` take `session_id` and do validation-subscribe + session-attach internally; delete `create_untitled` and `get_untitled`; `load_haystack` drops its factory arg; remove dead `workspace_root is None` branches in seven methods.
- `packages/haywire-studio/src/haywire_studio/app.py` — pass factory + subscriber when constructing `Haystack`; delete `open_graph_file`, `create_new_graph`, `open_graph_in_tab`; update `restore_persisted_tabs` to call `self.haystack.open_graph`.
- `packages/haywire-core/src/haywire/ui/context_events.py` — add `ContextChangeType.OPEN_GRAPH_REQUESTED`.
- `packages/haywire-core/src/haywire/ui/app/shell.py` — handle `OPEN_GRAPH_REQUESTED` in `_on_context_changed`; add `_handle_open_graph_requested` method.
- `barn/haybale-studio/haybale_studio/editors/haystack_editor.py` — callers use `haystack.open_graph` + `OPEN_GRAPH_REQUESTED`; `_on_entry_delete` prompts via new `_open_remove_confirm_dialog` on dirty entries; extract `_remove_entry` body; `_open_save_as_dialog` gains optional `on_success`.
- `barn/haybale-studio/haybale_studio/editors/file_browser.py` — caller uses `haystack.open_graph` + `OPEN_GRAPH_REQUESTED`.

**Created:**

- `tests/studio/__init__.py` — marker file.
- `tests/studio/test_haystack.py` — unit tests for the Haystack changes.

**Extended:**

- `tests/ui/test_app_shell.py` — tests for `OPEN_GRAPH_REQUESTED` handling.

---

## Task Order Rationale

Type dependencies flow from low-level to high-level:

1. **`context_events.py`** — introduces the new enum value first; nothing depends on it yet, so no breakage.
2. **`haystack.py`** — signature changes; compiles independently of callers.
3. **`app.py`** — updates construction, deletes helper methods, updates `restore_persisted_tabs`.
4. **`shell.py`** — adds handler for the new event type.
5. **`haystack_editor.py`** — updates 4 call sites, adds dirty-removal dialog, extracts `_remove_entry`.
6. **`file_browser.py`** — updates 1 call site.

Each task is independently committable only if callers still compile. Because this is a **breaking change across multiple files**, tasks 2-6 must be done back-to-back before the app can run again. The plan wraps them so that each intermediate commit leaves tests passing; only the smoke test at the end exercises the full flow.

---

## Task 1: Add the new event type

**Files:**

- Modify: `packages/haywire-core/src/haywire/ui/context_events.py`

- [ ] **Step 1: Add `OPEN_GRAPH_REQUESTED` to the enum**

In `packages/haywire-core/src/haywire/ui/context_events.py`, edit the `ContextChangeType` enum to insert a new value after `GRAPH_REMOVED`:

```python
class ContextChangeType(Enum):
    """What aspect of the context changed."""

    SELECTION_CHANGED = auto()  # node/edge selection changed
    ACTIVE_GRAPH_CHANGED = auto()  # switched to a different graph
    MODE_CHANGED = auto()  # interaction mode changed
    EDITOR_FOCUSED = auto()  # different editor gained focus
    WORKSPACE_CHANGED = auto()  # workspace preset switched
    DATA_MUTATED = auto()  # graph data changed (node values, structure)
    LIBRARY_STATE_CHANGED = auto()  # library enabled, disabled, installed, or selected
    ACTIVE_COMPONENT_CHANGED = auto()  # component (node/widget/renderer) selected in LibraryBrowser
    FILE_SELECTED = auto()  # file selected in FileBrowserEditor
    WORKBENCH_THEME_CHANGED = auto()  # active workbench theme switched
    CONTEXT_MENU_OPENED = auto()  # context menu popup was opened
    CONTEXT_MENU_CLOSED = auto()  # context menu popup was closed
    TAB_CLOSE_REQUESTED = auto()  # editor (or caller) is asking the shell to close a tab
    TAB_REPAYLOAD_REQUESTED = auto()  # re-key a tab after save-as / rename
    GRAPH_REMOVED = auto()  # a haystack entry was removed; shell closes matching tabs
    OPEN_GRAPH_REQUESTED = auto()  # caller asks AppShell to activate an entry + reveal its tab
    CUSTOM = auto()  # extensible
```

- [ ] **Step 2: Verify the package still imports**

Run: `uv run python -c "from haywire.ui.context_events import ContextChangeType; print(ContextChangeType.OPEN_GRAPH_REQUESTED)"`
Expected: `ContextChangeType.OPEN_GRAPH_REQUESTED`

- [ ] **Step 3: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/context_events.py
git commit -m "feat: add OPEN_GRAPH_REQUESTED context-change event"
```

---

## Task 2: Tighten Haystack construction signature

Covers: required-args constructor + dead-code cleanup of `workspace_root is None` branches. Internal only — no behaviour change at call sites yet.

**Files:**

- Modify: `packages/haywire-studio/src/haywire_studio/haystack.py` (lines 127-130, 346-357, 374-376, 441-443, 490-492, 528-530, 538-539)

- [ ] **Step 1: Tighten the constructor**

Replace the `__init__` block around line 127:

```python
    def __init__(
        self,
        workspace_root: Path,
        graph_factory: GraphFactory,
        validation_subscriber: "ValidationSubscriber",
    ):
        self._entries: Dict[str, GraphEntry] = {}
        self._new_counter: int = 0
        self._workspace_root: Path = workspace_root
        self._graph_factory: GraphFactory = graph_factory
        self._validation_subscriber: "ValidationSubscriber" = validation_subscriber
```

- [ ] **Step 2: Add the `ValidationSubscriber` type alias near `GraphFactory`**

Around line 47, alongside `GraphFactory`:

```python
# Factory signature: (graph_id: str, name: str) -> (BaseGraph, Editor)
GraphFactory = Callable[[str, str], Tuple[Any, Any]]

# Subscriber signature: called once per newly-created GraphEntry
ValidationSubscriber = Callable[["GraphEntry"], None]
```

- [ ] **Step 3: Remove dead `workspace_root is None` branches**

In `_haystacks_dir` (line 346) — change return type and drop the None guard:

```python
    def _haystacks_dir(self) -> Path:
        """Return the haystacks/ directory."""
        return self._workspace_root / "haystacks"
```

In `list_haystacks` (line 352) — drop the `hdir is None or` clause, keep the `.is_dir()` check:

```python
    def list_haystacks(self) -> List[str]:
        """Return sorted list of available haystack names (without extension)."""
        hdir = self._haystacks_dir()
        if not hdir.is_dir():
            return []
        return sorted(p.stem for p in hdir.glob("*.toml"))
```

In `save_haystack` (line 374) — drop the `hdir is None: raise RuntimeError` block:

```python
        hdir = self._haystacks_dir()
        hdir.mkdir(parents=True, exist_ok=True)
        filepath = hdir / f"{name}.toml"
```

In `load_haystack` (line 441) — drop the `hdir is None: raise RuntimeError` block:

```python
        hdir = self._haystacks_dir()
        filepath = hdir / f"{name}.toml"
        if not filepath.exists():
            raise FileNotFoundError(f"Haystack not found: {filepath}")
```

In `rename_haystack` (line 490) — drop the `hdir is None: return False` guard:

```python
        hdir = self._haystacks_dir()
        old_path = hdir / f"{old_name}.toml"
        new_path = hdir / f"{new_name}.toml"
```

In `list_graph_files` (line 528) — drop the `if self._workspace_root is None: return []` guard:

```python
    def list_graph_files(self) -> List[Path]:
        """Scan the graphs/ folder for all .haywire files."""
        graphs_dir = self._workspace_root / "graphs"
        if not graphs_dir.is_dir():
            return []
        return sorted(p for p in graphs_dir.rglob("*.haywire") if p.is_file())
```

In `delete_haystack` (line 535) — drop the `hdir is None: return False` guard:

```python
    def delete_haystack(self, name: str) -> bool:
        """Delete a haystack file. Returns True if removed."""
        hdir = self._haystacks_dir()
        filepath = hdir / f"{name}.toml"
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Haystack deleted: {filepath}")
            return True
        return False
```

- [ ] **Step 4: Run lint + type check**

Run: `uv run ruff check packages/haywire-studio/src/haywire_studio/haystack.py && uv run mypy packages/haywire-core/src/`
Expected: no errors. (Callers of `Haystack()` in `app.py` still pass `workspace_root` by keyword so they remain valid; subsequent tasks add the two new required args.)

**Note:** If mypy reports "Haystack missing positional args" on `app.py:147` that is expected — Task 3 fixes it. You can skip mypy for now and re-run after Task 3.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/haystack.py
git commit -m "refactor(haystack): require workspace_root, add callback types, drop dead branches"
```

---

## Task 3: Move entry creation + session attachment into Haystack

Changes `open_graph` / `create_new` to take `session_id`, fold in validation-subscribe + session-attach. Delete `create_untitled` and `get_untitled`. `load_haystack` drops its factory arg.

**Files:**

- Modify: `packages/haywire-studio/src/haywire_studio/haystack.py`

- [ ] **Step 1: Update the module docstring**

Replace the `Usage in app.py` example at the top of `haystack.py` (lines 12-29):

```python
"""
Haystack — file-centric multi-graph registry.

Each .haywire file gets its own GraphEntry (graph + editor). Two sessions
opening the same file share the same entry and collaborate in real time.

Haystack support: the current set of open graphs can be saved to / loaded
from a TOML file in the ``haystacks/`` folder at the workspace root.

Usage in app.py::

    haystack = Haystack(
        workspace_root=Path(...),
        graph_factory=app._graph_factory,
        validation_subscriber=app._subscribe_entry_validation,
    )

    # When a file is opened:
    entry = haystack.open_graph(path, session_id)

    # When the user creates a new unnamed graph:
    entry = haystack.create_new(session_id)

    # On save:
    haystack.save_graph(entry)

    # Save/load haystacks:
    haystack.save_haystack("default")
    haystack.load_haystack("default")

    # On session disconnect:
    haystack.session_detach(entry, session_id)
"""
```

- [ ] **Step 2: Replace `create_untitled` with nothing; delete `get_untitled`**

Delete the `create_untitled` method (lines 136-151) entirely. Delete `get_untitled` (lines 289-291) entirely.

- [ ] **Step 3: Rewrite `create_new`**

Replace `create_new` (currently lines 153-173):

```python
    def create_new(self, session_id: str) -> GraphEntry:
        """
        Create a new unnamed graph, subscribe validation, attach a session.

        Each call produces a fresh entry keyed as ``'__new_1__'``, ``'__new_2__'``, …
        and named ``'Untitled 1'``, ``'Untitled 2'``, …

        Args:
            session_id: Session to attach the new entry to.

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
        self.session_attach(entry, session_id)
        return entry
```

- [ ] **Step 4: Rewrite `open_graph`**

Replace `open_graph` (currently lines 175-200):

```python
    def open_graph(self, path: Path, session_id: str) -> GraphEntry:
        """
        Open a .haywire file, reusing the existing entry if already loaded.

        On first-time open, subscribes the validation callback. Always
        attaches the given session before returning.

        Args:
            path: Absolute path to the .haywire file.
            session_id: Session to attach the entry to.

        Returns:
            The (existing or newly-loaded) GraphEntry.
        """
        key = str(path)
        entry = self._entries.get(key)
        if entry is None:
            graph, editor = self._graph_factory(path.stem, str(path))
            graph.load_from_file(str(path))
            # Flush any deferred NODE_ADDED/EDGE_ADDED validation events that
            # load_from_file queues. This must happen BEFORE the entry is created
            # and before any validation handler is subscribed, so that those events
            # don't fire later and incorrectly mark the freshly loaded graph as unsaved.
            graph.force_validation()
            entry = GraphEntry(graph=graph, editor=editor, path=path)
            self._entries[key] = entry
            self._validation_subscriber(entry)
        self.session_attach(entry, session_id)
        return entry
```

- [ ] **Step 5: Update `load_haystack` signature**

Replace `load_haystack` (currently starts at line 418). Change the signature, docstring, and use the internal factory + subscriber:

```python
    def load_haystack(
        self,
        name: str,
    ) -> Tuple[List[GraphEntry], Optional[str]]:
        """
        Load a haystack file, replacing all current entries.

        Stops execution on all current entries, clears the registry,
        then opens each graph listed in the haystack. Graphs marked with
        ``execute = true`` are started automatically. Each freshly-opened
        entry has the validation subscriber invoked.

        Args:
            name: Haystack name (filename stem in haystacks/).

        Returns:
            Tuple of (list of opened GraphEntry instances,
            relative path of the active graph or None).

        Raises:
            FileNotFoundError: If the haystack file does not exist.
        """
        hdir = self._haystacks_dir()
        filepath = hdir / f"{name}.toml"
        if not filepath.exists():
            raise FileNotFoundError(f"Haystack not found: {filepath}")

        data = toml.loads(filepath.read_text())
        haystack_meta = data.get("haystack", {})
        active_graph_rel = haystack_meta.get("active_graph")
        graphs_data = data.get("graphs", [])

        # Stop execution and clear all current entries
        self._stop_all_execution()
        self._entries.clear()
        self._new_counter = 0

        # Open each graph — we reuse the entry-creation core by inlining it
        # (we don't need session_attach here; callers attach sessions later
        # via the AppShell reveal flow). Validation subscriber IS invoked.
        opened: List[GraphEntry] = []
        for gd in graphs_data:
            rel_path = gd.get("path")
            if not rel_path:
                continue
            abs_path = self._workspace_root / rel_path
            if not abs_path.exists():
                logger.warning(f"Haystack: skipping missing graph file: {abs_path}")
                continue

            key = str(abs_path)
            graph, editor = self._graph_factory(abs_path.stem, str(abs_path))
            graph.load_from_file(str(abs_path))
            graph.force_validation()
            entry = GraphEntry(graph=graph, editor=editor, path=abs_path)
            self._entries[key] = entry
            self._validation_subscriber(entry)
            opened.append(entry)

            if gd.get("execute", False):
                entry.start_execution()

        logger.info(f"Haystack loaded: {filepath} ({len(opened)}/{len(graphs_data)} graphs)")
        return opened, active_graph_rel
```

Rationale for inlining over calling `open_graph(abs_path, session_id)`: `load_haystack` has no session context. Calling `open_graph` would require inventing a fake session_id or adding an optional param — both worse than a five-line inline.

- [ ] **Step 6: Lint**

Run: `uv run ruff check packages/haywire-studio/src/haywire_studio/haystack.py`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/haystack.py
git commit -m "refactor(haystack): session_id on open_graph/create_new; drop factory from load_haystack"
```

---

## Task 4: Haystack unit tests

Add focused tests covering the new Haystack API contract before rewiring callers.

**Files:**

- Create: `tests/studio/__init__.py`
- Create: `tests/studio/test_haystack.py`

- [ ] **Step 1: Create the test directory marker**

Create `tests/studio/__init__.py` as an empty file:

```python
```

- [ ] **Step 2: Write the failing test file**

Create `tests/studio/test_haystack.py`:

```python
"""Unit tests for Haystack entry ownership + session attachment."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Import order: editor first to avoid circular imports, per CLAUDE.md.
import haywire.core.graph.editor  # noqa: F401

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire_studio.haystack import GraphEntry, Haystack


def _fake_factory():
    """Return a factory that creates real BaseGraph + Editor pairs."""

    def _factory(graph_id: str, name: str):
        graph = BaseGraph(graph_id, name)
        editor = Editor(graph, node_factory=MagicMock(), undo_config=MagicMock())
        return graph, editor

    return _factory


def _make_haystack(tmp_path: Path, subscriber=None):
    return Haystack(
        workspace_root=tmp_path,
        graph_factory=_fake_factory(),
        validation_subscriber=subscriber or (lambda entry: None),
    )


def test_create_new_calls_validation_subscriber(tmp_path: Path) -> None:
    sub = MagicMock()
    haystack = _make_haystack(tmp_path, subscriber=sub)

    entry = haystack.create_new(session_id="sess-1")

    assert sub.call_count == 1
    assert sub.call_args.args[0] is entry


def test_create_new_attaches_session(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)

    entry = haystack.create_new(session_id="sess-1")

    assert "sess-1" in entry.sessions


def test_create_new_unique_keys(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)

    a = haystack.create_new(session_id="sess-1")
    b = haystack.create_new(session_id="sess-1")

    assert a.key != b.key
    assert a.key == "__new_1__"
    assert b.key == "__new_2__"


def test_open_graph_first_time_calls_validation_subscriber(tmp_path: Path) -> None:
    sub = MagicMock()
    haystack = _make_haystack(tmp_path, subscriber=sub)

    # Pre-create a .haywire file by saving an empty graph.
    path = tmp_path / "foo.haywire"
    prep = BaseGraph("foo", str(path))
    prep.save_to_file(str(path))

    entry = haystack.open_graph(path, session_id="sess-1")

    assert sub.call_count == 1
    assert sub.call_args.args[0] is entry


def test_open_graph_reuse_does_not_resubscribe(tmp_path: Path) -> None:
    sub = MagicMock()
    haystack = _make_haystack(tmp_path, subscriber=sub)

    path = tmp_path / "foo.haywire"
    BaseGraph("foo", str(path)).save_to_file(str(path))

    first = haystack.open_graph(path, session_id="sess-1")
    second = haystack.open_graph(path, session_id="sess-2")

    assert first is second
    assert sub.call_count == 1


def test_open_graph_multiple_sessions_share_entry(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)

    path = tmp_path / "foo.haywire"
    BaseGraph("foo", str(path)).save_to_file(str(path))

    haystack.open_graph(path, session_id="sess-a")
    entry = haystack.open_graph(path, session_id="sess-b")

    assert entry.sessions == {"sess-a", "sess-b"}


def test_load_haystack_signature_no_factory(tmp_path: Path) -> None:
    """load_haystack now takes only the name; factory is internal."""
    haystack = _make_haystack(tmp_path)

    # Prepare a graph file and a haystack TOML referencing it.
    graphs_dir = tmp_path / "graphs"
    graphs_dir.mkdir()
    graph_path = graphs_dir / "foo.haywire"
    BaseGraph("foo", str(graph_path)).save_to_file(str(graph_path))

    haystacks_dir = tmp_path / "haystacks"
    haystacks_dir.mkdir()
    (haystacks_dir / "default.toml").write_text(
        '[haystack]\nname = "default"\n\n'
        '[[graphs]]\npath = "graphs/foo.haywire"\nexecute = false\n'
    )

    entries, active = haystack.load_haystack("default")

    assert len(entries) == 1
    assert entries[0].path == graph_path
    assert active is None


def test_load_haystack_subscribes_each_entry(tmp_path: Path) -> None:
    sub = MagicMock()
    haystack = _make_haystack(tmp_path, subscriber=sub)

    graphs_dir = tmp_path / "graphs"
    graphs_dir.mkdir()
    for name in ("a", "b"):
        p = graphs_dir / f"{name}.haywire"
        BaseGraph(name, str(p)).save_to_file(str(p))

    haystacks_dir = tmp_path / "haystacks"
    haystacks_dir.mkdir()
    (haystacks_dir / "default.toml").write_text(
        '[haystack]\nname = "default"\n\n'
        '[[graphs]]\npath = "graphs/a.haywire"\nexecute = false\n'
        '[[graphs]]\npath = "graphs/b.haywire"\nexecute = false\n'
    )

    entries, _ = haystack.load_haystack("default")

    assert len(entries) == 2
    assert sub.call_count == 2
```

- [ ] **Step 3: Run the tests — they should fail because Haystack callers (app.py) are still broken**

Run: `uv run pytest tests/studio/test_haystack.py -v`
Expected: the tests themselves should PASS (they exercise Haystack directly, not app.py). If any fail, read the failure message and fix the test file against what Task 2 + 3 produced.

- [ ] **Step 4: Commit**

```bash
git add tests/studio/__init__.py tests/studio/test_haystack.py
git commit -m "test(haystack): cover session attachment, subscriber, load_haystack signature"
```

---

## Task 5: Rewire HaywireApp construction and drop the three helpers

Pass callbacks to `Haystack()`, delete `open_graph_file` / `create_new_graph` / `open_graph_in_tab`, update `restore_persisted_tabs`.

**Files:**

- Modify: `packages/haywire-studio/src/haywire_studio/app.py`

- [ ] **Step 1: Update Haystack construction in `setup_shared_services`**

Replace the block around line 143-147:

```python
        # Graph manager — starts empty; graphs are created/opened on demand.
        # Haystack auto-load happens after workspace_manager is available (in main_page).
        from .haystack import Haystack

        self.haystack = Haystack(
            workspace_root=Path(self.workspace_root),
            graph_factory=self._graph_factory,
            validation_subscriber=self._subscribe_entry_validation,
        )
```

- [ ] **Step 2: Delete `open_graph_file` and `create_new_graph`**

Delete lines 161-190 (the block starting with `# ---…  Graph management (called by editors) ---…` down through the end of `create_new_graph`). Keep the separator comment bar that followed if it stands alone.

- [ ] **Step 3: Delete `open_graph_in_tab`**

Delete the block from line 192 (`# ---…  Multi-instance tab orchestration ---…`) through the end of `open_graph_in_tab` (ends around line 249). Remove both the section-header comment bar and the method body.

- [ ] **Step 4: Update `restore_persisted_tabs` to call `haystack.open_graph`**

In `restore_persisted_tabs` around line 328, replace:

```python
                self.open_graph_file(path, session_id)
```

with:

```python
                self.haystack.open_graph(path, session_id)
```

- [ ] **Step 5: Update the try_load_startup_haystack loader to drop factory arg**

In `try_load_startup_haystack` around line 293, replace:

```python
            self.haystack.load_haystack(haystack_name, self._graph_factory)
            # Subscribe validation handlers for each loaded entry
            for entry in self.haystack.all_entries().values():
                self._subscribe_entry_validation(entry)
```

with:

```python
            self.haystack.load_haystack(haystack_name)
```

(The subscriber is now called inside `load_haystack`, so the for-loop is redundant.)

- [ ] **Step 6: Update the section comment for `_graph_factory`**

Around line 264, update the banner comment to remove the now-deleted method names:

```python
    # ------------------------------------------------------------------
    # Graph factory (shared by Haystack)
    # ------------------------------------------------------------------
```

- [ ] **Step 7: Lint and type-check**

Run: `uv run ruff check packages/haywire-studio/src/haywire_studio/app.py`
Expected: no errors.

Run: `uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/`
Expected: no new errors in `app.py` or `haystack.py`. Existing mypy warnings elsewhere are preserved.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/app.py
git commit -m "refactor(app): inject callbacks into Haystack; delete three helper methods"
```

---

## Task 6: AppShell handler for OPEN_GRAPH_REQUESTED

Add the handler method; wire it into the existing `_on_context_changed` dispatcher.

**Files:**

- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py`

- [ ] **Step 1: Add the dispatcher branch**

In `_on_context_changed` around line 958-965, add the new branch next to the existing ones. Replace:

```python
    def _on_context_changed(self, event: ContextChangedEvent, context: "SessionContext") -> None:
        """Orchestrator callback: run the poll/draw cycle on every managed slot."""
        if event.change_type == ContextChangeType.TAB_CLOSE_REQUESTED:
            self._handle_tab_close_requested(event)
        elif event.change_type == ContextChangeType.TAB_REPAYLOAD_REQUESTED:
            self._handle_tab_repayload_requested(event)
        elif event.change_type == ContextChangeType.GRAPH_REMOVED:
            self._handle_graph_removed(event)
```

with:

```python
    def _on_context_changed(self, event: ContextChangedEvent, context: "SessionContext") -> None:
        """Orchestrator callback: run the poll/draw cycle on every managed slot."""
        if event.change_type == ContextChangeType.TAB_CLOSE_REQUESTED:
            self._handle_tab_close_requested(event)
        elif event.change_type == ContextChangeType.TAB_REPAYLOAD_REQUESTED:
            self._handle_tab_repayload_requested(event)
        elif event.change_type == ContextChangeType.GRAPH_REMOVED:
            self._handle_graph_removed(event)
        elif event.change_type == ContextChangeType.OPEN_GRAPH_REQUESTED:
            self._handle_open_graph_requested(event)
```

- [ ] **Step 2: Add the handler method**

Add `_handle_open_graph_requested` as a new method on `AppShell`, placed next to the other `_handle_*` methods (e.g. right after `_handle_graph_removed`). Use the surrounding methods' style:

```python
    def _handle_open_graph_requested(self, event: ContextChangedEvent) -> None:
        """Activate ``event.detail`` (a GraphEntry) in the session and reveal its tab.

        Does the detach/attach/context-update dance that used to live on
        ``HaywireApp.open_graph_in_tab``, then fires ``ACTIVE_GRAPH_CHANGED``
        with reveal fields so the main slot opens (or focuses) the right tab.
        """
        entry = event.detail
        editor_key = event.reveal_editor
        if entry is None or editor_key is None:
            logger.warning(
                "OPEN_GRAPH_REQUESTED dropped: missing detail=%r or reveal_editor=%r",
                entry,
                editor_key,
            )
            return

        context = self.session.context
        haystack = context.app.haystack

        # Detach from previous active entry (if any, and different)
        if context.active_graph_path is not None:
            prev_entry = haystack.get_by_path(context.active_graph_path)
        elif context.active_graph is not None:
            prev_entry = haystack.get_by_graph(context.active_graph)
        else:
            prev_entry = None
        if prev_entry is not None and prev_entry is not entry:
            haystack.session_detach(prev_entry, self.session.session_id)

        # Attach to target (idempotent)
        haystack.session_attach(entry, self.session.session_id)

        # Update context
        context.active_graph = entry.graph
        context.active_graph_path = entry.path

        # Fire ACTIVE_GRAPH_CHANGED with reveal fields — this triggers the tab reveal.
        self.session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                source_editor="app_shell",
                detail=entry,
                reveal_editor=editor_key,
                reveal_payload=entry.key,
                reveal_label=entry.display_name,
            )
        )
```

If `shell.py` does not already import `logger` / `logging`, confirm the file's existing logger by searching its top-level imports; the module already has a logger per convention (grep for `logger = logging.getLogger` in the file if unsure). Use the same logger.

- [ ] **Step 3: Lint and type-check**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/app/shell.py`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/shell.py
git commit -m "feat(shell): handle OPEN_GRAPH_REQUESTED with detach/attach/reveal"
```

---

## Task 7: AppShell handler tests

Extend `tests/ui/test_app_shell.py` with tests for the new handler.

**Files:**

- Modify: `tests/ui/test_app_shell.py`

- [ ] **Step 1: Add helper classes and tests at the end of the file**

Append to `tests/ui/test_app_shell.py`:

```python
# ---------------------------------------------------------------------------
# OPEN_GRAPH_REQUESTED handler tests
# ---------------------------------------------------------------------------


class _FakeEntry:
    """Minimal GraphEntry stand-in."""

    def __init__(self, key: str, graph, path=None, display_name: str = "Entry") -> None:
        self.key = key
        self.graph = graph
        self.path = path
        self.display_name = display_name


class _FakeHaystack:
    """Records detach/attach and supports lookup by path or graph."""

    def __init__(self) -> None:
        self.attached: list[tuple[object, str]] = []
        self.detached: list[tuple[object, str]] = []
        self._by_path: dict[object, _FakeEntry] = {}
        self._by_graph: dict[object, _FakeEntry] = {}

    def register(self, entry: _FakeEntry) -> None:
        if entry.path is not None:
            self._by_path[entry.path] = entry
        self._by_graph[entry.graph] = entry

    def session_attach(self, entry, session_id: str) -> None:
        self.attached.append((entry, session_id))

    def session_detach(self, entry, session_id: str) -> None:
        self.detached.append((entry, session_id))

    def get_by_path(self, path):
        return self._by_path.get(path)

    def get_by_graph(self, graph):
        return self._by_graph.get(graph)


def _make_shell_for_open_graph(prev_entry=None, target_entry=None):
    """Return (shell, session) wired for open-graph-requested testing."""
    from haywire.ui.app.shell import AppShell

    haystack = _FakeHaystack()
    if prev_entry is not None:
        haystack.register(prev_entry)
    if target_entry is not None:
        haystack.register(target_entry)

    app = SimpleNamespace(haystack=haystack)
    context = SimpleNamespace(
        app=app,
        active_graph=prev_entry.graph if prev_entry else None,
        active_graph_path=prev_entry.path if prev_entry else None,
        session=None,  # set below
    )

    session = _FakeSession()
    session.session_id = "sess-1"
    session.context = context
    context.session = session

    # AppShell has a lot of setup; we only need the handler, so instantiate bare.
    shell = AppShell.__new__(AppShell)
    shell.session = session
    return shell, session, haystack


def test_open_graph_requested_attaches_target_entry() -> None:
    target = _FakeEntry(key="/tmp/a.haywire", graph=object(), path="/tmp/a.haywire")
    shell, session, haystack = _make_shell_for_open_graph(target_entry=target)

    shell._handle_open_graph_requested(
        ContextChangedEvent(
            change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
            detail=target,
            reveal_editor="editor.key",
        )
    )

    assert (target, "sess-1") in haystack.attached


def test_open_graph_requested_detaches_previous_entry() -> None:
    prev = _FakeEntry(key="/tmp/prev.haywire", graph=object(), path="/tmp/prev.haywire")
    target = _FakeEntry(key="/tmp/next.haywire", graph=object(), path="/tmp/next.haywire")
    shell, session, haystack = _make_shell_for_open_graph(prev_entry=prev, target_entry=target)

    shell._handle_open_graph_requested(
        ContextChangedEvent(
            change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
            detail=target,
            reveal_editor="editor.key",
        )
    )

    assert (prev, "sess-1") in haystack.detached


def test_open_graph_requested_same_entry_does_not_detach() -> None:
    same = _FakeEntry(key="/tmp/a.haywire", graph=object(), path="/tmp/a.haywire")
    shell, session, haystack = _make_shell_for_open_graph(prev_entry=same, target_entry=same)

    shell._handle_open_graph_requested(
        ContextChangedEvent(
            change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
            detail=same,
            reveal_editor="editor.key",
        )
    )

    assert haystack.detached == []


def test_open_graph_requested_updates_context() -> None:
    target = _FakeEntry(key="/tmp/a.haywire", graph=object(), path="/tmp/a.haywire")
    shell, session, _ = _make_shell_for_open_graph(target_entry=target)

    shell._handle_open_graph_requested(
        ContextChangedEvent(
            change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
            detail=target,
            reveal_editor="editor.key",
        )
    )

    assert session.context.active_graph is target.graph
    assert session.context.active_graph_path == target.path


def test_open_graph_requested_fires_active_graph_changed() -> None:
    target = _FakeEntry(
        key="/tmp/a.haywire",
        graph=object(),
        path="/tmp/a.haywire",
        display_name="a.haywire",
    )
    shell, session, _ = _make_shell_for_open_graph(target_entry=target)

    shell._handle_open_graph_requested(
        ContextChangedEvent(
            change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
            detail=target,
            reveal_editor="editor.key",
        )
    )

    assert len(session.notified_events) == 1
    downstream = session.notified_events[0]
    assert downstream.change_type == ContextChangeType.ACTIVE_GRAPH_CHANGED
    assert downstream.reveal_editor == "editor.key"
    assert downstream.reveal_payload == target.key
    assert downstream.reveal_label == target.display_name
    assert downstream.detail is target


def test_open_graph_requested_null_detail_is_noop() -> None:
    shell, session, haystack = _make_shell_for_open_graph()

    shell._handle_open_graph_requested(
        ContextChangedEvent(
            change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
            detail=None,
            reveal_editor="editor.key",
        )
    )

    assert haystack.attached == []
    assert haystack.detached == []
    assert session.notified_events == []
```

- [ ] **Step 2: Run the new tests**

Run: `uv run pytest tests/ui/test_app_shell.py -v -k open_graph_requested`
Expected: 6 PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/ui/test_app_shell.py
git commit -m "test(shell): cover OPEN_GRAPH_REQUESTED handler"
```

---

## Task 8: Rewire HaystackEditor call sites to the new pattern

Update the 4 call sites in `haystack_editor.py` that used `app.open_graph_file` / `create_new_graph` / `open_graph_in_tab`. No UI behaviour change yet.

**Files:**

- Modify: `barn/haybale-studio/haybale_studio/editors/haystack_editor.py`

- [ ] **Step 1: Update `_on_new` (currently lines 513-522)**

Replace the method body:

```python
    def _on_new(self, context: "SessionContext") -> None:
        """Create a new unnamed graph and activate it."""
        app: IProjectState = context.app
        session = context.session
        if app is None or session is None or not hasattr(app, "haystack"):
            return

        entry = app.haystack.create_new(session.session_id)
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
                source_editor="haystack",
                detail=entry,
                reveal_editor=_GRAPH_EDITOR_KEY,
            )
        )
```

- [ ] **Step 2: Update `_on_select` (currently lines 524-530)**

Replace:

```python
    def _on_select(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Activate an existing graph entry."""
        session = context.session
        if session is None:
            return
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
                source_editor="haystack",
                detail=entry,
                reveal_editor=_GRAPH_EDITOR_KEY,
            )
        )
```

- [ ] **Step 3: Update `_on_load_haystack` to drop factory arg and use OPEN_GRAPH_REQUESTED**

In `_on_load_haystack`, around line 635-655, replace the inner `_do_load` function:

```python
            def _do_load():
                name = haystack_select.value
                entries, active_rel = gm.load_haystack(name)

                active_entry = None
                if active_rel:
                    ws_root = Path(app.workspace_root)
                    active_entry = gm.get_by_path(ws_root / active_rel)
                if active_entry is None and entries:
                    active_entry = entries[0]

                session = context.session
                if session and session.workspace_manager:
                    session.workspace_manager.active.haystack = name
                    session.workspace_manager.save()

                self._notify_data_mutated(context)
                if active_entry is not None and session is not None:
                    session.notify_context_changed(
                        ContextChangedEvent(
                            change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
                            source_editor="haystack",
                            detail=active_entry,
                            reveal_editor=_GRAPH_EDITOR_KEY,
                        )
                    )

                self._update_header_title(context)
                ui.notify(f"Haystack '{name}' loaded", type="positive")
                popup.close()
```

Note: the `for entry in entries: app._subscribe_entry_validation(entry)` loop is gone — `load_haystack` now subscribes internally.

- [ ] **Step 4: Update `_on_open_graph` `_do_open` (currently lines 715-731)**

Replace `_do_open`:

```python
            def _do_open():
                selected = graph_select.value
                if not selected or selected not in options:
                    ui.notify("Please select a graph file", type="warning")
                    return

                path = options[selected]
                session = context.session
                if session is None or not hasattr(app, "haystack"):
                    ui.notify("Graph manager not available", type="warning")
                    popup.close()
                    return

                entry = app.haystack.open_graph(path, session.session_id)
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
                        source_editor="haystack",
                        detail=entry,
                        reveal_editor=_GRAPH_EDITOR_KEY,
                    )
                )
                ui.notify(f"Opened: {path.name}", type="positive", position="top-right")
                popup.close()
```

- [ ] **Step 5: Update docstring references**

Around line 71, replace the docstring line:

```
    The "+" header button calls app.create_new_graph() and immediately
    activates the freshly created entry.
```

with:

```
    The "+" header button calls app.haystack.create_new() and fires
    OPEN_GRAPH_REQUESTED to activate the freshly created entry.
```

- [ ] **Step 6: Lint**

Run: `uv run ruff check barn/haybale-studio/haybale_studio/editors/haystack_editor.py`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/haystack_editor.py
git commit -m "refactor(haystack_editor): use new Haystack API + OPEN_GRAPH_REQUESTED"
```

---

## Task 9: Rewire FileBrowser call site

**Files:**

- Modify: `barn/haybale-studio/haybale_studio/editors/file_browser.py`

- [ ] **Step 1: Update `_open_graph_file`**

Replace the method (currently lines 166-180):

```python
    def _open_graph_file(self, path: Path, context: "SessionContext") -> None:
        """Load a .haywire graph file and open its graph editor tab."""
        from haybale_studio.editors.graph_editor import GraphEditor

        app: "HaywireApp" = context.app
        session = context.session
        if app is None or session is None or not hasattr(app, "haystack"):
            return

        entry = app.haystack.open_graph(path, session.session_id)
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
                source_editor="file_browser",
                detail=entry,
                reveal_editor=GraphEditor.class_identity.registry_key,
            )
        )
```

- [ ] **Step 2: Lint**

Run: `uv run ruff check barn/haybale-studio/haybale_studio/editors/file_browser.py`
Expected: no errors.

- [ ] **Step 3: Run the full non-integration test suite**

Run: `uv run pytest -m "not integration" --tb=short`
Expected: all tests pass. This confirms the structural refactor is self-consistent.

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/file_browser.py
git commit -m "refactor(file_browser): use Haystack.open_graph + OPEN_GRAPH_REQUESTED"
```

---

## Task 10: Extend `_open_save_as_dialog` with optional `on_success` callback

Supports the chained save-as-then-remove flow in the dirty-removal dialog.

**Files:**

- Modify: `barn/haybale-studio/haybale_studio/editors/haystack_editor.py`

- [ ] **Step 1: Update the signature and success path**

In `_open_save_as_dialog` around line 420, update the signature:

```python
    def _open_save_as_dialog(
        self,
        app,
        entry: "GraphEntry",
        context: "SessionContext",
        on_success: "Optional[Callable[[], None]]" = None,
    ) -> None:
```

Inside `_do_save_as`, at the end of the success branch (right before `popup.close()` inside the `if success:` block), call the callback:

```python
                if success:
                    if entry.graph is context.active_graph:
                        context.active_graph_path = save_path
                        session = context.session
                        if session:
                            session.notify_context_changed(
                                ContextChangedEvent(
                                    change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                                    source_editor="haystack",
                                    detail=entry,
                                )
                            )
                    self._broadcast_mutation(app, entry)
                    ui.notify(f"Saved: {save_path.name}", type="positive", position="top-right")
                    popup.close()
                    if on_success is not None:
                        on_success()
                else:
                    ui.notify("Save failed — check the path and try again", type="negative")
```

- [ ] **Step 2: Add `Callable` to the imports**

Near the top of `haystack_editor.py`, update:

```python
from typing import TYPE_CHECKING, Optional
```

to:

```python
from typing import TYPE_CHECKING, Callable, Optional
```

- [ ] **Step 3: Lint**

Run: `uv run ruff check barn/haybale-studio/haybale_studio/editors/haystack_editor.py`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/haystack_editor.py
git commit -m "refactor(haystack_editor): add on_success callback to _open_save_as_dialog"
```

---

## Task 11: Extract `_remove_entry` from `_on_entry_delete`

Splits the current `_on_entry_delete` body so both the clean-entry branch and the future dirty-confirmation branch can share the teardown logic.

**Files:**

- Modify: `barn/haybale-studio/haybale_studio/editors/haystack_editor.py`

- [ ] **Step 1: Extract `_remove_entry`**

Replace the current `_on_entry_delete` method (lines 297-344) with two methods — the entry point and the extracted body:

```python
    def _on_entry_delete(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Remove a graph entry from the haystack (does not delete the file)."""
        if entry.is_executing:
            ui.notify("Stop execution before removing", type="warning")
            return
        app = context.app
        if app is None or not hasattr(app, "haystack"):
            ui.notify("Graph manager not available", type="warning")
            return
        self._remove_entry(entry, context)

    def _remove_entry(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Tear down a graph entry: stop execution, detach sessions, remove, notify.

        Pre-condition: ``entry`` is not executing and the haystack is available.
        Callers are responsible for the ``is_executing`` / ``hasattr`` guards
        and for any dirty-state confirmation flow before invoking this.
        """
        app = context.app
        is_active = entry.graph is context.active_graph
        removed_key = entry.key  # capture before remove_entry re-keys / drops

        # Stop execution if running (defensive — should already be stopped)
        entry.stop_execution()

        # Detach all sessions
        for sid in list(entry.sessions):
            app.haystack.session_detach(entry, sid)

        # Remove from haystack
        app.haystack.remove_entry(entry)

        session = context.session
        # Ask the shell to close any tab hosting this entry.
        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.GRAPH_REMOVED,
                    source_editor="haystack",
                    detail=removed_key,
                )
            )

        # If it was the active graph, clear the active graph → empty state
        if is_active:
            context.active_graph = None
            context.active_graph_path = None
            if session:
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                        source_editor="haystack",
                    )
                )

        ui.notify(f"Removed: {entry.display_name}", type="info", position="top-right")
        self._notify_data_mutated(context)
```

- [ ] **Step 2: Run the full non-integration test suite**

Run: `uv run pytest -m "not integration" --tb=short`
Expected: all pass (pure extraction — no behavioural change).

- [ ] **Step 3: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/haystack_editor.py
git commit -m "refactor(haystack_editor): extract _remove_entry from _on_entry_delete"
```

---

## Task 12: Add the dirty-removal confirmation dialog

**Files:**

- Modify: `barn/haybale-studio/haybale_studio/editors/haystack_editor.py`

- [ ] **Step 1: Update `_on_entry_delete` to branch on dirtiness**

Replace the current `_on_entry_delete` body with:

```python
    def _on_entry_delete(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Remove a graph entry; prompt for dirty entries before discarding."""
        if entry.is_executing:
            ui.notify("Stop execution before removing", type="warning")
            return
        app = context.app
        if app is None or not hasattr(app, "haystack"):
            ui.notify("Graph manager not available", type="warning")
            return

        is_dirty = entry.unsaved or entry.path is None
        if not is_dirty:
            self._remove_entry(entry, context)
            return

        self._open_remove_confirm_dialog(entry, context)
```

- [ ] **Step 2: Add the dialog method**

Add `_open_remove_confirm_dialog` as a new method, placed next to the other dialog methods (e.g. right before `_open_rename_dialog`):

```python
    def _open_remove_confirm_dialog(
        self, entry: "GraphEntry", context: "SessionContext"
    ) -> None:
        """Confirm before removing a dirty entry.

        For file-backed + modified entries: Save / Save As… / Discard / Cancel.
        For unnamed entries (``path is None``): Save As… / Discard / Cancel
        (no plain Save — there is no target file).
        """
        app = context.app
        can_save_in_place = entry.path is not None

        popup = Popup(
            title="Remove graph?",
            width="400px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
        )
        with popup:
            if can_save_in_place:
                msg = f'"{entry.display_name}" has unsaved changes.'
            else:
                msg = "This graph has never been saved."
            ui.label(msg).classes("text-sm")
            ui.label("What would you like to do?").classes("text-sm hw-text-dim")

            def _save_and_remove():
                success = app.haystack.save_graph(entry)
                if success:
                    self._broadcast_mutation(app, entry)
                    self._remove_entry(entry, context)
                    popup.close()
                else:
                    ui.notify("Save failed", type="negative", position="top-right")

            def _save_as_and_remove():
                popup.close()
                self._open_save_as_dialog(
                    app,
                    entry,
                    context,
                    on_success=lambda: self._remove_entry(entry, context),
                )

            def _discard_and_remove():
                self._remove_entry(entry, context)
                popup.close()

            with ui.row().classes("w-full justify-end gap-2 mt-3"):
                ui.button("Cancel", on_click=popup.close).props("flat dense")
                ui.button("Discard", on_click=_discard_and_remove).props(
                    "flat dense color=negative"
                )
                ui.button("Save As…", on_click=_save_as_and_remove).props("dense")
                if can_save_in_place:
                    ui.button("Save", on_click=_save_and_remove).props(
                        "color=positive dense"
                    )

        popup.open()
```

- [ ] **Step 3: Lint**

Run: `uv run ruff check barn/haybale-studio/haybale_studio/editors/haystack_editor.py`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/haystack_editor.py
git commit -m "feat(haystack_editor): confirm before discarding dirty entries"
```

---

## Task 13: Tests for dirty-removal confirmation

Unit-test the branching and dialog-button wiring. The Popup is opaque in tests, so we test the method-level branches by calling `_on_entry_delete` and `_open_remove_confirm_dialog` directly and asserting on the state changes they produce.

**Files:**

- Create: `tests/studio/test_haystack_editor_remove.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for HaystackEditor dirty-removal confirmation flow."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import haywire.core.graph.editor  # noqa: F401 -- circular-import guard

from haywire.ui.context_events import ContextChangeType


@pytest.fixture
def editor_and_context():
    """Return (editor, context, app, haystack) with a real HaystackEditor."""
    from haybale_studio.editors.haystack_editor import HaystackEditor

    editor = HaystackEditor()
    haystack = MagicMock()
    haystack.save_graph = MagicMock(return_value=True)
    haystack.remove_entry = MagicMock(return_value=True)
    haystack.session_detach = MagicMock()

    session = SimpleNamespace(
        session_id="sess-1",
        workspace_manager=None,
        notify_context_changed=MagicMock(),
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


def test_remove_clean_entry_skips_dialog_and_removes(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)

    with patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog:
        editor._on_entry_delete(entry, context)

    mock_dialog.assert_not_called()
    haystack.remove_entry.assert_called_once_with(entry)


def test_remove_dirty_file_backed_entry_opens_dialog(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=True)

    with patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog:
        editor._on_entry_delete(entry, context)

    mock_dialog.assert_called_once_with(entry, context)
    haystack.remove_entry.assert_not_called()


def test_remove_untitled_entry_opens_dialog(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path=None, unsaved=False)

    with patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog:
        editor._on_entry_delete(entry, context)

    mock_dialog.assert_called_once_with(entry, context)


def test_remove_executing_entry_blocked_before_dialog(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=True, is_executing=True)

    with patch.object(editor, "_open_remove_confirm_dialog") as mock_dialog, \
         patch("haybale_studio.editors.haystack_editor.ui.notify") as mock_notify:
        editor._on_entry_delete(entry, context)

    mock_dialog.assert_not_called()
    haystack.remove_entry.assert_not_called()
    # The guard message should have been shown
    assert any("Stop execution" in str(c) for c in mock_notify.call_args_list)


def test_remove_entry_helper_fires_graph_removed(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)

    with patch("haybale_studio.editors.haystack_editor.ui.notify"):
        editor._remove_entry(entry, context)

    event_types = [
        call.args[0].change_type
        for call in context.session.notify_context_changed.call_args_list
    ]
    assert ContextChangeType.GRAPH_REMOVED in event_types
    assert ContextChangeType.DATA_MUTATED in event_types


def test_remove_entry_helper_clears_active_graph_when_active(editor_and_context):
    editor, context, app, haystack = editor_and_context
    entry = _make_entry(path="/tmp/a.haywire", unsaved=False)
    # Mark this entry as the active one
    context.active_graph = entry.graph
    context.active_graph_path = entry.path

    with patch("haybale_studio.editors.haystack_editor.ui.notify"):
        editor._remove_entry(entry, context)

    assert context.active_graph is None
    assert context.active_graph_path is None
    event_types = [
        call.args[0].change_type
        for call in context.session.notify_context_changed.call_args_list
    ]
    assert ContextChangeType.ACTIVE_GRAPH_CHANGED in event_types
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/studio/test_haystack_editor_remove.py -v`
Expected: 6 PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/studio/test_haystack_editor_remove.py
git commit -m "test(haystack_editor): cover dirty-removal branching and _remove_entry helper"
```

---

## Task 14: Full suite + smoke test

**Files:** none — verification only.

- [ ] **Step 1: Run the full fast test suite**

Run: `uv run pytest -m "not integration" --tb=short`
Expected: all tests pass, including the new `tests/studio/` tests and the extended `tests/ui/test_app_shell.py`.

- [ ] **Step 2: Run the integration tests**

Run: `uv run pytest -m integration --tb=short`
Expected: all tests pass. (This is slower; run once per refactor, not after every task.)

- [ ] **Step 3: Manual smoke test — open, modify, remove with dialog**

Start the app:

```bash
uv run haywire
```

Then in the browser:

1. Double-click a `.haywire` file in the FileBrowser → tab opens, graph renders.
2. Drag a node on the canvas → dirty dot appears on the HaystackEditor row.
3. Click the row's overflow menu → Remove.
4. Expected: Popup appears with title "Remove graph?", buttons Cancel / Discard / Save As… / Save.
5. Click **Save** → popup closes, tab closes, entry gone from HaystackEditor, file contents updated on disk.
6. Repeat steps 1–3 with an unsaved **new** graph (use `+ New Graph`).
7. Expected: Popup message reads "This graph has never been saved." with buttons Cancel / Discard / Save As… (no Save).
8. Click **Discard** → popup closes, tab closes, entry gone.

- [ ] **Step 4: Manual smoke test — clean removal bypasses dialog**

1. Open a `.haywire` file (do not modify).
2. Overflow menu → Remove.
3. Expected: no popup; entry disappears immediately (today's behaviour preserved for clean entries).

- [ ] **Step 5: Manual smoke test — event path via FileBrowser**

1. Fully close the app.
2. Relaunch `uv run haywire`.
3. Click a `.haywire` file in the FileBrowser.
4. Expected: graph opens in a tab. Confirms `OPEN_GRAPH_REQUESTED` routes through AppShell.

- [ ] **Step 6: Commit — nothing to commit (verification only)**

If the smoke tests surface any issue, fix in a follow-up commit. Otherwise this task ends with no code changes.

---

## Done

After Task 14, the branch contains one self-contained series of commits implementing the spec:

1. `feat: add OPEN_GRAPH_REQUESTED context-change event`
2. `refactor(haystack): require workspace_root, add callback types, drop dead branches`
3. `refactor(haystack): session_id on open_graph/create_new; drop factory from load_haystack`
4. `test(haystack): cover session attachment, subscriber, load_haystack signature`
5. `refactor(app): inject callbacks into Haystack; delete three helper methods`
6. `feat(shell): handle OPEN_GRAPH_REQUESTED with detach/attach/reveal`
7. `test(shell): cover OPEN_GRAPH_REQUESTED handler`
8. `refactor(haystack_editor): use new Haystack API + OPEN_GRAPH_REQUESTED`
9. `refactor(file_browser): use Haystack.open_graph + OPEN_GRAPH_REQUESTED`
10. `refactor(haystack_editor): add on_success callback to _open_save_as_dialog`
11. `refactor(haystack_editor): extract _remove_entry from _on_entry_delete`
12. `feat(haystack_editor): confirm before discarding dirty entries`
13. `test(haystack_editor): cover dirty-removal branching and _remove_entry helper`

The breaking change is self-contained: every commit between 2 and 9 leaves the unit tests passing; the app itself only becomes runnable again after task 9.
