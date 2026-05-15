---
status: draft
doc_template: guide
scope: Authoring signals — signal_field for reactive state, hand-authored Signal/CommandSignal subclasses for payload-carrying events. Subscription via @redraw_on / @react_on. Hot-reload dependency rule.
see-also:
  - ../components/states/state-canon.md
  - ../architecture/studio/studio-arch.md
  - ../architecture/session-and-state/session-and-state-arch.md
  - ../../internals/speculatives/reactive_bus_unification.md
---

# Signals — authoring guide

A **signal** is anything that flows on the per-session bus. Editors and panels subscribe; writes trigger handlers. There are two equally first-class ways to author a signal:

1. **`signal_field`** — declare a field on a host class; assignment emits.
2. **Hand-authored `Signal` subclass** — declare a class; emit explicitly via `session.publish(...)`.

Both paths produce signals that travel on the same `SignalBus`, are subscribed via the same `@redraw_on` / `@react_on` decorators, and follow the same hot-reload semantics. Picking between them is about *how the signal is shaped*, not *what it does*.

The design rationale and historical context live in [internals/speculatives/reactive_bus_unification.md](../../internals/speculatives/reactive_bus_unification.md). This guide is the author-facing how-to.

## Two equal authoring paths

| Aspect            | `signal_field`                                       | Hand-authored `Signal` subclass                  |
| ----------------- | ---------------------------------------------------- | ------------------------------------------------ |
| What you author   | A field on a `SignalSource` subclass                 | A class in your module                           |
| Emit trigger      | Bare attribute assignment (`ctx.active_file = path`) | Explicit `session.publish(signal_instance)`      |
| Payload           | None — handler reads the field back                  | Whatever fields you declare on the dataclass     |
| Subscription key  | The field reference (`SessionContext.active_file`)   | The class (`SelectionMoved`)                     |
| Cross-session     | Derived from host class scope (AppState broadcasts)  | Set `cross_session: ClassVar[bool] = True`       |

The decorators, the bus, the dispatch order, and the handler protocol are identical for both. You can mix them freely in one `@redraw_on(...)`.

## When to use which

Use **`signal_field`** when:

- A single value changed and "just look again" is the right semantic.
- You'd otherwise pair a field with a sibling event class (`active_file` + `ActiveFileMoved`).
- The host class already exists (`SessionContext`, your `SessionState`, your `AppState`).

Use a **hand-authored Signal** when:

- The signal carries payload that *isn't a field value* — a delta (`NodesMutated(added=..., removed=...)`), a reason (`SelectionMoved(reason="undo")`), a transient input (`KeyPressed(key="Esc")`).
- The fact is coarse-grained and modeling it as per-field writes would produce signal storms during a multi-step operation (`HaystackReloaded`, `LibraryCatalogChanged`, `GraphDataMutated`).
- You're modeling an imperative — "do X" — rather than an observation. Use `CommandSignal` for these (`Reveal`, `Close`, `BroadcastClose`).

## Path 1: `signal_field`

### Hosts

`signal_field` works on the three `SignalSource` subclasses:

| Host             | Instance cardinality        | Emit cardinality           |
| ---------------- | --------------------------- | -------------------------- |
| `SessionContext` | one per session             | this session's bus         |
| `SessionState`   | one per session per class   | this session's bus         |
| `AppState`       | one, shared across sessions | broadcast to every session |

A reader sees `class HaystackState(AppState):` and knows signal fields on it reach every session — the same way they know `ctx.app_data[HaystackState]` returns a shared instance. No flag at the field site re-states this; the base class already does.

### Declaring

```python
from haywire.core.session.signals import signal_field

class EditState(SessionState):
    active_node: Optional[NodeWrapper] = signal_field(None)
    selected_nodes: set[str] = signal_field(set())
```

The annotation describes instance-level access — the value, not a wrapper. `signal_field(initial)` takes only the initial value. No signal class, no path argument, no flags.

Identical shape on `SessionContext`:

```python
class SessionContext(SignalSource):
    active_file: Optional[Path] = signal_field(None)
```

And on `AppState` — the only difference is emit cardinality (writes broadcast to every session):

```python
class HaystackState(AppState):
    active_haystack: Optional[HaystackInfo] = signal_field(None)
```

Mutable defaults (`set()`, `[]`) are deep-copied per instance.

### Reading and writing

```python
# Read — bare attribute.
path = ctx.active_file

# Write — bare attribute. Emits a signal if the value changed.
ctx.active_file = new_path

# Identity-equal writes are no-ops. No signal fires.
ctx.active_file = ctx.active_file  # silent
```

