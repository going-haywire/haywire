# Spec: LibraryState — library-owned runtime state

> Status: **v1 implemented (2026-05-06); v1.1 implemented (2026-05-06).**
> v1.1 introduces `SessionState` as a sibling of `AppState` (the renamed
> concrete app-global base) under an abstract `LibraryState` marker. See
> [`session_state.md`](session_state.md) for the per-session scope and
> [`spec_panel_reactivity.md`](spec_panel_reactivity.md) for the deferred
> Phase 2 reactive auto-tracking.
> 
> Scope: a new extension point for library plugins to declare app-global
> runtime data structures that are accessible from both UI panels/editors
> and node worker functions, via a uniform class-keyed access pattern.
> 
> **Companion documents:**
> 
> - [`spec_panel_reactivity.md`](spec_panel_reactivity.md) — Phase 2
>   reactive auto-tracking. LibraryState fields use the same
>   `reactive_field()` primitive and inherit Phase 2 behaviour
>   uniformly.

---

## 1. Mental model

`LibraryState` is the **abstract marker base** that roots the
library-state extension point. Library authors never subclass it
directly; they pick one of its two concrete siblings:

- **`AppState`** — one instance, shared across the entire app (every
  browser session and every VM execution). The subject of this
  document.
- **`SessionState`** — one instance per active UI session.
  Cross-referenced here; see [`session_state.md`](session_state.md) for
  the full spec.

```python
class LibraryState:               # abstract marker — never directly subclassed by users
    ...

class AppState(LibraryState):     # 1 instance, shared across all sessions + executions
    ...

class SessionState(LibraryState): # 1 instance per session
    ...
```

The mental rule is one line: **scope = base class.** Inheritance picks
multiplicity. No scope attribute, no config string, no decorator
parameter.

This document is the canonical reference for `AppState`. An **AppState**
is a Python class that a library declares to hold its own app-global
runtime data. The framework instantiates it once when the library is
enabled, owns its lifecycle, and exposes the instance through a uniform
access pattern on both `SessionContext` (UI, via `ctx.app_data`) and
`ExecutionContext` (node execution, via `exec_ctx.app_data`).

AppState is characterized by what it **is**:

- App-global. One instance, shared across all browser sessions and the VM.
- Library-owned. The owning library declares the class, and the
  framework destroys the instance when the library is disabled or
  hot-reloaded.
- Runtime, not persisted. AppState holds volatile state — open
  connections, caches, pools, live device handles, ML models. Persistent
  configuration belongs in `LibrarySettings`.
- Free in shape. An AppState may contain anything: plain Python
  attributes, `reactive_field()` cells, nested `LibrarySettings`
  instances, threads, sockets, NumPy arrays. The framework imposes no
  field-level constraints.
- Accessed by class, not by string. The canonical access pattern is
  `ctx.app_data[MidiPool]`. There is no namespace string and no
  attribute-style shorthand. The class itself is the unambiguous
  identifier. (`SessionState` lookups use `ctx.data` per
  [`session_state.md`](session_state.md) §2.3.)

AppState fills a previously empty slot in the architecture:

| concern                              | mechanism                                                   |
| ------------------------------------ | ----------------------------------------------------------- |
| persistent app/library config        | `LibrarySettings`, `FrameworkSettings`                      |
| per-graph state                      | `graph.variables`                                           |
| per-flow execution state             | `ExecutionContext.local_ctx`                                |
| external system inputs to a flow     | `ExecutionContext.global_ctx`                               |
| per-session UI selection state       | `SessionContext` reactive fields                            |
| per-session library runtime state    | `SessionState` (see [`session_state.md`](session_state.md)) |
| **app-global library runtime state** | **`AppState`** *(this spec)*                                |

---

## 2. The contract

### 2.1 Declaration

An AppState is a subclass of `AppState` placed in the library's
`state/` folder (or any folder the library registers with
`LibraryStateRegistry`).

```python
# barn/haybale-midi/haybale_midi/state/midi_pool.py

from haywire.core.state import AppState
from haywire.ui.reactive import reactive_field

class MidiPool(AppState):
    """Live MIDI device handles and connection state."""

    devices = reactive_field([])           # reactive — UI panels rerender on change
    connections: dict[str, "Connection"] = {}   # plain — not reactive

    def on_enable(self) -> None:
        """Acquire resources. Called once when the library is enabled."""
        self.devices.value = scan_midi_devices()

    def on_disable(self) -> None:
        """Release resources. Called once when the library is disabled."""
        for c in self.connections.values():
            c.close()
        self.connections.clear()
```

