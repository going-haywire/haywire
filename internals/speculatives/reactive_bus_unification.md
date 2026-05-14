# Reactive fields unified with the event bus

Status: **spec**, not implemented. Builds on `event_bus_redesign.md`.

## Problem

Two related issues, one root cause.

1. **Reactive fields don't notify.** `SessionContext.active_file`,
   `EditState.active_node`, and ~13 other fields are declared via
   `reactive_field()` and read/written through `.value`. The skeleton was
   meant to grow a subscriber set in "Phase 2" and never did. Today, a
   write goes nowhere — no handler fires.

2. **Field-to-event pairing is convention.** The bus carries
   `ActiveFileMoved`, `ActiveLibraryMoved`, etc. — empty `ContextSignal`
   subclasses that exist solely to represent "the matching field changed."
   No code publishes them. And a developer writing
   `@redraw_on(ActiveFileMoved)` has to *know*, out of band, that this
   event is the one paired with `ctx.active_file`. The pairing lives in
   naming, not in code.

We unify both: a reactive field write publishes an event on the existing
session bus, and the field reference *is* the subscription key. There is
no separate event class for the developer to learn or author.

## Out of scope

- Auto-tracking reads (Vue/SolidJS-style signal dependency capture).
  Explicitly rejected: ContextVar-based tracking conflicts with hot-reload
  ([project_di_context.md](../../.insights/project_di_context.md)).
- Backwards-compatible shims. Single-PR cutover, no `.value`-and-new-API
  dual support window.

## In scope, with scope-matched semantics

Reactive fields work on `SessionContext`, `SessionState`, and `AppState`.
Publish cardinality mirrors instance cardinality — the only coherent
mapping:

| Host             | Instance cardinality        | Publish cardinality        |
|------------------|-----------------------------|----------------------------|
| `SessionContext` | one per session             | this session's bus         |
| `SessionState`   | one per session per class   | this session's bus         |
| `AppState`       | one, shared across sessions | broadcast to every session |

A reader sees `class HaystackState(AppState):` and knows reactive fields
on it reach every session — the same way they know `ctx.app_data[HaystackState]`
returns a shared instance. No flag at the field site re-states this; the
base class already does.

---

# Developer API

## Declaring a reactive field

```python
from haywire.core.session.reactive import reactive_field

class SessionContext:
    active_file: Optional[Path] = reactive_field(None)
    active_library: Optional[LibraryInfo] = reactive_field(None)
```

The annotation describes instance-level access — the value, not a
wrapper. `reactive_field(initial)` takes only the initial value. No event
class, no path argument, no flags.

Identical on library `SessionState`:

```python
class EditState(SessionState):
    active_node: Optional[NodeWrapper] = reactive_field(None)
    selected_nodes: set[str] = reactive_field(set())
```

Identical on library `AppState`, with the only difference being publish
cardinality — writes broadcast to every session:

```python
class HaystackState(AppState):
    active_haystack: Optional[HaystackInfo] = reactive_field(None)
```

Mutable defaults (`set()`, `[]`) are deep-copied per instance — same as
today.

## Accessing state from a session

`SessionContext` exposes two scope-bound proxies. Reads look the same
regardless of host scope:

```python
# SessionContext — flat attribute on ctx.
path = ctx.active_file

# SessionState — per-session library state, scoped to this session.
node = ctx.data[EditState].active_node

# AppState — app-global library state, shared across all sessions.
haystack = ctx.app_data[HaystackState].active_haystack
```

Writes look the same too — `ctx.data[EditState].active_node = wrapper`
publishes to this session; `ctx.app_data[HaystackState].active_haystack
= info` broadcasts to every session.

## Reading and writing a reactive field

```python
# Read — bare attribute.
path = ctx.active_file

# Write — bare attribute. Publishes an event if the value changed.
ctx.active_file = new_path

# Equal-value writes are no-ops. No event fires.
ctx.active_file = same_path  # silent
```

No `.value` anywhere.

## Subscribing to a reactive field

```python
from haywire.core.session.handlers import redraw_on, react_on

class FileViewerEditor(BaseEditor):

    @redraw_on(SessionContext.active_file)   # ← the field is the key
    def _on_file_changed(self, ctx, event):
        ...   # framework calls wrapper.redraw() after this returns

    @react_on(SessionContext.active_library)
    def _on_library_changed(self, ctx, event):
        ...   # pure side-effect
```

