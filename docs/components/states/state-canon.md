---
status: draft
template: canonical-example
scope: Authoring AppState / SessionState classes — @state decorator, on_enable / on_disable, ctx.app_data and ctx.data access
see-also:
  - ../../architecture/session-and-state/session-and-state-arch.md
  - ../settings/setting-canon.md
  - ../libraries/library-canon.md
  - ../../reference/glossary.md
---

# State — Canonical Example

## 1. What it solves

A **state** class is library-owned runtime data — the live, volatile slot in haywire's architecture. As a library author, you declare a Python class that holds connections, caches, device handles, ML models, or any other runtime structure that doesn't fit settings (which are persisted), graph variables (which are per-graph), or session UI fields (which are per-session UI selection state). The framework instantiates it once per scope, owns its lifecycle, and exposes the instance through a uniform class-keyed access pattern on both `SessionContext` (UI side) and `ExecutionContext` (node-execution side).

There are two scopes, picked by **base class** (not by config string or decorator parameter):

- **`AppState`** — one instance, shared across the entire app (every browser session, every VM execution).
- **`SessionState`** — one instance per active UI session.

```text
class LibraryState:               ← abstract marker — never directly subclassed by users
    ...
class AppState(LibraryState):     ← one instance, app-global
class SessionState(LibraryState): ← one instance per session
```

**Mental rule: scope = base class.** Inheritance picks multiplicity. No `scope=`, no namespace string. Pick `AppState` if every session and every flow should see the same instance; pick `SessionState` if each browser tab should get its own.

## 2. How it fits

```text
Author declares                Library registers              Container instantiates
─────────────────              ─────────────────              ──────────────────────
@state(label='...')            @library(id='midi'):           LibraryStateContainer
class MidiPool(AppState):        register_components(self):     observes registry
   devices = reactive_field(      self.add_folder_to_             lifecycle events:
     [])                            registry(                    on register: cls() →
   def on_enable(self): ...           folder=base/'state',         store → on_enable()
   def on_disable(self): ...          registry_cls=                on unregister:
                                      LibraryStateRegistry)        on_disable() → drop


Worker / panel reads
────────────────────
ctx.app_data[MidiPool]   ─► O(1) lookup in app pool       (AppState)
ctx.data[TimelineCursor] ─► O(1) lookup in session pool   (SessionState; SessionContext only)
```

Three architectural slots state fills, distinct from anything else:

| Concern | Slot |
|---|---|
| Persistent app/library config | `LibrarySettings`, `FrameworkSettings` ([components/settings](../settings/setting-canon.md)) |
| Per-graph state | `graph.variables` |
| Per-flow execution state | `ExecutionContext.local_ctx` |
| External system inputs to a flow | `ExecutionContext.global_ctx` |
| Per-session UI selection state | `SessionContext` reactive fields |
| **App-global library runtime state** | **`AppState`** |
| **Per-session library runtime state** | **`SessionState`** |

**Boundaries.** Framework mechanics — registry events, container subscription, hot-reload coordination, lifecycle ordering — live in [architecture/session-and-state](../../architecture/session-and-state/session-and-state-arch.md). The `LibrarySettings` system that AppState compositions sometimes wrap lives in [components/settings](../settings/setting-canon.md). The `Library` class that registers state folders lives in [components/libraries](../libraries/library-canon.md).

## 3. Important concepts

**The `@state` decorator.** Optional but recommended — sets `class_identity` and label metadata. Undecorated `AppState`/`SessionState` subclasses still work (the registry derives `class_identity` at registration time as a fallback), but use `@state` when you want explicit `label=`, `description=`, or `registry_id=`.

```python
from haywire.core.state import AppState, SessionState, state, reactive_field

@state(label='MIDI Pool')
class MidiPool(AppState): ...
```

The decorator does **not** carry a scope parameter. Scope is determined by which base class you inherit from.

**Lifecycle hooks (both scopes).**

| Hook | When | Purpose |
|---|---|---|
| `on_enable(self)` | After construction, after `self.session_id` is stamped (SessionState) | Acquire resources — open sockets, scan hardware, instantiate a `LibrarySettings()` |
| `on_disable(self)` | Before destruction (library disable, hot-reload teardown, session detach) | Release resources — close handles, stop threads |

Both are optional and duck-typed. If absent, the framework skips them silently.

