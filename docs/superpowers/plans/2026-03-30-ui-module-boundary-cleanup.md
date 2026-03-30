# haywire.ui / haywire-studio Module Boundary Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a clean `haywire.core → haywire.ui → haywire-studio` dependency hierarchy by removing studio-specific strings from core, consolidating session tracking, eliminating the singleton pattern from `ConsoleBridge`, and expanding the `IProjectState` protocol.

**Architecture:** Five targeted changes with no new abstractions beyond one new file (`haywire_studio/workspace/defaults.py`). Each change is independent and can be committed separately. Existing tests are updated in the same task as the code change.

**Tech Stack:** Python, NiceGUI, pytest. Run tests with `uv run pytest`. Lint with `uv run ruff check .`.

---

## File Map

| File | Action | What changes |
|---|---|---|
| `packages/haywire-core/src/haywire/ui/workspace/workspace_state.py` | Modify | Remove all `_K_*` constants; `None`-ify field defaults |
| `packages/haywire-core/src/haywire/ui/workspace/manager.py` | Modify | Add `initial_presets` param; remove `DEFAULT_PRESETS` class var |
| `packages/haywire-core/src/haywire/ui/session.py` | Modify | Drop `project_path`; accept `workspace_manager: WorkspaceManager` |
| `packages/haywire-core/src/haywire/ui/context.py` | Modify | Theme key fields → `Optional[str] = None` |
| `packages/haywire-core/src/haywire/ui/protocols.py` | Modify | Add `IGraphManager`; expand `IProjectState` |
| `packages/haywire-core/src/haywire/ui/console_bridge.py` | Modify | Remove singleton; add module-level `_bridge` + `get_bridge()` |
| `packages/haywire-studio/src/haywire_studio/workspace/__init__.py` | Create | Empty package marker |
| `packages/haywire-studio/src/haywire_studio/workspace/defaults.py` | Create | `_K_*` constants + `DEFAULT_PRESETS` dict |
| `packages/haywire-studio/src/haywire_studio/app.py` | Modify | Remove `self.sessions`; use `SessionManager`; set theme defaults; use `get_bridge()` |
| `tests/ui/test_workspace_state.py` | Modify | Update tests to use `initial_presets`; move studio-key assertions to new test file |
| `tests/ui/test_workspace_defaults.py` | Create | Tests for `DEFAULT_PRESETS` and studio key constants |

---

## Task 1: Strip `_K_*` constants from `workspace_state.py`; create `haywire_studio/workspace/defaults.py`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/workspace/workspace_state.py`
- Create: `packages/haywire-studio/src/haywire_studio/workspace/__init__.py`
- Create: `packages/haywire-studio/src/haywire_studio/workspace/defaults.py`
- Modify: `tests/ui/test_workspace_state.py`
- Create: `tests/ui/test_workspace_defaults.py`

- [ ] **Step 1: Write failing tests for `workspace_state.py` (no studio strings) and `defaults.py`**

```python
# tests/ui/test_workspace_state.py  — replace the two failing tests at the bottom of the file

def test_workspace_state_roundtrip(self):
    """Serializing then deserializing WorkspaceState fields preserves data."""
    ws = WorkspaceState(name="My WS")
    d = asdict(ws)
    assert d["name"] == "My WS"
    assert d["left"]["editor_key"] is None   # no studio strings in core
    assert d["right"]["editor_key"] is None

def test_default_workspace_state(self):
    ws = WorkspaceState()
    assert ws.name == "default"
    assert ws.left.editor_key is None        # generic — no studio strings
    assert ws.right.editor_key is None
    assert ws.middle.tabs[0].editor_key == "graph_editor"  # sensible generic default
```

