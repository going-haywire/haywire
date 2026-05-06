# Spec: LibraryState — library-owned runtime state

> Status: **v1 implemented (2026-05-06).** This document is the canonical
> reference for LibraryState. Phase 2 (observable container, reactive
> auto-tracking) remains pending — see spec_panel_reactivity.md.
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

A **LibraryState** is a Python class that a library declares to hold its
own app-global runtime data. The framework instantiates it once when the
library is enabled, owns its lifecycle, and exposes the instance through
a uniform access pattern on both `SessionContext` (UI) and
`ExecutionContext` (node execution).

LibraryState is characterized by what it **is**:

- App-global. One instance, shared across all browser sessions and the VM.
- Library-owned. The owning library declares the class, and the
  framework destroys the instance when the library is disabled or
  hot-reloaded.
- Runtime, not persisted. LibraryState holds volatile state — open
  connections, caches, pools, live device handles, ML models. Persistent
  configuration belongs in `LibrarySettings`.
- Free in shape. A LibraryState may contain anything: plain Python
  attributes, `reactive_field()` cells, nested `LibrarySettings`
  instances, threads, sockets, NumPy arrays. The framework imposes no
  field-level constraints.
- Accessed by class, not by string. The canonical access pattern is
  `ctx.data[MidiPool]`. There is no namespace string and no
  attribute-style shorthand. The class itself is the unambiguous
  identifier.

LibraryState fills a previously empty slot in the architecture:

| concern                              | mechanism                              |
| ------------------------------------ | -------------------------------------- |
| persistent app/library config        | `LibrarySettings`, `FrameworkSettings` |
| per-graph state                      | `graph.variables`                      |
| per-flow execution state             | `ExecutionContext.local_ctx`           |
| external system inputs to a flow     | `ExecutionContext.global_ctx`          |
| per-session UI selection state       | `SessionContext` reactive fields       |
| **app-global library runtime state** | **`LibraryState`** *(this spec)*       |

---

## 2. The contract

### 2.1 Declaration

A LibraryState is a subclass of `LibraryState` placed in the library's
`state/` folder (or any folder the library registers with
`LibraryStateRegistry`).

```python
# barn/haybale-midi/haybale_midi/state/midi_pool.py

from haywire.core.state import LibraryState
from haywire.ui.reactive import reactive_field

class MidiPool(LibraryState):
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

A library may declare zero, one, or many LibraryState subclasses. Each
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
hot-reload propagation, so a `LibraryState` whose `on_enable` reads a
`LibrarySettings()` value finds the schema already wired, and node /
panel / editor classes that import a `LibraryState` for use as a
`ctx.data[Cls]` key resolve it during their own scan.

Folder scan discovers every `LibraryState` subclass in the folder and
registers it. Discovery order within a folder is alphabetical; if one
LibraryState's `on_enable` depends on another already being initialised,
the dependent library should declare `dependencies=` on its `@library`
decorator (the existing inter-library dependency mechanism applies — no
new ordering machinery is added).

### 2.3 Access

Both `SessionContext` and `ExecutionContext` gain a `data` attribute of
type `_DataNamespace`. The only access pattern is class-keyed:

```python
# From a panel (UI side):
def draw(self, ctx: SessionContext, layout, actions) -> None:
    pool = ctx.data[MidiPool]
    for device in pool.devices.value:
        layout.label(device.name)

# From a node worker (execution side):
def worker(self, exec_ctx: ExecutionContext) -> dict:
    pool = exec_ctx.data[MidiPool]
    return {"device_count": len(pool.devices.value)}