**Reactivity is opt-in via `reactive_field()`.** Plain attributes are not reactive — `devices: dict = {}` is a normal Python dict. `devices = reactive_field([])` is a reactive cell that re-renders subscribed UI panels when its `.value` changes.

```python
class MidiPool(AppState):
    devices = reactive_field([])           # reactive — UI re-renders on change
    connections: dict[str, Connection] = {} # plain — not reactive
    _lock = threading.Lock()                # plain
```

**Class-keyed access only.** Both contexts expose state through generic-typed namespaces:

```python
# SessionContext (panels, editors)
ctx.app_data[MidiPool]            # AppState lookup
ctx.data[TimelineCursor]          # SessionState lookup (SessionContext-only)

# ExecutionContext (workers)
exec_ctx.app_data[MidiPool]       # AppState only — exec has no session
# exec_ctx.data does not exist (graphs run app-globally, not per session)
```

`__getitem__` raises `KeyError` if the class isn't registered; `.get(Cls)` returns `None`. Use `__getitem__` when the dependency is part of your contract; use `.get` when absence is a valid runtime state.

There is **no string-keyed access** (`ctx.app_data.midi`) and **no namespace= kwarg**. The class is the unambiguous identifier; type-checkers infer the correct return type from the class argument.

**`SessionContext` has both, `ExecutionContext` has only `app_data`.** This is honest about the architecture: node graphs run app-globally — the VM has no notion of which UI session triggered execution. So:

| Context | `ctx.app_data` | `ctx.data` |
|---|---|---|
| `SessionContext` (UI) | yes — `AppDataNamespace` | yes — `SessionDataNamespace` |
| `ExecutionContext` (workers) | yes — `AppDataNamespace` | does not exist |

Type-checker enforces the asymmetry: `exec_ctx.data` is an `AttributeError` at runtime and a type error at check time.

**The "look up at access site" idiom.** Always re-resolve through `ctx.app_data[Cls]` rather than caching a long-lived reference, especially in panels and persistent helpers — hot-reload swaps the instance, and a captured reference goes stale.

```python
# Recommended — re-resolves on each access
def draw(self, ctx, layout):
    pool = ctx.app_data[MidiPool]
    for device in pool.devices.value:
        layout.label(device.name)

# Acceptable inside a short worker body — captured once
def worker(self, exec_ctx):
    pool = exec_ctx.app_data[MidiPool]
    pool.send(self.props.message.value)

# AVOID — stale after hot-reload
class MyPanel(Panel):
    def __init__(self, ctx):
        self.pool = ctx.app_data[MidiPool]   # don't
```

**Folder convention and registration order.** State classes go in the library's `state/` folder; register that folder with `LibraryStateRegistry` in `register_components()`. The folder scan picks up both `AppState` and `SessionState` subclasses in one pass.

**Recommended scan order in `register_components()`:** `settings → state → nodes / panels / editors / themes`. This mirrors the framework's hot-reload propagation chain (`SettingsRegistry → LibraryStateRegistry → NodeRegistry`, `PanelRegistry`, `EditorTypeRegistry`). Following the same order at first-load keeps initial-load aligned with hot-reload, so an `AppState` whose `on_enable` reads a `LibrarySettings()` value finds the schema already wired.

**`session_id` on SessionState.** Stamped by the container *between* `cls()` and `on_enable`. Read it in `on_enable` or later — `__init__` runs before stamping:

```python
class TimelineCursor(SessionState):
    position = reactive_field(0.0)

    def on_enable(self):
        # self.session_id is now available (str) — set by the container
        load_cursor_for(self.session_id)
```

**Composing `LibrarySettings` inside `AppState`.** Recommended pattern for state with persisted, user-tweakable knobs (poll rate, port, cache size). Instantiate the settings *in `on_enable`*, not `__init__` or class body — `LibrarySettings()` requires `cls._registry` to be wired by `SettingsRegistry`, which happens after class registration but before `on_enable` fires.

**`SessionState` is prohibited from composing `LibrarySettings`.** Per-session state shouldn't read persisted singleton settings — if both apply to the same concern, hold the settings on a sibling `AppState` and reference it through `ctx.app_data[...]`.

**Hot-reload semantics.** Implemented as `disable + enable`:

1. `on_disable` runs on the *old* instance against the *old* class.
2. Class is swapped.
3. `on_enable` runs on a *new* instance against the *new* class.