A library may declare zero, one, or many AppState subclasses. Each
is registered, instantiated, and lifecycle-managed independently.

`on_enable` and `on_disable` are optional. If absent, the framework does
nothing for that hook.

### 2.2 Registration

The owning library registers a folder with `LibraryStateRegistry` from
its `register_components()` method, identical to every other registry:

```python
# haybale_midi/__init__.py

from haywire.core.state import LibraryStateRegistry

@library(id="midi", ...)
class Library(BaseLibrary):
    def register_components(self) -> None:
        base_path = Path(__file__).parent

        # Recommended folder-scan order — matches the framework's
        # registry-subscriber chain (settings → state → consumers):
        self.add_folder_to_registry(
            folder_path=str(base_path / "settings"),
            registry_cls=SettingsRegistry,
        )
        self.add_folder_to_registry(
            folder_path=str(base_path / "state"),
            registry_cls=LibraryStateRegistry,
        )
        self.add_folder_to_registry(
            folder_path=str(base_path / "nodes"),
            registry_cls=NodeRegistry,
        )
        # ... panels, editors, themes, etc.
```

**Recommended folder-scan order:** settings → state → nodes / panels /
editors / themes. This mirrors the framework's hot-reload propagation
chain: `SettingsRegistry → LibraryStateRegistry → NodeRegistry`,
`PanelRegistry`, `EditorTypeRegistry`. Following the same order in
`register_components()` keeps initial-load ordering aligned with
hot-reload propagation, so an `AppState` whose `on_enable` reads a
`LibrarySettings()` value finds the schema already wired, and node /
panel / editor classes that import an `AppState` for use as a
`ctx.app_data[Cls]` key resolve it during their own scan.

Folder scan discovers every concrete `LibraryState` subclass
(`AppState` and `SessionState` alike) in the folder and registers it.
Discovery order within a folder is alphabetical; if one AppState's
`on_enable` depends on another already being initialised, the dependent
library should declare `dependencies=` on its `@library` decorator (the
existing inter-library dependency mechanism applies — no new ordering
machinery is added).

### 2.3 Access

Both `SessionContext` and `ExecutionContext` expose AppState lookups
through an `app_data` attribute of type `AppDataNamespace`. The only
access pattern is class-keyed:

```python
# From a panel (UI side):
def draw(self, ctx: SessionContext, layout, actions) -> None:
    pool = ctx.app_data[MidiPool]
    for device in pool.devices.value:
        layout.label(device.name)

# From a node worker (execution side):
def worker(self, exec_ctx: ExecutionContext) -> dict:
    pool = exec_ctx.app_data[MidiPool]
    return {"device_count": len(pool.devices.value)}
```

> **Note:** `SessionState` lookups use `ctx.data` (only available on
> `SessionContext`, not on `ExecutionContext`). See
> [`session_state.md`](session_state.md) §2.3 for the per-session
> namespace.

Two access methods are defined on `AppDataNamespace`:

```python
def __getitem__(self, key: type[T]) -> T: ...   # raises KeyError if not registered
def get(self, key: type[T]) -> Optional[T]: ... # returns None if not registered
```

Use `ctx.app_data[Cls]` when the AppState is required (the dependency
on that library is part of the call site's contract; missing it is a
bug). Use `ctx.app_data.get(Cls)` when absence is a valid runtime
state.

### 2.4 Type-checking

`AppDataNamespace.__getitem__` is generic over `T = TypeVar("T", bound=AppState)`,
so type-checkers (mypy, pyright, pylance) infer the correct type from
the class argument:

```python
ctx.app_data[MidiPool].devices.value      # type-checker: list[Device]
ctx.app_data[MidiPool].nonexistent        # type-checker: error, no attribute
ctx.app_data[42]                          # type-checker: error, int isn't type[AppState]
```

This is the same idiom used by `dependency-injector`, FastAPI's
`Depends`, Django's `apps.get_model`, and SQLAlchemy 2.0's typed
`Session.get`. No codegen, no mypy plugin, no `.pyi` stubs — type
inference works out of the box on every modern Python toolchain.

There is deliberately no string-keyed access (`ctx.app_data.midi`) and
no `namespace=` kwarg on the class declaration. Class-keyed access is
the single canonical path. The trade-off is four extra characters and
an import per call site, in exchange for full IDE support and zero
naming ambiguity.

---