```python
# tests/ui/test_workspace_defaults.py  — new file
"""Tests for haywire_studio workspace defaults."""

from haywire_studio.workspace.defaults import DEFAULT_PRESETS, _K_GRAPH_EDITOR, _K_PROPERTIES, _K_LIBRARY_BROWSER, _K_CONSOLE
from haywire.ui.workspace.workspace_state import WorkspaceState


def test_default_presets_keys_present():
    assert "Graph Editing" in DEFAULT_PRESETS
    assert "Development" in DEFAULT_PRESETS
    assert "Debugging" in DEFAULT_PRESETS


def test_default_presets_are_workspace_state_instances():
    for name, preset in DEFAULT_PRESETS.items():
        assert isinstance(preset, WorkspaceState), f"Preset '{name}' is not a WorkspaceState"


def test_studio_key_constants_have_studio_prefix():
    assert _K_GRAPH_EDITOR.startswith("studio:editor:")
    assert _K_PROPERTIES.startswith("studio:editor:")
    assert _K_LIBRARY_BROWSER.startswith("studio:editor:")
    assert _K_CONSOLE.startswith("studio:editor:")


def test_graph_editing_preset_layout():
    ws = DEFAULT_PRESETS["Graph Editing"]
    assert ws.left.editor_key == _K_LIBRARY_BROWSER
    assert ws.right.editor_key == _K_PROPERTIES
    assert ws.middle.tabs[0].editor_key == _K_GRAPH_EDITOR


def test_development_preset_has_bottom_visible():
    dev = DEFAULT_PRESETS["Development"]
    assert dev.middle.bottom_visible is True
    assert dev.middle.bottom_editor_key == _K_CONSOLE


def test_debugging_preset_left_collapsed():
    dbg = DEFAULT_PRESETS["Debugging"]
    assert dbg.left.visible is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/ui/test_workspace_state.py::TestWorkspaceStateSerialization::test_workspace_state_roundtrip tests/ui/test_workspace_state.py::TestWorkspaceStateSerialization::test_default_workspace_state tests/ui/test_workspace_defaults.py -v
```

Expected: FAIL — `test_workspace_defaults.py` module not found; the two state tests fail because defaults are still `"studio:editor:*"`.

- [ ] **Step 3: Strip `_K_*` constants from `workspace_state.py` and update field defaults**

Replace the entire `workspace_state.py` with:

```python
# packages/haywire-core/src/haywire/ui/workspace/workspace_state.py
"""
Workspace state dataclasses for the Haywire UI layout system.

WorkspaceState is serializable to JSON for persistence. Each named workspace
is a saved instance of this class. All editor_key values are full registry_key
strings (e.g. 'studio:editor:graph_editor') supplied by the host application —
this module contains no host-specific strings.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class AreaState:
    """
    State of a single area in the workspace layout.

    Attributes:
        editor_key: Full registry_key of the editor currently in this area.
        visible: Whether the area is visible/expanded.
        size: Size in pixels (width for left/right, height for bottom).
    """

    editor_key: Optional[str] = None
    visible: bool = True
    size: int = 300


@dataclass
class TabState:
    """
    State of a single tab in the middle area.

    Attributes:
        editor_key: Full registry_key of the editor in this tab.
        label: Tab display label.
        metadata: Editor-specific state (e.g., which graph is open).
    """

    editor_key: str = "graph_editor"
    label: str = "Graph"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MiddleAreaState:
    """
    State of the middle (main) area which supports tabs and a bottom split.

    Attributes:
        tabs: List of open tabs.
        active_tab_index: Which tab is currently active.
        bottom_visible: Whether the bottom split area is shown.
        bottom_size: Height of the bottom area in pixels.
        bottom_editor_key: Full registry_key of the editor in the bottom split.
    """

    tabs: List[TabState] = field(default_factory=lambda: [TabState()])
    active_tab_index: int = 0
    bottom_visible: bool = False
    bottom_size: int = 200
    bottom_editor_key: Optional[str] = None


@dataclass
class WorkspaceState:
    """
    Complete workspace configuration.

    Serializable to JSON for persistence. Each named workspace
    is a saved instance of this class.

    Attributes:
        name: Workspace name (e.g., "Graph Editing", "Development").
        left_bar_active: Full registry_key of the active activity bar editor.
        left: Left area state.
        middle: Middle area state (with tabs and bottom split).
        right: Right area state.
        right_bar_active: Full registry_key of the active context bar editor.
    """

    name: str = "default"
    left_bar_active: Optional[str] = None
    left: AreaState = field(default_factory=AreaState)
    middle: MiddleAreaState = field(default_factory=MiddleAreaState)
    right_bar_active: Optional[str] = None
    right: AreaState = field(default_factory=AreaState)
```

