# GraphEditor Carve-Out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `GraphEditor` from `haybale-haystack` into a new plugin library `haybale-graph-editor`, decoupled from `HaystackState` via a `GraphAppState` registry, so other graph-management libraries can host the same editor.

**Architecture:** A new plugin library `barn/haybale-graph-editor/` exposes a `GraphContainer` protocol, a `GraphAppState` registry (one entry per open graph, keyed by `binding_id`), and the moved `GraphEditor`. `haybale-haystack` keeps its own `HaystackState._entries` but additionally registers/unregisters/rekeys each entry against `GraphAppState`, and `GraphEntry` gains a `save()` method that delegates back to `HaystackState` via a back-reference. `haywire-core` is **not modified**.

**Tech Stack:** Python 3.10+, NiceGUI, `injector` DI, attrs/dataclasses, pytest, ruff, mypy, hatchling, uv workspace.

---

## File Structure

### Created files

```
barn/haybale-graph-editor/
├── pyproject.toml
├── README.md
└── haybale_graph_editor/
    ├── __init__.py                       # @library decorator, Library class
    ├── protocols.py                       # GraphContainer Protocol
    ├── state/
    │   ├── __init__.py
    │   └── graph_app_state.py            # GraphAppState(AppState)
    └── editors/
        ├── __init__.py
        └── graph_editor.py                # moved from haybale-haystack
```

### Tests created

```
tests/graph_editor/
├── __init__.py
├── test_graph_app_state.py               # register/unregister/get/rekey unit tests
├── test_graph_container_protocol.py      # protocol shape + structural conformance
└── test_graph_editor_save.py             # editor reads registry, calls container.save()
```

### Files modified

- `pyproject.toml` (workspace root) — add `haybale-graph-editor` workspace member
- `barn/haybale-haystack/pyproject.toml` — add dependency on `haybale-graph-editor`
- `barn/haybale-haystack/haybale_haystack/graph_entry.py` — rename `entry_id` → `binding_id`; add `haystack` back-ref; add `save()` method; structural conformance with `GraphContainer`
- `barn/haybale-haystack/haybale_haystack/state/haystack_state.py` — call `GraphAppState.register/unregister/rekey`; rename `save_graph` body to a private `_save_entry` (keep public `save_graph` for backward call sites); pass `haystack=self` into every `GraphEntry(...)` construction; rename internal uses of `entry_id` → `binding_id` consistently
- `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py` — import `GraphEditor` from new library; update `.entry_id` → `.binding_id` references
- `barn/haybale-haystack/haybale_haystack/panels/file_browser/open_in_haystack.py` — import `GraphEditor` from new library; update `.entry_id` → `.binding_id`
- `barn/haybale-haystack/haybale_haystack/editors/graph_editor.py` — **DELETED** (moved)
- `barn/haybale-haystack/haybale_haystack/signals.py` — no change (the `HaystackTeardown.entry_ids` field is a *signal payload* of binding-ids; it stays named `entry_ids` because renaming a frozen signal field touches cross-session compatibility and is out of scope for this carve-out)
- `barn/haybale-studio/haybale_studio/editors/file_browser_menu/actions.py` — docstring update (mentions `GraphEditor`)
- `tests/studio/test_graph_editor_on_focus.py` — update import path and `.entry_id` references; add `graph_app_state` to test fixtures
- `tests/haystack/test_graph_entry.py` — update `.entry_id` → `.binding_id`; cover `save()`
- `tests/haystack/test_haystack_state.py` — update `.entry_id` → `.binding_id`; assert `GraphAppState` participation
- `tests/studio/test_haystack_editor_remove.py` — update `.entry_id` → `.binding_id`
- `docs/components/editors/editor-canon.md` — note `GraphEditor` now lives in `haybale-graph-editor`
- `docs/reference/glossary.md` — add `GraphContainer`, `GraphAppState`; clarify `binding_id` is registry key
- `.codemap/INDEX.md` — add row for `haybale-graph-editor`
- `.codemap/modules/haybale-graph-editor.md` — new module manifest
- `.codemap/modules/haybale-haystack.md` — note dependency on `haybale-graph-editor`

---

## Implementation Sequence

The plan is staged so the test suite **stays green at every commit boundary**:

1. **Stage A (Tasks 1–6):** Scaffold the new library with `GraphAppState` and `GraphContainer`. No code is moved yet; the new library is empty of editors but its registry works in isolation. Existing tests continue to pass because nothing is touched.
2. **Stage B (Tasks 7–10):** Rename `entry_id` → `binding_id` across haystack and tests. Mechanical, isolated, green at end.
3. **Stage C (Tasks 11–13):** Add `haystack` back-ref + `save()` to `GraphEntry`; refactor `HaystackState.save_graph` into an internal `_save_entry`; haystack participates in the `GraphAppState` registry. `GraphEditor` still lives in haystack and still works.
4. **Stage D (Tasks 14–16):** Move `GraphEditor` to the new library; adapt it to read from `GraphAppState` instead of `HaystackState`; update all import sites.
5. **Stage E (Tasks 17–18):** Docs and codemap.

---

## Stage A — Scaffold haybale-graph-editor

### Task 1: Create library directory skeleton and pyproject.toml

**Files:**
- Create: `barn/haybale-graph-editor/pyproject.toml`
- Create: `barn/haybale-graph-editor/README.md`
- Create: `barn/haybale-graph-editor/haybale_graph_editor/__init__.py` (stub)
- Create: `barn/haybale-graph-editor/haybale_graph_editor/state/__init__.py` (empty)
- Create: `barn/haybale-graph-editor/haybale_graph_editor/editors/__init__.py` (empty)
- Modify: workspace root `pyproject.toml` — add `barn/haybale-graph-editor` to workspace members

- [ ] **Step 1: Create directory tree**

```bash
mkdir -p barn/haybale-graph-editor/haybale_graph_editor/state
mkdir -p barn/haybale-graph-editor/haybale_graph_editor/editors
```

- [ ] **Step 2: Write `barn/haybale-graph-editor/pyproject.toml`**

```toml
[project]
name = "haybale-graph-editor"
version = "0.1.0"
description = "Graph editor library for Haywire — host-agnostic visual graph editing"
requires-python = ">=3.10"
license = {text = "MIT"}

dependencies = [
    "haywire-core>=0.1.0",
    "haywire-studio>=0.1.0",
    "haybale-core>=0.1.0",
    "haybale-studio>=0.1.0",
]

[project.entry-points."haywire.libraries"]
graph_editor = "haybale_graph_editor:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["haybale_graph_editor"]

[tool.uv.sources]
haywire-core = { workspace = true }
haywire-studio = { workspace = true }
haybale-core = { workspace = true }
haybale-studio = { workspace = true }
```

- [ ] **Step 3: Write `barn/haybale-graph-editor/README.md`**

```markdown
# haybale-graph-editor

Visual graph editor library for Haywire. Provides:

- `GraphContainer` (Protocol) — what a graph-source library must implement
- `GraphAppState` (AppState) — shared registry of open graph containers, keyed by `binding_id`
- `GraphEditor` (BaseEditor) — the canvas-hosting editor surface

Source libraries (e.g. `haybale-haystack`) register containers; this library renders them.
```

- [ ] **Step 4: Write `barn/haybale-graph-editor/haybale_graph_editor/__init__.py` (stub)**

```python
"""haybale-graph-editor: graph editor library for Haywire.

Provides the GraphContainer protocol, GraphAppState registry, and
GraphEditor surface. Decoupled from any specific graph source — source
libraries register their containers, this library renders them.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.state import LibraryStateRegistry
from haywire.ui.editor.registry import EditorTypeRegistry


@library(
    label="Graph Editor",
    id="graph_editor",
    version="0.1.0",
    description="Visual graph editor library — host-agnostic",
    url="",
    help_url="",
    author="",
    author_url="",
    dependencies=["haybale_core", "haybale_studio"],
    tags=["graph-editor"],
    file_watcher=True,
)
class Library(BaseLibrary):
    """Graph Editor library."""

    def register_components(self):
        base_path = Path(__file__).parent

        self.add_folder_to_registry(
            folder_path=str(base_path / "state"),
            registry_cls=LibraryStateRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "editors"),
            registry_cls=EditorTypeRegistry,
        )

    def validate(self) -> bool:
        return True
```