```

Two access methods are defined on `_DataNamespace`:

```python
def __getitem__(self, key: type[T]) -> T: ...   # raises KeyError if not registered
def get(self, key: type[T]) -> Optional[T]: ... # returns None if not registered
```

Use `ctx.data[Cls]` when the LibraryState is required (the dependency on
that library is part of the call site's contract; missing it is a bug).
Use `ctx.data.get(Cls)` when absence is a valid runtime state.

### 2.4 Type-checking

`_DataNamespace.__getitem__` is generic over `T = TypeVar("T", bound=LibraryState)`,
so type-checkers (mypy, pyright, pylance) infer the correct type from
the class argument:

```python
ctx.data[MidiPool].devices.value      # type-checker: list[Device]
ctx.data[MidiPool].nonexistent        # type-checker: error, no attribute
ctx.data[42]                          # type-checker: error, int isn't type[LibraryState]
```

This is the same idiom used by `dependency-injector`, FastAPI's
`Depends`, Django's `apps.get_model`, and SQLAlchemy 2.0's typed
`Session.get`. No codegen, no mypy plugin, no `.pyi` stubs — type
inference works out of the box on every modern Python toolchain.

There is deliberately no string-keyed access (`ctx.data.midi`) and no
namespace=` kwarg on the class declaration. Class-keyed access is the
single canonical path. The trade-off is four extra characters and an
import per call site, in exchange for full IDE support and zero naming
ambiguity.

---

## 3. Lifecycle and ownership

### 3.1 Two-component split: registry + container

Following the existing `NodeRegistry` / `NodeFactory` pattern, lifecycle
management is split between two cooperating components. **Registries
hold classes, not instances** — that convention is preserved.

- **`LibraryStateRegistry`** is a `BaseRegistry` subclass. It holds
  *classes* (`LibraryState` subclasses), discovered via folder-scan
  exactly like `NodeRegistry` finds node classes. It inherits the full
  hot-reload, dependency-graph, and folder-scan machinery from
  `BaseRegistry`. It does not instantiate anything.

- **`LibraryStateContainer`** holds the *instances* — the "big pool"
  the user sees through `ctx.data`. Internally a flat
  `dict[type[LibraryState], LibraryState]`. The container subscribes
  to the registry's lifecycle events (the same
  `_batch_event_subscribers` hook `NodeFactory` uses) and reacts:

  ```text
  on class registered      → cls()  → store instance → call on_enable
  on class unregistered    → call on_disable → drop instance
  ```

  `_DataNamespace[cls]` looks up the instance directly in the
  container's dict — O(1).

Both live in the DI graph alongside the existing registries, resolved
and wired by `LibrarySystemService.initialize()`. No new singleton, no
new service class — `LibraryStateRegistry` is added the same way
`PanelRegistry` was.

### 3.2 Enable / disable

The lifecycle of every `LibraryState` instance is bound to its owning
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

Folder-scan order within a library is alphabetical. If `LibraryState`
A in library X depends on `LibraryState` B in library Y being
initialised first, library X declares `dependencies=["Y"]` on its
`@library` decorator. The library load order already respects declared
dependencies, and instance lifecycle is bound to the registry events
the container subscribes to, so the dependency is transitively
respected.

Within a single library, if two `LibraryState` subclasses depend on
each other's `on_enable` having run, the author should split them
across sibling libraries or compose them into one class. Cross-
`LibraryState` dependency ordering inside one library is not
supported.

### 3.5 Observability — VM and other consumers

In v1, **the VM is not informed** when state appears or disappears. It
doesn't need to be. The VM creates an `ExecutionContext` per flow; the
context carries a `_DataNamespace` that performs a live container
lookup on each `ctx.data[Cls]` access. Workers naturally see the
current state at access time.

The documented idiom is **look up state at the access site, not via
long-lived local variables**:

```python
# Recommended — re-resolves on each access:
def worker(self, exec_ctx):
    for msg in self.props.messages.value:
        exec_ctx.data[MidiPool].send(msg)

# Acceptable for short worker bodies — captured at function start:
def worker(self, exec_ctx):
    pool = exec_ctx.data[MidiPool]
    pool.send(self.props.message.value)
    return {}

# Avoid in long-lived contexts (panels, persistent helpers) — the
# captured reference goes stale on hot-reload:
class MyPanel(Panel):
    def __init__(self, ctx):
        self.pool = ctx.data[MidiPool]   # stale after hot-reload — DON'T
```

