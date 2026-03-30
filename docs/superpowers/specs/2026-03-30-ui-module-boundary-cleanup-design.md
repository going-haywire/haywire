# Design: haywire.ui / haywire-studio Module Boundary Cleanup

**Date:** 2026-03-30
**Status:** Approved

## Goal

Establish a clean `haywire.core → haywire.ui → haywire-studio` dependency hierarchy.
No new abstractions beyond what is necessary. Five targeted changes.

---

## Change 1: `workspace_state.py` and `WorkspaceManager`

### `haywire.ui.workspace.workspace_state`

Remove all `_K_*` editor key constants. Dataclass fields that referenced them default to `None`.
The module becomes pure generic dataclasses with no studio-specific strings.

### New file: `haywire_studio/workspace/defaults.py`

All `_K_*` constants move here. `DEFAULT_PRESETS: Dict[str, WorkspaceState]` is defined here
using those constants. This is the only new file in the refactor.

### `WorkspaceManager.__init__` signature change

```python
# Before
def __init__(self, project_path: Optional[Path] = None)

# After
def __init__(
    self,
    initial_presets: Optional[Dict[str, WorkspaceState]] = None,
    project_path: Optional[Path] = None,
)
```

If `initial_presets` is `None`, `self.presets` starts empty and `self.active` is a blank
`WorkspaceState()`. Studio passes `DEFAULT_PRESETS`.

### `Session.__init__` signature change

```python
# Before
def __init__(self, project_state, project_path=None)

# After
def __init__(self, project_state, workspace_manager: WorkspaceManager)
```

`project_path` is dropped. Studio creates `WorkspaceManager(initial_presets=DEFAULT_PRESETS,
project_path=Path(workspace_root))` and passes it in.

### `HaywireApp.create_ui()` change

```python
from haywire_studio.workspace.defaults import DEFAULT_PRESETS

workspace_manager = WorkspaceManager(
    initial_presets=DEFAULT_PRESETS,
    project_path=Path(self.workspace_root),
)
haywire_session = self.session_manager.create_session(
    project_state=self,
    workspace_manager=workspace_manager,
)
```

---

## Change 2: `SessionContext` — remove hardcoded `studio:` defaults

```python
# Before
active_workbench_theme_key: str = "core:theme:workbench:haywire-dark"
active_node_theme_key: str = "core:theme:node:default"

# After
active_workbench_theme_key: Optional[str] = None
active_node_theme_key: Optional[str] = None
```

`HaywireApp.create_ui()` sets both fields on the session context immediately after session
creation and before `AppShell.render()` is called. `AppShell._build_initial_theme_css()`
already reads from the settings registry and writes back to context — it handles `None`
naturally via its existing fallback logic.

---

## Change 3: Remove `HaywireApp.self.sessions`, consolidate into `SessionManager`

### Deleted from `HaywireApp`

- `self.sessions: dict`
- `get_session_data()` method
- `_cleanup_session()` method (NiceGUI timer/console cleanup inside was dead code;
  `SessionManager.remove_session()` already calls `session.cleanup()`)

### Client ID → session ID mapping

NiceGUI's `app.on_disconnect` receives a `Client` object. To map it back to a haywire
session, store the session ID as an attribute on the `Client` at connect time:

```python
# in create_ui() / main_page():
haywire_session = self.session_manager.create_session(...)
context.client._haywire_session_id = haywire_session.session_id
```

```python
# in on_disconnect():
def on_disconnect(self, client):
    if self._is_shutting_down:
        return
    session_id = getattr(client, "_haywire_session_id", None)
    if session_id:
        self.session_manager.remove_session(session_id)
```

The `Client` object lives for exactly the connection lifetime. No `storage_secret` required.

### `on_app_shutdown` simplification

```python
def on_app_shutdown(self):
    ...
    # Clean up all sessions via SessionManager
    self.session_manager.cleanup_all()
    ...
```

---