- [ ] **Step 5: Add member to workspace root `pyproject.toml`**

Locate `[tool.uv.workspace]` (or equivalent `members = [...]` list) in the workspace root `pyproject.toml` and add `"barn/haybale-graph-editor"` to the list, preserving existing entries. (Run `grep -n "members\|workspace" pyproject.toml` first to find the right spot.)

- [ ] **Step 6: Verify workspace recognises the new package**

Run: `uv sync`
Expected: completes successfully; `haybale-graph-editor` shows up in the resolved dependency graph (no errors).

- [ ] **Step 7: Run the full test suite to confirm green baseline**

Run: `uv run pytest -m "not integration"`
Expected: PASS (same set of tests as before; the new package added no tests yet).

- [ ] **Step 8: Commit**

```bash
git add barn/haybale-graph-editor pyproject.toml
git commit -m "feat(graph-editor): scaffold haybale-graph-editor library skeleton"
```

---

### Task 2: Define the GraphContainer protocol (failing test first)

**Files:**
- Create: `tests/graph_editor/__init__.py` (empty)
- Create: `tests/graph_editor/test_graph_container_protocol.py`
- Create: `barn/haybale-graph-editor/haybale_graph_editor/protocols.py`

- [ ] **Step 1: Write failing test in `tests/graph_editor/test_graph_container_protocol.py`**

```python
"""Tests for the GraphContainer protocol shape.

The protocol is a structural contract — anything with the right
attributes and methods satisfies it. These tests pin the shape so
accidental drift gets caught.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

from haybale_graph_editor.protocols import GraphContainer


@dataclass
class _DummyContainer:
    """Minimal struct that satisfies GraphContainer structurally."""

    binding_id: str = "id-1"
    editor: object = field(default_factory=object)
    path: Optional[Path] = None
    unsaved: bool = False
    display_name: str = "Dummy"

    def save(self, save_as: Optional[Path] = None) -> Optional[str]:
        return None


def test_dummy_container_satisfies_protocol():
    """A struct with the right shape is a GraphContainer at runtime."""
    c = _DummyContainer()
    assert isinstance(c, GraphContainer)


def test_missing_save_method_does_not_satisfy_protocol():
    """A struct without save() is not a GraphContainer."""

    @dataclass
    class _NoSave:
        binding_id: str = "x"
        editor: object = field(default_factory=object)
        path: Optional[Path] = None
        unsaved: bool = False
        display_name: str = "x"

    assert not isinstance(_NoSave(), GraphContainer)


def test_protocol_attributes_are_accessible():
    """Every documented attribute can be read off a conforming container."""
    c = _DummyContainer(binding_id="abc", path=Path("/tmp/x.haywire"), unsaved=True)
    assert c.binding_id == "abc"
    assert c.path == Path("/tmp/x.haywire")
    assert c.unsaved is True
    assert c.display_name == "Dummy"
    assert c.editor is not None
    assert c.save() is None
    assert c.save(save_as=Path("/tmp/y.haywire")) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graph_editor/test_graph_container_protocol.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haybale_graph_editor.protocols'`

- [ ] **Step 3: Write `barn/haybale-graph-editor/haybale_graph_editor/protocols.py`**

```python
"""Protocols for the graph editor library.

GraphContainer is the structural contract a source library must
implement (or satisfy structurally) to host a graph in GraphEditor.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor


@runtime_checkable
class GraphContainer(Protocol):
    """One open graph, ready to be edited by GraphEditor.

    A source library (e.g. haybale-haystack) constructs containers and
    registers them in :class:`GraphAppState`. GraphEditor reads
    containers by binding_id; it never knows which source produced one.

    Attributes:
        binding_id: Stable identifier within :class:`GraphAppState`.
            Workspace-persisted (the wrapper's binding_id field). For a
            saved graph this is typically the file path string; for an
            unsaved graph a synthetic token assigned by the source.
        editor: The graph Editor (undo/redo, mutation API).
        path: Absolute filesystem path, or None for unsaved/in-memory.
        unsaved: True when in-memory state differs from disk.
        display_name: Human label for tab and header chrome.
    """

    binding_id: str
    editor: "Editor"
    path: Optional[Path]
    unsaved: bool
    display_name: str

    def save(self, save_as: Optional[Path] = None) -> Optional[str]:
        """Persist the container.

        Args:
            save_as: When provided and different from ``self.path``,
                this is a save-as: the container's identity changes.

        Returns:
            New ``binding_id`` if the save renamed/rekeyed the container
            (typically only on save-as). ``None`` otherwise — including
            when the save failed; callers detect failure via the
            unchanged ``unsaved`` flag or surface dialog.
        """
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graph_editor/test_graph_container_protocol.py -v`
Expected: PASS — all 3 tests green.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/protocols.py tests/graph_editor
git commit -m "feat(graph-editor): add GraphContainer protocol"
```

---

### Task 3: Write failing tests for GraphAppState

**Files:**
- Create: `tests/graph_editor/test_graph_app_state.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for GraphAppState — the binding_id → GraphContainer registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

from haybale_graph_editor.state.graph_app_state import GraphAppState


@dataclass
class _Container:
    binding_id: str
    editor: object = field(default_factory=object)
    path: Optional[Path] = None
    unsaved: bool = False
    display_name: str = "C"

    def save(self, save_as: Optional[Path] = None) -> Optional[str]:
        return None


def test_register_then_get_returns_container():
    state = GraphAppState()
    c = _Container(binding_id="a")
    state.register(c)
    assert state.get("a") is c


def test_get_unknown_id_returns_none():
    state = GraphAppState()
    assert state.get("missing") is None


def test_unregister_removes_container():
    state = GraphAppState()
    c = _Container(binding_id="a")
    state.register(c)
    state.unregister("a")
    assert state.get("a") is None


def test_unregister_unknown_id_is_noop():
    state = GraphAppState()
    state.unregister("missing")  # must not raise


def test_register_same_id_replaces():
    """Re-registering the same binding_id replaces the prior container."""
    state = GraphAppState()
    c1 = _Container(binding_id="a", display_name="first")
    c2 = _Container(binding_id="a", display_name="second")
    state.register(c1)
    state.register(c2)
    assert state.get("a") is c2


def test_rekey_moves_container():
    state = GraphAppState()
    c = _Container(binding_id="old")
    state.register(c)
    state.rekey("old", "new")
    assert state.get("old") is None
    assert state.get("new") is c


def test_rekey_unknown_old_id_is_noop():
    state = GraphAppState()
    state.rekey("missing", "anything")  # must not raise


def test_rekey_to_same_id_is_noop():
    state = GraphAppState()
    c = _Container(binding_id="a")
    state.register(c)
    state.rekey("a", "a")
    assert state.get("a") is c


def test_rekey_overwrites_existing_destination():
    """If destination key is taken, rekey replaces it.

    Rationale: rekey is called by sources after a save-as where the new
    binding_id has just been claimed by the renaming entry; collisions
    in practice mean stale state and the new claim should win.
    """
    state = GraphAppState()
    c1 = _Container(binding_id="a")
    c2 = _Container(binding_id="b")
    state.register(c1)
    state.register(c2)
    state.rekey("a", "b")
    assert state.get("a") is None
    assert state.get("b") is c1