If a hot-reload occurs mid-flow, the next `ctx.data[Cls]` returns the
new instance; any local variable still holding the old one has stale
data, but the strict lifecycle (§3.2) bounds the window to a single
disable/enable cycle.

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

LibraryState fields are reactive **only when the author opts in via
`reactive_field()`**. Non-reactive attributes are plain Python:

```python
class RenderCache(LibraryState):
    last_clear = reactive_field(0.0)       # reactive
    entries: dict[str, bytes] = {}         # plain
    _lock = threading.Lock()               # plain
```

This is identical to how `SessionContext` already declares its fields.
There is no separate `ReactiveLibraryState` base, no auto-wrapping, no
introspection: the developer's choice per field, fully explicit.

When Phase 2 reactive auto-tracking lands (see
[`spec_panel_reactivity.md`](spec_panel_reactivity.md)), it will apply
to `LibraryState` reactive fields with no special-casing — the same
`Reactive[T]` cells, the same `.value` reads, the same subscription
machinery. Library authors learn one reactive primitive and use it
everywhere.

### 4.1 Threading

Phase 1 `Reactive[T]` is a pure value holder with no subscribers. There
is no observable cross-thread bug today.

When Phase 2 reactive subscription machinery lands, thread-safety for
worker-thread mutations of reactive fields will be addressed uniformly
across `SessionContext` and `LibraryState` (they use the same primitive).
Until then, library authors who mutate `reactive_field` cells from a VM
worker thread should treat that as an open question with the same
caveats as mutating `SessionContext` fields from a worker — to be
resolved by Phase 2.

---

## 5. Boundary — what LibraryState is NOT for

LibraryState fills exactly one slot. The boundary is strict; misuse
should be caught in code review.

LibraryState is **not** for:

| anti-use                               | use instead                      |
| -------------------------------------- | -------------------------------- |
| serializable / persisted configuration | `LibrarySettings`                |
| per-graph state (graph variables)      | `graph.variables`                |
| per-flow execution state               | `ExecutionContext.local_ctx`     |
| external system inputs to a flow       | `ExecutionContext.global_ctx`    |
| per-session UI state                   | `SessionContext` reactive fields |
| cross-library coordination protocols   | direct Python imports            |

Per-session state deserves a callout: there is exactly one instance of each `LibraryState`, shared across all sessions. A library author who needs per-session-keyed data implements it inside their LibraryState (`self.per_session: dict[str, Foo]`), keying by `session_id` themselves. The framework does not partition LibraryState by session.

### 5.1 Composing LibrarySettings inside LibraryState

A `LibraryState` may hold a `LibrarySettings` instance to give it a
serialised configuration slice. This is the **recommended pattern** for
any state that has user-tweakable knobs — poll rates, server ports,
cache sizes — that should persist across runs.