The class-level reference (`SessionContext.active_file`) is the
subscription key. The developer never names a separate event class —
because there isn't one to name. There is one Python object that
represents "this field, on this class, when it changes," and it's the
class-level attribute itself.

Hand-authored domain events (`SelectionMoved`, `Reveal`, `Close`,
`GraphDataMutated`, `LibraryCatalogChanged`) keep working unchanged:

```python
@redraw_on(SelectionMoved, GraphDataMutated)
def _refresh(self, ctx, event): ...
```

You can mix them freely:

```python
@redraw_on(SessionContext.active_file, SelectionMoved)
def _handle(self, ctx, event): ...
```

## Inside the handler

The event payload carries no value. The handler reads the field back:

```python
@redraw_on(SessionContext.active_file)
def _on_file_changed(self, ctx, event):
    path = ctx.active_file        # current value
    # event.old / event.new do NOT exist
```

This matches `SelectionMoved`'s existing payload-free convention.
Subscribers always read the source of truth (the field) at handler time.

## In-place mutation does not fire

Reactive fields follow Python reference semantics. Reassignment fires;
mutation through the existing reference does not.

```python
# Fires — new object assigned.
edit.selected_nodes = edit.selected_nodes | {"new"}

# Silent — mutates the existing set in place.
edit.selected_nodes.add("new")
```

This is unchanged from today's `Reactive.value` semantics. Mutating-then-
reassigning is the explicit pattern when an event is needed:

```python
new_set = edit.selected_nodes | {"new"}
edit.selected_nodes = new_set
```

## Constraints

- **Host must implement `_haywire_publish`.** A class that uses
  `reactive_field()` must inherit (or implement) the publish protocol —
  `SessionContext`, `SessionState`, and `AppState` do this for you.
  Direct subclasses of other types that try to add reactive fields fail
  at class-definition time with a clear error.

- **Hand-authored events still exist alongside reactive fields.** Use
  reactive fields for "a value changed" semantics; use a hand-authored
  `ContextSignal` subclass when an event represents a compound or
  coarse-grained fact (`HaystackReloaded`, `LibraryCatalogChanged`,
  `GraphDataMutated`) where modeling it as a per-field write would
  produce event storms during ordinary multi-step operations.

---

# Technical details

## Components

### The descriptor (`reactive_field` / `_ReactiveDescriptor`)

Lives at `packages/haywire-core/src/haywire/core/session/reactive/descriptor.py`.

A **data descriptor** (defines both `__get__` and `__set__`). Three
responsibilities:

1. **Generate the synthetic event class.** At `__set_name__(owner, name)`
   (host class definition time), builds:

   ```python
   cross = issubclass(owner, AppState)
   event_class = type(
       name,                         # __name__ = "active_file"
       (ContextSignal,),
       {
           "__qualname__": f"{owner.__qualname__}.{name}",
           "__module__": owner.__module__,
           "cross_session": cross,   # ClassVar[bool], True for AppState
       },
   )
   ```

   Decorated as a frozen dataclass for consistency with the rest of the
   event vocabulary. Cached on the descriptor as `self._event_class`. One
   class per (host_class, attr_name) pair. Identity is stable as long as
   the host class is not reloaded; on hot-reload, the host class is fresh
   and so is the descriptor and so is the synthetic class — which is the
   correct invalidation, matching how every other event class behaves on
   reload.

   The `cross_session` flag follows host scope: AppState reactive fields
   broadcast (matching the instance's app-global cardinality);
   SessionState / SessionContext fields stay local. The flag isn't
   author-facing — it's derived from the base class.

2. **Verify the host can publish.** Also in `__set_name__`, check
   `hasattr(owner, "_haywire_publish")`. If not, raise `TypeError` with a
   message pointing the author at `SessionContext` / `SessionState` as
   the supported host bases.

3. **Storage and dispatch.** `__set__(instance, value)` performs:

   ```python
   # Read current value from the per-instance storage slot.
   current = instance.__dict__.get(self._attr_name, self._initial)
   if value == current:
       return                        # equality short-circuit, silent
   instance.__dict__[self._attr_name] = value
   instance._haywire_publish(self._event_class())
   ```

   `__get__(instance, owner)`:

   ```python
   if instance is None:
       return self._event_class      # class-level access → event class
   return instance.__dict__.get(self._attr_name, self._initial)
   ```

   `_initial` is held on the descriptor; per-instance storage is lazy
   (only populated on first write), avoiding a need for an init loop in
   simple cases. Mutable defaults still need explicit per-instance copy —
   see "Initialization" below.

### Initialization

The host class's `__init__` (or `__init_subclass__`-installed hook)
iterates the descriptors and seeds per-instance storage with a `copy()`
of the initial value for mutable defaults. This is essentially what
`iter_reactive_fields` does today; the loop survives in spirit but the
function is internal-only (no longer called from user code).

`SessionContext.__init__` keeps its existing init loop. Library
`SessionState` subclasses inherit a base-class implementation that does
the same; `EditState` no longer needs its hand-written init loop.

### The `_haywire_publish` protocol

```python
class ReactiveHost(Protocol):
    def _haywire_publish(self, event: ContextSignal) -> None: ...
```

`SessionContext`:

```python
def _haywire_publish(self, event: ContextSignal) -> None:
    self.session.publish(event)
```

`SessionState` (base class in `haywire.core.state.base`):

```python
def _haywire_publish(self, event: ContextSignal) -> None:
    self.session.publish(event)
```

`AppState` (base class in `haywire.core.state.base`):

```python
def _haywire_publish(self, event: ContextSignal) -> None:
    self._session_manager.broadcast(event)
```

The protocol signature is uniform; the implementation differs because
the scope differs. SessionContext / SessionState publish into one
session's bus (via `Session.publish`). AppState fans out to every
session (via `SessionManager.broadcast`). The synthetic event class
carries `cross_session=True` when the host is AppState, so even if a
session-scoped publish path were used by mistake, `Session.publish`
would route it through `broadcast` anyway — the routing is defensive
on both ends.

### Container stamping (session ref, manager ref)

`LibraryStateContainer` stamps lifecycle references on state instances
between `cls()` and `on_enable()`:

- **`SessionState`** — already stamps `self.session_id`. Extend to also
  set `self.session` (weakref to the owning `Session`). Resolved by
  passing the `Session` into `attach_session` / `_instantiate_session_state`;
  `SessionManager.create_session` already has the `Session` in scope
  when it calls `self._container.attach_session(...)` and can pass it
  through.

- **`AppState`** — set `self._session_manager` (weakref to the
  `SessionManager`). `_add_app_class` runs at library-enable time;
  the container is given the manager at the same point it learns
  about library enables (the existing `bind_to_lifecycle` /
  `on_library_enabled` plumbing).

Both refs are weakrefs so state instances don't artificially extend the
lifetime of the Session / SessionManager that owns them.

## Event flow

### Publish path (session-local)

```
ctx.active_file = path                          # or SessionState field
  → _ReactiveDescriptor.__set__(host, path)
     → equality check; bail if unchanged
     → host.__dict__["active_file"] = path
     → host._haywire_publish(event_class())
        → host.session.publish(event_class())
           → EventBus.publish(event)
              → handlers for type(event) fire in registration order
```

### Publish path (AppState, broadcast)

```
haystack_state.active_haystack = info
  → _ReactiveDescriptor.__set__(haystack_state, info)
     → equality check; bail if unchanged
     → haystack_state.__dict__["active_haystack"] = info
     → haystack_state._haywire_publish(event_class())
        → haystack_state._session_manager.broadcast(event_class())
           → for each session: session._dispatch(event)
              → EventBus.publish(event)
                 → handlers for type(event) fire (per session)
```

By the time the handlers run, the field already reflects the new value
(write-then-publish, sync).

### Subscribe path

```
@redraw_on(SessionContext.active_file)
  → validate_event_types sees SessionContext.active_file
  → at class-level access, descriptor.__get__(None, SessionContext)
     returns the synthetic event class
  → validate_event_types accepts it (issubclass(..., ContextSignal) is True)
  → decorator stores it as a redraw_on target on the method
  → discover_handlers indexes it normally
  → EditorWrapper subscribes the bound method to the bus
     for this exact synthetic class
```

No changes to `validate_event_types`, the bus, `discover_handlers`,
`EditorWrapper`, or any other dispatch machinery. The synthetic event
class participates as a first-class `ContextSignal` subclass.

## Deletions

- `Reactive[T]` class (`reactive/reactive.py`) — internalized or removed.
  No longer part of the public API.
- `ReactivePath` (`reactive/path.py`) — file deleted. Was scaffolding for
  a `@reads`-style verification feature that is no longer planned.
- `iter_reactive_fields` as a public name — becomes internal to the
  reactive module, used by base-class init logic.
- Four field-mirroring events from `session/events.py`:
  - `ActiveFileMoved`
  - `ActiveLibraryMoved`
  - `ActiveComponentMoved`
  - `ThemeMoved`
- Their `__all__` entries.

## Surface affected

Confirmed by grep at spec time.

**Reactive fields (15 total, all session-scoped today):**
- `SessionContext` (5): active_file, active_library, active_component,
  active_workbench_theme_key, active_node_theme_key
- `EditState` (8): active_graph, active_graph_path, active_node,
  active_edge, active_port, selected_nodes, selected_edges, clipboard
- `FileBrowserState` (1): right_clicked_file
- `haybale-testing` fixture (1): counter

No `AppState` reactive fields exist today. The descriptor supports them
from day one (so the design is uniform across host scopes), but the PR
ships zero AppState reactive fields. Adoption is on libraries when they
have a concrete use case — `HaystackState.active_haystack` is the
obvious candidate.

**Write/read sites (~50, mechanical):** `.value =` → bare assignment;
`.value` (read) → bare attribute access. Audit step:
`grep -rn '\.value\.\(add\|remove\|clear\|append\|update\|pop\)\b'` —
identify in-place-mutation sites that need to be rewritten as
reassignment if the event matters.

**Tests rewritten:**
- `tests/ui/reactive/test_reactive_descriptor.py` — new spec for the
  data descriptor: `__set__` publishes, `__get__` returns raw value,
  class-level access returns the synthetic event class, equality
  short-circuit silent.
- `tests/ui/reactive/test_iter_reactive_fields.py` — adjusted for
  internal-only API (or removed if no longer load-bearing).
- `tests/core/test_session/test_context_reactive.py` — read/write idiom
  changes.
- ~10 barn/test files that touch `.value` on EditState/FileBrowserState.

**Documentation rewritten in the same PR:**
- `docs/architecture/session-and-state/session-and-state-arch.md`
- `SessionContext` class docstring
- `EditState` class docstring
- `reactive/__init__.py`, `reactive/descriptor.py` docstrings
- `internals/speculatives/event_bus_redesign.md` — paragraph that
  references the Reactive/Phase-2 split

## Verification before merge

Per CLAUDE.md:

```sh
uv run ruff check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ \
            barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ \
            barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ \
            barn/haybale-visiongraph/haybale_visiongraph/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest
```

Pre-edit baseline established before starting — required for a refactor
this broad. Anything new after the edit is mine.

## Decisions captured

| # | Decision |
|---|---|
| 1 | Solves both: Reactive notifications + field/event pairing convention. Bus is the only notification channel. |
| 2 | No `event=` arg on `reactive_field()`. Framework synthesizes the event class. |
| 3 | Data descriptor on the host, no `.value`. Read/write are bare attribute access. |
| 4 | `ReactivePath` deleted. |
| 5 | Sync, write-then-publish. Equality short-circuit kept. |
| 6 | Event payload empty. Subscribers read the field back. |
| 7 | Subscribe to the field reference directly. Synthetic class is internal. |
| 8 | Synthetic class generated in `__set_name__`, cached on descriptor. |
| 9 | Host implements `_haywire_publish`; verified at class-definition. |
| 10 | Full rollout: `SessionContext` + all library `SessionState` in one PR. |
| 11 | In-place container mutation stays silent. Audit `.value.add` style sites. |
| 12 | Container stamps lifecycle refs: `self.session` (weakref) on SessionState, `self._session_manager` (weakref) on AppState. |
| 13 | Annotation is `T`, not `Reactive[T]`. `Reactive` removed from public API. |
| 14 | `cross_session` is derived from host scope, not a field flag. AppState reactive fields auto-broadcast; SessionState/SessionContext stay local. |
| 15 | Single PR, including docs and `.insights` updates. |
