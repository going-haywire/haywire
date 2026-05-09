# PR 2: Haystack Carve-Out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract Haystack functionality from `haywire-studio` into a new `haybale-haystack` library. The current `Haystack` class becomes `HaystackState(AppState)` (in-memory entry registry), `HaystackSettings(LibrarySettings)` (per-workspace scalars: `last_haystack_name`, `new_counter`), and free functions in `persistence.py` (per-haystack TOML I/O). `HaystackEditor` and `GraphEditor` move from `haybale-studio` into `haybale-haystack`. A new "Open in Haystack" file-context-menu panel registers against the `FileFocus` infrastructure built in PR 1.

**Architecture:** The new library follows the standard barn pattern (entry-point + `register_components()`). `HaystackState.on_enable()` resolves `SessionManager`, `workspace_root`, and `node_factory` from ambient DI globals (Q5C, Q13A, Q14A); subscribes to per-entry validation events and broadcasts `GraphDataMutated` directly via `SessionManager` (no editor or library-bridge intermediary). On startup, `on_enable` reads `HaystackSettings.last_haystack_name` and rehydrates from `<workspace_root>/haystacks/<name>.toml`, restarting interpreters for entries flagged `execute=true` (Q9B). Persistence is split: scalars live in `LibrarySettings` (workspace tier — Q15A); per-haystack entry lists live in dedicated TOML files manipulated by free functions in `persistence.py` (Q4D). `IProjectState.haystack` is dropped; consumers migrate to `ctx.app_data[HaystackState]`. `GraphEditor` moves with `HaystackState` because the coupling is deep (Q12B); the deeper restructure to "graph editor independent of any specific manager" is deferred until a second graph-management library exists.

**Tech Stack:** Python 3.12, NiceGUI/Quasar, `pytest`, the haywire library system (entry-points + folder scanning).

**Prerequisites:** PR 1 must be merged. PR 1 provides:
- `haywire.core.session.session_manager.SessionManager` (and the ambient `get_session_manager()`)
- `haywire.core.di.context.get_workspace_root()`
- `FileBrowserState`, `FileFocus`, `FileBrowserActions`, `SessionFileMenuProvider` (the file context menu infrastructure)
- The shell-upstream disconnect flow (no impact on this PR but a stability prerequisite)

---

## File Structure

### Files created

```
barn/haybale-haystack/
├── pyproject.toml
├── haybale_haystack/
│   ├── __init__.py                  # Library entry point + register_components()
│   ├── state/
│   │   ├── __init__.py
│   │   └── haystack_state.py        # HaystackState(AppState)
│   ├── settings/
│   │   ├── __init__.py
│   │   └── haystack_settings.py     # HaystackSettings(LibrarySettings)
│   ├── persistence.py               # Free functions: dump_haystack, load_haystack, list_haystacks, etc.
│   ├── graph_entry.py               # GraphEntry dataclass (moved from haystack.py)
│   ├── editors/
│   │   ├── __init__.py
│   │   ├── graph_editor.py          # MOVED from barn/haybale-studio/haybale_studio/editors/graph_editor.py
│   │   └── haystack_editor.py       # MOVED from barn/haybale-studio/haybale_studio/editors/haystack_editor.py
│   └── panels/
│       ├── __init__.py
│       └── open_in_haystack.py      # File-context-menu panel
└── tests/
    ├── __init__.py
    ├── test_haystack_state.py
    ├── test_haystack_settings.py
    ├── test_persistence.py
    └── test_open_in_haystack_panel.py
```

### Files modified

- `pyproject.toml` (workspace root) — add `haybale-haystack` to `[tool.uv.workspace]` members
- `packages/haywire-studio/src/haywire_studio/app.py` — remove direct `Haystack` instantiation (lines ~140–145), remove `try_load_startup_haystack` (~177), remove `save_workspace` haystack save (~190–200); remove the `haystack` attribute on `HaywireApp`
- `packages/haywire-core/src/haywire/core/session/protocols.py` — drop `haystack: IGraphManager` from `IProjectState`; consider dropping `IGraphManager` entirely
- `barn/haybale-studio/haybale_studio/editors/file_browser.py` — delete `_open_graph_file()` method and the `if ext in self._GRAPH_EXTS` branch in `_on_select`
- `barn/haybale-studio/haybale_studio/editors/__init__.py` — drop `graph_editor` / `haystack_editor` exports
- `barn/haybale-studio/haybale_studio/editors/graph_canvas/handlers/context_menu.py` and `barn/haybale-studio/haybale_studio/panels/context_menu/node_actions.py` — verify nothing references `app.haystack`; update if so
- `packages/haywire-studio/src/haywire_studio/haystack.py` — DELETED
- `barn/haybale-studio/haybale_studio/editors/graph_editor.py` — DELETED (moved)
- `barn/haybale-studio/haybale_studio/editors/haystack_editor.py` — DELETED (moved)

### Test files

- `barn/haybale-haystack/tests/test_haystack_state.py`
- `barn/haybale-haystack/tests/test_haystack_settings.py`
- `barn/haybale-haystack/tests/test_persistence.py`
- `barn/haybale-haystack/tests/test_open_in_haystack_panel.py`
- `tests/integration/test_haystack_carve_out.py` — end-to-end: load haystack on startup, restart execute=true graphs, confirm UI shows them

---

## Phase 1 — Scaffold the new library

### Task 1: Create `barn/haybale-haystack/` package skeleton

**Files:**
- Create: `barn/haybale-haystack/pyproject.toml`
- Create: `barn/haybale-haystack/haybale_haystack/__init__.py`
- Create: empty subdirectories: `state/`, `settings/`, `editors/`, `panels/`, `tests/`
- Modify: `pyproject.toml` (workspace root)

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p barn/haybale-haystack/haybale_haystack/state \
         barn/haybale-haystack/haybale_haystack/settings \
         barn/haybale-haystack/haybale_haystack/editors \
         barn/haybale-haystack/haybale_haystack/panels \
         barn/haybale-haystack/tests
touch barn/haybale-haystack/haybale_haystack/state/__init__.py \
      barn/haybale-haystack/haybale_haystack/settings/__init__.py \
      barn/haybale-haystack/haybale_haystack/editors/__init__.py \
      barn/haybale-haystack/haybale_haystack/panels/__init__.py \
      barn/haybale-haystack/tests/__init__.py
```

- [ ] **Step 2: Create `pyproject.toml`**

Create `barn/haybale-haystack/pyproject.toml`:

```toml
[project]
name = "haybale-haystack"
version = "0.1.0"
description = "Haystack — file-centric multi-graph manager for Haywire"
requires-python = ">=3.10"
license = {text = "MIT"}

dependencies = [
    "haywire-core>=0.1.0",
    "haywire-studio>=0.1.0",
    "haybale-core>=0.1.0",
    "haybale-studio>=0.1.0",
]

[project.entry-points."haywire.libraries"]
haystack = "haybale_haystack:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["haybale_haystack"]

