---
status: draft
doc_template: impl-spec
scope: LibraryStateRegistry, LibraryStateContainer, lifecycle pipeline, session attach/detach, hot-reload coordination
see-also:
  - ../../components/states/state-canon.md
  - ../../guides/signals.md
  - ../library-system/library-system-arch.md
  - ../hot-reload/hot-reload-arch.md
  - ../../reference/glossary.md
---

# Session and State — Architecture

## 1. Mental model

The state subsystem holds **library-owned runtime data** at two scopes — app-global (`AppState`) and per-session (`SessionState`) — and routes every read through a class-keyed namespace on `SessionContext` (UI side) or `ExecutionContext` (workers). Two cooperating components, one shape each:

- **`LibraryStateRegistry`** — a `BaseRegistry` subclass holding *classes*. Discovers concrete `LibraryState` subclasses (both `AppState` and `SessionState`) via folder-scan, exactly like `NodeRegistry` finds node classes. It does not instantiate anything.
- **`LibraryStateContainer`** — holds the *instances*, in two side-by-side stores: a flat `dict[type[AppState], AppState]` for the app-global pool and a per-session `dict[type[SessionState], dict[str, SessionState]]` for per-session pools. Subscribes to the registry's lifecycle events and routes by class kind.

This is the same separation `NodeRegistry`/`NodeFactory` uses: registries hold classes, factories or containers hold instances. No new singleton pattern, no new service class — `LibraryStateRegistry` is added to the DI graph the same way `PanelRegistry` was.

The authoring side (`@state` decorator, `on_enable`/`on_disable` hooks, the access patterns) lives in [components/states](../../components/states/state-canon.md). This file documents what happens *under* that surface.

## 2. Contract

### 2.1 Type hierarchy

```python
# haywire/core/state/base.py
class LibraryState:               # abstract marker — never directly subclassed by users
    class_identity: LibraryStateClassIdentity

class AppState(LibraryState):     # 1 instance, app-global
    ...

class SessionState(LibraryState): # 1 instance per session
    session_id: str   # set by container before on_enable
    ...
```

`LibraryState` is the type root for `LibraryStateRegistry`'s class filter. The filter accepts *concrete* subclasses of `LibraryState` and excludes the three marker bases (`LibraryState`, `AppState`, `SessionState`).

### 2.2 Two access namespaces

`SessionContext` and `ExecutionContext` expose state through generic-typed namespaces:

```python
A = TypeVar("A", bound=AppState)
S = TypeVar("S", bound=SessionState)

class AppDataNamespace:
    def __getitem__(self, cls: type[A]) -> A: ...   # raises KeyError
    def get(self, cls: type[A]) -> A | None: ...

class SessionDataNamespace:
    def __getitem__(self, cls: type[S]) -> S: ...
    def get(self, cls: type[S]) -> S | None: ...
```

| Context | `ctx.app_data` | `ctx.data` |
|---|---|---|
| `SessionContext` (UI) | `AppDataNamespace` | `SessionDataNamespace` |
| `ExecutionContext` (workers) | `AppDataNamespace` | does not exist |

**Asymmetric on purpose.** Node graphs run app-globally — the VM has no notion of which UI session triggered execution. So `ExecutionContext.data` doesn't exist; reading it is a type error and an `AttributeError` at runtime.

### 2.3 Signal fields

A signal field is a class attribute that emits a `Signal` on write. Declared with `signal_field(initial_value)` on a `SignalSource` subclass (`SessionContext`, `SessionState`, or `AppState`):

```python
class EditState(SessionState):
    active_node: Optional[NodeWrapper] = signal_field(None)
```

Read with bare attribute access (`edit.active_node`). Write with bare assignment (`edit.active_node = wrapper`). Identity-equal writes are no-ops.

Subscribe by referencing the class-level field as the signal type:

```python
@redraw_on(EditState.active_node)
def _on(self, ctx, signal): ...
```

The framework synthesizes one `Signal` subclass per field at class-definition time; the field reference IS the subscription key. No separate event class to import.