- [ ] **Step 4: Create `haywire_studio/workspace/__init__.py`**

```python
# packages/haywire-studio/src/haywire_studio/workspace/__init__.py
```

(Empty file — package marker only.)

- [ ] **Step 5: Create `haywire_studio/workspace/defaults.py`**

```python
# packages/haywire-studio/src/haywire_studio/workspace/defaults.py
"""
Studio-specific workspace preset defaults.

All editor registry key constants for haywire-studio editors live here.
WorkspaceManager in haywire.ui accepts these as initial_presets at construction.
"""

from typing import Dict

from haywire.ui.workspace.workspace_state import (
    WorkspaceState,
    AreaState,
    MiddleAreaState,
    TabState,
)

# Canonical registry keys for all built-in studio editors.
_K_GRAPH_EDITOR = "studio:editor:graph_editor"
_K_LIBRARY_BROWSER = "studio:editor:library_browser"
_K_LIBRARY_DETAIL = "studio:editor:library_detail"
_K_COMPONENT_DETAIL = "studio:editor:component_detail"
_K_PROPERTIES = "studio:editor:properties"
_K_CONSOLE = "studio:editor:console"
_K_FILE_BROWSER = "studio:editor:file_browser"
_K_FILE_VIEWER = "studio:editor:file_viewer"
_K_GRAPH_MANAGER = "studio:editor:graph_manager"


DEFAULT_PRESETS: Dict[str, WorkspaceState] = {
    "Graph Editing": WorkspaceState(
        name="Graph Editing",
        left_bar_active=_K_LIBRARY_BROWSER,
        left=AreaState(editor_key=_K_LIBRARY_BROWSER, visible=True, size=250),
        middle=MiddleAreaState(
            tabs=[
                TabState(editor_key=_K_GRAPH_EDITOR, label="Graph"),
                TabState(editor_key=_K_LIBRARY_DETAIL, label="Library"),
                TabState(editor_key=_K_FILE_VIEWER, label="File"),
            ],
            active_tab_index=0,
            bottom_visible=False,
        ),
        right_bar_active=_K_PROPERTIES,
        right=AreaState(editor_key=_K_PROPERTIES, visible=True, size=350),
    ),
    "Development": WorkspaceState(
        name="Development",
        left_bar_active=_K_LIBRARY_BROWSER,
        left=AreaState(editor_key=_K_LIBRARY_BROWSER, visible=True, size=250),
        middle=MiddleAreaState(
            tabs=[
                TabState(editor_key=_K_GRAPH_EDITOR, label="Graph"),
                TabState(editor_key=_K_LIBRARY_DETAIL, label="Library"),
                TabState(editor_key=_K_FILE_VIEWER, label="File"),
            ],
            active_tab_index=0,
            bottom_visible=True,
            bottom_size=200,
            bottom_editor_key=_K_CONSOLE,
        ),
        right_bar_active=_K_PROPERTIES,
        right=AreaState(editor_key=_K_PROPERTIES, visible=True, size=350),
    ),
    "Debugging": WorkspaceState(
        name="Debugging",
        left_bar_active=_K_LIBRARY_BROWSER,
        left=AreaState(editor_key=_K_LIBRARY_BROWSER, visible=False, size=250),
        middle=MiddleAreaState(
            tabs=[
                TabState(editor_key=_K_GRAPH_EDITOR, label="Graph"),
                TabState(editor_key=_K_LIBRARY_DETAIL, label="Library"),
                TabState(editor_key=_K_FILE_VIEWER, label="File"),
            ],
            active_tab_index=0,
            bottom_visible=True,
            bottom_size=300,
            bottom_editor_key=_K_CONSOLE,
        ),
        right_bar_active=_K_PROPERTIES,
        right=AreaState(editor_key=_K_PROPERTIES, visible=True, size=350),
    ),
}
```