In-flight state is lost. If `on_enable` is expensive (warming a cache, scanning hardware), reload pays that cost again — by design. The alternative (state migration across class versions) is a class of bug we are not building.

**Imports** (verified against codebase 2026-05):

```python
from haywire.core.state import (
    LibraryState,           # abstract marker — never subclassed by users
    AppState,               # concrete app-scoped base
    SessionState,           # concrete per-session base
    state,                  # decorator
    LibraryStateRegistry,   # for register_components()
)
from haywire.ui.reactive import reactive_field
```

## 4. One comprehensive example

A library `haybale_midi` that exercises both scopes: an `AppState` (`MidiPool`) holding live device handles plus a composed `LibrarySettings` for poll rate, and a `SessionState` (`MidiSelection`) tracking which device the active session has picked. Plus a panel and a worker reading both.

```python
# haybale_midi/state/midi_pool.py — AppState

from haywire.core.state import AppState, state
from haywire.ui.reactive import reactive_field


# Companion settings (covered in components/settings/setting-canon.md).
# Lives in the same library so on_enable can find the wired registry.
from ..settings import MidiSettings


@state(label='MIDI Device Pool')
class MidiPool(AppState):
    """App-global pool of live MIDI devices. One instance shared across
    every session and every flow."""

    devices = reactive_field([])             # reactive — UI rerenders on changes
    connections: dict[str, "Connection"] = {} # plain — not reactive
    config: MidiSettings | None = None        # holds composed settings instance

    def on_enable(self) -> None:
        # Instantiate AFTER SettingsRegistry has wired MidiSettings._registry.
        # By the time on_enable fires, every LibrarySettings class registered
        # by this library is fully wired.
        self.config = MidiSettings()

        if self.config.auto_connect.value:
            self.devices.value = scan_midi_devices(
                rate_hz=self.config.poll_rate.value,
            )

    def on_disable(self) -> None:
        # Release resources before the instance is dropped from the pool.
        for conn in self.connections.values():
            conn.close()
        self.connections.clear()
        self.devices.value = []
```

```python
# haybale_midi/state/midi_selection.py — SessionState

from haywire.core.state import SessionState, state
from haywire.ui.reactive import reactive_field


@state(label='MIDI Selection (session)')
class MidiSelection(SessionState):
    """Per-session state — each browser session has its own selected
    device and per-session preferences."""

    selected_device_id = reactive_field("")
    preferred_channel = reactive_field(1)

    def on_enable(self) -> None:
        # session_id is stamped by the container BEFORE on_enable fires
        # — safe to read here. Not safe in __init__.
        load_session_prefs(self.session_id)

    def on_disable(self) -> None:
        # Persist any session preferences before the session is detached.
        save_session_prefs(self.session_id, self.preferred_channel.value)
```

```python
# haybale_midi/__init__.py — registration in register_components

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.state import LibraryStateRegistry
from haywire.core.node.registry import NodeRegistry


@library(
    id='midi',
    label='MIDI',
    file_watcher=True,
)
class Library(BaseLibrary):
    def register_components(self):
        base = Path(__file__).parent

        # Recommended scan order: settings → state → nodes / panels / etc.
        # Mirrors the framework's hot-reload propagation chain so first-
        # load and reload paths agree.
        self.add_folder_to_registry(
            folder_path=str(base / 'settings'),
            registry_cls=SettingsRegistry,
        )
        self.add_folder_to_registry(
            folder_path=str(base / 'state'),
            registry_cls=LibraryStateRegistry,
        )
        self.add_folder_to_registry(
            folder_path=str(base / 'nodes'),
            registry_cls=NodeRegistry,
        )
        # ... panels, editors, themes ...

    def validate(self) -> bool:
        return True
```

```python
# haybale_midi/panels/device_list.py — UI side reading both scopes

from haywire.ui.panel import Panel, panel


@panel(focus=GraphFocus, label='MIDI Devices')
class MidiDeviceListPanel(Panel):
    def draw(self, ctx, layout, actions):
        # AppState — same instance for everyone
        pool = ctx.app_data[MidiPool]

        # SessionState — this session's selection
        selection = ctx.data[MidiSelection]

        for device in pool.devices.value:
            row = layout.row()
            row.label(device.name)
            if device.id == selection.selected_device_id.value:
                row.label('✓ selected')
            else:
                row.button('Select', on_click=lambda d=device:
                    setattr(selection.selected_device_id, 'value', d.id))
```