Routing is scope-determined: a `SessionState` / `SessionContext` field publishes on the owning `Session`'s `SignalBus`; an `AppState` field broadcasts cross-session via `SessionManager`. Subscribers attach to the same bus they would for any hand-authored `Signal`.

### 2.4 Registry filter

```python
class LibraryStateRegistry(BaseRegistry):
    def _class_filter(self, cls: type) -> bool:
        return (
            issubclass(cls, LibraryState)
            and cls is not LibraryState
            and cls is not AppState
            and cls is not SessionState
        )
```

This is what makes `add_folder_to_registry(folder=base/'state', registry_cls=LibraryStateRegistry)` work: every concrete `LibraryState` subclass in the folder is registered, regardless of whether it inherits from `AppState` or `SessionState`. The container disambiguates downstream.

### 2.5 Container storage

```python
class LibraryStateContainer:
    _app: dict[type[AppState], AppState]
    _session: dict[type[SessionState], dict[str, SessionState]]
```

`AppDataNamespace.__getitem__(cls)` does an O(1) dict lookup in `_app`. `SessionDataNamespace.__getitem__(cls)` does a two-level lookup: `_session[cls][session_id]`.

## 3. Lifecycle

### 3.1 AppState lifecycle

```text
library.enable()
  ├─ register_components()         ← author-written
  │   └─ folder-scan finds class
  │
  ├─ LibraryStateRegistry registers each class
  │
  └─ Container observes the lifecycle event:
      ├─ instantiate (cls())
      ├─ store in _app pool
      └─ call on_enable() if defined

library.disable()
  ├─ LibraryStateRegistry unregisters each class
  │
  └─ Container observes the lifecycle event:
      ├─ call on_disable() if defined
      └─ drop instance from _app pool
```

Standard `BaseRegistry` event pipeline — same hook `NodeFactory` uses (`_batch_event_subscribers`).

### 3.2 SessionState lifecycle — eager fanout

`SessionState` is more involved because there's an N×M cross product (N classes × M sessions). The container handles this by **eager fanout on both axes**:

- When a `SessionState` *class* registers and one or more sessions are already attached, the container instantiates one instance *per attached session* and calls `on_enable` on each.
- When a session *attaches* and one or more `SessionState` classes are already registered, the container instantiates one instance *per registered class* and calls `on_enable` on each.

```text
Class registers (with sessions attached)
  ├─ for each session in attached:
  │   ├─ instance = cls()
  │   ├─ instance.session_id = session.id  ← stamped BEFORE on_enable
  │   ├─ store in _session[cls][session.id]
  │   └─ call on_enable() if defined

Session attaches (with classes registered)
  ├─ for each cls in registered SessionState classes:
  │   ├─ instance = cls()
  │   ├─ instance.session_id = session.id
  │   ├─ store in _session[cls][session.id]
  │   └─ call on_enable() if defined

Session detaches
  ├─ for each cls in _session:
  │   ├─ instance = _session[cls].pop(session.id)
  │   ├─ call on_disable() if defined
  │   └─ release reference

Class unregisters
  ├─ for each session_id in _session[cls]:
  │   ├─ instance = _session[cls].pop(session_id)
  │   ├─ call on_disable() if defined
  │   └─ release reference
  └─ del _session[cls]
```

**`session_id` stamping.** Set by the container *between* `cls()` and `on_enable`. The base class declares the attribute so type-checkers know it exists; `__init__` cannot read it (not yet stamped); `on_enable` is the first lifecycle moment where it's available.

**`attach_session` / `detach_session` API.** Called by the framework's session manager when a browser session connects/disconnects:

```python
container.attach_session(session)    # eager fanout for all registered SessionState classes
container.detach_session(session)    # tear down and drop all instances for this session
```

These are not author-callable surfaces — the framework owns session lifecycle.

### 3.3 Ordering — first-load and hot-reload

**Recommended scan order in `register_components()`:** `settings → state → nodes / panels / editors / themes`.

This mirrors the framework's hot-reload propagation chain:

```text
SettingsRegistry → LibraryStateRegistry → NodeRegistry, PanelRegistry, EditorTypeRegistry
```