## 3. Lifecycle and ownership

### 3.1 Two-component split: registry + container

Following the existing `NodeRegistry` / `NodeFactory` pattern, lifecycle
management is split between two cooperating components. **Registries
hold classes, not instances** — that convention is preserved.

- **`LibraryStateRegistry`** is a `BaseRegistry` subclass. It holds
  *classes* — both `AppState` and `SessionState` subclasses — discovered
  via folder-scan exactly like `NodeRegistry` finds node classes. It
  inherits the full hot-reload, dependency-graph, and folder-scan
  machinery from `BaseRegistry`. It does not instantiate anything. The
  marker bases (`LibraryState`, `AppState`, `SessionState`) are excluded
  by the class filter.

- **`LibraryStateContainer`** holds the *instances*. It now stores two
  scopes side by side: a flat `dict[type[AppState], AppState]` for the
  app-global pool that this document covers, and a per-session
  `dict[type[SessionState], dict[str, SessionState]]` for the SessionState
  scope (see [`session_state.md`](session_state.md) §3 for the
  per-session lifecycle, eager fanout, and `attach_session` /
  `detach_session` machinery). The container subscribes to the
  registry's lifecycle events (the same `_batch_event_subscribers` hook
  `NodeFactory` uses) and routes by class kind:

  ```text
  on AppState class registered     → cls() → store in app pool → call on_enable
  on AppState class unregistered   → call on_disable → drop from app pool
  ```

  `AppDataNamespace[cls]` looks up the instance directly in the app
  pool dict — O(1).

Both live in the DI graph alongside the existing registries, resolved
and wired by `LibrarySystemService.initialize()`. No new singleton, no
new service class — `LibraryStateRegistry` is added the same way
`PanelRegistry` was.

### 3.2 Enable / disable

The lifecycle of every `AppState` instance is bound to its owning
library's enable/disable cycle, mediated by the registry → container
subscription:

```text
library.enable()  →  register_components()  →  folder-scan finds classes
                                            →  LibraryStateRegistry registers each class
                                            →  Container observes the lifecycle event:
                                                ├─ instantiate (cls())
                                                ├─ store in pool
                                                └─ call on_enable() if defined

library.disable() →  LibraryStateRegistry unregisters each class
                  →  Container observes the lifecycle event:
                      ├─ call on_disable() if defined
                      └─ drop instance from pool
```

The instance is destroyed on disable. A subsequent enable creates a
fresh instance. There is no state preservation across the cycle. This
matches the existing semantics for nodes, panels, themes, and other
library-registered components.

### 3.3 Hot-reload

Hot-reload is implemented as `disable + enable`. The container calls
`on_disable` on the *old* instance (still pointing at the old class)
*before* the class is swapped, then instantiates and calls `on_enable`
on the *new* instance with the *new* class. Standard exit-before-enter
discipline, driven by the registry's hot-reload events.

In-flight state is lost on hot-reload. If a library has expensive
startup (warming a large cache, scanning hardware), reload will pay
that cost again. This is by design — the alternative (state migration
across class versions) is a class of bug we are not building.

### 3.4 Order

Folder-scan order within a library is alphabetical. If `AppState`
A in library X depends on `AppState` B in library Y being
initialised first, library X declares `dependencies=["Y"]` on its
`@library` decorator. The library load order already respects declared
dependencies, and instance lifecycle is bound to the registry events
the container subscribes to, so the dependency is transitively
respected.

Within a single library, if two `AppState` subclasses depend on
each other's `on_enable` having run, the author should split them
across sibling libraries or compose them into one class. Cross-
`AppState` dependency ordering inside one library is not
supported.

### 3.5 Observability — VM and other consumers

In v1, **the VM is not informed** when state appears or disappears. It
doesn't need to be. The VM creates an `ExecutionContext` per flow; the
context carries an `AppDataNamespace` that performs a live container
lookup on each `exec_ctx.app_data[Cls]` access. Workers naturally see
the current state at access time.

The documented idiom is **look up state at the access site, not via
long-lived local variables**:

```python
# Recommended — re-resolves on each access:
def worker(self, exec_ctx):
    for msg in self.props.messages.value:
        exec_ctx.app_data[MidiPool].send(msg)

# Acceptable for short worker bodies — captured at function start:
def worker(self, exec_ctx):
    pool = exec_ctx.app_data[MidiPool]
    pool.send(self.props.message.value)
    return {}

# Avoid in long-lived contexts (panels, persistent helpers) — the
# captured reference goes stale on hot-reload:
class MyPanel(Panel):
    def __init__(self, ctx):
        self.pool = ctx.app_data[MidiPool]   # stale after hot-reload — DON'T
```