No `.value` anywhere.

### Accessing state from a session

`SessionContext` exposes two scope-bound proxies. Reads look the same regardless of host scope:

```python
# SessionContext — flat attribute on ctx.
path = ctx.active_file

# SessionState — per-session library state, scoped to this session.
node = ctx.data[EditState].active_node

# AppState — app-global library state, shared across all sessions.
haystack = ctx.app_data[HaystackState].active_haystack
```

Writes look the same too — `ctx.data[EditState].active_node = wrapper` emits to this session; `ctx.app_data[HaystackState].active_haystack = info` broadcasts to every session.

The asymmetry between subscription key (`EditState.active_node`) and read path (`ctx.data[EditState].active_node`) is intentional: the subscription key points at the field's *identity*; the read path goes through the namespace that encodes *scope*.

### Change detection: identity, not equality

The descriptor short-circuits on **identity** (`is`), not equality (`==`):

```python
if value is current:
    return
```

Same object suppresses; fresh object fires. Predictable across every value type — including wrappers, NaN, and rich types whose `__eq__` raises (numpy, pandas, torch).

This means wrapper re-binding fires correctly. For example, after a library is hot-reloaded:

```python
old = ctx.active_library          # LibraryInfo("foo", "1.0") — v1
new = LibraryInfo("foo", "1.0")   # same content, fresh instance — v2

old == new                        # True  (dataclass eq)
old is new                        # False (different objects)

ctx.active_library = new
# `new is old` → False → fires. Subscribers re-read and rebind to v2.
```

If the short-circuit were `==`-based, this assignment would skip silently. `active_library` on `SessionContext` is exactly this pattern.

### In-place mutation does not fire

Signal fields follow Python reference semantics. Reassignment fires; mutation through the existing reference does not.

```python
# Fires — new object assigned.
edit.selected_nodes = edit.selected_nodes | {"new"}

# Silent — mutates the existing set in place.
edit.selected_nodes.add("new")
```

Mutating-then-reassigning is the explicit pattern when an emit is needed:

```python
new_set = edit.selected_nodes | {"new"}
edit.selected_nodes = new_set
```

## Path 2: Hand-authored `Signal` subclass

### Declaring

Inherit `Signal` for observations or `CommandSignal` for imperatives. Both are frozen dataclasses with `kw_only=True`:

```python
from dataclasses import dataclass
from typing import ClassVar
from haywire.core.session.signals import Signal, CommandSignal


@dataclass(frozen=True, kw_only=True)
class SelectionMoved(Signal):
    """Fires when the selection changes. Payload is the new selection
    identifier set."""
    selected_nodes: frozenset[str]
    selected_edges: frozenset[str]


@dataclass(frozen=True, kw_only=True)
class Reveal(CommandSignal):
    """Imperative: open this editor in its default slot."""
    editor_key: str
    binding_id: str
```

`Signal` and `CommandSignal` both carry the `cross_session: ClassVar[bool] = False` flag from `Signal`. Override on a subclass to opt into cross-session broadcast:

```python
@dataclass(frozen=True, kw_only=True)
class LibraryCatalogChanged(Signal):
    cross_session: ClassVar[bool] = True   # every session sees this
    library_id: str
```

### Emitting

Publish through the session bus:

```python
# Inside an editor / panel / handler with a Session reference:
ctx.session.publish(SelectionMoved(
    selected_nodes=frozenset({"node-1"}),
    selected_edges=frozenset(),
))
```

`Session.publish` routes the signal based on the class's `cross_session` flag — local signals go to this session's bus, cross-session signals delegate to `SessionManager.broadcast` which dispatches to every session (including the originator).

`CommandSignal` subclasses travel the same way. The AppShell subscribes to each command type and routes it (e.g. `Reveal` opens the editor in its default slot).

### Hot-reload dependency rule

When your library defines a `Signal` subclass that **another** library subscribes to, declare your library in the subscriber's `LibraryIdentity.dependencies`:

```python
# In the subscriber library's identity:
LIBRARY = LibraryIdentity(
    id="haybale_studio",
    label="Studio",
    dependencies=["haybale_haystack"],   # we subscribe to its signals
    # ...
)
```

Without this, hot-reload of the signal-declaring library can leave the subscriber holding a stale class reference, causing `isinstance` checks to spuriously return `False`. Synthetic signals from `signal_field` follow the same rule: if you `@redraw_on(OtherLibState.some_field)`, declare `OtherLibState`'s library in your dependencies.