[tool.uv.sources]
haywire-core = { workspace = true }
haywire-studio = { workspace = true }
haybale-core = { workspace = true }
haybale-studio = { workspace = true }
```

- [ ] **Step 3: Create the entry-point library class**

Create `barn/haybale-haystack/haybale_haystack/__init__.py`:

```python
"""Haybale-Haystack: file-centric multi-graph manager.

Provides:
  - HaystackState (AppState): in-memory registry of open graphs.
  - HaystackSettings (LibrarySettings): per-workspace persistence of
    last_haystack_name and new_counter.
  - persistence module: free functions for per-haystack TOML I/O.
  - GraphEditor and HaystackEditor: UI surfaces.
  - "Open in Haystack" file-context-menu panel.

Intended as ONE possible graph-management library for Haywire. Future
libraries may provide alternative managers; haybale-haystack does not
claim exclusive ownership of GraphEditor.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.state import LibraryStateRegistry

from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.panel.registry import PanelRegistry


@library(
    label="Haystack",
    id="haystack",
    version="0.1.0",
    description="File-centric multi-graph manager",
    url="",
    help_url="",
    author="",
    author_url="",
    dependencies=["haybale_core", "haybale_studio"],
    tags=["graph-management"],
    file_watcher=True,
)
class Library(BaseLibrary):
    """Haystack library — file-centric graph management."""

    def register_components(self):
        base_path = Path(__file__).parent

        # state/ first (panels/editors transitively import it)
        self.add_folder_to_registry(
            folder_path=str(base_path / "state"),
            registry_cls=LibraryStateRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "settings"),
            registry_cls=SettingsRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "panels"),
            registry_cls=PanelRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "editors"),
            registry_cls=EditorTypeRegistry,
        )

    def validate(self) -> bool:
        return True
```

- [ ] **Step 4: Add the new package to the workspace**

Open the root `pyproject.toml`. Find the `[tool.uv.workspace]` section (likely with `members = [...]`). Add `"barn/haybale-haystack"` to the members list, preserving alphabetical order if present.

- [ ] **Step 5: Sync the workspace**

Run: `uv sync`
Expected: dependency resolution succeeds; `haybale-haystack` shows up as installed.

- [ ] **Step 6: Verify the library is discoverable but currently empty**

Run: `uv run python -c "from haybale_haystack import Library; print(Library)"`
Expected: `<class 'haybale_haystack.Library'>`.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-haystack/ pyproject.toml
git commit -m "feat(haystack): scaffold haybale-haystack library

Empty package with entry point, library class, and folder structure.
Subsequent commits add HaystackState, HaystackSettings, editors, and panels."
```

---

## Phase 2 — Build the persistence layer FIRST (no dependencies on UI)

### Task 2: Move `GraphEntry` dataclass to the new library

**Files:**
- Create: `barn/haybale-haystack/haybale_haystack/graph_entry.py`
- Test: `barn/haybale-haystack/tests/test_graph_entry.py`

`GraphEntry` is the tiny dataclass currently inside `packages/haywire-studio/src/haywire_studio/haystack.py` ([haystack.py:60–127](packages/haywire-studio/src/haywire_studio/haystack.py#L60)). It carries a graph, an editor, an optional file path, an unsaved flag, an interpreter, and validation-related fields. It needs to come over verbatim (with imports adjusted).

- [ ] **Step 1: Read the current `GraphEntry` definition**

Inspect `packages/haywire-studio/src/haywire_studio/haystack.py:60–127`. Note the fields and methods (`entry_id`, `display_name`, `is_executing`, `start_execution`, `stop_execution`).

- [ ] **Step 2: Write a failing test for `GraphEntry` in the new location**

Create `barn/haybale-haystack/tests/test_graph_entry.py`:

```python
"""GraphEntry — dataclass tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_graph_entry_default_unsaved():
    from haybale_haystack.graph_entry import GraphEntry
    g = MagicMock()
    e = MagicMock()
    entry = GraphEntry(graph=g, editor=e, path=None, unsaved=True)
    assert entry.unsaved is True
    assert entry.path is None
    assert entry.interpreter is None


def test_entry_id_uses_path_when_set():
    from haybale_haystack.graph_entry import GraphEntry
    p = Path("/tmp/foo.haywire")
    entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=p, unsaved=False)
    assert entry.entry_id == str(p)


def test_entry_id_uses_synthetic_for_unsaved():
    from haybale_haystack.graph_entry import GraphEntry
    g = MagicMock()
    g.name = "MyGraph"
    entry = GraphEntry(graph=g, editor=MagicMock(), path=None, unsaved=True)
    # __unsaved__ pattern — verify by checking it doesn't equal a real path
    assert "__unsaved__" in entry.entry_id or "__new__" in entry.entry_id


def test_display_name_uses_path_stem_when_set():
    from haybale_haystack.graph_entry import GraphEntry
    entry = GraphEntry(
        graph=MagicMock(), editor=MagicMock(),
        path=Path("/tmp/MyName.haywire"), unsaved=False,
    )
    assert entry.display_name == "MyName"
```

- [ ] **Step 3: Run the test**

Run: `uv run pytest barn/haybale-haystack/tests/test_graph_entry.py -v`
Expected: ImportError on `haybale_haystack.graph_entry`.

- [ ] **Step 4: Copy the `GraphEntry` class to the new location**

Read `packages/haywire-studio/src/haywire_studio/haystack.py:36-127` to get the full GraphEntry definition. Create `barn/haybale-haystack/haybale_haystack/graph_entry.py`:

```python
"""GraphEntry — one open graph in a Haystack.

Carries the graph object, its editor, optional file path, dirty flag,
and an optional Interpreter when execution is running. Validation
subscriptions are managed by HaystackState (not GraphEntry).

Moved from haywire-studio's haystack.py during the haybale-haystack
carve-out.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from haywire.core.graph.base_graph import BaseGraph
    from haywire.core.graph.editor import Editor
    from haywire.core.execution.interpreter import Interpreter

logger = logging.getLogger(__name__)


@dataclass
class GraphEntry:
    """One graph open in a Haystack.

    Fields:
        graph: BaseGraph — the in-memory graph object.
        editor: Editor — the wrapper providing edit operations on `graph`.
        path: Optional[Path] — file path on disk; None for never-saved.
        unsaved: bool — True if dirty since last save (or never saved).
        interpreter: Optional[Interpreter] — present iff execution is running.
    """

    graph: "BaseGraph"
    editor: "Editor"
    path: Optional[Path] = None
    unsaved: bool = True
    interpreter: Optional["Interpreter"] = field(default=None, repr=False)

    @property
    def entry_id(self) -> str:
        """Stable string identifier — file path if saved, synthetic otherwise."""
        if self.path is not None:
            return str(self.path)
        # Synthetic for never-saved graphs; uses graph.id which is stable
        # within the lifetime of this Haystack instance.
        return f"__unsaved__:{self.graph.id}"

    @property
    def display_name(self) -> str:
        """Human-readable label for this entry."""
        if self.path is not None:
            return self.path.stem
        return getattr(self.graph, "name", None) or "Untitled"

    @property
    def is_executing(self) -> bool:
        """True iff this entry's interpreter is currently executing."""
        return self.interpreter is not None and self.interpreter.is_executing

    def start_execution(self) -> None:
        """Construct and start an Interpreter for this entry."""
        from haywire.core.execution.interpreter import Interpreter
        from haywire.core.di.context import get_settings_registry
        from haywire.core.state import LibraryStateContainer
        # The interpreter needs the LibraryStateContainer; get it via DI ambient
        # context. (NodeFactory and SettingsRegistry come via the same channel
        # in the underlying Interpreter constructor.)
        # NOTE: This mirrors today's pattern — the original Haystack passed
        # library_state_container to Interpreter explicitly. Here we read
        # it from ambient context.
        from haywire.core.di.context_extra import get_library_state_container  # see Task 6
        container = get_library_state_container()
        self.interpreter = Interpreter(library_state_container=container)
        self.interpreter.load_graph(self.graph)
        self.interpreter.start_execution()
        logger.info(f"Execution started for graph '{self.display_name}'")

    def stop_execution(self) -> None:
        """Stop the interpreter (if any) and drop the reference."""
        if self.interpreter is None:
            return
        try:
            self.interpreter.stop_execution()
        except Exception as e:
            logger.warning(f"Error stopping execution on '{self.display_name}': {e}")
        self.interpreter = None
        logger.info(f"Execution stopped for graph '{self.display_name}'")
```

**Note on `get_library_state_container`:** the original `Haystack` constructor took `library_state_container` from `HaywireApp` directly. To mirror this without coupling `GraphEntry` to studio, we need an ambient getter. This is added in **Task 6** (extending the DI context). For now, write the import as `from haywire.core.di.context_extra import get_library_state_container` (will resolve once Task 6 lands). To unblock testing of `GraphEntry` itself, the test mocks `start_execution` rather than calling it directly.

- [ ] **Step 5: Run the test**

Run: `uv run pytest barn/haybale-haystack/tests/test_graph_entry.py -v`
Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/graph_entry.py \
        barn/haybale-haystack/tests/test_graph_entry.py
git commit -m "feat(haystack): add GraphEntry dataclass to haybale-haystack

Carries graph, editor, path, unsaved flag, and optional Interpreter.
entry_id and display_name properties match the legacy Haystack
behavior. Execution methods reference an ambient
LibraryStateContainer getter added in a later task."
```

---

### Task 3: Add `get_library_state_container` ambient global

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/di/context.py`
- Modify: `packages/haywire-core/src/haywire/core/di/config.py` — call setter from `provide_library_state_container`
- Test: `tests/core/test_di/test_library_state_container_global.py`

`HaystackState.on_enable` needs `LibraryStateContainer` to construct interpreters. Same pattern as `set_session_manager` from PR 1.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_di/test_library_state_container_global.py`:

```python
"""Test the ambient LibraryStateContainer getter."""

from unittest.mock import MagicMock

import pytest


def test_get_raises_before_set():
    import haywire.core.di.context as ctx_mod
    ctx_mod._library_state_container = None
    from haywire.core.di.context import get_library_state_container
    with pytest.raises(RuntimeError, match="LibraryStateContainer not set"):
        get_library_state_container()


def test_set_then_get():
    from haywire.core.di.context import set_library_state_container, get_library_state_container
    container = MagicMock()
    set_library_state_container(container)
    assert get_library_state_container() is container
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `uv run pytest tests/core/test_di/test_library_state_container_global.py -v`
Expected: ImportError.

- [ ] **Step 3: Add the slot/setter/getter to `core/di/context.py`**

In `packages/haywire-core/src/haywire/core/di/context.py`:

In the TYPE_CHECKING block:
```python
    from haywire.core.state import LibraryStateContainer
```

After `_workspace_root: Optional[Path] = None`:
```python
_library_state_container: Optional["LibraryStateContainer"] = None
```

In the setters section:
```python
def set_library_state_container(container: "LibraryStateContainer") -> None:
    global _library_state_container
    _library_state_container = container
```

In the getters section:
```python
def get_library_state_container() -> "LibraryStateContainer":
    if _library_state_container is None:
        raise RuntimeError(
            "LibraryStateContainer not set in ambient context. "
            "Ensure HaywireApp has been initialised before requesting it."
        )
    return _library_state_container
```

- [ ] **Step 4: Wire the ambient setter in `provide_library_state_container`**

In `packages/haywire-core/src/haywire/core/di/config.py`, find `provide_library_state_container` (around line 183). Update:

```python
@provider
@singleton
def provide_library_state_container(self) -> LibraryStateContainer:
    """Provide singleton LibraryStateContainer — instance pool for LibraryStates.

    Subscription to LibraryStateRegistry events is wired in
    LibrarySystemService.initialize().

    Also publishes via set_library_state_container() so AppState authors
    can read it from ambient context (e.g. for constructing Interpreters).
    """
    container = LibraryStateContainer()
    set_library_state_container(container)  # NEW
    return container
```

Add `set_library_state_container` to the import block at the top:
```python
from haywire.core.di.context import (
    set_node_factory,
    set_adapter_factory,
    set_type_registry,
    set_settings_registry,
    set_session_manager,
    set_library_state_container,  # NEW
)
```

- [ ] **Step 5: Update `GraphEntry` to use the actual import path**

In `barn/haybale-haystack/haybale_haystack/graph_entry.py`, change:
```python
from haywire.core.di.context_extra import get_library_state_container  # see Task 6
```
to:
```python
from haywire.core.di.context import get_library_state_container
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/core/test_di/test_library_state_container_global.py barn/haybale-haystack/tests/test_graph_entry.py -v`
Expected: all pass.

- [ ] **Step 7: Run the full unit suite to confirm `provide_library_state_container` change doesn't break anything**

Run: `uv run pytest -m "not integration" -q`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-core/src/haywire/core/di/context.py \
        packages/haywire-core/src/haywire/core/di/config.py \
        barn/haybale-haystack/haybale_haystack/graph_entry.py \
        tests/core/test_di/test_library_state_container_global.py
git commit -m "feat(di): add LibraryStateContainer ambient global

provide_library_state_container() now also calls set_library_state_container()
so AppState authors can read the container from ambient context (e.g.
to construct Interpreters)."
```

---

### Task 4: Implement `persistence.py` (free functions for TOML I/O)

**Files:**
- Create: `barn/haybale-haystack/haybale_haystack/persistence.py`
- Test: `barn/haybale-haystack/tests/test_persistence.py`