If a hot-reload occurs mid-flow, the next `ctx.app_data[Cls]` returns
the new instance; any local variable still holding the old one has
stale data, but the strict lifecycle (§3.2) bounds the window to a
single disable/enable cycle.

**Phase 2 evolution.** The container will gain an observable surface as
part of the Phase 2 reactive work
([`spec_panel_reactivity.md`](spec_panel_reactivity.md)):

```python
container.subscribe(cls, callback)   # callback(old_instance, new_instance)
```

Phase 2 reactive auto-tracking will use this internally so panels and
other reactive consumers re-run automatically when an instance is
swapped. Active VM cancellation of in-flight flows on state teardown,
if it ever becomes a real requirement, will subscribe via the same
hook. v1 ships without this surface; v1 consumers re-resolve on access.

---

## 4. Reactivity

AppState fields are reactive **only when the author opts in via
`reactive_field()`**. Non-reactive attributes are plain Python:

```python
class RenderCache(AppState):
    last_clear = reactive_field(0.0)       # reactive
    entries: dict[str, bytes] = {}         # plain
    _lock = threading.Lock()               # plain
```

This is identical to how `SessionContext` already declares its fields.
There is no separate `ReactiveAppState` base, no auto-wrapping, no
introspection: the developer's choice per field, fully explicit.

When Phase 2 reactive auto-tracking lands (see
[`spec_panel_reactivity.md`](spec_panel_reactivity.md)), it will apply
to `AppState` reactive fields with no special-casing — the same
`Reactive[T]` cells, the same `.value` reads, the same subscription
machinery. Library authors learn one reactive primitive and use it
everywhere.

### 4.1 Threading

Phase 1 `Reactive[T]` is a pure value holder with no subscribers. There
is no observable cross-thread bug today.

When Phase 2 reactive subscription machinery lands, thread-safety for
worker-thread mutations of reactive fields will be addressed uniformly
across `SessionContext` and `AppState` (they use the same primitive).
Until then, library authors who mutate `reactive_field` cells from a VM
worker thread should treat that as an open question with the same
caveats as mutating `SessionContext` fields from a worker — to be
resolved by Phase 2.

---

## 5. Boundary — what AppState is NOT for

AppState fills exactly one slot. The boundary is strict; misuse
should be caught in code review.

AppState is **not** for:

| anti-use                               | use instead                                                 |
| -------------------------------------- | ----------------------------------------------------------- |
| serializable / persisted configuration | `LibrarySettings`                                           |
| per-graph state (graph variables)      | `graph.variables`                                           |
| per-flow execution state               | `ExecutionContext.local_ctx`                                |
| external system inputs to a flow       | `ExecutionContext.global_ctx`                               |
| per-session UI state                   | `SessionContext` reactive fields                            |
| per-session library runtime state      | `SessionState` (see [`session_state.md`](session_state.md)) |
| cross-library coordination protocols   | direct Python imports                                       |

Per-session state deserves a callout: there is exactly one instance of
each `AppState`, shared across all sessions. A library author who
needs per-session-keyed data should declare a `SessionState` instead
(see [`session_state.md`](session_state.md)). The framework does not
partition AppState by session; that's what SessionState is for.

### 5.1 Composing LibrarySettings inside AppState

An `AppState` may hold a `LibrarySettings` instance to give it a
serialised configuration slice. This is the **recommended pattern** for
any state that has user-tweakable knobs — poll rates, server ports,
cache sizes — that should persist across runs. (`SessionState` is
**prohibited** from composing `LibrarySettings`; see
[`session_state.md`](session_state.md) §5.2.)

```python
@settings(namespace='midi.pool', label='MIDI Pool')
class MidiSettings(LibrarySettings):
    poll_rate = setting[int](100, label='Poll rate (Hz)')
    auto_connect = setting[bool](True, label='Auto-connect on startup')


class MidiPool(AppState):
    devices = reactive_field([])
    config: MidiSettings | None = None    # type-annotation only

    def on_enable(self) -> None:
        # Instantiate AFTER the settings registry has wired MidiSettings._registry.
        # By the time on_enable fires, every LibrarySettings class registered by
        # this library (or its dependencies) is fully wired.
        self.config = MidiSettings()
        if self.config.auto_connect.value:
            self.devices.value = scan_midi_devices(rate=self.config.poll_rate.value)
```