## Subscribing — uniform across both paths

The decorators don't care which authoring path produced the signal:

```python
from haywire.core.session.handlers import redraw_on, react_on
from haywire.core.session.context import SessionContext


class FileViewerEditor(BaseEditor):

    # signal_field signal — the field reference IS the subscription key:
    @redraw_on(SessionContext.active_file)
    def _on_file_changed(self, ctx, signal):
        path = ctx.active_file
        ...

    # Hand-authored signal — the class is the subscription key:
    @redraw_on(SelectionMoved)
    def _on_selection(self, ctx, signal):
        ...   # signal.selected_nodes carries the payload

    # Mix freely:
    @redraw_on(SessionContext.active_file, SelectionMoved)
    def _refresh(self, ctx, signal):
        ...
```

`@redraw_on` triggers `wrapper.redraw()` after the handler returns — exactly once per dispatch pass even if several `@redraw_on` handlers on this editor match the same signal. `@react_on` is for pure side-effects without redraw.

### Inside the handler

**For `signal_field` signals**, the payload is empty. Read the field back:

```python
@redraw_on(SessionContext.active_file)
def _on_file_changed(self, ctx, signal):
    path = ctx.active_file        # current value
    # signal.old / signal.new do NOT exist
```

This matches the framework convention that subscribers always read the source of truth at handler time, not from a cached event payload.

**For hand-authored signals**, the payload is whatever you declared:

```python
@redraw_on(SelectionMoved)
def _on_selection(self, ctx, signal):
    nodes = signal.selected_nodes
    edges = signal.selected_edges
```

### Re-entrant writes

A handler that writes back to a signal field re-enters the dispatch depth-first — the inner emit completes before the outer dispatch resumes.

```python
@react_on(SessionContext.active_file)
def _normalize(self, ctx, signal):
    if ctx.active_file.suffix == ".bak":
        ctx.active_file = ctx.active_file.with_suffix(".txt")  # re-entrant
```

Trivial loops (writing back the same value) self-terminate via the identity short-circuit. Cross-field ping-pong is an author bug; the bus does not guard against it.

## Common patterns

### "I want to add reactive state to my library"

Use `signal_field` on a `SessionState` or `AppState` subclass:

```python
from haywire.core.state import SessionState
from haywire.core.session.signals import signal_field


@state
class MyLibState(SessionState):
    active_device: Optional[DeviceInfo] = signal_field(None)
    selected_channels: set[int] = signal_field(set())
```

Subscribers reference the field directly: `@redraw_on(MyLibState.active_device)`.

### "I want to emit a coarse-grained event with payload"

Author a `Signal` subclass:

```python
@dataclass(frozen=True, kw_only=True)
class CalibrationCompleted(Signal):
    device_id: str
    quality: float
    duration_ms: int


# Somewhere in the calibration worker:
ctx.session.publish(CalibrationCompleted(
    device_id=dev.id,
    quality=0.92,
    duration_ms=1340,
))
```

### "I want to model an imperative"

Use `CommandSignal`:

```python
@dataclass(frozen=True, kw_only=True)
class FlashLed(CommandSignal):
    device_id: str
    duration_ms: int


# Emit from anywhere with a Session reference:
ctx.session.publish(FlashLed(device_id="dev-1", duration_ms=200))
```

A single subscriber (typically a device driver editor) handles it. Convention is one subscriber per `CommandSignal` type, but the bus does not enforce that.

## Constraints

- **Hosts of `signal_field` must inherit `SignalSource`.** The three concrete bases are `SessionContext`, `SessionState`, `AppState`. A class that uses `signal_field()` without one of those fails at class-definition time with a clear error.

- **Shadowing `signal_field`s in subclasses is forbidden.** A subclass that redeclares a parent's signal field raises `TypeError` at class-definition. If a subclass needs different per-class behavior, model it as two different fields.

- **Don't write `signal_field`s in `__init__`.** Container weakref wiring (the `self.session` / `self._session_manager` references that `_signal_emit` derefs) is stamped between `cls()` and `on_enable()`. Writes during `__init__` predate the wiring and raise. Write in `on_enable()` or later.

- **Hand-authored signals must be frozen dataclasses with `kw_only=True`.** This matches the framework's signal vocabulary; non-frozen or positional dataclasses won't interoperate cleanly with re-entrant write detection or the synthesis path.

- **Subscribers across libraries require the dependency declaration.** See "Hot-reload dependency rule" above.