Following the same order at first-load means an `AppState` whose `on_enable` reads a `LibrarySettings()` value finds the schema already wired, and node/panel/editor classes that import an `AppState` for use as a `ctx.app_data[Cls]` key resolve it during their own scan.

Within a single library, folder-scan order is alphabetical. Cross-library ordering respects `dependencies=` declared on `@library` (the existing inter-library dependency mechanism — no new ordering machinery is added). Cross-`AppState` dependency ordering inside one library is **not** supported; if A's `on_enable` requires B already initialised, split them into sibling libraries.

### 3.4 Hot-reload semantics

Hot-reload is implemented as **`disable + enable`**:

1. Container calls `on_disable` on the *old* instance (still pointing at the old class) *before* the class is swapped.
2. Class is swapped in the registry.
3. Container instantiates a *new* instance with the *new* class and calls `on_enable`.

In-flight state is lost. The alternative — state migration across class versions — is a class of bug we are not building.

For SessionState the same pipeline runs *per session* — each session's instance is disabled, the class swaps, then each session gets a fresh instance with `on_enable` called.

**Signal-field reload semantics.** Each signal field on a reloaded class synthesizes a fresh `Signal` subclass at class-definition time, distinct from the pre-reload one. Subscribers that captured the old class's signal type will not receive emits from the new class's writes.

Recovery is the same `disable + enable` pipeline above — editors and panels tear down (dropping their subscriptions) and are recreated, at which point they pick up the new synthetic signal class. No special framework machinery is required; synthetic signal classes participate exactly like hand-authored `Signal` subclasses.

The full hot-reload pipeline (file watcher → import → rebuild downstream) lives in [architecture/hot-reload](../hot-reload/hot-reload-arch.md). State is one of several systems that subscribe to it.

### 3.5 Composing `LibrarySettings` inside `AppState`

`AppState` may hold a `LibrarySettings` instance to give it a serialised configuration slice — the recommended pattern for state with persisted, user-tweakable knobs. The lifecycle order during library enable is critical:

```text
1. register_components() runs → folder-scans register classes
2. SettingsRegistry wires every LibrarySettings subclass's _registry attribute
3. LibraryStateRegistry registers concrete LibraryState subclasses
4. Container instantiates each state class and calls on_enable
```

`on_enable` is the first lifecycle moment where every `LibrarySettings` class in the library is guaranteed to be fully wired. Instantiating in `__init__` or the class body risks running before step 2 and crashing with a `None` registry.

`SessionState` is **prohibited** from composing `LibrarySettings` — per-session state shouldn't read persisted singleton settings. If the same concern needs both, hold the settings on a sibling `AppState` and reference it through the access namespaces.

### 3.6 Observability — VM and other consumers

In v1, **the VM is not informed** when state appears or disappears. It doesn't need to be: the VM creates an `ExecutionContext` per flow; the context carries an `AppDataNamespace` that performs a live container lookup on each `exec_ctx.app_data[Cls]` access. Workers naturally see the current state at access time.

