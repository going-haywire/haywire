# Signal-field unification

Status: **DONE** — landed in `<TBD-after-merge>`. (Originally drafted as
"Reactive fields unified with the event bus"; builds on `event_bus_redesign.md`.)

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

We unify both. A field write emits a **signal** on the existing session
bus, and the field reference *is* the subscription key. There is no
separate event class for the developer to learn or author.

This unification also reframes vocabulary. The bus carries **signals**,
not "events". One word for one concept: things that flow on the bus.
Hand-authored signals (`SelectionMoved`, `GraphDataMutated`) and
synthetic field signals (`SessionContext.active_file`) are the same
species. See "Vocabulary" below.

## Out of scope

- Auto-tracking reads (Vue/SolidJS-style signal dependency capture).
  Explicitly rejected: ContextVar-based tracking conflicts with hot-reload
  ([project_di_context.md](../../.insights/project_di_context.md)).
- Backwards-compatible shims. Single-PR cutover, no `.value`-and-new-API
  dual support window. No deprecation alias for `Reactive` / `ReactivePath`.

## Vocabulary

The rename happens in the same PR. One word for one concept.

| Was                         | Becomes                                              |
| --------------------------- | ---------------------------------------------------- |
| `Event` (abstract root)     | `Signal`                                             |
| `ContextSignal`             | deleted — concrete signals inherit `Signal` directly |
| `LifecycleCommand`          | `CommandSignal(Signal)`                              |
| `EventBus`                  | `SignalBus`                                          |
| `EventHandler` (type alias) | `SignalHandler`                                      |
| `reactive_field(...)`       | `signal_field(...)`                                  |
| `_haywire_publish`          | `_signal_emit`                                       |
| `Reactive[T]`               | deleted                                              |
| `ReactivePath`              | deleted                                              |
| `iter_reactive_fields`      | `iter_signal_fields` (internal-only)                 |
| `_seed_reactive_fields`     | `_seed_signal_fields` (internal helper)              |
| module `session/reactive/`  | module `session/signals/`                            |
| `validate_event_types`      | `validate_signal_types`                              |

Decorators `@redraw_on` and `@react_on` are kept — they describe handler
semantics (redraw the editor vs. pure side-effect), not bus vocabulary.

The four field-mirroring signal classes are deleted (no replacement
needed — the synthetic class is the replacement):

- `ActiveFileMoved`
- `ActiveLibraryMoved`
- `ActiveComponentMoved`
- `ThemeMoved`

## In scope, with scope-matched semantics

Signal fields work on `SessionContext`, `SessionState`, and `AppState`.
Emit cardinality mirrors instance cardinality — the only coherent mapping:

| Host             | Instance cardinality        | Emit cardinality           |
| ---------------- | --------------------------- | -------------------------- |
| `SessionContext` | one per session             | this session's bus         |
| `SessionState`   | one per session per class   | this session's bus         |
| `AppState`       | one, shared across sessions | broadcast to every session |

A reader sees `class HaystackState(AppState):` and knows signal fields
on it reach every session — the same way they know
`ctx.app_data[HaystackState]` returns a shared instance. No flag at the
field site re-states this; the base class already does. `cross_session`
on the synthetic signal class is derived from host scope, not
author-facing.

---

# Developer API

## Declaring a signal field

```python
from haywire.core.session.signals import signal_field

class SessionContext:
    active_file: Optional[Path] = signal_field(None)
    active_library: Optional[LibraryInfo] = signal_field(None)
```

The annotation describes instance-level access — the value, not a wrapper.
`signal_field(initial)` takes only the initial value. No signal class, no
path argument, no flags.

Identical on library `SessionState`:

```python
class EditState(SessionState):
    active_node: Optional[NodeWrapper] = signal_field(None)
    selected_nodes: set[str] = signal_field(set())
```

Identical on library `AppState`, with the only difference being emit
cardinality — writes broadcast to every session:

```python
class HaystackState(AppState):
    active_haystack: Optional[HaystackInfo] = signal_field(None)
```

Mutable defaults (`set()`, `[]`) are deep-copied per instance — see
"Initialization" below.

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
emits to this session; `ctx.app_data[HaystackState].active_haystack = info`
broadcasts to every session.

