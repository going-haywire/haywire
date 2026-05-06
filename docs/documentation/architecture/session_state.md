# Spec: SessionState — per-session library-owned runtime state

> Status: **Speculative (v1.1).** Designed via inquisition on 2026-05-06.
> Builds on the LibraryState v1 system (see [`library_state.md`](library_state.md)).
>
> Scope: extends the LibraryState extension point with a second scope —
> per-UI-session — alongside the existing app-global scope. Restructures
> the taxonomy so both scopes are first-class siblings.
>
> **Companion documents:**
>
> - [`library_state.md`](library_state.md) — the v1 spec; shared machinery
>   (registry, lifecycle hooks, hot-reload semantics, identity, container
>   subscription model) is documented there. This spec cross-references
>   rather than restates.
> - [`spec_panel_reactivity.md`](spec_panel_reactivity.md) — Phase 2
>   reactive auto-tracking, applies uniformly to both `AppState` and
>   `SessionState` reactive fields.

---

## 1. Mental model

A library may now declare runtime state at **two scopes**:

| scope                | base class      | multiplicity                          | example                                     |
| -------------------- | --------------- | ------------------------------------- | ------------------------------------------- |
| app-global           | `AppState`      | 1 instance, shared across the app     | `MidiPool` — live device handles            |
| per-UI-session       | `SessionState`  | 1 instance per active session         | `TimelineCursor` — playhead position per UI |

Both inherit from a shared abstract marker base, `LibraryState`, which
exists purely as a type root for the registry filter and for type-system
hierarchy. Library authors never subclass `LibraryState` directly — they
pick `AppState` or `SessionState`.

```python
class LibraryState:               # abstract marker — never directly subclassed by users
    class_identity: LibraryStateClassIdentity

class AppState(LibraryState):     # 1 instance, shared across all sessions + executions
    ...

class SessionState(LibraryState): # 1 instance per session
    ...
```

The mental rule is one line: **scope = base class.** Inheritance picks
multiplicity. No scope attribute, no config string, no decorator
parameter. The class declaration is the entire scope decision.

The framework's container handles both scopes through one machinery —
same registry events, same hooks, same hot-reload semantics. Only the
internal storage differs (one map per scope) and the access path
(separate namespace per scope on the contexts that have them).

---

## 2. The contract

### 2.1 Declaration

A `SessionState` is declared just like a `LibraryState` in v1, except
the base class is `SessionState`:

```python
# barn/haybale-tracker/haybale_tracker/state/timeline_cursor.py

from haywire.core.state import SessionState
from haywire.ui.reactive import reactive_field

class TimelineCursor(SessionState):
    """Per-session playback cursor for the tracker UI."""

    position = reactive_field(0.0)        # reactive — UI panels rerender on change
    is_playing = reactive_field(False)    # reactive

    def on_enable(self) -> None:
        """Called once per session, after self.session_id is stamped."""
        # self.session_id is available here (str) — set by the container
        # between cls() and on_enable.
        pass

    def on_disable(self) -> None:
        """Called when the session ends or the library is disabled."""
        pass
```

Same lifecycle hooks (`on_enable`, `on_disable`) as `AppState`, with
identical signatures and identical duck-typing semantics. Hooks are
optional.

**`self.session_id` is set by the container** between `cls()` and
`on_enable()`. The base class declares the attribute so type-checkers
know it exists:

```python
class SessionState(LibraryState):
    session_id: str   # set by the container before on_enable runs
```