- [ ] **Step 6: Update `test_workspace_state.py` — fix tests that checked for studio strings**

In `tests/ui/test_workspace_state.py`, update `TestWorkspaceManager.setup_method` and the two affected tests:

```python
# Replace setup_method:
def setup_method(self):
    from haywire_studio.workspace.defaults import DEFAULT_PRESETS
    self.manager = WorkspaceManager(initial_presets=DEFAULT_PRESETS, project_path=None)
```

```python
# Replace test_development_preset_has_bottom_visible:
def test_development_preset_has_bottom_visible(self):
    from haywire_studio.workspace.defaults import _K_CONSOLE
    dev = self.manager.presets["Development"]
    assert dev.middle.bottom_visible is True
    assert dev.middle.bottom_editor_key == _K_CONSOLE
```

Also update `TestWorkspaceStateSerialization.test_workspace_state_roundtrip` and `test_default_workspace_state` to match the new `None` defaults (as written in Step 1 above).

- [ ] **Step 7: Run the tests to verify they pass**

```bash
uv run pytest tests/ui/test_workspace_state.py tests/ui/test_workspace_defaults.py -v
```

Expected: All PASS.

- [ ] **Step 8: Commit**

```bash
git add \
  packages/haywire-core/src/haywire/ui/workspace/workspace_state.py \
  packages/haywire-studio/src/haywire_studio/workspace/__init__.py \
  packages/haywire-studio/src/haywire_studio/workspace/defaults.py \
  tests/ui/test_workspace_state.py \
  tests/ui/test_workspace_defaults.py
git commit -m "refactor: strip studio key constants from workspace_state, move to studio/workspace/defaults"
```

---

## Task 2: Update `WorkspaceManager` and `Session` to accept injected presets/manager

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/workspace/manager.py`
- Modify: `packages/haywire-core/src/haywire/ui/session.py`
- Modify: `tests/ui/test_workspace_state.py`

- [ ] **Step 1: Write failing test for `WorkspaceManager` with no presets**

Add to `tests/ui/test_workspace_state.py` inside `TestWorkspaceManager`:

```python
def test_empty_presets_when_none_provided(self):
    """WorkspaceManager with no initial_presets starts with empty presets and blank active."""
    manager = WorkspaceManager()
    assert manager.presets == {}
    assert isinstance(manager.active, WorkspaceState)
    assert manager.active.name == "default"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/ui/test_workspace_state.py::TestWorkspaceManager::test_empty_presets_when_none_provided -v
```

Expected: FAIL — `WorkspaceManager()` currently populates `DEFAULT_PRESETS`.

- [ ] **Step 3: Update `WorkspaceManager.__init__`**

Replace the `__init__` method and `DEFAULT_PRESETS` class variable in `packages/haywire-core/src/haywire/ui/workspace/manager.py`:

Remove the `DEFAULT_PRESETS` class variable entirely.

Replace `__init__` with:

```python
def __init__(
    self,
    initial_presets: Optional[Dict[str, WorkspaceState]] = None,
    project_path: Optional[Path] = None,
):
    self._project_path = project_path
    self.presets: Dict[str, WorkspaceState] = dict(initial_presets) if initial_presets else {}
    self.active: WorkspaceState = (
        next(iter(self.presets.values())) if self.presets else WorkspaceState()
    )

    if project_path:
        self._load_user_presets(project_path)