This subscribe/read asymmetry is intentional. The subscription key
(`EditState.active_node`) points at the field's *identity*; the read path
(`ctx.data[EditState].active_node`) goes through the namespace that
encodes *scope*. The namespace tells the reader "per-session" vs.
"app-global"; erasing that cue would re-introduce ambiguity the explicit
base-class scoping was meant to remove. Future signals that need to carry
information beyond "changed" remain hand-authored — synthetic signal
classes stay payload-free.

## Reading and writing a signal field

```python
# Read — bare attribute.
path = ctx.active_file

# Write — bare attribute. Emits a signal if the value changed.
ctx.active_file = new_path

# Identity-equal writes are no-ops. No signal fires.
ctx.active_file = ctx.active_file  # silent
```

No `.value` anywhere.

### Change detection: identity, not equality

The descriptor short-circuits on **identity** (`is`), not equality (`==`):

```python
if value is current:
    return
```

Same object suppresses; fresh object fires. Predictable across every
value type — including wrappers, NaN, and rich types whose `__eq__`
raises (numpy, pandas, torch).

#### Wrapper rebinding after hot-reload — the load-bearing case

The library that owns `LibraryInfo` is reloaded. The framework rebuilds
its `LibraryInfo` instance and reassigns it:

```python
old = ctx.active_library           # LibraryInfo("foo", "1.0") — v1
new = LibraryInfo("foo", "1.0")    # same content, fresh instance — v2

old == new                         # True  (dataclass eq)
old is new                         # False (different objects)

ctx.active_library = new
# is-check: new is old → False → does not skip.
# Field now points at v2; subscribers fire and re-read,
# rebinding weakrefs and any cached state to the reloaded module.
```

If the short-circuit were `==`-based, this assignment would skip
silently — the field would keep pointing at the stale v1, and
subscribers would never re-bind. `active_library` on `SessionContext`
is exactly this rebinding pattern, so the case is concrete.

#### NaN

```python
nan = float("nan")
state.threshold = nan                  # fires
state.threshold = nan                  # is → True; skips.
state.threshold = float("nan")         # fresh object; fires.
```

Identity makes NaN behave like every other value. (Under `==`, every
NaN write would re-fire because `nan == nan` is `False` per IEEE 754.)

#### Rich types whose `__eq__` raises

```python
state.payload = np.array([1, 2, 3])   # storage = the array
state.payload = "cleared"
# is-check: "cleared" is array → False → does not skip.
# Write lands; subscribers fire.
```

Identity (`is`) never raises. Equality would have crashed
(`ValueError: truth value of an array is ambiguous` from numpy's
elementwise `__eq__`) before the storage line ran, leaving the field
silently unchanged.

#### Trade-off

Identity-only re-fires when value-equal but identity-distinct objects
are written fresh:

```python
ctx.active_file = Path("/x")           # fires
ctx.active_file = Path("/x")           # fresh Path; fires again
```

Absorbed by the payload-free convention (decision 6 / Q11): handlers
re-read the field, and re-reading the same value is a no-op. A
redundant fire costs one extra handler invocation; a missed hot-reload
rebind costs a debugging session.

## Subscribing to a signal field

```python
from haywire.core.session.handlers import redraw_on, react_on

class FileViewerEditor(BaseEditor):

    @redraw_on(SessionContext.active_file)   # ← the field is the key
    def _on_file_changed(self, ctx, signal):
        ...   # framework calls wrapper.redraw() after this returns

    @react_on(SessionContext.active_library)
    def _on_library_changed(self, ctx, signal):
        ...   # pure side-effect
```

The class-level reference (`SessionContext.active_file`) is the
subscription key. The developer never names a separate signal class —
because there isn't one to name. There is one Python object that
represents "this field, on this class, when it changes," and it's the
class-level attribute itself.

Hand-authored signals (`SelectionMoved`, `Reveal`, `Close`,
`GraphDataMutated`, `LibraryCatalogChanged`) keep working unchanged:

```python
@redraw_on(SelectionMoved, GraphDataMutated)
def _refresh(self, ctx, signal): ...
```

You can mix them freely:

```python
@redraw_on(SessionContext.active_file, SelectionMoved)
def _handle(self, ctx, signal): ...
```

## Inside the handler

The signal payload carries no value. The handler reads the field back:

```python
@redraw_on(SessionContext.active_file)
def _on_file_changed(self, ctx, signal):
    path = ctx.active_file        # current value
    # signal.old / signal.new do NOT exist
```

This matches `SelectionMoved`'s existing payload-free convention.
Subscribers always read the source of truth (the field) at handler time.

## In-place mutation does not fire

Signal fields follow Python reference semantics. Reassignment fires;
mutation through the existing reference does not.

```python
# Fires — new object assigned.
edit.selected_nodes = edit.selected_nodes | {"new"}

# Silent — mutates the existing set in place.
edit.selected_nodes.add("new")
```

This is unchanged from today's `Reactive.value` semantics. Mutating-then-
reassigning is the explicit pattern when an emit is needed:

```python
new_set = edit.selected_nodes | {"new"}
edit.selected_nodes = new_set
```

## Re-entrant writes are allowed

A handler that writes back to a signal field re-enters the dispatch
depth-first — the inner emit completes before the outer dispatch resumes.
This matches the existing bus contract for hand-authored signals.

```python
@react_on(SessionContext.active_file)
def _on_file_changed(self, ctx, signal):
    if ctx.active_file.suffix == ".bak":
        ctx.active_file = ctx.active_file.with_suffix(".txt")   # re-entrant
```

Trivial loops (writing back the same value) self-terminate via the
identity short-circuit. Non-trivial loops (cross-field ping-pong) are
author bugs; the bus does not guard against them.

## Constraints

- **Host must inherit `SignalSource`.** The descriptor checks
  `issubclass(owner, SignalSource)` at `__set_name__`. `SessionContext`,
  `SessionState`, and `AppState` are the three concrete bases that
  satisfy this. A class that uses `signal_field()` without one of those
  bases fails at class-definition time with a clear error.

- **Shadowing is forbidden.** A subclass that redeclares a signal field
  inherited from a base raises `TypeError` at class-definition time
  (`__init_subclass__` check, mirroring
  `SessionState._reject_library_settings_fields`). Allowing shadowing
  would silently create two different synthetic signal classes for the
  "same" name, breaking subscribers wired to the base.

- **Don't write signal fields in `__init__`.** AppState and SessionState
  instances have their framework wiring (`session` weakref,
  `_session_manager` weakref) stamped by the container *between* `cls()`
  and `on_enable()`. Writes during `__init__` predate the wiring and
  raise. Write in `on_enable()` or later. Mirrors the existing
  `SessionState.session_id` contract.

- **Hand-authored signals still exist alongside signal fields.** Use
  signal fields for "a value changed" semantics; use a hand-authored
  `Signal` subclass when a signal represents a compound or coarse-grained
  fact (`HaystackReloaded`, `LibraryCatalogChanged`, `GraphDataMutated`)
  where modeling it as a per-field write would produce signal storms
  during ordinary multi-step operations, or when the signal needs to
  carry payload that isn't a field value (a delta, a reason, a transient
  input).

---

# Technical details

## Components

### The descriptor (`signal_field` / `_SignalFieldDescriptor`)

Lives at `packages/haywire-core/src/haywire/core/session/signals/descriptor.py`.

A **data descriptor** (defines both `__get__` and `__set__`). Three
responsibilities:

1. **Generate the synthetic signal class.** At `__set_name__(owner, name)`
   (host class definition time), builds:
   
   ```python
   cross = issubclass(owner, AppState)
   signal_class = type(
       name,                         # __name__ = "active_file"
       (Signal,),
       {
           "__qualname__": f"{owner.__qualname__}.{name}",
           "__module__": owner.__module__,
           "cross_session": cross,   # ClassVar[bool], True for AppState
       },
   )
   ```
   
   Decorated as a frozen dataclass for consistency with the rest of the
   signal vocabulary. Cached on the descriptor as `self._signal_class`.
   The synthetic class is **stashed on the descriptor only** — no
   module-level binding, no sibling namespace. The only handle is
   `Owner.field` (which returns it via `__get__(None, owner)`). One class
   per (host_class, attr_name) pair. Identity is stable as long as the
   host class is not reloaded; on hot-reload, the host class is fresh and
   so is the descriptor and so is the synthetic class — which is the
   correct invalidation, matching how every other signal class behaves on
   reload.
   
   The `cross_session` flag follows host scope: AppState signal fields
   broadcast (matching the instance's app-global cardinality);
   SessionState / SessionContext fields stay local. The flag isn't
   author-facing — it's derived from the base class.

2. **Verify the host inherits `SignalSource`.** Also in `__set_name__`,
   check `issubclass(owner, SignalSource)`. If not, raise `TypeError`
   pointing the author at `SessionContext` / `SessionState` / `AppState`
   as the supported host bases.

3. **Forbid shadowing.** In `__set_name__`, walk the MRO above `owner`.
   If any ancestor's `__dict__` already contains a `_SignalFieldDescriptor`
   with the same `name`, raise `TypeError`. Authors who need a different
   default per subclass should compose, not shadow.

4. **Storage and dispatch.** `__set__(instance, value)` performs:
   
   ```python
   current = instance.__dict__.get(self._attr_name, self._initial)
   if value is current:              # identity short-circuit; see above
       return
   instance.__dict__[self._attr_name] = value
   instance._signal_emit(self._signal_class())
   ```
   
   `__get__(instance, owner)`:
   
   ```python
   if instance is None:
       return self._signal_class     # class-level access → signal class
   return instance.__dict__.get(self._attr_name, self._initial)
   ```
   
   `_initial` is held on the descriptor; per-instance storage is seeded
   eagerly by `_seed_signal_fields` (see "Initialization").

### Initialization

A shared internal helper seeds per-instance storage:

```python
def _seed_signal_fields(instance: SignalSource) -> None:
    for name, initial in iter_signal_fields(type(instance)):
        instance.__dict__[name] = copy.deepcopy(initial) if _needs_copy(initial) else initial
```

Each of the three base classes calls it once from `__init__`:

```python
# SessionContext.__init__
self.session = session
_seed_signal_fields(self)
...

# SessionState.__init__
def __init__(self) -> None:
    _seed_signal_fields(self)

# AppState.__init__
def __init__(self) -> None:
    _seed_signal_fields(self)
```

`EditState` (and other concrete `SessionState` subclasses) lose their
hand-written init loops, inheriting the base behavior.

`iter_signal_fields(cls)` is an internal MRO walker that yields
`(name, initial)` for each `_SignalFieldDescriptor` on `cls`. It is no
longer part of the public API.

### `SignalSource` — the host ABC

```python
# session/signals/host.py
from abc import ABC, abstractmethod
from haywire.core.session.signals import Signal

class SignalSource(ABC):
    """Anything that can emit signal-field signals.

    Concrete implementors: SessionContext, SessionState, AppState.
    Authors do not subclass this directly — they subclass one of the
    three concrete bases.
    """

    @abstractmethod
    def _signal_emit(self, signal: Signal) -> None: ...
```

`SessionContext`, `LibraryState` (and through it `AppState` and
`SessionState`) inherit from `SignalSource`. Python's own ABC machinery
refuses to instantiate any concrete class that omits `_signal_emit` —
the descriptor's `issubclass(owner, SignalSource)` check at class-
definition time catches the "wrong base class" mistake earlier, with a
clearer error.

### `_signal_emit` — three implementations

```python
# SessionContext
def _signal_emit(self, signal: Signal) -> None:
    self.session.publish(signal)


# SessionState
def _signal_emit(self, signal: Signal) -> None:
    session = self.session()           # weakref deref
    if session is None:
        return                          # session gone; silently drop
    session.publish(signal)


# AppState
def _signal_emit(self, signal: Signal) -> None:
    manager = self._session_manager()   # weakref deref
    if manager is None:
        return                           # manager gone; silently drop
    manager.broadcast(signal)
```

The protocol shape is uniform; the implementation differs because the
scope differs. SessionContext / SessionState emit into one session's bus
(via `Session.publish`). AppState fans out to every session (via
`SessionManager.broadcast`). The synthetic signal class carries
`cross_session=True` when the host is AppState, so even if a session-
scoped emit path were used by mistake, `Session.publish` would route it
through `broadcast` anyway — the routing is defensive on both ends.

`Session.publish` already routes `cross_session=True` signals through
`SessionManager.broadcast`, which iterates *every* session including the
originator. AppState writes from a session's request thus fire the
originator's handlers synchronously in the same call stack — uniform
with peers. The bus's "no ordering primitives" rule still holds.

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
lifetime of the Session / SessionManager that owns them. The post-cleanup
window (write after the referenced Session/Manager has been torn down)
is handled by the `is None` guard in `_signal_emit` — a silent drop.

## Signal flow

### Emit path (session-local)

```
ctx.active_file = path                          # or SessionState field
  → _SignalFieldDescriptor.__set__(host, path)
     → identity check; bail if `is` current
     → host.__dict__["active_file"] = path
     → host._signal_emit(signal_class())
        → host.session.publish(signal_class())
           → SignalBus.publish(signal)
              → handlers for type(signal) fire in registration order
```

### Emit path (AppState, broadcast)

```
haystack_state.active_haystack = info
  → _SignalFieldDescriptor.__set__(haystack_state, info)
     → identity check; bail if `is` current
     → haystack_state.__dict__["active_haystack"] = info
     → haystack_state._signal_emit(signal_class())
        → haystack_state._session_manager().broadcast(signal_class())
           → for each session: session._dispatch(signal)
              → SignalBus.publish(signal)
                 → handlers for type(signal) fire (per session)
```

By the time the handlers run, the field already reflects the new value
(write-then-emit, sync). Re-entrant writes from inside a handler push
nested emits depth-first.

### Subscribe path

```
@redraw_on(SessionContext.active_file)
  → validate_signal_types sees SessionContext.active_file
  → at class-level access, descriptor.__get__(None, SessionContext)
     returns the synthetic signal class
  → validate_signal_types accepts it (issubclass(..., Signal) is True)
  → decorator stores it as a redraw_on target on the method
  → discover_handlers indexes it normally
  → EditorWrapper subscribes the bound method to the bus
     for this exact synthetic class
```

No changes to `validate_signal_types`, the bus, `discover_handlers`,
`EditorWrapper`, or any other dispatch machinery beyond the rename. The
synthetic signal class participates as a first-class `Signal` subclass.

## Deletions

- `Reactive[T]` class (`reactive/reactive.py`) — file deleted.
- `ReactivePath` (`reactive/path.py`) — file deleted.
- `iter_reactive_fields` as a public name — survives as
  `iter_signal_fields`, internal-only.
- `ContextSignal` — class deleted; hand-authored signals inherit `Signal`
  directly.
- Four field-mirroring signal classes from `session/events.py`:
  - `ActiveFileMoved`
  - `ActiveLibraryMoved`
  - `ActiveComponentMoved`
  - `ThemeMoved`
- Their `__all__` entries.

## Surface affected

Confirmed by grep at spec time.

**Signal fields (15 total, all session-scoped today):**

- `SessionContext` (5): active_file, active_library, active_component,
  active_workbench_theme_key, active_node_theme_key
- `EditState` (8): active_graph, active_graph_path, active_node,
  active_edge, active_port, selected_nodes, selected_edges, clipboard
- `FileBrowserState` (1): right_clicked_file
- `haybale-testing` fixture (1): counter

No `AppState` signal fields exist today. The descriptor supports them
from day one (so the design is uniform across host scopes), but the PR
ships zero AppState signal fields. Adoption is on libraries when they
have a concrete use case — `HaystackState.active_haystack` is the
obvious candidate.

**Write/read sites (~50, mechanical):** `.value =` → bare assignment;
`.value` (read) → bare attribute access. Audit step:
`grep -rn '\.value\.\(add\|remove\|clear\|append\|update\|pop\)\b'` —
identify in-place-mutation sites that need to be rewritten as
reassignment if the emit matters. The known case at
[tests/studio/test_edit_state.py:80](../../tests/studio/test_edit_state.py)
is the canonical example.

**Subscriber audit:** in-commit grep for the four deleted signal class
names (`ActiveFileMoved`, `ActiveLibraryMoved`, `ActiveComponentMoved`,
`ThemeMoved`) and rewrite each `@redraw_on(ActiveFileMoved)` to
`@redraw_on(SessionContext.active_file)` (and so on). These subscriptions
are currently *dead* — nothing publishes the old classes — so the rewrite
converts dead decorators into live ones for the first time. Import errors
on the deleted class names provide the safety net.

**Tests rewritten:**

- `tests/ui/signals/test_signal_field_descriptor.py` — new spec for the
  data descriptor: `__set__` emits, `__get__` returns raw value,
  class-level access returns the synthetic signal class, identity
  short-circuit silent, shadowing raises.
- `tests/core/test_session/test_context_signals.py` — read/write idiom
  changes; assert subscribed handlers fire via real `Session`.
- New: `tests/core/test_state/test_session_state_signals.py` — same
  pattern with `EditState.active_node`.
- New: `tests/core/test_state/test_app_state_signals.py` — write to an
  `AppState` field, assert *every* session's bus receives the signal.
- New: `tests/core/test_state/test_session_state_post_cleanup_drop.py` —
  drop the session, then write through a held `SessionState` instance;
  assert no crash, no signal delivered (the silent-drop guard).
- New: `tests/core/test_signals/test_hot_reload_roundtrip.py` — reload
  `EditState`, recreate editors, assert old-class subscriptions are
  cleaned up and new-class subscriptions receive emits.
- ~10 barn/test files that touch `.value` on EditState/FileBrowserState.

Tests assert via the real publish path — a real `Session`, subscribe to
`Owner.field`, and assert on captured signals. No test-only API; mock-
based tests would bypass the `_signal_emit` glue, which is exactly where
this PR's risk lives.

**Documentation rewritten in the same PR:**

- `docs/architecture/session-and-state/session-and-state-arch.md`
- `SessionContext` class docstring
- `EditState` class docstring
- `signals/__init__.py`, `signals/descriptor.py`, `signals/host.py`
  docstrings
- `internals/speculatives/event_bus_redesign.md` — paragraph that
  references the Reactive/Phase-2 split

## Rollout — sequenced commits inside one PR

Per CLAUDE.md, a "substantial" change requires a pre-edit baseline.
Run once at PR start:

```sh
uv run ruff check .
uv run mypy <8 paths>
uv run pytest
```

Then six commits, each leaving the tree green:

1. **Land the new module.** Add `session/signals/` with descriptor,
   `signal_field()`, `SignalSource(ABC)`, the renamed bus
   (`SignalBus` — temporarily co-existing or aliased; if aliased, alias
   removed by step 5), the renamed root (`Signal`), `CommandSignal`.
   Nothing wired yet. Old `Reactive`, `ReactivePath`, `Event`,
   `ContextSignal`, `EventBus`, `LifecycleCommand` still live.
2. **Wire the host base classes.** Add `_signal_emit` to
   `SessionContext` / `SessionState` / `AppState`; extend container
   stamping for `self.session` weakref (`SessionState`) and
   `self._session_manager` weakref (`AppState`). No fields use it yet.
   Suite green.
3. **Migrate `SessionContext` fields** (5 fields, annotations + ~15
   read/write sites). Delete `ActiveFileMoved`/`ActiveLibraryMoved`/
   `ActiveComponentMoved`/`ThemeMoved`; rewrite their dead subscribers.
   Suite green.
4. **Migrate `EditState` + `FileBrowserState` + `haybale-testing` fixture**
   (10 fields, ~35 read/write sites). Suite green.
5. **Delete the old surface.** Remove `Reactive`, `ReactivePath`,
   `Event`, `ContextSignal`, `EventBus`, `LifecycleCommand` (and any
   aliases). Update `session/__init__.py`. Suite green.
6. **Rewrite docs.** `session-and-state-arch.md`, class docstrings,
   module docstrings. Mark this spec as **Done** and (optionally) move
   it out of `speculatives/`.

Each commit is independently revertable and bisect-friendly. The full
verification suite runs at the end of each commit; the final commit's
green state is the PR-merge prerequisite.

## Decisions captured

Includes the original 15 decisions and the 15 settled during the
inquisition round.

### Original

| #   | Decision                                                                                                                                     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Solves both: signal-field notifications + field/event pairing convention. Bus is the only notification channel.                              |
| 2   | No `signal=` arg on `signal_field()`. Framework synthesizes the signal class.                                                                |
| 3   | Data descriptor on the host, no `.value`. Read/write are bare attribute access.                                                              |
| 4   | `ReactivePath` deleted.                                                                                                                      |
| 5   | Sync, write-then-emit. Identity short-circuit kept (see Q3 below).                                                                           |
| 6   | Signal payload empty. Subscribers read the field back.                                                                                       |
| 7   | Subscribe to the field reference directly. Synthetic class is internal.                                                                      |
| 8   | Synthetic class generated in `__set_name__`, cached on descriptor.                                                                           |
| 9   | Host implements `_signal_emit`; verified at class-definition.                                                                                |
| 10  | Full rollout: `SessionContext` + all library `SessionState` in one PR.                                                                       |
| 11  | In-place container mutation stays silent. Audit `.value.add` style sites.                                                                    |
| 12  | Container stamps lifecycle refs: `self.session` (weakref) on `SessionState`, `self._session_manager` (weakref) on `AppState`.                |
| 13  | Annotation is `T`, not `Reactive[T]`. `Reactive` removed from public API.                                                                    |
| 14  | `cross_session` is derived from host scope, not a field flag. AppState signal fields auto-broadcast; SessionState/SessionContext stay local. |
| 15  | Single PR, including docs and `.insights` updates.                                                                                           |

### Inquisition

| Q   | Decision                                                                                                                                                   |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q1  | Synthetic signal class stashed on the descriptor only; accessed via `Owner.field`.                                                                         |
| Q2  | Class-level access returns the synthetic signal class itself (no wrapper type).                                                                            |
| Q3  | Identity-only short-circuit (`is`), no `==` fallback — handles wrapper rebinding, `NaN`, and numpy `==`-raises.                                            |
| Q4  | AppState signal fields: don't write in `__init__`; mirror the existing `session_id` rule. Zero-session broadcast is a silent no-op.                        |
| Q5  | AppState broadcast includes the originating session, synchronous.                                                                                          |
| Q6  | Re-entrant writes allowed; depth-first dispatch; identity short-circuit terminates trivial loops.                                                          |
| Q7  | Shadowing signal fields in subclasses is **forbidden** at class-definition time.                                                                           |
| Q8  | Tests assert via real-Session subscribe; no test-only API.                                                                                                 |
| Q9  | Hard cutover in one PR; no deprecation shim.                                                                                                               |
| Q10 | Sequenced commits inside the PR, each green; baseline before/after per CLAUDE.md.                                                                          |
| Q11 | Keep the subscribe/read asymmetry; signal-field signals stay payload-free; hand-authored signals carry payload when needed.                                |
| Q12 | `SignalSource(ABC)` with `@abstractmethod _signal_emit`; `LibraryState` and `SessionContext` inherit; descriptor checks `issubclass(owner, SignalSource)`. |
| Q13 | In-commit grep-and-rewrite for the four deleted signal classes; rely on test suite + import errors.                                                        |
| Q14 | `iter_signal_fields` stays as internal MRO walker; shared `_seed_signal_fields(instance)` helper called from each base class's `__init__`.                 |
| Q15 | Hot-reload: identical treatment to hand-authored signals; add one round-trip test as confirmation.                                                         |

### Vocabulary

| V   | Decision                                                                                                                                               |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| V1  | System word: **signal**. The bus carries signals, not events.                                                                                          |
| V2  | `Event` → `Signal` (abstract root). `ContextSignal` deleted; concrete signals inherit `Signal` directly. `LifecycleCommand` → `CommandSignal(Signal)`. |
| V3  | `EventBus` → `SignalBus`. `EventHandler` → `SignalHandler`.                                                                                            |
| V4  | `reactive_field` → `signal_field`. `_haywire_publish` → `_signal_emit`. `ReactiveHost` (working name) → `SignalSource`.                                |
| V5  | Module `session/reactive/` → `session/signals/`. Files `reactive.py`, `path.py` deleted.                                                               |
| V6  | Decorators `@redraw_on` / `@react_on` kept — they describe handler semantics, not bus vocabulary.                                                      |