The documented idiom (covered in [components/states §3](../../components/states/state-canon.md#3-important-concepts)) is: **look up state at the access site, not via long-lived local variables**. Captured references go stale on hot-reload.

**Container-level observation.** The container may later gain an observable surface for class swap events (so panels can re-run automatically when an `AppState` / `SessionState` instance is replaced by hot-reload):

```python
container.subscribe(cls, callback)   # callback(old_instance, new_instance)
```

Field-level reactivity is already covered by the signal-field channel (§2.3) — writes to declared signal fields fan out through `SignalBus`. Class-replacement notification is a separate, deferred concern; add it if and when a concrete consumer needs it.

## 4. Boundary

The state subsystem is **not**:

- A **persistence layer**. AppState and SessionState are runtime-only; persistent configuration belongs in `LibrarySettings`.
- A **cross-library coordination protocol**. Direct Python imports are the right tool there — state isn't an IPC mechanism.
- A way to share **session-keyed data through `ExecutionContext`**. Graphs run app-globally; if a node needs session-keyed input, the orchestrating panel must pass it via `ExecutionContext.global_ctx`.
- A replacement for `graph.variables`. Per-graph state lives there; AppState is per-app, SessionState is per-session.

## 5. Examples

### 5.1 Container subscription (internal pattern)

```python
class LibraryStateContainer:
    def __init__(self, registry: LibraryStateRegistry):
        self._registry = registry
        self._app: dict[type[AppState], AppState] = {}
        self._session: dict[type[SessionState], dict[str, SessionState]] = {}
        self._sessions: dict[str, Session] = {}

        registry.subscribe_lifecycle_events(self._on_class_event)

    def _on_class_event(self, event):
        cls = event.cls
        if event.kind == 'registered':
            if issubclass(cls, AppState):
                self._instantiate_app(cls)
            elif issubclass(cls, SessionState):
                self._fanout_session_class(cls)
        elif event.kind == 'unregistered':
            self._teardown(cls)

    def _instantiate_app(self, cls: type[AppState]):
        instance = cls()
        self._app[cls] = instance
        if hasattr(instance, 'on_enable'):
            instance.on_enable()

    def _fanout_session_class(self, cls: type[SessionState]):
        self._session[cls] = {}
        for session in self._sessions.values():
            self._instantiate_session(cls, session)

    def _instantiate_session(self, cls, session):
        instance = cls()
        instance.session_id = session.id   # stamp BEFORE on_enable
        self._session[cls][session.id] = instance
        if hasattr(instance, 'on_enable'):
            instance.on_enable()
```

### 5.2 LibrarySystemService wiring

```python
# haywire/core/di/config.py
class LibrarySystemService:
    def initialize(self):
        # Resolve registries from the injector
        state_registry = self._injector.get(LibraryStateRegistry)
        state_container = self._injector.get(LibraryStateContainer)

        # Wire the container as a subscriber of the registry's events
        # — same hook NodeFactory uses
        state_container._subscribe_to_registry(state_registry)

        # Add to the existing class-registry pipeline so enable_all_libraries()
        # / hot-reload drives state lifecycle automatically
        self._library_registry.add_class_registry(
            LibraryStateRegistry, state_registry,
        )
```

### 5.3 Type-checker enforcement of the asymmetry

```python
ctx: SessionContext
exec_ctx: ExecutionContext

ctx.data[TimelineCursor]            # OK — SessionContext has .data
ctx.app_data[MidiPool]              # OK — both have .app_data
exec_ctx.app_data[MidiPool]         # OK
exec_ctx.data                       # type error: ExecutionContext has no attribute 'data'
ctx.data[MidiPool]                  # type error: MidiPool : type[AppState], not type[SessionState]
ctx.app_data[TimelineCursor]        # type error: TimelineCursor : type[SessionState]
```

The generic `TypeVar("A", bound=AppState)` / `TypeVar("S", bound=SessionState)` constraints surface these mismatches in mypy / pyright / pylance.

## 6. Open questions

- **Sub-state lifecycle ordering within one library.** Currently unsupported (alphabetical folder order). If a real use case appears, add a `depends_on=` ClassVar on state subclasses.
- **State preservation across hot-reload.** Currently destroyed. Optional `on_reload(old_instance)` hook can be added later if a library has expensive startup that justifies the migration risk.
- **Cross-thread signal-field writes.** `SignalBus` is sync, main-loop-only; cross-thread writes would need `call_soon_threadsafe` plumbing on the `Session` layer. Not state-subsystem-specific.
- **Framework-side EditState migration (v1.2).** A planned move of the framework's per-session edit state (selection, scroll, modal stack) into the `SessionState` taxonomy. Currently held in ad-hoc fields on `SessionContext`; would unify with library-author-declared session state.
- **`.pyi` stubs / autocomplete on `ctx.app_data.<TAB>`.** Not provided — class-keyed access is the canonical path and provides full type inference without codegen. Revisit only if a string-keyed shorthand becomes desirable.

For the authoring API surface — `AppState` / `SessionState` declaration, `@state` decorator, lifecycle hooks, the `ctx.app_data` / `ctx.data` access patterns — see [components/states](../../components/states/state-canon.md).