`__init__` cannot read `self.session_id` (it isn't stamped yet). Read it
in `on_enable` or any later method.

### 2.2 Registration

Identical to `AppState` (and to v1's `LibraryState`). The registry
filter accepts every concrete subclass of `LibraryState` — both
`AppState` and `SessionState` subclasses go through the same
`LibraryStateRegistry`, same folder-scan, same hot-reload pipeline. The
filter excludes the three marker bases themselves
(`LibraryState`, `AppState`, `SessionState`).

```python
# haybale_tracker/__init__.py — unchanged from v1
@library(id="tracker", ...)
class Library(BaseLibrary):
    def register_components(self) -> None:
        base_path = Path(__file__).parent
        self.add_folder_to_registry(
            folder_path=str(base_path / "state"),
            registry_cls=LibraryStateRegistry,
        )
        # ...
```

The folder scan picks up both `AppState` and `SessionState` subclasses
in the same pass. Library authors don't choose which registry to use —
the scope choice is the inheritance choice.

### 2.3 Access

Both `SessionContext` and `ExecutionContext` expose **two access
namespaces**, each scoped to the state kind it can route to:

| context            | `ctx.data`                          | `ctx.app_data`                        |
| ------------------ | ----------------------------------- | ------------------------------------- |
| `SessionContext`   | `SessionDataNamespace` — SessionState lookups | `AppDataNamespace` — AppState lookups |
| `ExecutionContext` | *(does not exist)*                  | `AppDataNamespace` — AppState lookups |

```python
# From a panel (UI side):
def draw(self, ctx: SessionContext, layout, actions) -> None:
    cursor = ctx.data[TimelineCursor]            # SessionState — this session's
    pool   = ctx.app_data[MidiPool]              # AppState — app-global

# From a node worker (execution side):
def worker(self, exec_ctx: ExecutionContext) -> dict:
    pool = exec_ctx.app_data[MidiPool]           # AppState only — exec has no session
    # exec_ctx.data does not exist — graphs run app-globally, not per session
    return {"device_count": len(pool.devices.value)}
```

**Asymmetric availability is honest about the architecture.** Node
graphs run app-globally — the VM has no notion of which UI session
triggered execution. `ExecutionContext` therefore has no `data`
attribute at all; trying to read `exec_ctx.data` is an `AttributeError`
caught by the type-checker.

Both namespaces use the same generic `__getitem__` shape as v1, with
tighter `TypeVar` bounds:

```python
A = TypeVar("A", bound=AppState)
S = TypeVar("S", bound=SessionState)

class AppDataNamespace:
    def __getitem__(self, cls: type[A]) -> A: ...
    def get(self, cls: type[A]) -> A | None: ...

class SessionDataNamespace:
    def __getitem__(self, cls: type[S]) -> S: ...
    def get(self, cls: type[S]) -> S | None: ...
```

Mismatches fail at type-check time:

```python
ctx.data[MidiPool]            # TYPE ERROR: MidiPool : type[AppState], not type[SessionState]
ctx.app_data[TimelineCursor]  # TYPE ERROR: TimelineCursor : type[SessionState]
```

### 2.4 Type-checking

Same idiom as v1 (`bound` TypeVar parameter on `__getitem__`). With
two narrower namespace classes, scope mistakes are caught statically by
mypy / pyright / pylance before runtime.

---

## 3. Lifecycle

### 3.1 One container, two scopes

`LibraryStateContainer` (v1's instance pool) is extended to hold both
scopes side by side:

```python
class LibraryStateContainer:
    def __init__(self) -> None:
        # App-scoped: one instance per class
        self._app: dict[type[AppState], AppState] = {}
        # Session-scoped: one instance per (class, session_id) pair
        self._sessions: dict[type[SessionState], dict[str, SessionState]] = {}
        # Active sessions tracked for fanout on CLASS_ADDED
        self._known_session_ids: set[str] = set()
        # Existing — unchanged from v1
        self._class_by_registry_key: dict[str, type] = {}
```

The registry → container subscription is unchanged from v1: the
container subscribes to `LibraryStateRegistry` batch lifecycle events
and dispatches by class kind. On each event, the container checks
`issubclass(cls, SessionState)` and routes to the right path:

```python
def _add(self, event: LifeCycleEvent) -> None:
    cls = event.affected_class
    if cls is None:
        return
    if issubclass(cls, SessionState):
        self._add_session_class(cls)        # eager fanout across known sessions
    else:                                    # AppState
        self._add_app_class(cls)            # singleton instantiation (v1 behaviour)
```

### 3.2 Eager instantiation

When a `SessionState` class is registered (CLASS_ADDED) **and** sessions
are already active, the container fans out:

```python
def _add_session_class(self, cls: type[SessionState]) -> None:
    self._sessions[cls] = {}
    for sid in self._known_session_ids:
        inst = cls()
        inst.session_id = sid          # stamp before on_enable
        self._sessions[cls][sid] = inst
        self._call_on_enable(inst)
```

When a session is attached and `SessionState` classes are already
registered, the container fans out the other way:

```python
def attach_session(self, sid: str) -> None:
    self._known_session_ids.add(sid)
    for cls, bag in self._sessions.items():
        inst = cls()
        inst.session_id = sid
        bag[sid] = inst
        self._call_on_enable(inst)
```

Both paths converge: every `(SessionState class, active session)` pair
has exactly one instance. `on_enable` fires exactly once per pair.

`cls()` exceptions follow the same pattern as v1's `_call_on_enable` —
logged, swallowed, lifecycle continues. A misbehaving SessionState
class doesn't break session creation or other libraries.

### 3.3 Detach

When a session ends:

```python
def detach_session(self, sid: str) -> None:
    self._known_session_ids.discard(sid)
    for bag in self._sessions.values():
        inst = bag.pop(sid, None)
        if inst is not None:
            self._call_on_disable(inst)
```

When a SessionState class is unregistered (library disable, CLASS_REMOVED):

```python
def _remove_session_class(self, cls: type[SessionState]) -> None:
    bag = self._sessions.pop(cls, {})
    for inst in bag.values():
        self._call_on_disable(inst)
```

Order of operations is **UI tears down first, state second.** This
ensures a panel or editor doesn't try to read a `ctx.data[X]` that has
already been dropped:

```python
# In SessionManager.remove_session:
session.cleanup()                              # editors, panels, slots
self._container.detach_session(session_id)     # SessionState on_disable runs
```

### 3.4 Hot-reload

A `CLASS_RELOADED` event for a `SessionState` class fans out across
every active session:

```text
CLASS_RELOADED for class V (V_old → V_new):
   for each sid in _sessions[V_old].keys():
       call on_disable on _sessions[V_old][sid]    # old instance disabled
   _sessions[V_new] = {}
   for each sid in _known_session_ids:
       inst = V_new()
       inst.session_id = sid
       _sessions[V_new][sid] = inst
       call on_enable(inst)                        # new instance enabled
```

Ordering is exit-before-enter, identical to v1's AppState reload — just
fanned out per session. In-flight per-session state is lost (matches
v1 semantics; state migration across class versions is explicitly not
built).

### 3.5 Construction order

Per-session lifecycle is driven by `SessionManager`. The container
attachment happens between `Session()` returning and `SessionManager`
returning the session to the caller, so panels and editors that read
`ctx.data[X]` during their own setup see populated state:

```python
# SessionManager.create_session — proposed shape
def create_session(self, **session_kwargs) -> Session:
    session = Session(session_manager=self, **session_kwargs)
    self._sessions[session.session_id] = session
    self._container.attach_session(session.session_id)   # SessionState on_enable runs here
    return session                                       # caller sees fully-attached session
```

Same logic in reverse for teardown — `cleanup` first, then detach.

`SessionManager.__init__` gains a `container: LibraryStateContainer`
parameter; the studio's `HaywireApp.setup_shared_services` passes the
container in.

---

## 4. Reactivity

Identical to LibraryState v1 — `reactive_field()` is the universal
primitive across both scopes. SessionState authors use the same
declarations they would use in `AppState` (and the same that
SessionContext uses today for its own reactive fields):

```python
class TimelineCursor(SessionState):
    position = reactive_field(0.0)              # reactive — Phase 2 will auto-track
    history: list[float] = []                   # plain — not reactive
```

Phase 2 reactive auto-tracking applies to SessionState reactive fields
with no special-casing — same `Reactive[T]` cells, same `.value` reads,
same subscription machinery. See
[`spec_panel_reactivity.md`](spec_panel_reactivity.md).

---

## 5. Boundary — when to use SessionState

### 5.1 Scope decision table

The framework's full scope-vs-mechanism table, extended with the new
SessionState row:

| scope                              | mechanism                              |
| ---------------------------------- | -------------------------------------- |
| persistent app/library config      | `LibrarySettings`, `FrameworkSettings` |
| per-graph state                    | `graph.variables`                      |
| per-flow execution state           | `ExecutionContext.local_ctx`           |
| external system inputs to a flow   | `ExecutionContext.global_ctx`          |
| **app-global library runtime**     | **`AppState`** (renamed from `LibraryState`) |
| **per-session library runtime**    | **`SessionState`** *(this spec)*       |
| per-session framework UI selection | `SessionContext` reactive fields *(see Q9 — migrating to a built-in `EditState: SessionState` in v1.2)* |

**Strict rule.** Each kind of state has exactly one mechanism. A library
that wants per-graph data uses `graph.variables` — not a SessionState
keyed by graph_id. A library that wants persistent configuration uses
`LibrarySettings` — not an AppState that writes to disk in `on_enable`.

The framework will not partition SessionState by anything finer than
session_id. If a library author needs per-graph or per-editor-instance
data, they implement that keying inside their SessionState (e.g.
`self.per_graph: dict[str, ...]`); the spec doesn't endorse this as a
documented pattern.

### 5.2 Prohibition: no `LibrarySettings` composition inside `SessionState`

A `SessionState` **must not** hold a `LibrarySettings` instance as a
field. Settings are app-global and persisted; sessions are per-session
and ephemeral. Composing them creates a semantic contradiction: either
every session shares the same settings (defeating session isolation) or
each session writes to global persistence independently (defeating the
idea of "settings").

**Allowed:** read settings values inside methods/hooks at access time.

```python
# OK:
class TimelineCursor(SessionState):
    def on_enable(self) -> None:
        rate = TrackerSettings().poll_rate.value   # read once
        self.poll_rate_cache = rate                # store the value, not the instance

    def tick(self) -> None:
        if TrackerSettings().auto_advance.value:   # re-read each access
            self.advance()
```

**Forbidden:** holding a `LibrarySettings` instance as a field.

```python
# BAD:
class TimelineCursor(SessionState):
    config: TrackerSettings | None = None        # ← REJECTED at class definition time

    def on_enable(self) -> None:
        self.config = TrackerSettings()
```

**Enforcement.** `SessionState.__init_subclass__` walks the class's
type annotations (including `Optional[X]` / `X | None` / `Union[X, ...]`
unions) and raises `TypeError` if any annotation resolves to a
`LibrarySettings` subclass:

```python
class SessionState(LibraryState):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from haywire.core.settings.schema import LibrarySettings
        from typing import get_type_hints
        hints = get_type_hints(cls, include_extras=False)
        for name, ann in hints.items():
            for resolved in _flatten_union(ann):
                if isinstance(resolved, type) and issubclass(resolved, LibrarySettings):
                    raise TypeError(
                        f"SessionState '{cls.__name__}' has field "
                        f"'{name}: {resolved.__name__}' — LibrarySettings cannot be "
                        f"composed inside SessionState (settings are app-global; "
                        f"sessions are per-session). Read settings values inside "
                        f"methods/hooks instead, never hold a LibrarySettings instance."
                    )
```

The check fires during library load (when the SessionState class is
imported). A misbehaving library fails fast with a clear error pointing
at the offending field.

The escape (`self.config = TrackerSettings()` set dynamically inside
`on_enable`) is not caught by the annotation check. Code review is the
fallback enforcement layer for that case.

### 5.3 Other anti-patterns

| anti-use                                                  | use instead                       |
| --------------------------------------------------------- | --------------------------------- |
| holding cross-session shared state inside SessionState    | `AppState` (the right scope)      |
| persisting SessionState across browser refresh            | `LibrarySettings` for the persisted slice; `SessionState` for the live derived view |
| mutating SessionState from another session via session_id | direct method calls — but consider whether the data really belongs in `AppState` |

A SessionState that depends on knowing about *other* sessions is a
smell — it's reaching outside its scope. The right model is: the
shared piece lives in an `AppState`, and each session reads from it.

---

## 6. Implementation surface

### 6.1 New types

- `haywire.core.state.SessionState` — base class. Optional
  `on_enable` / `on_disable` methods (duck-typed). Class-level
  attribute `session_id: str` (set by container). `__init_subclass__`
  rejects `LibrarySettings`-typed fields.
- `haywire.core.state.AppState` — renamed concrete app-scoped base
  (takes over the role of v1's concrete `LibraryState`).
- `haywire.core.state.SessionDataNamespace` — typed proxy with `bound=SessionState` generics; carries `session_id`. Constructed inline in `SessionContext.__init__`.

### 6.2 Changed types

- `haywire.core.state.LibraryState` — repurposed as **abstract marker
  base**. Documented as "never directly subclassed by users — pick
  `AppState` or `SessionState`." Internal type hints across
  `registry.py` / `container.py` continue to use `LibraryState` as the
  union root.
- `haywire.core.state.DataNamespace` → renamed to `AppDataNamespace`.
  Tighter `bound=AppState` on the TypeVar.
- `haywire.core.state.LibraryStateRegistry._class_filter` — exclusion
  list extended:

  ```python
  return (
      inspect.isclass(cls)
      and issubclass(cls, LibraryState)
      and cls not in (LibraryState, AppState, SessionState)
  )
  ```

- `haywire.core.state.LibraryStateContainer` — extended internal
  storage (two scope dicts), new `attach_session` / `detach_session`
  methods, scope dispatch in `_add` / `_remove` / `_reload`.
- `haywire.core.state.LibraryStateClassIdentity` — registry key
  generation includes scope marker:
  `{library_id}:state:{class_name}` is fine for both scopes (the class
  name is unique per library). No change.
- `haywire.ui.context.SessionContext`:
  - `data: DataNamespace` → renamed `app_data: AppDataNamespace`
  - new `data: SessionDataNamespace`
  - `__init__` constructs both: `self.app_data = AppDataNamespace(app.library_state_container)`, `self.data = SessionDataNamespace(app.library_state_container, session_id)`
- `haywire.core.execution.execution_context.ExecutionContext`:
  - `data: DataNamespace | None` → renamed `app_data: AppDataNamespace | None`
  - no `data` attribute
- `haywire.core.execution.vm.HaywireVM._create_execution_context` —
  populates `app_data` (renamed from `data`), still pulls from the
  same container reference.
- `haywire.ui.session_manager.SessionManager`:
  - `__init__` gains `container: LibraryStateContainer` parameter
  - `create_session` calls `container.attach_session(session.session_id)` after Session construction
  - `remove_session` calls `container.detach_session(session_id)` after `session.cleanup()`
- `haywire_studio.app.HaywireApp.setup_shared_services` — passes
  `self.library_state_container` to `SessionManager(...)`.

### 6.3 Breaking changes

All breaking changes are internal — zero external library consumers
(verified by smoke test: 0 LibraryState classes registered across all
shipped barn libraries).

| break                                                                  | impact                            |
| ---------------------------------------------------------------------- | --------------------------------- |
| `class Foo(LibraryState)` no longer works as concrete base             | Internal: ~12 test files migrate to `class Foo(AppState)`. Atomic in one commit. |
| `ctx.data` semantics change (v1: AppState namespace; v1.1: SessionState namespace on SessionContext, removed on ExecutionContext) | Internal: `ctx.data[X]` → `ctx.app_data[X]` in ~20 internal references. |
| `DataNamespace` class renamed to `AppDataNamespace`                    | Internal imports updated. |
| `SessionManager()` no longer zero-arg                                  | Internal: one call site in `app.py:124`. |

The taxonomy renaming and the namespace renaming should land in the
same commit (or adjacent commits in one PR) so the test suite stays
consistent. The plan covers both as a single bundled refactor task
before any new SessionState code is added.

### 6.4 What is *not* changing

- `LibraryStateRegistry` — same class, same DI provider, same
  registration path. The class filter is widened by one tuple element.
- Lifecycle hook semantics — `on_enable` / `on_disable` for both
  scopes. Hot-reload, identity, registration, folder-scan all unchanged.
- `LibrarySettings` and `FrameworkSettings` — untouched.
- `graph.variables`, `ExecutionContext.local_ctx`,
  `ExecutionContext.global_ctx` — untouched.
- `reactive_field()` — universal primitive, unchanged. Both `AppState`
  and `SessionState` use it identically.
- The DI singleton wiring of `LibraryStateContainer` — same.
- The hot-reload subscriber chain (`settings → state → node/panel/editor`) — same.

---

## 7. Examples

### 7.1 Per-session reactive UI cache

A library wants to cache rendered timeline data per session, with
automatic invalidation when the session ends.

```python
# barn/haybale-tracker/haybale_tracker/state/timeline_view.py

from haywire.core.state import SessionState
from haywire.ui.reactive import reactive_field

class TimelineView(SessionState):
    """Per-session render cache for the timeline panel."""

    cursor_position = reactive_field(0.0)
    selected_clips = reactive_field(set())
    _render_cache: dict[str, bytes] = {}    # plain — not observable

    def on_enable(self) -> None:
        # self.session_id is available here
        pass

    def on_disable(self) -> None:
        # Free per-session render buffers. Each session gets its own
        # _render_cache; one session ending doesn't affect others.
        self._render_cache.clear()
```

A panel reads it directly:

```python
# barn/haybale-tracker/haybale_tracker/panels/timeline_panel.py

def draw(self, ctx: SessionContext, layout, actions) -> None:
    view = ctx.data[TimelineView]
    layout.label(f"Cursor: {view.cursor_position.value}")
```

### 7.2 Per-session connection (resource isolation)

A library that opens a per-user upstream connection (each session
authenticates independently):

```python
class UpstreamConnection(SessionState):
    """One open connection per user session."""

    connected = reactive_field(False)

    def on_enable(self) -> None:
        token = self._lookup_session_token(self.session_id)
        self._client = SomeClient(token=token)
        self.connected.value = True

    def on_disable(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self.connected.value = False
```

`self.session_id` lets the SessionState resolve session-specific
resources during `on_enable`.

### 7.3 Mixed scope — AppState + SessionState in one library

A library may declare both scopes; they coexist in the same `state/`
folder and use the same registry path:

```python
# barn/haybale-midi/haybale_midi/state/

# midi_pool.py — app-global hardware
class MidiPool(AppState):
    devices = reactive_field([])

    def on_enable(self) -> None:
        self.devices.value = scan_midi_devices()

# midi_view.py — per-session UI selection
class MidiView(SessionState):
    selected_device = reactive_field(None)
```

A panel reads both, scope visible at every call:

```python
def draw(self, ctx: SessionContext, layout, actions) -> None:
    pool = ctx.app_data[MidiPool]                # AppState — shared
    view = ctx.data[MidiView]                    # SessionState — this session's
    for device in pool.devices.value:
        is_selected = view.selected_device.value == device.id
        layout.label(device.name, highlighted=is_selected)
```

The two-namespace shape keeps scope visible at every call site —
reading the call alone tells you whether you're touching shared or
isolated state.

---

## 8. Migration & sequencing

### 8.1 v1.1 (this spec) — abstraction only

v1.1 lands the SessionState abstraction without migrating any existing
framework state. Specifically:

1. **Rename**: `LibraryState` → marker base. Add `AppState` as concrete
   app-scoped base. All internal code that subclasses `LibraryState`
   migrates to `AppState` in the same commit.
2. **Add**: `SessionState` base + `__init_subclass__` LibrarySettings
   prohibition check.
3. **Container**: extend `LibraryStateContainer` with two-scope
   internal storage, `attach_session` / `detach_session`,
   `_add_session_class` / `_remove_session_class` /
   `_reload_session_class` methods.
4. **Namespaces**: rename `DataNamespace` → `AppDataNamespace`. Add
   `SessionDataNamespace`.
5. **Contexts**: `SessionContext.data` → `SessionContext.app_data`
   (rename); add new `SessionContext.data` (SessionDataNamespace).
   `ExecutionContext.data` → `ExecutionContext.app_data` (rename); no
   new attribute. VM populates `app_data` (renamed).
6. **Wiring**: `SessionManager(container=...)`. Constructor takes
   container; `create_session` calls `attach_session`; `remove_session`
   calls `detach_session` after `session.cleanup()`.
7. **Tests**: full unit coverage for the new SessionState base, the
   container's two-scope dispatch, `SessionDataNamespace`, the
   LibrarySettings rejection check, and the SessionManager attach/detach
   wiring. Plus rename of all existing tests that used
   `class Foo(LibraryState)` to `class Foo(AppState)`.

After v1.1, `ctx.data` exists on `SessionContext` but is empty until a
library registers a `SessionState`. Libraries can immediately start
declaring SessionState classes.

### 8.2 v1.2 (separate spec/plan) — framework migration

v1.2 introduces the framework's own built-in SessionState — `EditState`
— and migrates the graph-editor reactive cluster off of direct
`SessionContext` fields.

Out of scope for this spec; covered in a follow-up plan after v1.1
lands. The migration is purely mechanical (rewrite ~50 call sites of
`ctx.active_node.value` to `ctx.data[EditState].active_node.value`)
and benefits from being reviewable as its own PR.

The fields targeted for migration in v1.2:

```
active_graph
active_node
active_edge
active_port
selected_nodes
selected_edges
active_graph_path
```

Other reactive fields on `SessionContext` (`active_library`,
`active_component`, `active_file`, `active_workbench_theme_key`,
`active_node_theme_key`, `clipboard`) stay as direct fields in v1.2 —
they're not part of the graph-editor cluster.

---

## 9. Open questions for v1.2

1. **Framework registration mechanism.** `EditState` is owned by
   haywire-core, not by a library. v1.2 needs a registration path
   parallel to how `FrameworkSettings` is registered against a
   framework identity. Worth designing explicitly — possibly a
   `register_framework_state()` call in `LibrarySystemService.initialize`
   alongside the existing `register_framework_settings()`.
2. **Call-site refactor scope.** ~50 call sites read selection state
   directly (`ctx.active_node.value`). The v1.2 plan needs a clear list
   and a mechanical refactor strategy (sed-like search/replace, or
   AST-based codemod, or task-by-task).
3. **Should `EditState` be reactive-aware before Phase 2 lands?** v1.2
   migration would expose more `Reactive[T]` reads in non-panel code
   paths (canvas handlers, etc.). The Phase 1 `.value` shape works
   today, but Phase 2's auto-tracking lands on top — the migration
   should anticipate this.
4. **Optional extension: a per-graph or per-editor-instance scope.**
   Q13 settled as "strict; not endorsed." If demand surfaces during
   v1.2 work, designing a third scope (`GraphState` or similar) is a
   v1.3+ conversation, not a v1.2 one.

---

## 10. Summary

v1.1 of the LibraryState system introduces a second scope —
per-UI-session — alongside the existing app-global scope. The
mechanism is a one-line rule (**scope = base class**) that reuses every
piece of v1's machinery (registry, container subscription, hot-reload,
identity, lifecycle hooks). The taxonomy is restructured so both scopes
are first-class siblings under an abstract `LibraryState` marker base.

The visible developer surface is small: pick `AppState` or
`SessionState`; read `ctx.data[X]` for session-scoped, `ctx.app_data[X]`
for app-scoped; ExecutionContext sees only `app_data` (graphs run
app-globally).

The contract is strict: a `SessionState` cannot compose
`LibrarySettings` (enforced at class-definition time). Each kind of
state has exactly one mechanism.

Framework-state migration to its own built-in `SessionState`
(`EditState`) is sequenced into v1.2 as a focused refactor PR, after
the abstraction itself ships and stabilizes in v1.1.