```

- [ ] **Step 4: Update `Session.__init__` to accept `workspace_manager`**

In `packages/haywire-core/src/haywire/ui/session.py`, replace `__init__`:

```python
def __init__(self, project_state, workspace_manager: "WorkspaceManager"):
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

    # Active editor instances (keyed by area slot: 'left', 'middle', 'right', 'bottom')
    self._editors: Dict[str, "BaseEditor"] = {}

    # Context change subscribers (editor.on_context_changed callbacks)
    self._context_subscribers: List[Callable] = []

    logger.info(f"Session created: {self.session_id}")
```

Also update the import at the top of `session.py` — add `WorkspaceManager` to the imports:

```python
from .workspace.manager import WorkspaceManager
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/ui/test_workspace_state.py -v
```

Expected: All PASS.

- [ ] **Step 6: Run full suite to check for regressions**

```bash
uv run pytest -m "not integration" -x
```

Expected: All PASS. Fix any failures before continuing.

- [ ] **Step 7: Commit**

```bash
git add \
  packages/haywire-core/src/haywire/ui/workspace/manager.py \
  packages/haywire-core/src/haywire/ui/session.py \
  tests/ui/test_workspace_state.py
git commit -m "refactor: WorkspaceManager accepts initial_presets; Session accepts workspace_manager"
```

---

## Task 3: Update `SessionContext` theme key defaults

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/context.py`

- [ ] **Step 1: Write failing test**