```python
@settings(namespace='midi.pool', label='MIDI Pool')
class MidiSettings(LibrarySettings):
    poll_rate = setting[int](100, label='Poll rate (Hz)')
    auto_connect = setting[bool](True, label='Auto-connect on startup')


class MidiPool(LibraryState):
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
3. `LibraryStateRegistry` registers `LibraryState` subclasses.
4. The container instantiates each state class and calls `on_enable`.

`on_enable` is the first lifecycle moment where every settings class
in the library is guaranteed to be fully wired. Instantiating in the
class body or in `__init__` risks running before step 2 and crashing
with a `None` registry.

**Hot-reload coordination.** If a `LibrarySettings` schema hot-reloads
while a `LibraryState` instance holds a `LibrarySettings()` reference,
the cached reference follows the existing `SettingsRegistry`
hot-reload semantics — not a `LibraryState` concern. If the
`LibraryState` itself hot-reloads, `on_disable` runs, the old
`config` reference is dropped, and `on_enable` creates a fresh
`MidiSettings()` against the current registry. Clean.

This composition keeps the boundary clean (settings persist, state
doesn't) while giving the LibraryState a single coherent surface to
its consumers — `ctx.data[MidiPool].config.poll_rate.value` and
`ctx.data[MidiPool].devices.value` read from the same object.

---

## 6. Implementation surface

### 6.1 New types

- `haywire.core.state.LibraryState` — base class. Optional `on_enable`
  and `on_disable` methods (duck-typed; absence is fine).
- `haywire.core.state.LibraryStateRegistry` — `BaseRegistry` subclass.
  Holds `LibraryState` *classes*, not instances. `_class_filter`
  checks `issubclass(cls, LibraryState)`. Inherits hot-reload,
  dependency-graph, and folder-scan from `BaseRegistry`. Same shape as
  `NodeRegistry`, `PanelRegistry`, etc.
- `haywire.core.state.LibraryStateContainer` — holds the *instances*.
  Internal `dict[type[LibraryState], LibraryState]`. Subscribes to
  `LibraryStateRegistry` lifecycle events to instantiate / call
  `on_enable` on class registration, and to call `on_disable` / drop
  the instance on unregistration. Mirrors the `NodeRegistry` →
  `NodeFactory` relationship.
- `haywire.ui.context._DataNamespace` (or equivalent module) — generic
  proxy with `__getitem__[T]` and `get[T]`. Holds a reference to the
  `LibraryStateContainer` and performs live container lookups. Used by
  both `SessionContext` and `ExecutionContext`.

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
  - **add** `data: _DataNamespace` field, populated at construction
    from the app's container.
  - **delete** the unused `metadata: Dict[str, Any]` field. Zero call
    sites in the current code; superseded by `LibraryState`.
- `ExecutionContext`:
  - **add** `data: _DataNamespace` field, populated by
    `HaywireVM._create_execution_context()` from the container the
    VM was constructed with.
- `HaywireVM`:
  - Gain a reference to the `LibraryStateContainer` (via constructor
    argument or DI lookup at construction). No reference to the
    *registry* — the VM only ever needs the live instance pool.
  - `_create_execution_context()` populates `ExecutionContext.data`
    with a `_DataNamespace` pointing at the container.
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

These are the only breaking changes. `ExecutionContext.data` is purely
additive. Existing libraries that don't use `LibraryState` are
unaffected.

---

## 7. Examples

### 7.1 A live MIDI device pool

```python
# barn/haybale-midi/haybale_midi/state/midi_pool.py

class MidiPool(LibraryState):
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
        for device in ctx.data[MidiPool].devices.value:
            layout.label(device.name)
```

```python
# barn/haybale-midi/haybale_midi/nodes/midi_send.py

class MidiSendNode(BaseNode):
    def worker(self, exec_ctx: ExecutionContext) -> dict:
        pool = exec_ctx.data[MidiPool]
        device_id = self.props.device_id.value
        pool.connections[device_id].send(self.props.message.value)
        return {}
```

### 7.2 A render cache (non-reactive, not configurable)

```python
class RenderCache(LibraryState):
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

### 7.3 A LibraryState with composed settings

```python
class OscBridge(LibraryState):
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
port, address, log level. `OscBridge` (a `LibraryState`) holds the
runtime server instance. Clean separation, both accessible together via
`ctx.data[OscBridge]`.

---

## 8. Open questions

These are deliberately deferred for now and noted for future spec
revisions:

- **Sub-state lifecycle ordering within one library.** Currently
  unsupported (alphabetical folder order). If a real use case appears,
  add a `depends_on=` ClassVar on LibraryState subclasses.
- **State preservation across hot-reload.** Currently destroyed.
  Optional `on_reload(old_instance)` hook can be added later if a
  library has expensive startup that justifies the migration risk.
- **Cross-thread reactive writes.** Bound to Phase 2 reactive work; not
  a LibraryState-specific concern.
- **`.pyi` stubs / autocomplete on `ctx.data.<TAB>`.** Not provided —
  class-keyed access is the canonical path and provides full type
  inference without codegen. Revisit only if a string-keyed shorthand
  becomes desirable.