def test_all_containers_returns_snapshot():
    state = GraphAppState()
    c1 = _Container(binding_id="a")
    c2 = _Container(binding_id="b")
    state.register(c1)
    state.register(c2)
    result = state.all_containers()
    assert set(result) == {c1, c2}
    # Returned list is a copy — mutating it must not affect the registry.
    result.clear()
    assert state.get("a") is c1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/graph_editor/test_graph_app_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haybale_graph_editor.state.graph_app_state'`

- [ ] **Step 3: Commit (tests only, for TDD checkpoint)**

```bash
git add tests/graph_editor/test_graph_app_state.py
git commit -m "test(graph-editor): add failing tests for GraphAppState"
```

---

### Task 4: Implement GraphAppState

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/state/graph_app_state.py`

- [ ] **Step 1: Write the implementation**

```python
"""GraphAppState — app-wide registry of open GraphContainers.

Lives at ``app_data[GraphAppState]``. Source libraries (haystack,
future cloud-graph libraries, etc.) register their containers when a
graph opens, unregister on close, and rekey on save-as. GraphEditor
looks up the container for its tab by ``binding_id`` on every render.

The registry holds *references* only — owning libraries remain
responsible for the underlying container's lifecycle (file I/O,
execution state, signal broadcast). GraphAppState's only job is
identity routing: "which container does this binding_id point to?"
"""

from __future__ import annotations

import logging
from typing import Optional

from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

from haybale_graph_editor.protocols import GraphContainer

logger = logging.getLogger(__name__)


@state(label="Graph App State")
class GraphAppState(AppState):
    """Registry: ``binding_id`` → :class:`GraphContainer`.

    One instance per app, shared across sessions. Source libraries
    coordinate writes; GraphEditor performs reads.
    """

    def __init__(self) -> None:
        super().__init__()
        self._graphs: dict[str, GraphContainer] = {}

    def register(self, container: GraphContainer) -> None:
        """Add or replace a container under its current ``binding_id``."""
        self._graphs[container.binding_id] = container

    def unregister(self, binding_id: str) -> None:
        """Remove a container by ``binding_id``. Idempotent."""
        self._graphs.pop(binding_id, None)

    def get(self, binding_id: str) -> Optional[GraphContainer]:
        """Look up a container by ``binding_id``. Returns None when absent."""
        return self._graphs.get(binding_id)

    def rekey(self, old_id: str, new_id: str) -> None:
        """Move a container from ``old_id`` to ``new_id``.

        Source libraries call this after a save-as that changes the
        container's identity. No-op when ``old_id`` is unknown or
        identical to ``new_id``. When ``new_id`` is already occupied,
        the destination is overwritten — see test_rekey_overwrites_existing_destination.
        """
        if old_id == new_id:
            return
        container = self._graphs.pop(old_id, None)
        if container is None:
            return
        self._graphs[new_id] = container

    def all_containers(self) -> list[GraphContainer]:
        """Snapshot of all registered containers. Mutating the list does
        not affect the registry."""
        return list(self._graphs.values())
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/graph_editor/test_graph_app_state.py -v`
Expected: PASS — all 9 tests green.

- [ ] **Step 3: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/state/graph_app_state.py
git commit -m "feat(graph-editor): implement GraphAppState registry"
```

---

### Task 5: Re-export public API and verify lint/type baseline

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/__init__.py`

- [ ] **Step 1: Add public re-exports to `__init__.py`**

Append the following imports below the `Library` class (the file already exists from Task 1; keep the existing `@library` decorated class and add re-exports above it for the public surface):

Open `barn/haybale-graph-editor/haybale_graph_editor/__init__.py` and replace the module-level docstring + imports block with this expanded form, keeping the `Library` class definition exactly as written in Task 1:

```python
"""haybale-graph-editor: graph editor library for Haywire.

Provides the GraphContainer protocol, GraphAppState registry, and
GraphEditor surface. Decoupled from any specific graph source — source
libraries register their containers, this library renders them.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.state import LibraryStateRegistry
from haywire.ui.editor.registry import EditorTypeRegistry

# Public API re-exports
from haybale_graph_editor.protocols import GraphContainer
from haybale_graph_editor.state.graph_app_state import GraphAppState

__all__ = ["GraphContainer", "GraphAppState", "Library"]
```

(Keep the `@library(...)` decorated `Library` class definition below `__all__` exactly as it was.)

- [ ] **Step 2: Run lint + type-check on the new library (baseline; should be clean)**

Run:
```bash
uv run ruff check barn/haybale-graph-editor
uv run mypy barn/haybale-graph-editor/haybale_graph_editor
```
Expected: zero errors. If mypy reports issues, the new code has them — fix before continuing.

- [ ] **Step 3: Run the full graph_editor test directory**

Run: `uv run pytest tests/graph_editor -v`
Expected: PASS — all tests from Tasks 2 + 3 green.

- [ ] **Step 4: Run the full test suite to confirm nothing else broke**

Run: `uv run pytest -m "not integration"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/__init__.py
git commit -m "feat(graph-editor): re-export public API (GraphContainer, GraphAppState)"
```

---

### Task 6: Verify library integration via app boot smoke test

**Files:**
- Create: `tests/graph_editor/test_library_integration.py`

- [ ] **Step 1: Write integration smoke test**

```python
"""Smoke test: GraphAppState appears in app_data after library load.

Marks the boundary where the new library is wired into the framework's
discovery + state-container lifecycle. Mirrors the pattern used in
``tests/haystack/test_haystack_state.py`` — see that file for the
canonical setup if this test needs deeper assertions later.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(
    reason="Stub — flesh out using existing app-boot integration patterns from tests/haystack"
)
def test_graph_app_state_loads_via_library_system(tmp_path):
    """Booting HaywireApp with haybale-graph-editor enabled puts
    GraphAppState into app_data.

    Contract:
      - workspace_root = tmp_path
      - HaywireApp constructed; library system discovers
        haybale-graph-editor via entry-points and runs
        Library.register_components()
      - LibraryStateContainer holds an instance of GraphAppState whose
        on_enable has fired (the default no-op is fine)
      - context.app_data[GraphAppState] is the same instance
    """
```

- [ ] **Step 2: Verify it runs (skipped is acceptable for this checkpoint)**

Run: `uv run pytest tests/graph_editor/test_library_integration.py -v`
Expected: 1 test SKIPPED (not failed).

- [ ] **Step 3: Commit**

```bash
git add tests/graph_editor/test_library_integration.py
git commit -m "test(graph-editor): stub integration smoke test for library boot"
```

---

## Stage B — Rename `entry_id` → `binding_id` in haystack

This stage is mechanical. Run it as a single pass with care: `entry_id` appears both as a property name on `GraphEntry` and as a *parameter name* on `HaystackState.get_by_id(entry_id)` — the latter is fine to rename too. **Do NOT rename `HaystackTeardown.entry_ids`** — that's a frozen signal payload field; renaming would break cross-session compatibility and is out of scope.

### Task 7: Rename `entry_id` → `binding_id` on `GraphEntry`

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/graph_entry.py`
- Modify: `tests/haystack/test_graph_entry.py`

- [ ] **Step 1: Update the failing test side first — write the new assertions**

Open `tests/haystack/test_graph_entry.py` and replace every occurrence of `.entry_id` with `.binding_id` in test method bodies and docstrings. (Run `grep -n "entry_id" tests/haystack/test_graph_entry.py` to enumerate.)