Add to `tests/ui/test_workspace_state.py` (or create `tests/ui/test_session_context.py` if it doesn't exist):

```python
# tests/ui/test_session_context.py
"""Tests for SessionContext."""

from haywire.ui.context import SessionContext, InteractionMode


class FakeApp:
    """Minimal stand-in for IProjectState."""
    workspace_root = "/tmp"
    library_service = None


def test_theme_keys_default_to_none():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    assert ctx.active_workbench_theme_key is None
    assert ctx.active_node_theme_key is None


def test_theme_keys_can_be_set():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    ctx.active_workbench_theme_key = "core:theme:workbench:haywire-dark"
    assert ctx.active_workbench_theme_key == "core:theme:workbench:haywire-dark"


def test_interaction_mode_defaults_to_idle():
    ctx = SessionContext(session_id="test-123", app=FakeApp())
    assert ctx.interaction_mode == InteractionMode.IDLE
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/ui/test_session_context.py::test_theme_keys_default_to_none -v
```

Expected: FAIL — currently defaults to `"core:theme:workbench:haywire-dark"` not `None`.

- [ ] **Step 3: Update `context.py`**

In `packages/haywire-core/src/haywire/ui/context.py`, change the two theme key fields:

```python
# Before
active_workbench_theme_key: str = (
    "core:theme:workbench:haywire-dark"  # Active WorkbenchTheme registry_key
)
active_node_theme_key: str = "core:theme:node:default"  # Active NodeTheme registry_key

# After
active_workbench_theme_key: Optional[str] = None  # set by host app after session creation
active_node_theme_key: Optional[str] = None  # set by host app after session creation
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/ui/test_session_context.py -v
```

Expected: All PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -m "not integration" -x
```

Expected: All PASS. Fix any failures before continuing.

- [ ] **Step 6: Commit**

```bash
git add \
  packages/haywire-core/src/haywire/ui/context.py \
  tests/ui/test_session_context.py
git commit -m "refactor: SessionContext theme keys default to None, set by host app"
```

---

## Task 4: Expand `IProjectState` protocol — add `IGraphManager`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/protocols.py`

No new tests needed here — this is a typing-only change. `mypy` is the verification.

- [ ] **Step 1: Rewrite `protocols.py`**

```python
# packages/haywire-core/src/haywire/ui/protocols.py
"""
Structural protocols for the Haywire UI system.

These protocols define the interface the framework expects from host application
objects, avoiding circular imports while providing full IDE type resolution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.di.config import LibrarySystemService
    from haywire.core.execution import Interpreter
    from haywire.core.execution.interpreter_loop_manager import InterpreterLoopManager
    from haywire.ui.session_manager import SessionManager


class IGraphManager(Protocol):
    """
    Structural interface for graph file management.

    GraphManager in haywire-studio satisfies this protocol without inheriting from it.
    Factory args are typed as Any to avoid importing the studio-specific GraphFactory
    type alias into haywire.ui.
    """

    def open_graph(self, path: Path, factory: Any) -> Any: ...
    def create_new(self, factory: Any) -> Any: ...
    def save_graph(self, entry: Any) -> None: ...
    def session_attach(self, entry: Any, session_id: str) -> None: ...
    def session_detach(self, entry: Any, session_id: str) -> None: ...


class IProjectState(Protocol):
    """
    Structural interface the framework expects from the host application.

    HaywireApp satisfies this protocol without inheriting from it.
    """

    library_service: "LibrarySystemService"
    workspace_root: str
    session_manager: "SessionManager"
    graph_manager: IGraphManager
    node_registry: Any        # NodeRegistry
    node_factory: Any         # NodeFactory
    interpreter: "Interpreter"
    loop_manager: "InterpreterLoopManager"
```

- [ ] **Step 2: Run mypy to verify no new type errors**

```bash
uv run mypy packages/haywire-core/src/ --ignore-missing-imports
```

Expected: No new errors introduced by this change. Fix any that appear.

- [ ] **Step 3: Run full suite**

```bash
uv run pytest -m "not integration" -x
```

Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/protocols.py
git commit -m "refactor: expand IProjectState protocol; add IGraphManager protocol"
```

---

## Task 5: Replace `ConsoleBridge` singleton with module-level instance

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/console_bridge.py`

- [ ] **Step 1: Write failing test**

```python
# tests/ui/test_console_bridge.py
"""Tests for ConsoleBridge module-level instance."""

from haywire.ui.console_bridge import get_bridge, console_print, ConsoleBridge


def test_get_bridge_returns_console_bridge():
    bridge = get_bridge()
    assert isinstance(bridge, ConsoleBridge)


def test_get_bridge_returns_same_instance():
    assert get_bridge() is get_bridge()


def test_console_print_queues_message():
    bridge = get_bridge()
    bridge.clear()
    console_print("hello test")
    # Drain one message from the queue
    msg = bridge.message_queue.get_nowait()
    assert msg == "hello test"


def test_no_get_instance_classmethod():
    assert not hasattr(ConsoleBridge, "get_instance"), \
        "ConsoleBridge.get_instance() should be removed in favour of get_bridge()"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/ui/test_console_bridge.py -v
```

Expected: `test_get_bridge_returns_console_bridge` and `test_get_bridge_returns_same_instance` FAIL (no `get_bridge`); `test_no_get_instance_classmethod` FAIL (method still exists).

- [ ] **Step 3: Rewrite `console_bridge.py`**

```python
# packages/haywire-core/src/haywire/ui/console_bridge.py
"""
Thread-safe console bridge for NiceGUI.

Allows worker threads to print messages that appear in the UI.
Access the shared bridge via get_bridge() or use console_print() directly.
"""

from __future__ import annotations
from threading import Lock
from queue import Queue, Empty
from nicegui import ui


class ConsoleBridge:
    """
    Thread-safe bridge between worker threads and NiceGUI log elements.

    Usage:
        # In UI setup (per session):
        bridge = get_bridge()
        log = ui.log(max_lines=100)
        bridge.register_log_with_polling(log)

        # In worker thread (e.g., Print Message node):
        from haywire.ui.console_bridge import console_print
        console_print("Hello from node!")
    """

    def __init__(self):
        self.message_queue: Queue[str] = Queue()
        self.log_elements: dict = {}  # Maps log element to its timer
        self._lock = Lock()
        self._max_messages_per_poll = 50
        self._history: list[str] = []
        self._max_history = 500

    def register_log_with_polling(self, log_element, interval: float = 0.1):
        """
        Register a ui.log element and create a dedicated timer for it.

        Each timer polls the shared queue and broadcasts to ALL log elements.
        This ensures all sessions see the same output even if only one timer
        fires (in multi-session scenarios).

        Returns:
            The timer object for cleanup by caller.
        """
        timer = ui.timer(interval, self._poll_and_broadcast)
        self.log_elements[log_element] = timer
        return timer

    def register_log(self, log_element):
        """Register a ui.log element (deprecated - use register_log_with_polling)."""
        if log_element not in self.log_elements:
            self.log_elements[log_element] = None

    def unregister_log(self, log_element):
        """Unregister a ui.log element and cancel its timer."""
        if log_element in self.log_elements:
            timer = self.log_elements[log_element]
            if timer:
                try:
                    timer.cancel()
                except Exception:
                    pass
            del self.log_elements[log_element]

    def start_polling(self, interval: float = 0.1):
        """Deprecated no-op. Use register_log_with_polling instead."""
        pass

    def stop_polling(self):
        """Deprecated no-op."""
        pass

    def _poll_and_broadcast(self):
        """Poll message queue and broadcast to ALL log elements."""
        messages = []
        with self._lock:
            for _ in range(self._max_messages_per_poll):
                try:
                    msg = self.message_queue.get_nowait()
                    messages.append(msg)
                except Empty:
                    break

        if messages:
            for log_element in list(self.log_elements.keys()):
                try:
                    for msg in messages:
                        log_element.push(msg)
                except Exception:
                    self.unregister_log(log_element)

    def write(self, message: str):
        """Queue a message for display (thread-safe)."""
        if message.strip():
            self.message_queue.put(message.rstrip())
            self._history.append(message.rstrip())
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def get_history_text(self) -> str:
        """Get all history as text for copying."""
        return "\n".join(self._history)

    def clear_history(self):
        """Clear the history buffer."""
        self._history.clear()

    def clear(self):
        """Clear the message queue."""
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except Empty:
                break


# Module-level instance — accessible from any thread without DI context.
_bridge = ConsoleBridge()


def get_bridge() -> ConsoleBridge:
    """Return the shared ConsoleBridge instance."""
    return _bridge


def console_print(*args, **kwargs):
    """
    Print to the NiceGUI console (thread-safe).

    Can be called from any thread, including node execution threads.

    Usage:
        from haywire.ui.console_bridge import console_print
        console_print("Value:", 42)
    """
    message = " ".join(str(arg) for arg in args)
    _bridge.write(message)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/ui/test_console_bridge.py -v
```

Expected: All PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -m "not integration" -x
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add \
  packages/haywire-core/src/haywire/ui/console_bridge.py \
  tests/ui/test_console_bridge.py
git commit -m "refactor: replace ConsoleBridge singleton with module-level instance and get_bridge()"
```

---

## Task 6: Update `HaywireApp` — remove `self.sessions`, wire `SessionManager`, set theme defaults, use `get_bridge()`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py`

This task has no new unit tests — `HaywireApp` is NiceGUI-entangled. Verification is the full test suite plus a manual smoke check.

- [ ] **Step 1: Update imports at top of `app.py`**

Replace:
```python
from haywire.ui.console_bridge import ConsoleBridge
```
With:
```python
from haywire.ui.console_bridge import get_bridge
```

Add at the top of the file (with other imports):
```python
from haywire_studio.workspace.defaults import DEFAULT_PRESETS
```

- [ ] **Step 2: Remove `self.sessions` from `__init__`**

In `HaywireApp.__init__`, remove:
```python
# Per-client session bookkeeping (client_id → session_data dict)
self.sessions: dict = {}
```

- [ ] **Step 3: Delete `get_session_data()` and `_cleanup_session()` methods entirely**

Remove both methods from `HaywireApp`. They are replaced by `SessionManager`.

- [ ] **Step 4: Rewrite `on_disconnect()`**

```python
def on_disconnect(self, client):
    """Handle client disconnect."""
    if self._is_shutting_down:
        return
    session_id = getattr(client, "_haywire_session_id", None)
    if session_id:
        print(f"Client disconnected, cleaning up session {session_id[:8]}")
        self.session_manager.remove_session(session_id)
```

- [ ] **Step 5: Rewrite `on_app_shutdown()`**

```python
def on_app_shutdown(self):
    """Clean up all resources on application shutdown."""
    if self._is_shutting_down:
        return
    self._is_shutting_down = True
    print("Application shutdown initiated...")

    # 1. Stop interpreter loop
    if self.loop_manager and self.loop_manager.is_running:
        print("  Stopping interpreter loop...")
        self.stop_interpreter()

    # 2. Clean up all sessions
    print(f"  Cleaning up {self.session_manager.session_count} sessions...")
    self.session_manager.cleanup_all()

    # 3. Clean up graph manager
    try:
        if hasattr(self, "graph_manager"):
            self.graph_manager.cleanup()
    except Exception as e:
        print(f"  Error cleaning up graph manager: {e}")

    # 4. Clean up console bridge
    try:
        bridge = get_bridge()
        bridge.log_elements.clear()
        bridge.clear_history()
    except Exception as e:
        print(f"  Error cleaning up console bridge: {e}")

    # 5. Shutdown interpreter
    try:
        if self.interpreter:
            self.interpreter.shutdown()
    except Exception as e:
        print(f"  Error shutting down interpreter: {e}")

    # 6. Cleanup library system
    try:
        if hasattr(self.library_service, "cleanup"):
            self.library_service.cleanup()
    except Exception as e:
        print(f"  Error cleaning up library system: {e}")

    print("Application shutdown complete")
```

- [ ] **Step 6: Rewrite `create_ui()` main_page handler**

Replace the `main_page` inner function with:

```python
@ui.page("/", title="Haywire")
def main_page():
    from haywire.ui.app.shell import AppShell
    from haywire.ui.editor.registry import EditorTypeRegistry
    from haywire.ui.workspace.manager import WorkspaceManager
    from nicegui import context

    print(f"Creating UI for session: {context.client.id[:8]}")

    workspace_manager = WorkspaceManager(
        initial_presets=DEFAULT_PRESETS,
        project_path=Path(self.workspace_root),
    )

    haywire_session = self.session_manager.create_session(
        project_state=self,
        workspace_manager=workspace_manager,
    )

    # Store session ID on NiceGUI Client for disconnect lookup
    context.client._haywire_session_id = haywire_session.session_id

    # Set studio theme defaults on context before rendering
    haywire_session.context.active_workbench_theme_key = "core:theme:workbench:haywire-dark"
    haywire_session.context.active_node_theme_key = "core:theme:node:default"

    editor_registry = self.library_service.injector.get(EditorTypeRegistry)
    app_shell = AppShell(haywire_session, editor_registry=editor_registry)
    app_shell.render()
```

- [ ] **Step 7: Run full suite**

```bash
uv run pytest -m "not integration" -x
```

Expected: All PASS. Fix any failures before continuing.

- [ ] **Step 8: Run linter**

```bash
uv run ruff check packages/haywire-studio/src/haywire_studio/app.py
```

Expected: No errors.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/app.py
git commit -m "refactor: remove self.sessions from HaywireApp, consolidate into SessionManager"
```

---

## Task 7: Final verification

- [ ] **Step 1: Run the complete test suite**

```bash
uv run pytest --tb=short
```

Expected: All tests PASS including integration tests. Fix any failures.

- [ ] **Step 2: Run linter across all changed packages**

```bash
uv run ruff check packages/haywire-core/src/ packages/haywire-studio/src/
```

Expected: No errors.

- [ ] **Step 3: Run mypy**

```bash
uv run mypy packages/haywire-core/src/ --ignore-missing-imports
```

Expected: No new errors.

- [ ] **Step 4: Final commit if any lint/type fixes were needed**

```bash
git add -p
git commit -m "fix: lint and type fixes from boundary cleanup"
```