## Change 4: Expand `IProjectState` protocol

### `IGraphManager` protocol (new, in `haywire.ui.protocols`)

`GraphManager` lives in haywire-studio so cannot be imported into `haywire.ui` directly.
A structural protocol is added to `haywire.ui.protocols` declaring only the methods
editors actually call:

```python
class IGraphManager(Protocol):
    def open_graph(self, path: Path, factory: Any) -> Any: ...
    def create_new(self, factory: Any) -> Any: ...
    def save_graph(self, entry: Any) -> None: ...
    def session_attach(self, entry: Any, session_id: str) -> None: ...
    def session_detach(self, entry: Any, session_id: str) -> None: ...
```

`GraphFactory` is a `Callable` type alias defined in `haywire_studio/graph_manager.py`.
Since the protocol lives in `haywire.ui`, factory args are typed as `Any` to avoid
the downward import. The protocol still enforces method names and arity.

### Expanded `IProjectState`

```python
class IProjectState(Protocol):
    library_service: LibrarySystemService
    workspace_root: str
    session_manager: "SessionManager"
    graph_manager: IGraphManager
    node_registry: Any        # NodeRegistry
    node_factory: Any         # NodeFactory
    interpreter: Any          # Interpreter
    loop_manager: Any         # InterpreterLoopManager
```

Types that live in `haywire.core` (registries, interpreter) are imported under
`TYPE_CHECKING` in `protocols.py`. Types from studio use `IGraphManager` protocol
or `Any` where a protocol would add no practical value.

All imports are under `TYPE_CHECKING` to avoid circular imports.

---

## Change 5: `ConsoleBridge` — replace singleton with module-level instance

### What changes in `console_bridge.py`

- Remove `_instance: Optional[ConsoleBridge]`, class-level `_lock`, and `get_instance()` classmethod
- Add module-level instance and accessor at the bottom of the file:
  ```python
  _bridge = ConsoleBridge()

  def get_bridge() -> ConsoleBridge:
      return _bridge
  ```
- `console_print()` calls `_bridge.write()` directly

The threading `Lock` inside `_poll_and_broadcast` is retained — it protects the message
queue, not the singleton.

### What changes in `app.py`

All `ConsoleBridge.get_instance()` calls become `get_bridge()`.

---

## What does NOT change

- `AppShell` stays in `haywire.ui` — it is the NiceGUI layout engine
- `Session`, `SessionManager`, `SessionContext`, `ContextChangedEvent` stay in `haywire.ui`
- `WorkspaceManager` persistence logic (`project_path`, `_load_user_presets`, `_persist_presets`) stays in `haywire.ui` — studio passes `project_path` at construction
- `workspace_state.py` dataclasses (`WorkspaceState`, `AreaState`, `MiddleAreaState`, `TabState`) stay in `haywire.ui`
- No changes to `haywire.core`
- No changes to editor classes, panel classes, or barn plugins

---

## Files changed

| File | Change |
|---|---|
| `haywire.ui/workspace/workspace_state.py` | Remove `_K_*` constants, `None`-ify defaults |
| `haywire.ui/workspace/manager.py` | Add `initial_presets` param, drop `DEFAULT_PRESETS` class var |
| `haywire.ui/session.py` | Drop `project_path`, accept `workspace_manager` |
| `haywire.ui/session_manager.py` | No change |
| `haywire.ui/context.py` | Theme key fields become `Optional[str] = None` |
| `haywire.ui/protocols.py` | Add `IGraphManager`, expand `IProjectState` |
| `haywire.ui/console_bridge.py` | Remove singleton, add module-level `_bridge` + `get_bridge()` |
| `haywire_studio/app.py` | Remove `self.sessions`, use `SessionManager`, set theme defaults, use `get_bridge()` |
| `haywire_studio/workspace/defaults.py` | **New file** — `_K_*` constants + `DEFAULT_PRESETS` |

---

## Open questions

None. All design decisions resolved.