```python
# haybale_midi/nodes/midi_send.py — Execution side

from haywire.core.execution.execution_context import ExecutionContext


@node(label='MIDI Send')
class MidiSendNode(BaseNode):
    def init(self):
        self.add(STRING.as_inlet('device_id'))
        self.add(INT.as_inlet('note'))

    def worker(self, exec_ctx: ExecutionContext, device_id: str, note: int):
        # AppState — workers can read this; same pool every flow sees
        pool = exec_ctx.app_data[MidiPool]

        # NOT possible: exec_ctx.data — ExecutionContext has no session.
        # Graphs run app-globally; if a node needs session-keyed data,
        # the orchestrating panel must pass it in via the ExecutionContext
        # global_ctx mechanism (see [architecture/execution]).

        if device_id in pool.connections:
            pool.connections[device_id].send_note(note)
```

What this example exercises:

| Concept | Where |
|---|---|
| `AppState` for app-global single-instance state | `MidiPool` |
| `SessionState` for per-session state | `MidiSelection` |
| `@state(label=...)` decorator | both classes |
| `reactive_field()` for reactive attributes | `devices`, `selected_device_id` |
| Plain attributes for non-reactive state | `connections: dict` |
| `on_enable` / `on_disable` lifecycle hooks | both classes |
| Composing `LibrarySettings` inside `AppState` | `MidiPool.config = MidiSettings()` |
| Instantiating `LibrarySettings` in `on_enable`, not `__init__` | `MidiPool.on_enable` |
| Reading `self.session_id` in `on_enable` (post-stamp) | `MidiSelection.on_enable` |
| Recommended folder scan order in `register_components` | `Library.register_components` |
| `ctx.app_data[Cls]` from a panel | `MidiDeviceListPanel.draw` |
| `ctx.data[Cls]` from a panel (SessionContext-only) | `MidiDeviceListPanel.draw` |
| `exec_ctx.app_data[Cls]` from a worker | `MidiSendNode.worker` |
| No `exec_ctx.data` — workers can't reach SessionState | `MidiSendNode.worker` (commented) |

For the framework mechanics — `LibraryStateRegistry`, `LibraryStateContainer`, registry events, hot-reload pipeline, lifecycle ordering — see [architecture/session-and-state](../../architecture/session-and-state/session-and-state-arch.md).

---

## Quick reference

### Authoring checklist

- [ ] Pick scope: `AppState` (one global) or `SessionState` (one per session)
- [ ] `@state(label='...')` decorator (optional but recommended)
- [ ] Inherit from chosen base; never inherit from `LibraryState` directly
- [ ] Use `reactive_field()` for fields that should drive UI re-renders; plain attributes otherwise
- [ ] Implement `on_enable` / `on_disable` for resource lifecycle (both optional)
- [ ] Place file in `state/` folder; register the folder via `LibraryStateRegistry` in `register_components`
- [ ] For SessionState: read `self.session_id` in `on_enable` (not `__init__`)
- [ ] For AppState composing settings: instantiate `LibrarySettings()` in `on_enable` (not class body or `__init__`)

### Imports

```python
from haywire.core.state import (
    AppState, SessionState, state, LibraryStateRegistry,
)
from haywire.ui.reactive import reactive_field
```

### Access patterns

| From a… | AppState lookup | SessionState lookup |
|---|---|---|
| Panel (`SessionContext`) | `ctx.app_data[Cls]` | `ctx.data[Cls]` |
| Worker (`ExecutionContext`) | `exec_ctx.app_data[Cls]` | not available |

Use `[Cls]` when the dependency is required (raises `KeyError`); `.get(Cls)` when absence is valid (returns `None`).

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| Inheriting from `LibraryState` directly | The marker is excluded by the registry filter; nothing is registered |
| Reading `self.session_id` in `__init__` | Not stamped yet — read in `on_enable` or later |
| Instantiating `LibrarySettings()` in class body or `__init__` | `cls._registry` not yet wired — crashes with a `None` registry |
| Caching `ctx.app_data[Cls]` in a long-lived `__init__` | Reference goes stale on hot-reload |
| Composing `LibrarySettings` inside a `SessionState` | Prohibited — per-session state must not read persisted settings |
| Trying `exec_ctx.data` in a worker | Doesn't exist — graphs run app-globally |