**Why instantiate in `on_enable` and not in `__init__` or the class
body?**

`LibrarySettings()` requires `cls._registry` to be wired by
`SettingsRegistry` at registration time. The lifecycle order during
library enable is:

1. `register_components()` runs — folder-scans register classes.
2. `SettingsRegistry` wires every `LibrarySettings` subclass's
   `_registry` attribute.
3. `LibraryStateRegistry` registers concrete `LibraryState`
   subclasses (both `AppState` and `SessionState`).
4. The container instantiates each state class and calls `on_enable`.

`on_enable` is the first lifecycle moment where every settings class
in the library is guaranteed to be fully wired. Instantiating in the
class body or in `__init__` risks running before step 2 and crashing
with a `None` registry.

**Hot-reload coordination.** If a `LibrarySettings` schema hot-reloads
while an `AppState` instance holds a `LibrarySettings()` reference,
the cached reference follows the existing `SettingsRegistry`
hot-reload semantics — not an `AppState` concern. If the
`AppState` itself hot-reloads, `on_disable` runs, the old
`config` reference is dropped, and `on_enable` creates a fresh
`MidiSettings()` against the current registry. Clean.

This composition keeps the boundary clean (settings persist, state
doesn't) while giving the AppState a single coherent surface to
its consumers — `ctx.app_data[MidiPool].config.poll_rate.value` and
`ctx.app_data[MidiPool].devices.value` read from the same object.

---

## 6. Implementation surface

> The types listed here are the AppState half of the v1.1 taxonomy.
> Their `SessionState` siblings (`SessionDataNamespace`, the
> per-session container storage, `attach_session` / `detach_session`,
> the `LibrarySettings` prohibition) are documented in
> [`session_state.md`](session_state.md) §6.

### 6.1 Types

- `haywire.core.state.LibraryState` — abstract marker base. Never
  directly subclassed by users; serves as the type root for
  `LibraryStateRegistry`'s class filter and the union root in internal
  type hints.
- `haywire.core.state.AppState` — concrete app-scoped base.
  Optional `on_enable` and `on_disable` methods (duck-typed; absence
  is fine).
- `haywire.core.state.SessionState` — concrete per-session base. See
  [`session_state.md`](session_state.md).
- `haywire.core.state.LibraryStateRegistry` — `BaseRegistry` subclass.
  Holds concrete `LibraryState` *classes*, not instances. `_class_filter`
  checks `issubclass(cls, LibraryState)` and excludes the marker bases
  (`LibraryState`, `AppState`, `SessionState`). Inherits hot-reload,
  dependency-graph, and folder-scan from `BaseRegistry`. Same shape as
  `NodeRegistry`, `PanelRegistry`, etc.
- `haywire.core.state.LibraryStateContainer` — holds the *instances*.
  Internally splits storage by scope: a flat
  `dict[type[AppState], AppState]` for the app-global pool, plus the
  per-session `dict[type[SessionState], dict[str, SessionState]]`
  documented in [`session_state.md`](session_state.md). Subscribes to
  `LibraryStateRegistry` lifecycle events to instantiate / call
  `on_enable` on class registration, and to call `on_disable` / drop
  the instance on unregistration. Mirrors the `NodeRegistry` →
  `NodeFactory` relationship.
- `haywire.ui.context.AppDataNamespace` — generic proxy with
  `__getitem__[T]` and `get[T]` bound to `AppState`. Holds a reference
  to the `LibraryStateContainer` and performs live container lookups.
  Used by both `SessionContext` (as `ctx.app_data`) and
  `ExecutionContext` (as `exec_ctx.app_data`).
- `haywire.ui.context.SessionDataNamespace` — sibling proxy bound to
  `SessionState`; only present on `SessionContext`. See
  [`session_state.md`](session_state.md) §6.

### 6.2 Changes to existing types

- `LibrarySystemService.initialize()`:
  - Resolve `LibraryStateRegistry` and `LibraryStateContainer` from
    the injector alongside the existing registries.
  - Wire the container as a subscriber of the registry's batch
    lifecycle events (the same hook `NodeFactory` uses).
  - Add `library_registry.add_class_registry(LibraryStateRegistry,
    state_registry)` so the existing
    `enable_all_libraries()` / hot-reload pipeline drives state
    lifecycle automatically.
- `SessionContext`:
  - **add** `app_data: AppDataNamespace` field, populated at construction
    from the app's container.
  - **add** `data: SessionDataNamespace` field (per-session lookups).
  - **delete** the unused `metadata: Dict[str, Any]` field. Zero call
    sites in the current code; superseded by AppState / SessionState.
- `ExecutionContext`:
  - **add** `app_data: AppDataNamespace` field, populated by
    `HaywireVM._create_execution_context()` from the container the
    VM was constructed with. (No `data` attribute — graphs run
    app-globally; see [`session_state.md`](session_state.md) §2.3.)
- `HaywireVM`:
  - Gain a reference to the `LibraryStateContainer` (via constructor
    argument or DI lookup at construction). No reference to the
    *registry* — the VM only ever needs the live instance pool.
  - `_create_execution_context()` populates `ExecutionContext.app_data`
    with an `AppDataNamespace` pointing at the container.
- `BaseLibrary`:
  - No new behaviour — the existing folder-scan call
    (`add_folder_to_registry(..., LibraryStateRegistry)`) is the only
    action a library author writes. Class registration drives
    instance lifecycle through the container subscription; libraries
    don't manage instances themselves.

### 6.3 Breaking changes

- `SessionContext.metadata` deleted. (Currently unused — verified
  zero call sites.)
- `HaywireVM.__init__` signature gains a container reference (or
  resolves one via DI). Tests that build a VM directly need updating.

These are the only breaking changes. `ExecutionContext.app_data` is
purely additive. Existing libraries that don't use AppState are
unaffected.

---

## 7. Examples

### 7.1 A live MIDI device pool

```python
# barn/haybale-midi/haybale_midi/state/midi_pool.py

class MidiPool(AppState):
    devices = reactive_field([])

    def on_enable(self) -> None:
        self.devices.value = scan_devices()

    def on_disable(self) -> None:
        self.devices.value = []
```

```python
# barn/haybale-midi/haybale_midi/panels/device_list.py

@panel(focus=GraphFocus, ...)
class MidiDeviceListPanel(Panel):
    def draw(self, ctx, layout, actions):
        for device in ctx.app_data[MidiPool].devices.value:
            layout.label(device.name)
```

```python
# barn/haybale-midi/haybale_midi/nodes/midi_send.py

class MidiSendNode(BaseNode):
    def worker(self, exec_ctx: ExecutionContext) -> dict:
        pool = exec_ctx.app_data[MidiPool]
        device_id = self.props.device_id.value
        pool.connections[device_id].send(self.props.message.value)
        return {}
```

### 7.2 A render cache (non-reactive, not configurable)

```python
class RenderCache(AppState):
    entries: dict[str, bytes] = {}
    max_bytes: int = 256 * 1024 * 1024

    def get_or_compute(self, key: str, fn: Callable[[], bytes]) -> bytes:
        if key not in self.entries:
            self.entries[key] = fn()
        return self.entries[key]

    def on_disable(self) -> None:
        self.entries.clear()
```

No `reactive_field()` because the cache's contents don't drive UI
re-renders. Consumers call `get_or_compute()` from worker functions.
No `LibrarySettings` involved because there's nothing to persist.

### 7.3 An AppState with composed settings

```python
class OscBridge(AppState):
    config: OscSettings
    server: OscServer | None = None

    def on_enable(self) -> None:
        self.config = OscSettings()
        self.server = OscServer(port=self.config.port)
        self.server.start()

    def on_disable(self) -> None:
        if self.server:
            self.server.stop()
            self.server = None
```

`OscSettings` (a `LibrarySettings` subclass) handles persisted config —
port, address, log level. `OscBridge` (an `AppState`) holds the
runtime server instance. Clean separation, both accessible together via
`ctx.app_data[OscBridge]`.

---

## 8. Open questions

These are deliberately deferred for now and noted for future spec
revisions:

- **Sub-state lifecycle ordering within one library.** Currently
  unsupported (alphabetical folder order). If a real use case appears,
  add a `depends_on=` ClassVar on AppState subclasses.
- **State preservation across hot-reload.** Currently destroyed.
  Optional `on_reload(old_instance)` hook can be added later if a
  library has expensive startup that justifies the migration risk.
- **Cross-thread reactive writes.** Bound to Phase 2 reactive work; not
  an AppState-specific concern.
- **`.pyi` stubs / autocomplete on `ctx.app_data.<TAB>`.** Not provided —
  class-keyed access is the canonical path and provides full type
  inference without codegen. Revisit only if a string-keyed shorthand
  becomes desirable.