`persistence.py` carries the per-haystack TOML I/O that today lives in `Haystack.save_haystack()` ([haystack.py:345–406](packages/haywire-studio/src/haywire_studio/haystack.py#L345)) and `Haystack.load_haystack()` ([haystack.py:421–512](packages/haywire-studio/src/haywire_studio/haystack.py#L421)). Free functions take the state and workspace root as parameters — pure functions, no global state.

- [ ] **Step 1: Read the existing save/load logic**

Inspect `packages/haywire-studio/src/haywire_studio/haystack.py:345–537` to understand the TOML format and the rules for the `execute=true` flag.

- [ ] **Step 2: Write the failing tests**

Create `barn/haybale-haystack/tests/test_persistence.py`:

```python
"""Persistence — free functions for per-haystack TOML I/O."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace with a haystacks/ subdirectory."""
    (tmp_path / "haystacks").mkdir()
    (tmp_path / "graphs").mkdir()
    return tmp_path


def test_dump_haystack_writes_toml_at_expected_path(tmp_workspace):
    from haybale_haystack.persistence import dump_haystack
    from haybale_haystack.graph_entry import GraphEntry

    g = MagicMock()
    g.serialize.return_value = {"nodes": [], "edges": []}
    p = tmp_workspace / "graphs" / "test.haywire"
    p.write_text("dummy")
    entry = GraphEntry(graph=g, editor=MagicMock(), path=p, unsaved=False)

    state = MagicMock()
    state.all_entries.return_value = [entry]

    dump_haystack(state, workspace_root=tmp_workspace, name="myset")

    expected = tmp_workspace / "haystacks" / "myset.toml"
    assert expected.exists()
    content = expected.read_text()
    assert "test.haywire" in content


def test_load_haystack_returns_empty_for_missing_file(tmp_workspace):
    from haybale_haystack.persistence import load_haystack

    state = MagicMock()
    state._entries = {}

    # Should not raise
    load_haystack(state, workspace_root=tmp_workspace, name="nonexistent")


def test_list_haystacks_returns_names(tmp_workspace):
    from haybale_haystack.persistence import list_haystacks
    (tmp_workspace / "haystacks" / "alpha.toml").write_text("")
    (tmp_workspace / "haystacks" / "beta.toml").write_text("")
    (tmp_workspace / "haystacks" / "ignore.txt").write_text("")  # non-toml ignored

    names = list_haystacks(workspace_root=tmp_workspace)
    assert set(names) == {"alpha", "beta"}


def test_dump_includes_execute_flag_for_running_entries(tmp_workspace):
    from haybale_haystack.persistence import dump_haystack
    from haybale_haystack.graph_entry import GraphEntry

    g = MagicMock()
    g.serialize.return_value = {}
    p = tmp_workspace / "graphs" / "running.haywire"
    p.write_text("")

    entry = GraphEntry(graph=g, editor=MagicMock(), path=p, unsaved=False)
    # Mark it as currently executing
    entry.interpreter = MagicMock()
    entry.interpreter.is_executing = True

    state = MagicMock()
    state.all_entries.return_value = [entry]

    dump_haystack(state, workspace_root=tmp_workspace, name="exec")

    content = (tmp_workspace / "haystacks" / "exec.toml").read_text()
    assert "execute" in content and "true" in content.lower()
```

- [ ] **Step 3: Run tests, expect ImportError**

Run: `uv run pytest barn/haybale-haystack/tests/test_persistence.py -v`
Expected: ImportError on `haybale_haystack.persistence`.

- [ ] **Step 4: Implement `persistence.py`**

Create `barn/haybale-haystack/haybale_haystack/persistence.py`:

```python
"""Persistence — free functions for per-haystack TOML I/O.

These functions move the file-I/O logic out of HaystackState (an AppState)
into pure helpers. HaystackState holds the in-memory registry; persistence.py
serializes/deserializes named haystacks to/from `<workspace>/haystacks/*.toml`.

Each TOML file represents one named haystack — a list of (path, execute_flag)
entries the user wants restored together.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import tomli
import tomli_w

if TYPE_CHECKING:
    from haybale_haystack.state.haystack_state import HaystackState

logger = logging.getLogger(__name__)


def haystack_dir(workspace_root: Path) -> Path:
    """Return the haystacks/ directory under the workspace root."""
    return workspace_root / "haystacks"


def haystack_path(workspace_root: Path, name: str) -> Path:
    """Return the file path for a named haystack."""
    return haystack_dir(workspace_root) / f"{name}.toml"


def list_haystacks(workspace_root: Path) -> list[str]:
    """Return the names of all saved haystacks under workspace_root."""
    d = haystack_dir(workspace_root)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.toml"))


def dump_haystack(
    state: "HaystackState",
    workspace_root: Path,
    name: str,
) -> None:
    """Serialize the current HaystackState entries to a named TOML file.

    Only entries with a path are persisted (untitled-only entries are
    transient). Each entry records its absolute path and whether its
    interpreter was running at save time (execute=true → restart on load).
    """
    target = haystack_path(workspace_root, name)
    target.parent.mkdir(parents=True, exist_ok=True)

    entries_data = []
    for entry in state.all_entries():
        if entry.path is None:
            continue
        entries_data.append({
            "path": str(entry.path),
            "execute": entry.is_executing,
        })

    payload = {
        "haystack": {
            "name": name,
            "entries": entries_data,
        },
    }

    with target.open("wb") as f:
        tomli_w.dump(payload, f)
    logger.info(f"Dumped haystack '{name}' with {len(entries_data)} entries to {target}")


def load_haystack(
    state: "HaystackState",
    workspace_root: Path,
    name: str,
) -> None:
    """Load a named haystack into the given state.

    For each entry in the TOML, opens the graph file via state.open_graph(path).
    For each entry flagged execute=true, starts its interpreter.

    Missing TOML file or missing graph files are warnings, not errors —
    the haystack proceeds with whatever it can load.
    """
    source = haystack_path(workspace_root, name)
    if not source.exists():
        logger.warning(f"Haystack '{name}' not found at {source}")
        return

    with source.open("rb") as f:
        payload = tomli.load(f)

    haystack_data = payload.get("haystack", {})
    entries_data = haystack_data.get("entries", [])

    for entry_data in entries_data:
        path_str = entry_data.get("path")
        if not path_str:
            continue
        path = Path(path_str)
        if not path.exists():
            logger.warning(f"Skipping missing graph: {path}")
            continue
        try:
            entry = state.open_graph(path)
            if entry_data.get("execute", False):
                entry.start_execution()
        except Exception as e:
            logger.error(f"Error loading entry {path}: {e}")

    logger.info(f"Loaded haystack '{name}' from {source}")


def delete_haystack(workspace_root: Path, name: str) -> bool:
    """Delete a named haystack file. Returns True if a file was removed."""
    target = haystack_path(workspace_root, name)
    if not target.exists():
        return False
    target.unlink()
    logger.info(f"Deleted haystack '{name}'")
    return True


def rename_haystack(workspace_root: Path, old_name: str, new_name: str) -> bool:
    """Rename a haystack file. Returns True on success."""
    src = haystack_path(workspace_root, old_name)
    dst = haystack_path(workspace_root, new_name)
    if not src.exists() or dst.exists():
        return False
    src.rename(dst)
    logger.info(f"Renamed haystack '{old_name}' -> '{new_name}'")
    return True
```

Note: imports `tomli` for read, `tomli_w` for write — verify these are already in the workspace dependencies (they typically are for Python <3.11; for 3.11+ use stdlib `tomllib` for read). If unavailable, add them via `uv add tomli tomli-w` in the haybale-haystack pyproject.

- [ ] **Step 5: Run tests**

Run: `uv run pytest barn/haybale-haystack/tests/test_persistence.py -v`
Expected: all 4 pass.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/persistence.py \
        barn/haybale-haystack/tests/test_persistence.py
git commit -m "feat(haystack): persistence.py — pure functions for TOML I/O

dump_haystack / load_haystack / list_haystacks / delete / rename.
Per-haystack TOML files at <workspace>/haystacks/<name>.toml.
Each entry records its path and an execute flag (restored on load)."
```

---

## Phase 3 — `HaystackSettings` (per-workspace scalars)

### Task 5: Implement `HaystackSettings(LibrarySettings)`

**Files:**
- Create: `barn/haybale-haystack/haybale_haystack/settings/haystack_settings.py`
- Test: `barn/haybale-haystack/tests/test_haystack_settings.py`

- [ ] **Step 1: Write the failing test**

Create `barn/haybale-haystack/tests/test_haystack_settings.py`:

```python
"""HaystackSettings — per-workspace settings for haystack scalars."""

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_default_last_haystack_name_is_empty():
    from haybale_haystack.settings.haystack_settings import HaystackSettings
    s = HaystackSettings()
    assert s.last_haystack_name.value == ""


def test_default_new_counter_starts_at_one():
    from haybale_haystack.settings.haystack_settings import HaystackSettings
    s = HaystackSettings()
    assert s.new_counter.value == 1


def test_settings_class_subclasses_library_settings():
    from haybale_haystack.settings.haystack_settings import HaystackSettings
    from haywire.core.settings.schema import LibrarySettings
    assert issubclass(HaystackSettings, LibrarySettings)


def test_can_set_and_read_last_haystack_name():
    from haybale_haystack.settings.haystack_settings import HaystackSettings
    s = HaystackSettings()
    s.last_haystack_name.value = "my_session"
    assert s.last_haystack_name.value == "my_session"
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `uv run pytest barn/haybale-haystack/tests/test_haystack_settings.py -v`
Expected: ImportError on `haybale_haystack.settings.haystack_settings`.

- [ ] **Step 3: Implement `HaystackSettings`**

Create `barn/haybale-haystack/haybale_haystack/settings/haystack_settings.py`:

```python
"""HaystackSettings — per-workspace settings for the haystack library.

Carries scalars that need to survive across app restarts:
  - last_haystack_name: rehydrated by HaystackState.on_enable.
  - new_counter: incremented when the user creates a new untitled graph.

Per Q15A, all fields are per-workspace. The settings system writes them
to <workspace>/.haywire/settings.toml under the 'haystack' namespace.
"""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings


@settings(namespace="haystack", label="Haystack")
class HaystackSettings(LibrarySettings):
    """Per-workspace persisted state for the haystack library."""

    last_haystack_name = setting[str](
        "",
        label="Last Haystack",
        description="Name of the haystack to auto-load on startup",
        category="haystack",
        order=10,
    )

    new_counter = setting[int](
        1,
        label="New Counter",
        description="Sequence used to name newly created untitled graphs",
        category="haystack",
        order=20,
    )
```

Verify the `setting[T]` and `@settings(...)` decorator API by inspecting `barn/haybale-studio/haybale_studio/settings/theme_settings.py` (we already read this in the plan-writing phase). If the API requires `tier="workspace"` or similar to enforce workspace-only scope, add that — refer to `packages/haywire-core/src/haywire/core/settings/schema.py` and `packages/haywire-core/src/haywire/core/settings/decorator.py` to confirm.

- [ ] **Step 4: Run the test**

Run: `uv run pytest barn/haybale-haystack/tests/test_haystack_settings.py -v`
Expected: all 4 pass.

If the `setting[str]("")` syntax raises (e.g. requires explicit `default=` kwarg), check theme_settings.py and match its exact form.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/settings/ \
        barn/haybale-haystack/tests/test_haystack_settings.py
git commit -m "feat(haystack): add HaystackSettings(LibrarySettings)

Per-workspace settings for last_haystack_name and new_counter.
Both fields persist across app restarts via the standard settings
system. Verification of workspace-only scope is an implementation
detail to confirm during integration test."
```

---

## Phase 4 — `HaystackState(AppState)` — the central registry

### Task 6: Implement `HaystackState` (the in-memory registry)

**Files:**
- Create: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`
- Test: `barn/haybale-haystack/tests/test_haystack_state.py`

This is the largest single task. It builds the AppState that replaces the old `Haystack` class. Functionality from `packages/haywire-studio/src/haywire_studio/haystack.py:130–556` migrates here, with three structural changes:
1. Subclass `AppState`; instantiated by `LibraryStateContainer` (no constructor args).
2. `on_enable` resolves dependencies from ambient context (no `__init__` params).
3. Validation broadcast goes directly via `SessionManager` (no `_session_manager` param).

- [ ] **Step 1: Write tests**

Create `barn/haybale-haystack/tests/test_haystack_state.py`:

```python
"""HaystackState — the in-memory entry registry as an AppState."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


@pytest.fixture
def state_with_mocked_deps():
    """Build a HaystackState with all on_enable deps mocked."""
    from haybale_haystack.state.haystack_state import HaystackState

    state = HaystackState()
    # Stub dependencies that on_enable would resolve
    state._session_manager = MagicMock()
    state._workspace_root = Path("/tmp/ws")
    state._node_factory = MagicMock()
    state._library_state_container = MagicMock()
    state._undo_config = None  # Will use Editor's default
    return state


def test_haystack_state_starts_empty():
    from haybale_haystack.state.haystack_state import HaystackState
    state = HaystackState()
    assert state.all_entries() == []


def test_haystack_state_is_an_app_state():
    from haybale_haystack.state.haystack_state import HaystackState
    from haywire.core.state.base import AppState
    assert issubclass(HaystackState, AppState)


def test_create_new_increments_counter_and_adds_entry(state_with_mocked_deps):
    state = state_with_mocked_deps
    initial_count = len(state.all_entries())
    entry = state.create_new()
    assert entry is not None
    assert len(state.all_entries()) == initial_count + 1
    assert entry.unsaved is True
    assert entry.path is None


def test_open_graph_returns_existing_if_already_open(state_with_mocked_deps, tmp_path):
    state = state_with_mocked_deps
    p = tmp_path / "x.haywire"
    p.write_text("{}")  # minimal stub
    with patch.object(state, "_load_graph_from_disk") as mock_load:
        mock_load.return_value = (MagicMock(), MagicMock())
        entry1 = state.open_graph(p)
        entry2 = state.open_graph(p)
    assert entry1 is entry2


def test_get_by_id_returns_entry(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()
    assert state.get_by_id(entry.entry_id) is entry


def test_remove_entry_drops_from_registry(state_with_mocked_deps):
    state = state_with_mocked_deps
    entry = state.create_new()
    state.remove_entry(entry)
    assert state.get_by_id(entry.entry_id) is None
```

- [ ] **Step 2: Run tests, expect ImportError**

Run: `uv run pytest barn/haybale-haystack/tests/test_haystack_state.py -v`
Expected: ImportError on `haybale_haystack.state.haystack_state`.

- [ ] **Step 3: Implement `HaystackState`**

Create `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`:

```python
"""HaystackState — AppState replacing the old studio.haystack.Haystack class.

In-memory registry of open graphs. One instance per app, shared across
sessions. Dependencies are resolved from the ambient DI context in
on_enable (Q5C, Q13A, Q14A).

Lifecycle:
  - on_enable: resolve SessionManager, workspace_root, node_factory,
    library_state_container; subscribe to validation events; rehydrate
    from HaystackSettings.last_haystack_name (Q9B).
  - on_disable: stop all interpreters, clear entries, drop subscriptions.

Key API:
  - create_new() -> GraphEntry
  - open_graph(path: Path) -> GraphEntry
  - save_graph(entry: GraphEntry, save_as: Path | None = None) -> bool
  - rename_graph(entry: GraphEntry, new_name: str) -> bool
  - remove_entry(entry: GraphEntry) -> bool
  - get_by_id(entry_id: str) -> GraphEntry | None
  - all_entries() -> list[GraphEntry]
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

from haybale_haystack.graph_entry import GraphEntry

logger = logging.getLogger(__name__)


@state(label="Haystack State")
class HaystackState(AppState):
    """Live registry of open graphs."""

    def __init__(self) -> None:
        super().__init__()
        self._entries: dict[str, GraphEntry] = {}
        # Dependencies — resolved in on_enable
        self._session_manager = None
        self._workspace_root: Optional[Path] = None
        self._node_factory = None
        self._library_state_container = None
        self._undo_config = None
        # Validation subscription handles for cleanup
        self._validation_subs: dict[str, object] = {}

    def on_enable(self) -> None:
        """Resolve ambient dependencies; rehydrate from settings."""
        from haywire.core.di.context import (
            get_session_manager,
            get_workspace_root,
            get_node_factory,
            get_library_state_container,
            get_settings_registry,
        )
        self._session_manager = get_session_manager()
        self._workspace_root = get_workspace_root()
        self._node_factory = get_node_factory()
        self._library_state_container = get_library_state_container()

        # Resolve HaystackSettings via the settings registry
        from haybale_haystack.settings.haystack_settings import HaystackSettings
        settings_reg = get_settings_registry()
        try:
            self._haystack_settings = settings_reg.get(HaystackSettings)
        except Exception:
            # Settings not yet registered or no instance — fall back to defaults
            self._haystack_settings = HaystackSettings()

        # Q9B: rehydrate from last_haystack_name (if any)
        last = self._haystack_settings.last_haystack_name.value
        if last:
            try:
                from haybale_haystack.persistence import load_haystack
                load_haystack(self, self._workspace_root, last)
                logger.info(f"HaystackState: rehydrated from '{last}'")
            except Exception as e:
                logger.error(f"HaystackState: failed to rehydrate '{last}': {e}")

    def on_disable(self) -> None:
        """Stop all interpreters and unsubscribe."""
        for entry in list(self._entries.values()):
            try:
                entry.stop_execution()
            except Exception as e:
                logger.warning(f"on_disable: stop_execution failed for {entry.display_name}: {e}")
        self._entries.clear()
        # Unsubscribe validation handlers
        for sub in list(self._validation_subs.values()):
            try:
                sub.unsubscribe()  # adjust to your signal API
            except Exception:
                pass
        self._validation_subs.clear()

    # ------------------------------------------------------------------
    # Entry construction
    # ------------------------------------------------------------------

    def _make_graph_and_editor(self, graph_id: str, name: str):
        """Construct a (BaseGraph, Editor) pair using ambient deps (Q14A)."""
        from haywire.core.graph.base_graph import BaseGraph
        from haywire.core.graph.editor import Editor

        g = BaseGraph(graph_id, name)
        e = Editor(g, self._node_factory, undo_config=self._undo_config)
        return g, e

    def create_new(self) -> GraphEntry:
        """Create a new untitled graph and add it to the registry."""
        counter = self._haystack_settings.new_counter.value
        name = f"Untitled {counter}"
        graph_id = f"new_{counter}"
        self._haystack_settings.new_counter.value = counter + 1

        g, e = self._make_graph_and_editor(graph_id, name)
        entry = GraphEntry(graph=g, editor=e, path=None, unsaved=True)
        self._entries[entry.entry_id] = entry
        self._subscribe_validation(entry)
        logger.info(f"HaystackState: created new entry {name}")
        return entry

    def open_graph(self, path: Path) -> GraphEntry:
        """Open a graph file. Returns the existing entry if already open."""
        path = Path(path).resolve()
        # Lookup by path-derived entry_id
        existing = self._entries.get(str(path))
        if existing is not None:
            return existing

        g, e = self._load_graph_from_disk(path)
        entry = GraphEntry(graph=g, editor=e, path=path, unsaved=False)
        self._entries[entry.entry_id] = entry
        self._subscribe_validation(entry)
        logger.info(f"HaystackState: opened {path}")
        return entry

    def _load_graph_from_disk(self, path: Path):
        """Load a graph file from disk into a (BaseGraph, Editor) pair."""
        # Read the existing logic in haystack.py:_load_graph (around line 213-225).
        # Construct via _make_graph_and_editor, then editor.deserialize() the file.
        g, e = self._make_graph_and_editor(path.stem, str(path))
        # Deserialize file contents into the graph via the editor.
        # The exact API depends on Editor.deserialize_from_file or similar —
        # match what today's Haystack does.
        with path.open("r") as f:
            data = f.read()
        e.deserialize(data)  # adjust to actual Editor API
        return g, e

    def save_graph(self, entry: GraphEntry, save_as: Optional[Path] = None) -> bool:
        """Serialize an entry to disk. If save_as is given, also rebind path."""
        target = save_as if save_as is not None else entry.path
        if target is None:
            logger.error("save_graph: no target path and entry has no path")
            return False
        try:
            data = entry.editor.serialize()  # adjust to actual API
            with target.open("w") as f:
                f.write(data)
            if save_as is not None:
                # Re-key the entry under the new path
                old_id = entry.entry_id
                entry.path = target
                self._entries.pop(old_id, None)
                self._entries[entry.entry_id] = entry
            entry.unsaved = False
            logger.info(f"Saved graph to {target}")
            return True
        except Exception as e:
            logger.error(f"save_graph failed: {e}")
            return False

    def rename_graph(self, entry: GraphEntry, new_name: str) -> bool:
        """Rename an entry's underlying file. Returns True on success."""
        if entry.path is None:
            return False
        new_path = entry.path.with_name(new_name + entry.path.suffix)
        try:
            entry.path.rename(new_path)
            old_id = entry.entry_id
            entry.path = new_path
            self._entries.pop(old_id, None)
            self._entries[entry.entry_id] = entry
            return True
        except Exception as e:
            logger.error(f"rename_graph failed: {e}")
            return False

    def remove_entry(self, entry: GraphEntry) -> bool:
        """Stop execution, drop from registry. Returns True if removed."""
        try:
            entry.stop_execution()
        except Exception as e:
            logger.warning(f"remove_entry: stop_execution failed: {e}")
        # Unsubscribe validation
        sub = self._validation_subs.pop(entry.entry_id, None)
        if sub is not None:
            try:
                sub.unsubscribe()
            except Exception:
                pass
        return self._entries.pop(entry.entry_id, None) is not None

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def all_entries(self) -> list[GraphEntry]:
        return list(self._entries.values())

    def get_by_id(self, entry_id: str) -> Optional[GraphEntry]:
        return self._entries.get(entry_id)

    def get_by_path(self, path: Path) -> Optional[GraphEntry]:
        return self._entries.get(str(Path(path).resolve()))

    def unsaved_entries(self) -> list[GraphEntry]:
        return [e for e in self._entries.values() if e.unsaved]

    # ------------------------------------------------------------------
    # Validation subscription / broadcast (Q5C)
    # ------------------------------------------------------------------

    def _subscribe_validation(self, entry: GraphEntry) -> None:
        """Subscribe to entry.graph's validation signal; broadcast on fire."""
        if self._session_manager is None:
            return  # on_enable hasn't run yet (e.g. test mode)
        try:
            sub = entry.graph.validation_signal.subscribe(
                lambda result: self._on_entry_validation(entry, result)
            )
            self._validation_subs[entry.entry_id] = sub
        except AttributeError:
            # Graph may not expose validation_signal — silently skip
            pass

    def _on_entry_validation(self, entry: GraphEntry, result) -> None:
        """Called when a graph fires its validation signal."""
        # Stop execution if validation failed (matches today's behavior at
        # haystack.py:165–170)
        if not getattr(result, "is_valid", True):
            entry.stop_execution()

        # Broadcast GraphDataMutated so editors refresh.
        from haywire.ui.context_signals import GraphDataMutated  # may be in core after PR1
        try:
            sig = GraphDataMutated(entry_id=entry.entry_id)
            self._session_manager.broadcast_signal(sig, origin_session_id="")
        except Exception as e:
            logger.warning(f"validation broadcast failed: {e}")
```

Several `# adjust to actual API` comments above are deliberate — when implementing, cross-reference the original `Haystack` class to get exact method names for `Editor.serialize`, `Editor.deserialize`, `BaseGraph.validation_signal`, etc. Don't guess; read the source.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest barn/haybale-haystack/tests/test_haystack_state.py -v`
Expected: 6 tests pass. If `_load_graph_from_disk` mocks fail because the test patches it but the API surface is wrong, adjust the test to match the actual API.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/state/ \
        barn/haybale-haystack/tests/test_haystack_state.py
git commit -m "feat(haystack): HaystackState(AppState) — central entry registry

Drop-in replacement for the legacy Haystack class. Resolves all
dependencies via ambient DI context (Q5C/Q13A/Q14A), broadcasts
validation events directly via SessionManager (Q5C), rehydrates
from HaystackSettings.last_haystack_name on on_enable (Q9B)."
```

---

## Phase 5 — Migrate `HaystackEditor` and `GraphEditor` (Q12B)

### Task 7: Move `HaystackEditor` into haybale-haystack

**Files:**
- Create: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py`
- Delete: `barn/haybale-studio/haybale_studio/editors/haystack_editor.py`

- [ ] **Step 1: Move the file**

```bash
git mv barn/haybale-studio/haybale_studio/editors/haystack_editor.py \
       barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py
```

- [ ] **Step 2: Update imports inside the moved file**

Open `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py`. Find every `from haybale_studio.editors.graph_editor import GraphEditor` and update to `from haybale_haystack.editors.graph_editor import GraphEditor`. Update any other `haybale_studio.editors` imports that target moved editors.

Find every `app.haystack.X(...)` call and replace with `ctx.app_data[HaystackState].X(...)`. The cleanest pattern:

```python
# At the top of methods that use it:
from haybale_haystack.state.haystack_state import HaystackState
hs = ctx.app_data[HaystackState]
# Then use hs.create_new(), hs.open_graph(...), etc.
```

Find every `from haywire.ui.protocols import IProjectState` and update to `from haywire.core.session.protocols import IProjectState`. Type annotations like `app: IProjectState = context.app` continue to work (the protocol is structural).

The old `haystack_editor.py` was around 900 lines with many call sites. Do this systematically: search for `app.haystack`, list every match, and rewrite each.

- [ ] **Step 3: Run any existing haystack-editor tests**

```bash
grep -rln "haystack_editor" tests/ 2>/dev/null
```

If tests exist, update their imports and run them. Expected: pass.

- [ ] **Step 4: Smoke check the import**

Run: `uv run python -c "from haybale_haystack.editors.haystack_editor import HaystackEditor; print(HaystackEditor)"`
Expected: prints the class. Any ImportError → fix the import path it complains about.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py \
        barn/haybale-studio/haybale_studio/editors/haystack_editor.py
git commit -m "refactor(haystack): move HaystackEditor to haybale-haystack

All app.haystack.X(...) calls rewritten to use
ctx.app_data[HaystackState].X(...). The editor structurally still
satisfies the same UX contract — list of entries, +/save/load/rename
buttons — but now reads from the AppState registry instead of the
legacy Haystack singleton."
```

---

### Task 8: Move `GraphEditor` into haybale-haystack

**Files:**
- Create: `barn/haybale-haystack/haybale_haystack/editors/graph_editor.py`
- Delete: `barn/haybale-studio/haybale_studio/editors/graph_editor.py`

GraphEditor uses `app.haystack` at lines 248, 339, 468 of the old file. All three become `ctx.app_data[HaystackState]`.

- [ ] **Step 1: Move the file**

```bash
git mv barn/haybale-studio/haybale_studio/editors/graph_editor.py \
       barn/haybale-haystack/haybale_haystack/editors/graph_editor.py
```

- [ ] **Step 2: Update imports and call sites**

Open `barn/haybale-haystack/haybale_haystack/editors/graph_editor.py`. Find each `app.haystack` usage and rewrite. For example, line 248:

```python
# OLD
return app.haystack.get_by_id(self.wrapper.payload)
# NEW
from haybale_haystack.state.haystack_state import HaystackState
return ctx.app_data[HaystackState].get_by_id(self.wrapper.payload)
```

If `ctx` isn't accessible at the call site (e.g. it's in a method that only takes `app`), figure out how to thread `ctx` through — likely the method has access to the full session context elsewhere.

Also update `from haywire.ui.protocols import IProjectState` → `from haywire.core.session.protocols import IProjectState`.

- [ ] **Step 3: Update or move associated tests**

```bash
grep -rln "graph_editor" tests/ 2>/dev/null | grep -v graph_canvas
```

For each test that imports `from haybale_studio.editors.graph_editor import GraphEditor`, update to `from haybale_haystack.editors.graph_editor import GraphEditor`. Move tests under `barn/haybale-haystack/tests/` if they're specific to GraphEditor's behavior.

- [ ] **Step 4: Smoke check the import and run tests**

Run:
```bash
uv run python -c "from haybale_haystack.editors.graph_editor import GraphEditor; print(GraphEditor)"
uv run pytest -m "not integration" -q
```
Expected: import works; tests green.

- [ ] **Step 5: Update `barn/haybale-studio/haybale_studio/editors/__init__.py`**

Remove any re-exports of `graph_editor` and `haystack_editor` (these no longer exist in haybale-studio).

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/editors/graph_editor.py \
        barn/haybale-studio/haybale_studio/editors/graph_editor.py \
        barn/haybale-studio/haybale_studio/editors/__init__.py \
        tests/
git commit -m "refactor(haystack): move GraphEditor to haybale-haystack (Q12B)

GraphEditor's app.haystack calls replaced with ctx.app_data[HaystackState].
The deep coupling between GraphEditor and Haystack is preserved as-is;
disentangling it (so other graph-management libraries could provide
their own editor) is deferred until a second consumer exists."
```

---

### Task 9: Drop `IProjectState.haystack` and clean up `IGraphManager`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/session/protocols.py`

- [ ] **Step 1: Delete the `haystack` field from `IProjectState`**

Open `packages/haywire-core/src/haywire/core/session/protocols.py`. In `IProjectState`, delete the line:
```python
haystack: IGraphManager
```

- [ ] **Step 2: Delete `IGraphManager` entirely (no remaining consumers)**

Verify nothing else in the codebase uses `IGraphManager`:

```bash
grep -rn "IGraphManager" packages/ barn/ --include="*.py"
```

If the only references are the definition and the (now-deleted) `IProjectState.haystack` annotation, delete the `IGraphManager` class. Update the corresponding shim in `packages/haywire-core/src/haywire/ui/protocols.py` to drop the `IGraphManager` re-export.

- [ ] **Step 3: Drop the `haystack` attribute from `HaywireApp`**

Open `packages/haywire-studio/src/haywire_studio/app.py`. Delete:
- The `from .haystack import Haystack` import (around line 139)
- The `self.haystack = Haystack(...)` block (around lines 141–145)
- The `try_load_startup_haystack()` method (around line 177–188)
- Any code that calls `self.haystack.X(...)`
- The `try ... if hasattr(self, 'haystack'): self.haystack.cleanup()` block in `on_app_shutdown` (around line 65–69)
- The call to `try_load_startup_haystack()` from `main_page` (around line 230–231)
- The `save_workspace()` method's haystack-save logic (around line 190–200) — keep the workspace JSON save, drop the haystack call

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -m "not integration" -q`
Expected: all green.

If anything fails referencing `app.haystack` or `IGraphManager`, that file needs migration to `ctx.app_data[HaystackState]`.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/protocols.py \
        packages/haywire-core/src/haywire/ui/protocols.py \
        packages/haywire-studio/src/haywire_studio/app.py
git commit -m "refactor: drop IProjectState.haystack and IGraphManager

HaystackState is now accessed via ctx.app_data[HaystackState].
HaywireApp no longer constructs or holds a Haystack instance.
try_load_startup_haystack and the workspace-save haystack hook are
gone — HaystackState.on_enable handles auto-load (Q9B); HaystackEditor
handles explicit save."
```

---

### Task 10: Delete the legacy `Haystack` class

**Files:**
- Delete: `packages/haywire-studio/src/haywire_studio/haystack.py`

- [ ] **Step 1: Verify no live consumers**

```bash
grep -rn "from haywire_studio.haystack import\|haywire_studio\.haystack" packages/ barn/ tests/
```

Expected: no matches except the file itself. If any remain, migrate them in this step.

- [ ] **Step 2: Delete the file**

```bash
git rm packages/haywire-studio/src/haywire_studio/haystack.py
```

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/haystack.py
git commit -m "refactor: delete legacy Haystack class from haywire-studio

All functionality has been migrated:
  - In-memory registry → HaystackState (haybale-haystack)
  - Per-haystack TOML I/O → persistence.py free functions
  - Scalars (last_haystack_name, new_counter) → HaystackSettings
  - Auto-load on startup → HaystackState.on_enable

The haystack.py file no longer has any consumers."
```

---

## Phase 6 — Add the "Open in Haystack" file-context-menu panel (Q1cA)

### Task 11: Implement and register the panel

**Files:**
- Create: `barn/haybale-haystack/haybale_haystack/panels/open_in_haystack.py`
- Test: `barn/haybale-haystack/tests/test_open_in_haystack_panel.py`

This panel uses the PR 1 file-context-menu infrastructure: `@panel(action=FileBrowserActions, focus=FileFocus, label=...)`, polling on `FileBrowserState.right_clicked_file.suffix == ".haywire"`, draw renders one button that calls `actions.reveal(GraphEditor, entry.entry_id, entry.display_name)`.

- [ ] **Step 1: Write the failing test**

Create `barn/haybale-haystack/tests/test_open_in_haystack_panel.py`:

```python
"""OpenInHaystack panel — file-context-menu entry for .haywire files."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_panel_polls_true_for_haywire_file():
    from haybale_haystack.panels.open_in_haystack import OpenInHaystackPanel
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state = FileBrowserState()
    state.right_clicked_file.value = Path("/tmp/foo.haywire")
    ctx.data = {FileBrowserState: state}

    assert OpenInHaystackPanel.poll(ctx) is True


def test_panel_polls_false_for_non_haywire_file():
    from haybale_haystack.panels.open_in_haystack import OpenInHaystackPanel
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state = FileBrowserState()
    state.right_clicked_file.value = Path("/tmp/foo.txt")
    ctx.data = {FileBrowserState: state}

    assert OpenInHaystackPanel.poll(ctx) is False


def test_panel_polls_false_when_no_right_click():
    from haybale_haystack.panels.open_in_haystack import OpenInHaystackPanel
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state = FileBrowserState()
    # right_clicked_file stays None
    ctx.data = {FileBrowserState: state}

    assert OpenInHaystackPanel.poll(ctx) is False


def test_panel_decorator_metadata():
    from haybale_haystack.panels.open_in_haystack import OpenInHaystackPanel
    from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions
    from haybale_studio.file_focus import FileFocus

    ident = OpenInHaystackPanel.class_identity
    assert ident.action is FileBrowserActions
    assert ident.focus is FileFocus
    assert "Haystack" in ident.label
```

- [ ] **Step 2: Run tests, expect ImportError**

Run: `uv run pytest barn/haybale-haystack/tests/test_open_in_haystack_panel.py -v`
Expected: ImportError on `haybale_haystack.panels.open_in_haystack`.

- [ ] **Step 3: Implement the panel**

Create `barn/haybale-haystack/haybale_haystack/panels/open_in_haystack.py`:

```python
"""OpenInHaystackPanel — file-context-menu entry for .haywire files.

Registered with focus=FileFocus, action=FileBrowserActions. Polls
true when the right-clicked file has the .haywire extension. On click,
calls HaystackState.open_graph(path) to derive the entry_id, then issues
actions.reveal(GraphEditor, entry_id, display_name).

Modeled on DeleteNodePanel
([context_menu/node_actions.py:31-50](barn/haybale-studio/haybale_studio/panels/context_menu/node_actions.py#L31)).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui import elements as hui

from haybale_studio.file_focus import FileFocus
from haybale_studio.state.file_browser_state import FileBrowserState
from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


_HAYSTACK_EXTS = frozenset({".haywire"})


@panel(
    action=FileBrowserActions,
    focus=FileFocus,
    label="Open in Haystack",
    icon=hui.icon.folder if hasattr(hui.icon, "folder") else "folder",
    order=10,
)
class OpenInHaystackPanel(BasePanel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        f = ctx.data[FileBrowserState].right_clicked_file.value
        return f is not None and f.suffix.lower() in _HAYSTACK_EXTS

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: FileBrowserActions,
    ) -> None:
        from haybale_haystack.state.haystack_state import HaystackState
        from haybale_haystack.editors.graph_editor import GraphEditor

        f = ctx.data[FileBrowserState].right_clicked_file.value
        if f is None:
            return

        def _do_open():
            hs = ctx.app_data[HaystackState]
            entry = hs.open_graph(f)
            actions.reveal(GraphEditor, entry.entry_id, entry.display_name)

        layout.button(
            "Open in Haystack",
            icon=hui.icon.folder if hasattr(hui.icon, "folder") else "folder",
            on_click=_do_open,
        )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest barn/haybale-haystack/tests/test_open_in_haystack_panel.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/panels/ \
        barn/haybale-haystack/tests/test_open_in_haystack_panel.py
git commit -m "feat(haystack): OpenInHaystackPanel for the file context menu

Right-click a .haywire file → menu shows 'Open in Haystack' →
HaystackState.open_graph(path) → Reveal GraphEditor.

Built on PR1 infrastructure (FileFocus, FileBrowserActions,
FileBrowserState). Per Q1cA, follows the DeleteNodePanel precedent
exactly: one-button @panel."
```

---

### Task 12: Drop FileBrowser's hardcoded `.haywire` routing

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/file_browser.py`

The file-context-menu panel now handles `.haywire` files. Remove the hardcoded `_open_graph_file` routing.

- [ ] **Step 1: Update `_on_select`**

In `barn/haybale-studio/haybale_studio/editors/file_browser.py`, find `_on_select` (around line 264). The dispatch block at lines 290–298 looks like:

```python
from haybale_studio.editors.code_editor import EDITABLE_EXTS

ext = path.suffix.lower()
if ext in self._GRAPH_EXTS:
    self._open_graph_file(path, context)
elif ext in EDITABLE_EXTS:
    self._open_in_code_editor(path, context)
else:
    self._open_in_file_viewer(path, context)
```

Change to:

```python
from haybale_studio.editors.code_editor import EDITABLE_EXTS

ext = path.suffix.lower()
if ext in EDITABLE_EXTS:
    self._open_in_code_editor(path, context)
else:
    self._open_in_file_viewer(path, context)
```

(Removed the `if ext in self._GRAPH_EXTS:` branch.)

- [ ] **Step 2: Delete `_open_graph_file` method**

Delete the entire `_open_graph_file` method (around lines 304–319).

- [ ] **Step 3: Delete `_GRAPH_EXTS` class field**

At the top of the class (around line 71), delete:
```python
_GRAPH_EXTS: frozenset = frozenset({".haywire"})
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest -m "not integration" -q`
Expected: all green.

- [ ] **Step 5: Smoke-test left-click on a non-`.haywire` file**

Run: `uv run haywire`. Click a `.py` file → opens in code editor (unchanged). Click a `.haywire` file → opens in file viewer (the default for unrouted extensions). Right-click a `.haywire` file → menu shows "Open in Haystack" → click it → graph opens.

If the left-click on `.haywire` doesn't behave as expected, verify the file viewer handles it gracefully (it should — it's the catch-all). Stop the app.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/file_browser.py
git commit -m "refactor(file-browser): drop hardcoded .haywire left-click routing

Left-click on a .haywire file now falls through to the default file
viewer. The 'Open in Haystack' file-context-menu panel handles the
explicit user gesture via right-click.

This was the last reference to app.haystack from haybale-studio."
```

---

## Phase 7 — Integration test + final polish

### Task 13: End-to-end integration test

**Files:**
- Create: `tests/integration/test_haystack_carve_out.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_haystack_carve_out.py`:

```python
"""End-to-end: haybale-haystack library loads, HaystackState rehydrates,
execute=true graphs restart on app startup."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_haystack_state_loads_via_library_system(tmp_path):
    """HaystackState is registered when haybale-haystack loads."""
    # This test exercises the real library system. It needs:
    #  - A workspace dir with haystacks/ and graphs/
    #  - HaywireApp constructed with workspace_root=tmp_path
    #  - The library system to discover haybale-haystack via entry-points
    # Check whether HaystackState appears in app.library_state_container._app
    # after startup.
    pass  # Stub — flesh out using existing integration test patterns.


def test_rehydrate_from_settings(tmp_path):
    """HaystackState.on_enable rehydrates from HaystackSettings.last_haystack_name."""
    pass  # Stub.


def test_execute_true_resumes_interpreter(tmp_path):
    """Entries flagged execute=true in TOML have running interpreters after load."""
    pass  # Stub.
```

These are stubs — flesh them out by referencing existing integration tests in `tests/integration/` for setup patterns. The stubs document the contract; implementing them concretely depends on the test infrastructure available.

- [ ] **Step 2: Run integration tests if implementations exist**

Run: `uv run pytest tests/integration/test_haystack_carve_out.py -v`
Expected: pass (or skipped if stubs only).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_haystack_carve_out.py
git commit -m "test(integration): scaffold haystack carve-out e2e tests

Stubs for: library load registers HaystackState, on_enable rehydrates
from settings, execute=true resumes interpreters. Flesh out using
existing integration test patterns for app construction."
```

---

### Task 14: Final smoke test + lint/type-check

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 2: Run linter, formatter, and type checker**

Run:
```bash
uv run ruff check . && \
  uv run ruff format --check . && \
  uv run mypy packages/haywire-core/src/ \
              packages/haywire-studio/src/ \
              barn/haybale-core/haybale_core/ \
              barn/haybale-studio/haybale_studio/ \
              barn/haybale-haystack/haybale_haystack/ \
              barn/haybale-testing/haybale_testing/ \
              barn/haybale-example/haybale_example/ \
              barn/haybale-visiongraph/haybale_visiongraph/ \
              barn/haybale-TEST_A/haybale_test_a/
```
Expected: clean.

- [ ] **Step 3: End-to-end smoke test**

Run: `uv run haywire` in a workspace with at least one saved haystack (set up by hand or via the editor).

Verify:
- App boots without error
- The file tree renders
- Right-click a `.haywire` file → "Open in Haystack" appears in the menu
- Clicking "Open in Haystack" opens the graph in GraphEditor
- HaystackEditor (sidebar panel) shows the open graph
- Save a graph via the editor → file persists; reload the haystack → graph reopens
- If a previous session had a graph executing, restart the app → that graph's interpreter is running
- Close the browser tab → server logs show clean disconnect

Stop the app.

- [ ] **Step 4: Final commit (if any cleanup was needed)**

```bash
git status
git add <stragglers>
git commit -m "fix: small cleanups from PR2 smoke testing"
```

PR 2 is complete. Open the PR.

---

## Self-review checklist

Before opening the PR, verify against the design decisions:

- [ ] `barn/haybale-haystack/` package exists with entry-point and `register_components`
- [ ] `HaystackState(AppState)` exists and is decorated with `@state(...)`
- [ ] `HaystackState.on_enable` resolves `SessionManager`, `workspace_root`, `node_factory`, `library_state_container`, `settings_registry` from ambient DI context
- [ ] `HaystackState.on_enable` rehydrates from `HaystackSettings.last_haystack_name` if non-empty (Q9B)
- [ ] `execute=true` flag in TOML is restored via `entry.start_execution()` on load (Q9B)
- [ ] `HaystackSettings(LibrarySettings)` exists with `last_haystack_name` and `new_counter` (Q15A — both are per-workspace)
- [ ] `persistence.py` free functions: `dump_haystack`, `load_haystack`, `list_haystacks`, `delete_haystack`, `rename_haystack`
- [ ] `GraphEditor` and `HaystackEditor` live in haybale-haystack; haybale-studio no longer has them
- [ ] All `app.haystack.X(...)` calls have been replaced with `ctx.app_data[HaystackState].X(...)`
- [ ] `IProjectState.haystack` is gone; `IGraphManager` is gone (verify nothing references it)
- [ ] `packages/haywire-studio/src/haywire_studio/haystack.py` is deleted
- [ ] `HaywireApp` no longer constructs or holds a `Haystack` instance
- [ ] `try_load_startup_haystack` is gone from `HaywireApp`
- [ ] FileBrowser's `_open_graph_file` and `_GRAPH_EXTS` are gone
- [ ] `OpenInHaystackPanel` exists with `@panel(action=FileBrowserActions, focus=FileFocus)` and polls on `.haywire` extension (Q1cA)
- [ ] Validation broadcast goes via `SessionManager.broadcast_signal` directly from `HaystackState._on_entry_validation` (Q5C — no editor or library-bridge intermediary)
- [ ] `LibraryStateContainer` ambient global getter exists and is set by `provide_library_state_container`

If any item is unchecked, address before opening the PR.

---

## Follow-ups (out of scope for PR 2; track separately)

- **State canon edit** — drop "not a persistence layer" prohibition; replace with positive guidance about lifecycle-hook resource attachment.
- **UndoConfig → LibrarySettings refactor** — sidesteps the need for an `undo_config` ambient global; lets users tune undo behavior from settings UI.
- **`haybale-graph-editing` extraction** — pull GraphEditor and the editing primitives out of both haybale-studio and haybale-haystack into a smaller library, when a second graph-management library exists to justify it.
- **CLI commands for haystack management** — `haywire haystack list`, `haywire haystack save`, etc. None today; design when there's demand.
- **Import-cleanup PR** — sweep all 53 (now updated) `from haywire.ui.session/context/etc.` import sites to canonical `haywire.core.session.*` paths and delete the shims.
- **AppState DI access pattern** — once 3+ AppStates exist that all reach for ambient globals in `on_enable`, design a proper DI hook (constructor injection? `on_enable(self, deps: AppDeps)`?). Three current motivations: SessionManager, workspace_root, library_state_container.