- [ ] **Step 2: Run tests to verify they fail (the property doesn't exist yet)**

Run: `uv run pytest tests/haystack/test_graph_entry.py -v`
Expected: FAIL with `AttributeError: 'GraphEntry' object has no attribute 'binding_id'`

- [ ] **Step 3: Rename the property on `GraphEntry`**

In `barn/haybale-haystack/haybale_haystack/graph_entry.py`, rename the `entry_id` property to `binding_id`:

```python
    @property
    def binding_id(self) -> str:
        """Stable identifier within the Haystack's ``_entries`` dict.

        For saved graphs this is ``str(path)``; for unsaved graphs it is the
        synthetic ``__unsaved_N__`` token set at creation time. Updates
        automatically when :attr:`path` is assigned on save-as or rename.

        Also serves as this entry's key in
        :class:`haybale_graph_editor.state.GraphAppState`.
        """
        return str(self.path) if self.path is not None else self._unsaved_id
```

(The docstring's mention of `GraphAppState` is forward-looking; the registry participation is added in Task 11. Wording is correct now.)

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest tests/haystack/test_graph_entry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/graph_entry.py tests/haystack/test_graph_entry.py
git commit -m "refactor(haystack): rename GraphEntry.entry_id -> binding_id"
```

---

### Task 8: Propagate the rename through `HaystackState`

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`

- [ ] **Step 1: Grep call sites inside the file**

Run: `grep -n "entry_id\|entry\.entry_id" barn/haybale-haystack/haybale_haystack/state/haystack_state.py`

Expected: ~15 occurrences. Most are local variables named `entry_id` and `entry.entry_id` reads.

- [ ] **Step 2: Replace `.entry_id` reads (property accesses on GraphEntry)**

In `haystack_state.py`, replace every `entry.entry_id` with `entry.binding_id` and every `e.entry_id` (where `e` is an entry loop variable) with `e.binding_id`.

Note: **leave the public method `get_by_id(entry_id: str)` parameter alone** in this task — it's a parameter name, not a property access. (Task 9 covers the parameter rename, kept separate so a bisect can isolate breakage.)

- [ ] **Step 3: Rename local variables `entry_id` → `binding_id` where they hold an entry's id**

The variable `entry_id` is used as a synthetic-id holder in `create_new` (e.g. `entry_id = f"__unsaved_{counter}__"`) and as a loop variable elsewhere. Rename every local `entry_id` → `binding_id` within `haystack_state.py`. (Skip the public parameter `get_by_id(entry_id: str)`.)

- [ ] **Step 4: Run haystack tests**

Run: `uv run pytest tests/haystack -v`
Expected: PASS (tests still reference `.entry_id` on entries — but Task 7 already migrated those).

If any test fails due to a leftover `.entry_id`, grep `tests/haystack` for stragglers and update.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/state/haystack_state.py
git commit -m "refactor(haystack): propagate binding_id rename through HaystackState"
```

---

### Task 9: Rename `HaystackState.get_by_id` parameter and update all callers

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`
- Modify: `barn/haybale-haystack/haybale_haystack/editors/graph_editor.py`
- Modify: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py`
- Modify: `barn/haybale-haystack/haybale_haystack/panels/file_browser/open_in_haystack.py`
- Modify: `tests/haystack/test_haystack_state.py`
- Modify: `tests/studio/test_haystack_editor_remove.py`
- Modify: `tests/studio/test_graph_editor_on_focus.py`

- [ ] **Step 1: Rename the parameter in `haystack_state.py`**

```python
    def get_by_id(self, binding_id: str) -> Optional[GraphEntry]:
        return self._entries.get(binding_id)
```

- [ ] **Step 2: Audit all callers**

Run: `grep -rn "get_by_id" barn/ tests/ | grep -v __pycache__`

Expected callers include lines in `editors/graph_editor.py:112,242,245`, `editors/haystack_editor.py` (multiple), and several test files. For each caller, if it uses `entry_id=` as a keyword argument, rename to `binding_id=`. Positional calls need no change.

- [ ] **Step 3: Audit references in tests**

```bash
grep -rn "entry_id" tests/ | grep -v __pycache__
```

Update every reference. Note: tests for `HaystackTeardown.entry_ids` (a signal field) stay unchanged.

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -m "not integration"`
Expected: PASS.

- [ ] **Step 5: Run lint + type-check on haystack**

Run:
```bash
uv run ruff check barn/haybale-haystack
uv run mypy barn/haybale-haystack/haybale_haystack
```
Expected: same noise level as before the carve-out started — anything new is from this task and must be fixed.

- [ ] **Step 6: Commit**

```bash
git add -u barn/ tests/
git commit -m "refactor(haystack): rename get_by_id parameter and update all callers"
```

---

### Task 10: Snapshot full-suite green checkpoint

**Files:** none — verification only.

- [ ] **Step 1: Run unit tests**

Run: `uv run pytest -m unit -v`
Expected: PASS.

- [ ] **Step 2: Run non-integration suite**

Run: `uv run pytest -m "not integration"`
Expected: PASS.

- [ ] **Step 3: Run lint + format check + type-check on touched packages**

Run:
```bash
uv run ruff check barn/haybale-haystack barn/haybale-graph-editor tests
uv run ruff format --check barn/haybale-haystack barn/haybale-graph-editor tests
uv run mypy barn/haybale-haystack/haybale_haystack barn/haybale-graph-editor/haybale_graph_editor
```
Expected: clean. This is a checkpoint — fix anything that's regressed before moving to Stage C.

- [ ] **Step 4: Tag checkpoint (no commit; this is a sanity sweep)**

If something is broken, stop and fix. Do not move to Stage C with red tests.

---

## Stage C — `GraphEntry.save()` + `HaystackState` participates in `GraphAppState`

### Task 11: Add the `haystack` back-ref to `GraphEntry`

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/graph_entry.py`
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py` (constructor call sites)
- Modify: `tests/haystack/test_graph_entry.py`

- [ ] **Step 1: Write failing test for `entry.haystack` reference**

In `tests/haystack/test_graph_entry.py`, add:

```python
def test_graph_entry_holds_haystack_back_reference():
    """GraphEntry carries a reference to its owning HaystackState.

    Used by GraphEntry.save() to delegate persistence back. The
    reference is required (kw-only) on construction; tests use a
    sentinel object since the contract is only that it round-trips.
    """
    from haybale_haystack.graph_entry import GraphEntry

    sentinel_haystack = object()
    fake_graph = object()
    fake_editor = object()

    entry = GraphEntry(
        graph=fake_graph,
        editor=fake_editor,
        haystack=sentinel_haystack,
    )
    assert entry.haystack is sentinel_haystack
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/haystack/test_graph_entry.py::test_graph_entry_holds_haystack_back_reference -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'haystack'`

- [ ] **Step 3: Add the field to `GraphEntry`**

In `barn/haybale-haystack/haybale_haystack/graph_entry.py`, update the TYPE_CHECKING block and dataclass:

```python
if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph as HaywireGraph
    from haywire.core.execution.interpreter import Interpreter
    from haywire.core.graph.editor import Editor
    from haybale_haystack.state.haystack_state import HaystackState
```

Inside `@dataclass class GraphEntry:`, add the field (kw-only, repr=False, default=None for backward compatibility during the migration; the next task will tighten it to required for all production call sites):

```python
    haystack: "Optional[HaystackState]" = field(default=None, repr=False)
```

Place it between `_unsaved_id` and the property block.

- [ ] **Step 4: Update every `GraphEntry(...)` construction in `HaystackState`**

Locate every `GraphEntry(...)` constructor call in `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`:

Run: `grep -n "GraphEntry(" barn/haybale-haystack/haybale_haystack/state/haystack_state.py`

Expected: 2 call sites (in `create_new` and `open_graph`). At each, add `haystack=self` as a keyword argument:

```python
entry = GraphEntry(graph=graph, editor=editor, path=None, _unsaved_id=binding_id, haystack=self)
```
and
```python
entry = GraphEntry(graph=graph, editor=editor, path=path, unsaved=False, haystack=self)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/haystack -v`
Expected: PASS — including the new back-ref test.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/graph_entry.py barn/haybale-haystack/haybale_haystack/state/haystack_state.py tests/haystack/test_graph_entry.py
git commit -m "feat(haystack): add haystack back-reference to GraphEntry"
```

---

### Task 12: Refactor `HaystackState.save_graph` into `_save_entry` and add `GraphAppState` rekey

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`
- Modify: `tests/haystack/test_haystack_state.py`

- [ ] **Step 1: Write failing test for `GraphAppState` participation on save-as**

In `tests/haystack/test_haystack_state.py`, add a test asserting that a save-as rekeys the `GraphAppState`. (Examine the existing test patterns at the top of `test_haystack_state.py` to mirror the fixture setup style; the test below assumes the standard haystack-state fixture.)

```python
def test_save_as_rekeys_graph_app_state(tmp_path, hs):
    """save_graph(save_as=new_path) rekeys the entry in GraphAppState."""
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    # 1. Open or create an entry. Pattern adapted from existing
    #    test_haystack_state.py setup — use whichever helper makes a
    #    fresh entry in the `hs` fixture.
    entry = hs.create_new()
    old_binding_id = entry.binding_id  # "__unsaved_1__" or similar

    # 2. Hand-register into a GraphAppState. In production, HaystackState
    #    does this automatically (Task 13). For this test we exercise
    #    the rekey logic in isolation.
    gas = GraphAppState()
    gas.register(entry)
    # Wire the registry onto the state so _save_entry can find it.
    hs._graph_app_state = gas   # private hook used by Task 13's impl

    new_path = tmp_path / "renamed.haywire"

    success = hs.save_graph(entry, save_as=new_path)
    assert success
    new_binding_id = entry.binding_id
    assert new_binding_id == str(new_path)
    assert gas.get(old_binding_id) is None
    assert gas.get(new_binding_id) is entry
```

If `hs` is not the existing fixture name, use whatever the file already uses (check the file's `conftest.py` or top of `test_haystack_state.py`).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/haystack/test_haystack_state.py::test_save_as_rekeys_graph_app_state -v`
Expected: FAIL — either the attribute doesn't exist, or the rekey doesn't happen.

- [ ] **Step 3: Wire `GraphAppState` reference into `HaystackState`**

In `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`, inside `__init__`:

```python
        # Reference to the shared graph registry; populated in on_enable.
        # Direct attribute (not in app_data dict) for fast access from
        # save / open / remove hot paths.
        self._graph_app_state: "Optional[GraphAppState]" = None
```

Add the type-checking import at the top of the file:

```python
if TYPE_CHECKING:
    from haybale_graph_editor.state.graph_app_state import GraphAppState
```

Update `on_enable` to populate the reference:

```python
    def on_enable(self) -> None:
        """Resolve ambient dependencies; rehydrate from settings."""
        from haywire.core.di.context import (
            get_app_state_container,
            get_library_state_container,
            get_node_factory,
            get_session_manager,
            get_workspace_root,
        )
        from haybale_graph_editor.state.graph_app_state import GraphAppState

        self._session_manager = get_session_manager()
        self._workspace_root = get_workspace_root()
        self._node_factory = get_node_factory()
        self._library_state_container = get_library_state_container()

        # Acquire the shared graph registry. Order is safe: graph_editor
        # library is listed in our dependencies, so its AppState is
        # instantiated before ours.
        container = get_app_state_container()
        self._graph_app_state = container.get(GraphAppState)

        # ... rest of on_enable unchanged (rehydrate from last_haystack_name)
```

**Sanity check:** verify the symbol `get_app_state_container` (or its equivalent) exists in `haywire.core.di.context`. Run:

```bash
grep -n "def get_" packages/haywire-core/src/haywire/core/di/context.py | head -20
```

If the symbol is named differently (e.g. `get_app_data` or accessed via `get_library_state_container().app_state(...)`), use that instead. The principle is: we need to fetch the live `GraphAppState` instance from the framework. Inspect `LibraryStateContainer` if no direct DI accessor exists.

- [ ] **Step 4: Refactor `save_graph` to call `_save_entry`**

Rename the current body of `save_graph` to a new private method `_save_entry`, and add `GraphAppState` rekey:

```python
    def save_graph(self, entry: GraphEntry, save_as: Optional[Path] = None) -> bool:
        """Public alias preserved for backward compatibility.

        Most callers should use ``entry.save(save_as=...)`` now; this
        method routes to the same implementation. Returns True on
        successful save (legacy bool contract); ``entry.save`` returns
        the new binding_id string on rename for the
        :class:`GraphContainer` protocol.
        """
        return self._save_entry(entry, save_as=save_as) is not False

    def _save_entry(self, entry: GraphEntry, save_as: Optional[Path] = None):
        """Internal save implementation.

        Returns:
            - ``False`` on failure
            - ``None`` on save-with-no-rename (success, identity unchanged)
            - ``str`` (new binding_id) on save-as that renamed the entry

        Side effects on success:
            - writes the graph TOML to disk
            - clears ``entry.unsaved``
            - on rename: rekeys ``self._entries`` AND
              ``self._graph_app_state``
            - broadcasts ``GraphDataMutated``
            - marks haystack dirty
        """
        target = save_as or entry.path
        if target is None:
            return False  # untitled with no explicit path

        success = entry.graph.save_to_file(str(target))
        if not success:
            return False

        entry.unsaved = False
        renamed_to: Optional[str] = None

        if save_as is not None and save_as != entry.path:
            old_binding_id = entry.binding_id
            self._entries.pop(old_binding_id, None)
            entry.path = save_as
            self._entries[entry.binding_id] = entry
            if self._graph_app_state is not None:
                self._graph_app_state.rekey(old_binding_id, entry.binding_id)
            renamed_to = entry.binding_id

        self._broadcast_data_mutated()
        self._mark_haystack_dirty()
        return renamed_to  # None when no rename; str on rename
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/haystack/test_haystack_state.py::test_save_as_rekeys_graph_app_state -v`
Expected: PASS.

- [ ] **Step 6: Run the full haystack test suite**

Run: `uv run pytest tests/haystack tests/studio -v`
Expected: PASS — the `save_graph` public method preserves its bool contract for existing callers.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-haystack/haybale_haystack/state/haystack_state.py tests/haystack/test_haystack_state.py
git commit -m "feat(haystack): rekey GraphAppState on save-as via _save_entry refactor"
```

---

### Task 13: Add `GraphEntry.save()` + register/unregister/rename hooks

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/graph_entry.py`
- Modify: `barn/haybale-haystack/haybale_haystack/state/haystack_state.py`
- Modify: `tests/haystack/test_graph_entry.py`
- Modify: `tests/haystack/test_haystack_state.py`

- [ ] **Step 1: Write failing test for `GraphEntry.save()`**

In `tests/haystack/test_graph_entry.py`, add:

```python
def test_graph_entry_save_delegates_to_haystack(monkeypatch):
    """entry.save() calls haystack._save_entry(self, save_as=...).

    The method is a thin shim — most logic lives in HaystackState.
    """
    from haybale_haystack.graph_entry import GraphEntry

    captured = {}

    class _FakeHaystack:
        def _save_entry(self, entry, save_as=None):
            captured["entry"] = entry
            captured["save_as"] = save_as
            return None  # no rename

    fake = _FakeHaystack()
    entry = GraphEntry(graph=object(), editor=object(), haystack=fake)
    result = entry.save()

    assert captured["entry"] is entry
    assert captured["save_as"] is None
    assert result is None


def test_graph_entry_save_propagates_new_binding_id(monkeypatch):
    """When _save_entry returns a new binding_id (rename case),
    entry.save() returns it untouched."""
    from haybale_haystack.graph_entry import GraphEntry

    class _FakeHaystack:
        def _save_entry(self, entry, save_as=None):
            return "new-id-from-save-as"

    entry = GraphEntry(graph=object(), editor=object(), haystack=_FakeHaystack())
    from pathlib import Path

    assert entry.save(save_as=Path("/tmp/x.haywire")) == "new-id-from-save-as"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/haystack/test_graph_entry.py -k save -v`
Expected: FAIL with `AttributeError: 'GraphEntry' object has no attribute 'save'`

- [ ] **Step 3: Add the `save()` method to `GraphEntry`**

In `barn/haybale-haystack/haybale_haystack/graph_entry.py`, add (below `stop_execution`, above end of class):

```python
    def save(self, save_as: "Optional[Path]" = None) -> "Optional[str]":
        """Persist this entry via its owning HaystackState.

        Implements the :class:`GraphContainer` protocol's save method.
        Delegates to ``HaystackState._save_entry`` so haystack-internal
        bookkeeping (signals, dirty flag, GraphAppState rekey) all run.

        Returns the new ``binding_id`` if the save-as renamed the entry,
        else ``None``. Failure is signalled by the entry's ``unsaved``
        flag remaining True (the haystack also returns False internally;
        we coerce to None for the protocol contract).
        """
        if self.haystack is None:
            return None  # detached entry — no place to save to
        result = self.haystack._save_entry(self, save_as=save_as)
        if result is False:
            return None
        return result  # None (no rename) or str (new binding_id)
```

Make sure `Optional` and `Path` are imported. `Path` is already imported; `Optional` is also already imported.

- [ ] **Step 4: Add `register`/`unregister` hooks in `HaystackState` lifecycle methods**

In `create_new`, immediately after `self._entries[entry.binding_id] = entry` and `self._subscribe_validation(entry)`, add:

```python
        if self._graph_app_state is not None:
            self._graph_app_state.register(entry)
```

In `open_graph`, in the same position (after entry construction and registration in `_entries`), add the same two lines.

In `remove_entry`, immediately before the `del self._entries[entry.binding_id]` line:

```python
        if self._graph_app_state is not None:
            self._graph_app_state.unregister(entry.binding_id)
```

In `rename_graph`, after the `_entries` rekey and before the broadcast, add a corresponding rekey:

```python
        if self._graph_app_state is not None:
            self._graph_app_state.rekey(old_binding_id, entry.binding_id)
```

(Note `rename_graph` uses a local `old_id` today; update its local rename to `old_binding_id` for consistency with Tasks 8 and 12.)

In `on_disable` (teardown), before clearing `self._entries`, unregister each:

```python
        if self._graph_app_state is not None:
            for binding_id in list(self._entries.keys()):
                self._graph_app_state.unregister(binding_id)
```

- [ ] **Step 5: Write failing test asserting full lifecycle participation**

In `tests/haystack/test_haystack_state.py`, add:

```python
def test_open_graph_registers_in_graph_app_state(tmp_path, hs):
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    gas = GraphAppState()
    hs._graph_app_state = gas

    graph_path = tmp_path / "graphs" / "g.haywire"
    graph_path.parent.mkdir(parents=True)
    # Use an existing test helper to create a minimal valid .haywire file,
    # OR copy from another existing test in this file that opens a graph.
    # Pattern: look for `hs.open_graph(...)` calls already used in this
    # file and reuse their fixture path.

    entry = hs.open_graph(graph_path)
    assert gas.get(entry.binding_id) is entry


def test_remove_entry_unregisters_from_graph_app_state(tmp_path, hs):
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    gas = GraphAppState()
    hs._graph_app_state = gas

    entry = hs.create_new()
    bid = entry.binding_id
    assert gas.get(bid) is entry

    hs.remove_entry(entry)
    assert gas.get(bid) is None


def test_create_new_registers_in_graph_app_state(hs):
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    gas = GraphAppState()
    hs._graph_app_state = gas

    entry = hs.create_new()
    assert gas.get(entry.binding_id) is entry
```

(If creating a `.haywire` fixture in `test_open_graph_registers_in_graph_app_state` is non-trivial, examine the surrounding tests in this file — they likely already have a fixture or helper. Use it.)

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/haystack -v`
Expected: PASS — back-ref test from Task 11 still green; new lifecycle tests green; existing tests untouched.

- [ ] **Step 7: Run lint + type-check**

Run:
```bash
uv run ruff check barn/haybale-haystack
uv run mypy barn/haybale-haystack/haybale_haystack
```
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add -u barn/haybale-haystack tests/haystack
git commit -m "feat(haystack): GraphEntry.save() + GraphAppState lifecycle participation"
```

---

## Stage D — Move `GraphEditor` to `haybale-graph-editor`

### Task 14: Add `haybale-graph-editor` as a dependency of `haybale-haystack`

**Files:**
- Modify: `barn/haybale-haystack/pyproject.toml`
- Modify: `barn/haybale-haystack/haybale_haystack/__init__.py`

- [ ] **Step 1: Add to `dependencies` and `[tool.uv.sources]` in haystack's pyproject.toml**

Edit `barn/haybale-haystack/pyproject.toml` so the `dependencies` list includes the new library:

```toml
dependencies = [
    "haywire-core>=0.1.0",
    "haywire-studio>=0.1.0",
    "haybale-core>=0.1.0",
    "haybale-studio>=0.1.0",
    "haybale-graph-editor>=0.1.0",
]
```

In `[tool.uv.sources]`, add:

```toml
haybale-graph-editor = { workspace = true }
```

- [ ] **Step 2: Declare the library dependency in `@library`**

In `barn/haybale-haystack/haybale_haystack/__init__.py`, update the `dependencies` argument of the `@library` decorator:

```python
    dependencies=["haybale_core", "haybale_studio", "graph_editor"],
```

(Use the library `id`, which is the string after `id=` in each `@library(...)` block — `"graph_editor"` for the new one. Verify by checking `barn/haybale-graph-editor/haybale_graph_editor/__init__.py` from Task 1, where we set `id="graph_editor"`.)

- [ ] **Step 3: Resync workspace**

Run: `uv sync`
Expected: completes; resolves the new dependency cleanly.

- [ ] **Step 4: Run the full suite to confirm no regression**

Run: `uv run pytest -m "not integration"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-haystack/pyproject.toml barn/haybale-haystack/haybale_haystack/__init__.py
git commit -m "build(haystack): depend on haybale-graph-editor"
```

---

### Task 15: Move `graph_editor.py` to the new library and adapt it to `GraphAppState`

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py`
- Delete: `barn/haybale-haystack/haybale_haystack/editors/graph_editor.py`

- [ ] **Step 1: Copy the file to its new location**

```bash
cp barn/haybale-haystack/haybale_haystack/editors/graph_editor.py \
   barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py
```

- [ ] **Step 2: Edit the moved file — rewrite all `HaystackState` references**

Open `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py` and apply these edits:

**(a) Imports.** Replace:

```python
from haybale_haystack.state.haystack_state import HaystackState
```

with:

```python
from haybale_graph_editor.state.graph_app_state import GraphAppState
from haybale_graph_editor.protocols import GraphContainer
```

Remove the `from haybale_haystack.graph_entry import GraphEntry` line in the `TYPE_CHECKING` block. Replace any `"GraphEntry"` type annotation with `"GraphContainer"`.

**(b) Replace `HaystackState`-typed lookups with `GraphAppState`-typed lookups, and call `container.save(...)` instead of `haystack_state.save_graph(...)`.**

Find every occurrence of:

```python
haystack_state = context.app_data.get(HaystackState)
```

Replace with:

```python
graph_app_state = context.app_data.get(GraphAppState)
```

Find:

```python
entry = haystack_state.get_by_id(binding_id)
```

Replace with:

```python
entry = graph_app_state.get(binding_id) if graph_app_state is not None else None
```

In `_get_entry`:

```python
    def _get_entry(self, context: "SessionContext") -> Optional["GraphContainer"]:
        """Look up this tab's GraphContainer from GraphAppState via binding_id."""
        if self.wrapper._binding_id is None:
            return None
        graph_app_state = context.app_data.get(GraphAppState)
        if graph_app_state is None:
            return None
        return graph_app_state.get(self.wrapper._binding_id)
```

**(c) Rewrite the save path.** Find `_save_graph`:

```python
    def _save_graph(self, context: "SessionContext") -> None:
        entry = self._get_entry(context)
        if entry is None:
            ui.notify("No graph to save", type="warning")
            return

        if entry.path is not None:
            # Already has a path — call container.save()
            new_id = entry.save()
            # save() returns None on no-rename; the editor doesn't repayload here
            # because path saves don't change binding_id
            if not entry.unsaved:
                ui.notify(f"Saved: {entry.path.name}", type="positive", position="top-right")
                self._update_header(context)
                session = context.session
                if session is not None:
                    session.publish(GraphDataMutated())
            else:
                ui.notify("Save failed", type="negative", position="top-right")
            return

        # No path yet — open the Save-As dialog
        app = context.app
        self._open_save_as_dialog(app, entry)
```

(Note: the old code routed through `haystack_state.save_graph(entry)` returning a bool. The new code asks the container directly and reads `entry.unsaved` to detect failure. This matches the `GraphContainer.save` contract — failure leaves `unsaved` true.)

Find `_do_save_as` and rewrite the post-save section. The old code was:

```python
        old_payload = self.wrapper._binding_id
        success = haystack_state.save_graph(entry, save_as=save_path)
        if success:
            ...
            new_payload = entry.entry_id   # already renamed binding_id in Tasks 7/9
            if old_payload != new_payload:
                self.wrapper.repayload(new_payload, new_label=entry.display_name)
            ...
```

Replace with:

```python
        old_binding_id = self.wrapper._binding_id
        new_binding_id = entry.save(save_as=save_path)
        if new_binding_id is not None or not entry.unsaved:
            context.data[EditState].active_graph_path = save_path
            session = context.session
            if new_binding_id is not None and old_binding_id != new_binding_id:
                self.wrapper.repayload(new_binding_id, new_label=entry.display_name)
            if session:
                session.publish(ActiveGraphMoved())
                session.publish(GraphDataMutated())
            ui.notify(f"Saved: {save_path.name}", type="positive", position="top-right")
            dialog.close()
        else:
            ui.notify("Save failed — check the path and try again", type="negative")
```

Also remove the `_do_save_as` line `haystack_state = context.app_data.get(HaystackState)` and the `if haystack_state is None: ... return` block — they're no longer needed because we go through the container.

**(d) Update the module docstring.** Replace `from haybale_haystack...Haystack...` references in docstrings with neutral wording. The "project_state in context.metadata" doc block at the top can stay — it describes app-level state, not haystack-specific state.

- [ ] **Step 3: Delete the old file**

```bash
rm barn/haybale-haystack/haybale_haystack/editors/graph_editor.py
```

- [ ] **Step 4: Update imports in `haybale-haystack` call sites**

In `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py`, change:

```python
from haybale_haystack.editors.graph_editor import GraphEditor
```

to:

```python
from haybale_graph_editor.editors.graph_editor import GraphEditor
```

In `barn/haybale-haystack/haybale_haystack/panels/file_browser/open_in_haystack.py`, change:

```python
from haybale_haystack.editors.graph_editor import GraphEditor
```

to:

```python
from haybale_graph_editor.editors.graph_editor import GraphEditor
```

(There's only one such import inside `_do_open` at line ~55.)

- [ ] **Step 5: Update the test import path**

In `tests/studio/test_graph_editor_on_focus.py`, change:

```python
from haybale_haystack.editors.graph_editor import GraphEditor
```

to:

```python
from haybale_graph_editor.editors.graph_editor import GraphEditor
```

Then audit the rest of the file for `HaystackState` references — the test's fake setup uses a fake haystack-state object that satisfies the editor's lookup. Now the editor reads `app_data[GraphAppState]` instead, so the fake context's `app_data.get(...)` needs to return a `GraphAppState` whose `get(...)` returns the fake entry. Update the test fixture accordingly:

Open `tests/studio/test_graph_editor_on_focus.py`. Locate the helper(s) that build the fake `context` or `app_data`. Where the current code returns a fake-`HaystackState` whose `get_by_id` returns a `_FakeEntry`, change it to return a fake-`GraphAppState` whose `get` returns the same `_FakeEntry`. Also ensure `_FakeEntry` has a `binding_id` attribute (it has `entry_id` today, renamed in Task 7).

Concretely the fake-entry's interface used by `on_focus` is: `entry.graph`, `entry.path`. The editor calls `graph_app_state.get(binding_id)`. So:

```python
class _FakeGraphAppState:
    def __init__(self, entry_by_id):
        self._entries = entry_by_id

    def get(self, binding_id):
        return self._entries.get(binding_id)
```

And wherever the test mocked `context.app_data.get(HaystackState)`, mock `context.app_data.get(GraphAppState)` instead.

- [ ] **Step 6: Update `barn/haybale-studio/haybale_studio/editors/file_browser_menu/actions.py`**

Open the file. There's a docstring at the top referencing `GraphEditor` — make it neutral or update it to reference the new library. (Code change is unnecessary; this is documentation hygiene.)

```bash
grep -n "GraphEditor" barn/haybale-studio/haybale_studio/editors/file_browser_menu/actions.py
```

Update each mention so the prose stays accurate.

- [ ] **Step 7: Run lint + type-check on touched packages**

```bash
uv run ruff check barn/haybale-graph-editor barn/haybale-haystack barn/haybale-studio
uv run mypy barn/haybale-graph-editor/haybale_graph_editor barn/haybale-haystack/haybale_haystack barn/haybale-studio/haybale_studio
```

Expected: clean. Fix any new errors before continuing.

- [ ] **Step 8: Run the full suite**

```bash
uv run pytest -m "not integration"
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add -u barn/ tests/
git commit -m "feat(graph-editor): move GraphEditor to haybale-graph-editor, route via GraphAppState"
```

---

### Task 16: Manual smoke test — launch the app, open a graph, save, save-as

**Files:** none — manual verification.

- [ ] **Step 1: Launch the app**

Run: `uv run haywire`

- [ ] **Step 2: Open an existing graph**

In the app, use the file browser to right-click a `.haywire` file → "Open in Haystack". The graph should appear in `GraphEditor` exactly as before. Header should show the file name.

- [ ] **Step 3: Make a change and save**

Add a node or move one. The tab should show a dirty indicator (`●`). Click the save button. Header dirty indicator should clear; the file on disk should update (verify with `stat path/to/file.haywire`).

- [ ] **Step 4: Save-As**

For an unsaved graph (use "New" in the Haystack panel), click save. The Save-As dialog opens. Save under a new name. Verify:
- the tab label updates to the new filename
- the file appears on disk
- closing and re-opening the file restores the graph

- [ ] **Step 5: Cross-session**

Open the app in a second browser tab (NiceGUI shares state). The new file should appear in the second session's Haystack panel. Open it; both sessions show the same graph.

- [ ] **Step 6: Workspace persistence**

Quit the app (`Ctrl+C` in the terminal). Restart with `uv run haywire`. The graph that was open should still be open in the same slot. Header and dirty state are correct.

If any of these manual checks fail, the carve-out is incomplete — stop and diagnose before continuing. No commit (smoke check only).

---

## Stage E — Docs and codemap

### Task 17: Update glossary, editor-canon, and codemap

**Files:**
- Modify: `docs/reference/glossary.md`
- Modify: `docs/components/editors/editor-canon.md`
- Modify: `.codemap/INDEX.md`
- Create: `.codemap/modules/haybale-graph-editor.md`
- Modify: `.codemap/modules/haybale-haystack.md`

- [ ] **Step 1: Update `docs/reference/glossary.md` — add `GraphContainer` and `GraphAppState`**

In the "Graph Management" table (around line 141), insert two new rows after the existing `Haystack` row:

```markdown
| **GraphContainer** | A protocol implemented by anything that can host a graph in **GraphEditor**: requires `binding_id`, `editor`, `path`, `unsaved`, `display_name`, and `save()`. **GraphEntry** is the haystack-flavoured implementation. See [haybale-graph-editor](../../barn/haybale-graph-editor/) | Graph host, graph holder |
| **GraphAppState** | The app-wide registry mapping `binding_id` → **GraphContainer**. Source libraries (haystack, future cloud-graph libraries) `register` / `unregister` / `rekey` their containers here; **GraphEditor** reads from it on every render. Lives at `app_data[GraphAppState]`. | Graph registry, graph index |
```

In the same file, locate the `binding_id` description (around line 210) and append one sentence:

> The same string is the key used in `GraphAppState`, the workspace-persisted identity in `slot.to_snapshot`, and the disambiguator in `EditorWrapper.editor_binding_id`.

- [ ] **Step 2: Update `docs/components/editors/editor-canon.md`**

Open the file, search for `GraphEditor`, and update any mention of "lives in haybale-haystack" to "lives in haybale-graph-editor". Add a sentence explaining: *"GraphEditor reads its container from `app_data[GraphAppState]`. To host a graph in GraphEditor, your library must (a) implement the `GraphContainer` protocol and (b) register every open container into `GraphAppState`."*

- [ ] **Step 3: Update `.codemap/INDEX.md`**

In the "Module Index" table, add a row for the new library (alphabetical order with the other `haybale-*`):

```markdown
| haybale-graph-editor | Visual graph editor plugin: GraphContainer protocol, GraphAppState registry, GraphEditor surface | [→ modules/haybale-graph-editor.md](modules/haybale-graph-editor.md) |
```

- [ ] **Step 4: Create `.codemap/modules/haybale-graph-editor.md`**

```markdown
# Module: haybale-graph-editor

**Purpose:** Provides the visual graph editor surface (`GraphEditor`) decoupled from any specific graph source. Defines the `GraphContainer` protocol that source libraries implement, and the `GraphAppState` registry that maps `binding_id` → `GraphContainer` so the editor can resolve its tab to a live container.

**Tier:** plugin (haybale-*)

## Always load

- [haybale_graph_editor/__init__.py](../../barn/haybale-graph-editor/haybale_graph_editor/__init__.py) — Library decorator, public re-exports
- [haybale_graph_editor/protocols.py](../../barn/haybale-graph-editor/haybale_graph_editor/protocols.py) — `GraphContainer` Protocol
- [haybale_graph_editor/state/graph_app_state.py](../../barn/haybale-graph-editor/haybale_graph_editor/state/graph_app_state.py) — `GraphAppState` registry

## Load on demand

- [haybale_graph_editor/editors/graph_editor.py](../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py) — `GraphEditor` (canvas + chrome + save-as dialog)

## Depends on

- `haywire-core` (BaseEditor, AppState, Reveal/Close signals, session context)
- `haywire-studio` (workspace metadata for save paths)
- `haybale-core` (no direct API — peer plugin)
- `haybale-studio` (GraphCanvasManager, EditState)

## Consumed by

- `haybale-haystack` (registers `GraphEntry` containers; reveals `GraphEditor` for haystack graphs)
- Future graph-management libraries by the same pattern

## Key invariants

- `GraphAppState` holds *references* only — owning libraries control lifecycle
- `binding_id` is the persistent identifier (workspace-serializable); the container is the runtime cache
- The library does not know which source produced any given container
```

- [ ] **Step 5: Update `.codemap/modules/haybale-haystack.md`**

Open the file. In the "Depends on" section, add:

```markdown
- `haybale-graph-editor` (GraphAppState registry, GraphEditor surface)
```

In the "Consumed by" or equivalent section, remove any mention of "owns GraphEditor" — it doesn't anymore.

- [ ] **Step 6: Commit**

```bash
git add docs/reference/glossary.md docs/components/editors/editor-canon.md .codemap
git commit -m "docs(graph-editor): update glossary, editor-canon, and codemap for carve-out"
```

---

### Task 18: Final verification pass

**Files:** none — verification only.

- [ ] **Step 1: Run unit tests**

Run: `uv run pytest -m unit`
Expected: PASS.

- [ ] **Step 2: Run the full non-integration suite**

Run: `uv run pytest -m "not integration"`
Expected: PASS.

- [ ] **Step 3: Run integration tests for haystack and graph_editor**

Run: `uv run pytest tests/haystack tests/graph_editor tests/studio -v`
Expected: PASS (some skip markers are fine; no failures).

- [ ] **Step 4: Lint and type-check the entire touched surface**

```bash
uv run ruff check barn/haybale-graph-editor barn/haybale-haystack barn/haybale-studio tests
uv run ruff format --check barn/haybale-graph-editor barn/haybale-haystack tests
uv run mypy barn/haybale-graph-editor/haybale_graph_editor \
            barn/haybale-haystack/haybale_haystack \
            barn/haybale-studio/haybale_studio
```

Expected: clean.

- [ ] **Step 5: Grep for stragglers**

Confirm no source code references the old paths:

```bash
grep -rn "from haybale_haystack.editors.graph_editor" barn/ tests/ packages/ | grep -v __pycache__
```

Expected: zero matches.

```bash
grep -rn "\.entry_id" barn/haybale-haystack barn/haybale-graph-editor | grep -v __pycache__ | grep -v "entry_ids"
```

Expected: zero matches (signal field `entry_ids` is allowed; standalone `entry_id` is not).

- [ ] **Step 6: Manual smoke (repeat Task 16 once more after all stages)**

Run the app, open a graph, save, save-as, quit, restart. Everything green? Carve-out is done.

- [ ] **Step 7: No final commit needed if Steps 1–6 are clean**

The carve-out is complete. Total commits: ~14 across 18 tasks (some tasks bundle test+impl per step).

---

## Spec coverage check

- **Q1A (multiple graph-management libraries coexist):** Tasks 4 + 13 + 15 — GraphAppState is the shared registry; haystack registers; editor reads via the registry without knowing the source.
- **Q2A (binding_id persistent, bound_object runtime):** Task 4 implements the registry; no haywire-core change.
- **Q3+Q4 C (registry with metadata split):** Tasks 4 + 13 — haystack keeps its own `_entries` + haystack-specific concerns; the registry holds only `GraphContainer` references.
- **Q5 B (protocol shape includes binding_id):** Task 2 — protocols.py defines exactly the agreed signature.
- **Q6 (GraphSource lookup) dropped:** Not implemented; superseded by single shared registry.
- **Q7A (back-ref):** Tasks 11 + 13 — `GraphEntry.haystack` field + `save()` delegating to `haystack._save_entry`.
- **Q8 scope:** Tasks 1–18 cover the IN-list; haywire-core is untouched per the OUT-list.
- **Q9A (plugin tier):** Task 1 — new library under `barn/`, plugin entry point.
- **Rename `entry_id` → `binding_id` (sub-decision i):** Tasks 7 + 8 + 9.

All locked-in decisions have a corresponding task.

---

## Risks and mitigations

- **Risk:** `get_app_state_container` (or equivalent DI accessor) might not be exactly the name used in `haywire.core.di.context`. **Mitigation:** Task 12 Step 3 includes a verification grep; the worker should adjust to match the real symbol before proceeding.
- **Risk:** `tests/studio/test_graph_editor_on_focus.py` is the most heavily-coupled test (it builds a fake context, fake `HaystackState`, fake entries). **Mitigation:** Task 15 Step 5 walks through the replacement of the HaystackState mock with a GraphAppState mock. If the test still fails after that change, examine which method on the fake state is being called by `on_focus` and replicate.
- **Risk:** Save-As behaviour changes from "haystack returns bool, we re-key" to "container returns new binding_id, we re-key". **Mitigation:** Task 15 Step 2(c) shows the exact code; the integration smoke in Task 16 Step 4 verifies save-as end-to-end.
- **Risk:** `HaystackTeardown.entry_ids` field name is *not* renamed. **Mitigation:** Documented explicitly in the File Structure section above; covered by Task 18 Step 5 grep, which excludes `entry_ids`.

---

**Plan complete.**
