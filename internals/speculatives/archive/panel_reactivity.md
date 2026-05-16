# Spec: panel reactivity

> **ARCHIVED** — Status: **Superseded**. This was the Phase 2 design (auto-tracking reactive subscriptions) for the panel contract; never implemented. The signal-field unification work (see [`reactive_bus_unification.md`](./reactive_bus_unification.md), also archived) shipped a different mechanism — explicit `signal_field` declarations with `@redraw_on` / `@react_on` decorators — and replaced the need for this layer. Kept for historical reference.

Original status header below (preserved for historical context):

> Status: speculative spec. Describes the reactive layer that drives
> panel re-evaluation. Companion to `spec_panel_contract.md`, which
> describes the panel contract itself.
>
> The contract spec stands on its own — panels can be implemented and
> mounted under the existing bus-message system without this layer.
> Reactivity is what makes panel updates surgical and dependency-aware.
> Treat the two specs as Phase 1 (contract) and Phase 2 (reactivity)
> for implementation planning.
>
> Scope: System A panels only. Editors, slots, and AppShell are out of
> scope — System B has its own state-propagation needs which this spec
> does not address.

---

## 1. What reactivity solves

Panels are functions of state. When state changes, panels need to:

- Re-evaluate visibility (`poll`) and toggle their rendered DOM if it
  flipped.
- Re-render content (`draw`) if they're visible and the state they
  display changed.

Naive approaches fail:

- **Rebuild everything on every change.** Causes flicker, loses
  scroll position, loses focus from input fields, scales poorly.
- **Manual subscriptions per panel.** Pushes the dependency-tracking
  burden onto panel authors. Drift bugs become invisible: a panel
  reads from a field but forgot to subscribe; the panel goes stale
  and nobody notices until the user complains.
- **Coarse signals (one signal per kind of change).** Any panel that
  cares about *anything* in the broadcast re-runs on *every*
  broadcast. Coalesces correctly but wastes work.

The reactive layer solves this with three properties:

1. **Per-cell granularity.** Each piece of state is its own cell.
   Subscribers watch specific cells, not categories.
2. **Auto-tracked dependencies.** When a method reads a cell during
   execution, the read auto-subscribes the method's wrapper to that
   cell. Panel authors don't enumerate dependencies; the framework
   observes them.
3. **Surgical re-render.** When a cell changes, only the methods that
   read it re-run. Sibling panels reading other cells are untouched.

The `@reads` decorator is layered on top of auto-tracking as a
*declared* contract — panel authors document what they intend to read,
the framework verifies against actual reads, and drift produces
warnings. Auto-tracking is the mechanism; `@reads` is the contract.

---

## 2. The four primitives

### 2.1 `Reactive[T]`

A value holder. Reads inside a tracking context auto-subscribe the
current tracker; writes notify all subscribers.

```python
class Reactive(Generic[T]):
    def __init__(self, initial: T) -> None: ...

    @property
    def value(self) -> T:
        # If a tracker is active (set via ContextVar), subscribe it.
        # Then return the stored value.

    @value.setter
    def value(self, new: T) -> None:
        # If equal to current, do nothing.
        # Otherwise store and notify all subscribers.
```

Key properties:

- **ContextVar-based tracking.** A module-level `ContextVar` holds
  the current tracker. When `Subscription.run()` enters its tracking
  scope, it sets the var; when `Reactive.value` is read inside that
  scope, the read sees the var and adds itself as a dependency. The
  tracker is reset on scope exit.
- **Equality-no-op writes.** Writing the same value twice doesn't
  notify. This guards against redundant updates and breaks naive
  feedback loops.
- **Strong subscriber refs.** Subscribers manage their own lifecycle
  (via `dispose()`); the Reactive holds them with a regular `set`,
  not a weakref. Subscribers must dispose themselves when they go
  away.

### 2.2 `Subscription`

A binding of one method to its current dependency set. Re-runs when
any dependency invalidates.

```python
class Subscription:
    def __init__(
        self,
        method: Callable,
        declared_paths: Iterable[ReactivePath],
        instance: Any,
        host: Host,
        label: str,
    ) -> None: ...

    def run(self) -> Any:
        # 1. Tear down old dependency subscriptions (deps may have changed).
        # 2. Set the ContextVar to self.
        # 3. Call the method; reads on Reactives auto-subscribe.
        # 4. Compare actually-read deps against declared_paths; warn on drift.
        # 5. Return the method's result.

    def invalidate(self) -> None:
        # Called by Reactive when a subscribed cell changes.
        # Forwards to host._mark_dirty(self) — the host owns coalescing.

    def dispose(self) -> None:
        # Tear down all dep subscriptions. Used on unmount or when
        # the subscription is replaced (e.g., draw_sub on hide).
```

Two responsibilities the Subscription does NOT have:

- It does not decide *when* to re-run on invalidation. That's the
  host's coalescing strategy.
- It does not decide *what* the result means. The host interprets
  the result (a bool means visibility; None means a draw completed).

### 2.3 `Host` (the framework-side mount manager)

The host wires Subscriptions around panel methods, manages the dirty
queue, and coordinates flushes. It is framework-internal — panel
authors never see it directly. Each editor/popup/menu that hosts
panels has a host instance backing it.

The host's responsibilities:

- For each mounted panel: own one `vis_sub` (always live) and at most
  one `draw_sub` (live only while the panel is visible).
- Maintain a dirty queue of invalidated Subscriptions.
- On invalidation, schedule a flush via `asyncio.call_soon_threadsafe`
  (threadsafe because invalidations may originate from background
  threads — hot-reload watchers, file watchers, etc.).
- On flush, drain the queue with a `while self._dirty:` loop so
  Subscriptions added mid-flush land in the same flush.
- Catch panel exceptions, wrap as `HaywireException`, render inline
  (per the contract spec's §6).

The host is the seam between the reactive primitives (which are
generic) and the panel contract (which is panel-specific). Different
hosts may exist for different mounting surfaces (e.g., a stack-host
for vertically-listed panels, a tab-host for popups), but they all
share this lifecycle.

### 2.4 `@reads(...)` and `ReactivePath`

```python
@dataclass(frozen=True)
class ReactivePath:
    owner: type
    attr: str
```

A `ReactivePath` is a typed reference to a single Reactive field on
a class. It identifies which cell a method intends to read — without
actually reading it.

```python
def reads(*paths: ReactivePath) -> Callable[[F], F]:
    """Records `paths` as metadata on a method via setattr."""
```

`@reads` is metadata only. It does not intercept the method call. The
real subscription work happens via the ContextVar auto-tracking
inside `Subscription.run()`. The Subscription compares actually-read
deps against `_haywire_reactive_paths` after each run and emits a
deduplicated warning on drift.

The four primitives compose:

- A panel author writes `def poll(self, ctx)` and reads
  `ctx.active_node.value` inside it.
- Decorate with `@reads(SessionContext.active_node)` to declare
  intent.
- The host wraps `poll` in a `Subscription`.
- On `Subscription.run()`, the ContextVar is set; the read auto-
  subscribes; the declared paths are checked against actual reads;
  drift produces a warning.

---

## 3. The host's lifecycle

### 3.0 Why `poll` becomes an instance method

The contract spec defines `poll` as a classmethod: the host evaluates
`poll(cls, ctx)` before deciding whether to instantiate the panel. In
Phase 1 (no reactivity), this lazy-instantiation is genuinely useful
— panels that don't apply to the current state cost nothing.

Phase 2 changes the model: `poll` is wrapped in a Subscription, which
must be bound to a stable callable. A classmethod-based Subscription
cannot dispose-and-recreate cleanly when the panel's lifetime extends
across visibility flips. Phase 2 therefore:

- Promotes `poll` from a classmethod to an instance method.
- Instantiates panels eagerly at mount (one instance per panel
  returned by the registry query).
- Wraps `panel.poll(ctx)` in `vis_sub`; runs once at mount; runs
  again on dependency change.
- Wraps `panel.draw(ctx, layout, actions)` in `draw_sub`; lifecycle
  scoped to "panel currently visible."

The lazy-instantiation cost paid in Phase 2 is one Panel allocation +
one Subscription wiring per registered-but-currently-hidden panel.
This is bounded by the registry's filter (action + focus + accepted-
focus match), which is small in practice.

Migration: panels written for Phase 1 use `@classmethod def poll(cls,
ctx)`. Phase 2 rewrites these as `def poll(self, ctx)`. The signature
otherwise stays identical.

### 3.1 Mount

For each panel returned by a registry query (per the contract spec's
§8), the host:

1. **Instantiates the panel.** `__init__` is called once. Panel state
   (if any) is established. Ctx is NOT available here.

2. **Builds `vis_sub`.** A Subscription wrapping
   `lambda: panel.poll(ctx)`. The Subscription's `instance` parameter
   is `ctx` — that's what's used for drift verification (declared
   paths are resolved against ctx's class).

3. **Runs `vis_sub` once.** The first run executes `poll` inside the
   tracking context; reads auto-subscribe; the result tells the host
   whether to render.

4. **If `vis_sub` returned `True`, renders.** The host opens a body
   container (NiceGUI element), then builds a `draw_sub` wrapping
   `lambda: panel.draw(ctx, layout, actions)` and runs it inside the
   container.

After mount, both Subscriptions are live. The panel is "mounted and
visible." If `vis_sub` returned `False`, the panel is "mounted and
hidden" — the panel instance and `vis_sub` exist, but no body
container, no `draw_sub`.

### 3.2 Invalidation and flush

When any Reactive that some Subscription depends on is written, the
Reactive iterates its subscriber set and calls `invalidate()` on each.
The Subscription forwards to `host._mark_dirty(self)`:

```python
def _mark_dirty(self, sub: Subscription) -> None:
    self._dirty.add(sub)
    if not self._scheduled:
        self._scheduled = True
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._flush)
        except RuntimeError:
            # No running loop (sync tests) — flush immediately.
            self._flush()
```

Two non-obvious choices:

- **`get_running_loop()` not `get_event_loop()`.** Python 3.12 returns
  a non-running loop from the latter, silently dropping callbacks.
  The former raises if there's no loop, which the except branch
  handles.
- **`call_soon_threadsafe` not `call_soon`.** Invalidations may fire
  from background threads (hot-reload watchers, file watchers); the
  threadsafe variant is cross-thread-safe and the perf cost is one
  mutex.

`_flush` drains the dirty queue:

```python
def _flush(self) -> None:
    try:
        while self._dirty:
            batch = list(self._dirty)
            self._dirty.clear()
            for sub in batch:
                self._handle_invalidation(sub)
    finally:
        self._scheduled = False
```

The `while self._dirty:` loop is intentional: a Subscription's re-run
might write to a Reactive (rarely, but legal), causing further
invalidations. Those land in `self._dirty` mid-iteration; the outer
loop picks them up in the same flush rather than deferring them to
the next tick.

### 3.3 Per-Subscription handling

The host routes each invalidated sub by what it represents:

**`vis_sub` invalidated:**

```python
now_visible = vis_sub.run()
if now_visible and not was_visible:
    # False → True flip: lazy-create draw_sub and render.
    open_body_container()
    draw_sub = Subscription(panel.draw, ...)
    draw_sub.run()
    was_visible = True
elif not now_visible and was_visible:
    # True → False flip: tear down draw_sub, clear body.
    draw_sub.dispose()
    draw_sub = None
    clear_body_container()
    was_visible = False
# If unchanged, no-op.
```

**`draw_sub` invalidated:**

```python
if was_visible:
    clear_body_container()
    draw_sub.run()  # re-runs panel.draw(ctx, layout, actions) inside the cleared body
```

The `draw_sub.run()` call:

1. Tears down old deps.
2. Sets the ContextVar to `draw_sub`.
3. Calls `panel.draw(ctx, layout, actions)`. The panel renders into
   the layout's container; reads from ctx auto-subscribe.
4. Verifies declared paths.
5. Returns (draw is `-> None`).

### 3.4 Unmount

When the host's lifetime ends (focus switch, editor unmount, host
disposed), every `_PanelMount` is disposed:

```python
def dispose(self) -> None:
    if self.vis_sub is not None:
        self.vis_sub.dispose()
    if self.draw_sub is not None:
        self.draw_sub.dispose()
```

`Subscription.dispose()` removes the subscription from each
Reactive's subscriber set. The panel instance becomes garbage when
the host releases its reference. No cleanup callback is invoked on
the panel itself by default; panels that need cleanup expose
`dispose()` and the host calls it.

### 3.5 Tick coalescing in practice

The flush loop's drain pattern means an action that writes multiple
Reactives in one tick produces exactly one flush:

```python
# Inside an action handler:
ctx.active_node.value = None
ctx.active_edge.value = None
ctx.active_port.value = None

# Three writes → three invalidations → one _flush on next tick →
# all dependent panels re-run their subs once each → DOM updates.
```

This is what makes "clear selection" feel atomic instead of three
flickering redraws.

---

## 4. SessionContext: the reactive surface

The contract spec (§10.5) describes `SessionContext` fields as having
dual access: class-level returns `ReactivePath`; instance-level
returns `Reactive[T]`. This is how `@reads` references compose with
the actual read sites.

### 4.1 The descriptor pattern

The natural Python implementation is a descriptor:

```python
class _ReactiveField(Generic[T]):
    def __init__(self, initial: T) -> None:
        self._initial = initial
        self._attr_name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            # Class-level: SessionContext.active_node → ReactivePath
            return ReactivePath(owner=owner, attr=self._attr_name)
        # Instance-level: ctx.active_node → the Reactive container
        return instance.__dict__[self._attr_name]


def reactive_field(initial: T) -> _ReactiveField[T]:
    return _ReactiveField(initial)
```

`SessionContext` declares its fields:

```python
class SessionContext:
    active_node: Reactive[NodeWrapper | None] = reactive_field(None)
    active_edge: Reactive[EdgeWrapper | None] = reactive_field(None)
    active_graph: Reactive[GraphWrapper | None] = reactive_field(None)
    # ...

    def __init__(self) -> None:
        # Initialize each Reactive on the instance dict.
        for name, descriptor in self._reactive_fields().items():
            self.__dict__[name] = Reactive(descriptor._initial)
```

Reads:

```python
# In a panel's @reads decorator (class-level access):
@reads(SessionContext.active_node)  # → ReactivePath
def poll(self, ctx: SessionContext) -> bool:
    # In the body (instance-level access):
    return ctx.active_node.value is not None
    #          ^^^^^^^^^^^^^^ Reactive[NodeWrapper | None]
    #                       ^^^^^^ T (auto-subscribes if tracker active)
```

### 4.2 Type-checker story

Mypy sees `active_node: Reactive[NodeWrapper | None]` from the
class-level annotation. Instance-level access types correctly.
Class-level access (the `@reads` site) is typed loosely — mypy will
say `Reactive[...]` where the runtime returns `ReactivePath`. This
is acceptable because `@reads` accepts `ReactivePath` arguments
positionally and the decorator is metadata; the type mismatch is
not a correctness issue.

A future plugin or PEP-695-style narrowing could tighten this; for
now, the cost is one place where the type checker is permissive.

### 4.3 Shallow-only reactivity

The framework provides reactivity at the field level, not at deep
paths. `ctx.active_node` is reactive; `ctx.active_node.value.label`
is NOT — mutating `node.label` does not invalidate any subscriber.

Two implications:

- **Collection mutations need a separate mechanism.** Adding/removing
  edges from `active_graph.edges` doesn't fire reactive invalidation.
  Today's codebase handles this via the `GraphDataMutated`
  ContextSignal — a coarse event subscribers re-render on. This is a
  legitimate place for the bus to coexist with reactive cells; see §6.

- **For a reactive collection, replace the whole reactive value.** If
  selected_nodes is `Reactive[frozenset[str]]`, write a new frozenset
  on each change rather than mutating in place. The equality-no-op
  guard means writing the same set twice doesn't notify.

---

## 5. Bridging hot-reload

Library classes are hot-reloaded. Panels, focuses, and action
Protocols can all be reloaded independently. The reactive layer
must accommodate this without losing subscriptions or leaking
disposed objects.

### 5.1 Panel-class reload

When a panel class is reloaded:

1. The host's existing `_PanelMount` for that panel is disposed
   (subs dispose, body cleared, instance released).
2. The host re-queries the registry. The new panel class appears in
   the result.
3. The host mounts the new class as if it were new: instantiate, wire
   subs, render.

State on the old instance (per the contract spec's §7.1 — UI-local
ephemeral state) is discarded. Session-level reactive state is
unaffected because it lives on `SessionContext`, not the panel.

### 5.2 SessionContext reload

In practice, `SessionContext` is rarely reloaded — it's framework
infrastructure, not library code. If it is reloaded, every Reactive
field on every active context instance is replaced. The migration
strategy is application-specific: typically discard all hosts and
re-mount everything.

### 5.3 Focus-class reload

Focuses are class-keyed. When reloaded:

- Hosts holding `accepted_focuses` references update via the registry
  reload event.
- Panels declared with the old focus class become unreachable until
  re-registered against the new class. The registry's reload handling
  takes care of this.
- The `Subscription` wrapping `Focus.available()` (if any) is keyed on
  the focus class; on reload, the host disposes and re-creates.

---

## 6. Reactive cells vs. context signals

The framework already has `ContextSignal` as a bus for events
(`GraphDataMutated`, `LibraryCatalogChanged`, etc.). The reactive
layer adds `Reactive[T]` for cells. Both will exist; both have
legitimate roles.

### 6.1 When to use which

**Use `Reactive[T]` when:**

- The state is a single value (selection, active item, theme).
- Subscribers want fine-grained updates ("only re-render if the
  active node changed, not if the active edge changed").
- The value is read by panels through ctx.

**Use `ContextSignal` when:**

- The change is an event, not a value transition (graph contents
  mutated, library installed, file saved).
- Subscribers are external to the panel system (other editors,
  cross-session listeners, persistence layers).
- Cross-session fan-out is required (`cross_session: ClassVar[bool] = True`).

### 6.2 The legitimate overlap

Some changes are both: a selection move is a value transition (use
Reactive) AND something cross-session listeners might want to know
about (use a signal). The pragmatic answer is to write the Reactive
and have the writer also emit a signal:

```python
def set_active_node(self, ctx: SessionContext, node: NodeWrapper | None) -> None:
    ctx.active_node.value = node                          # local reactivity
    if node is not None:
        ctx.session.signal(SelectionMoved(...))             # bus broadcast
```

This is a writer-side decision, not a framework feature. The
framework provides both mechanisms; the application chooses which to
use per change.

### 6.3 What NOT to do

- Don't replace every `Reactive` with a signal-per-field.
  Per-attribute signal classes inflate the signal vocabulary and
  give up auto-tracking. The dual mechanism stays.
- Don't replace every signal with a `Reactive`. Some events have no
  meaningful "value" to hold — `GraphDataMutated` is "something
  changed in the graph contents," not "the graph data is now equal
  to X." Forcing it into a Reactive is awkward.

The boundary is "values that subscribers read" vs. "events
subscribers act on." Reactive for values; signals for events.

---

## 7. Open questions

### 7.1 `Focus.available`'s reactive contract

`Focus.available(ctx)` is wrapped in a Subscription by hosts that use
focuses for toolbar availability. Today's pattern (in the
`panels_and_hosts` branch) constructs the Subscription with
`declared_paths=()`, accepting drift warnings as informational —
because the Focus author doesn't declare what they read; they just
read.

Two possible resolutions:

**A. Apply `@reads` to `Focus.available` like panel methods.**
Uniformity with the panel contract; drift warnings become meaningful.
Each Focus author declares its dependencies.

**B. Leave focuses permissive.** Accept that `Focus.available` is
framework-adjacent and small enough that drift detection isn't
useful. Suppress the drift warnings for focus methods specifically
(or pass a sentinel to Subscription that disables verification).

The decision affects:

- Whether library authors writing new focuses need to learn `@reads`
  before their toolbar buttons work correctly.
- Whether the framework treats panels and focuses uniformly or with
  a specific Focus-only escape hatch.
- Whether the drift-warning log noise is a constant background or
  cleanly silenced for known-permissive call sites.

This is left as an explicit open question, to be resolved after the
contract spec is implemented and exercised. The implementation
should make either resolution easy to apply (e.g., a Subscription
constructor flag for "skip drift verification").

### 7.2 Collection-level reactivity

Today's reactivity is shallow: `Reactive[T]` wraps a value, not the
fields of T. Collection-level changes (adding/removing edges,
adding/removing ports) are handled via `GraphDataMutated` signals
that trigger coarse rebuilds.

This is the right initial trade — collection reactivity multiplies
framework complexity (per-element subscriptions, mutation tracking,
diffing). But it leaves a known performance ceiling: panels that
display "all edges of the active node" rebuild fully on any graph
change.

If/when a real consumer needs collection reactivity, the framework
gains a `ReactiveSet[T]`/`ReactiveList[T]` primitive with the same
auto-tracking semantics, OR a Reactive-backed observable-collections
library is integrated. Until then, signals + coarse rebuild is the
documented path.

### 7.3 The Reactive-vs-bus boundary documentation

§6 sketches the boundary, but a real codebase will accumulate edge
cases. The boundary should be an evolving documentation artifact
in `internals/documentation/` once the reactive layer is implemented and
real usage is observed.

---

## 8. Implementation guidance

### 8.1 Minimum viable reactive layer

The smallest implementation that delivers the contract spec's
guarantees:

1. `Reactive[T]` with ContextVar tracking.
2. `Subscription` with `run`/`invalidate`/`dispose`.
3. `ReactivePath` and `@reads` metadata.
4. A single `Host` class with the mount/flush lifecycle described
   in §3.
5. A `_ReactiveField` descriptor and its application to
   `SessionContext`'s reactive fields.

This is roughly the surface that landed in `panels_and_hosts` Steps
0–3. The branch's commits are a usable starting point even if the
final implementation diverges.

### 8.2 Test coverage that catches regressions

Synthetic stress tests proved their worth in the earlier work. The
test surface should at minimum cover:

- A Reactive notifying a Subscription on write; equality-no-op writes
  not notifying.
- A Subscription tearing down old deps before re-running (so
  conditional reads don't accumulate stale subscriptions).
- The Host's flush loop draining `while self._dirty:` so subs added
  mid-flush land in the same flush.
- Tick coalescing — three writes in one tick collapse to one flush.
- `call_soon_threadsafe` from a background thread reaching the flush
  on the main loop.
- A panel exception in `poll` or `draw` being caught, wrapped, and
  rendered inline without breaking sibling panels.
- Hot-reload of a panel class disposing the old `_PanelMount` and
  mounting the new class cleanly.

### 8.3 Migrating from bus-only to reactive

If the contract spec lands first under bus-message propagation, the
reactive migration is roughly:

1. Add `Reactive[T]` and `Subscription` primitives.
2. Convert `SessionContext` fields to descriptor-backed reactive
   fields. Update every reader and writer in one pass — this is a
   breaking change, no shims.
3. Convert one host (e.g., the properties editor's panel host) to
   the reactive lifecycle. Validate end-to-end.
4. Convert remaining hosts.
5. Remove the bus-driven panel re-render path once all hosts are
   reactive.

Per-step gates (test suite green, smoke test passing) are in
`internals/superpowers/` per the project's existing roadmap conventions.

### 8.4 What NOT to build

- Don't build `ReactiveDict`/`ReactiveList` until a real consumer
  appears. Keep collection updates on the signal bus initially.
- Don't build cross-session reactive sync. Reactive cells are
  session-local; cross-session sync is the signal channel's job
  (`cross_session: ClassVar[bool] = True`).
- Don't build a reactive computation graph (computed/derived
  Reactives). Panel `draw` IS the computation; the framework
  re-runs it on dependency change. Memoization is YAGNI until
  measurement proves a need.

---

## 9. Out of scope

- **Editors, slots, AppShell, EditorWrapper.** System B has its own
  state-propagation needs. Reactivity for editors is a separate
  question.
- **Cross-session synchronization.** Cells are local to a session;
  signals are the cross-session channel.
- **Performance tuning beyond tick coalescing.** Throttling,
  debouncing, batching are not provided by the framework. Hosts that
  need them implement them.
- **Reactive primitives beyond `Reactive[T]`.** No
  `ReactiveDict`/`ReactiveList`/`Computed`/`Effect` etc. until a real
  consumer needs them.
- **Devtools.** A subscription inspector / dependency graph
  visualizer would be useful but is not part of this spec.

---

## 10. Glossary

- **Reactive cell** (`Reactive[T]`) — a value holder with a subscriber
  set. Auto-subscribes readers; notifies subscribers on write.
- **Subscription** — a binding of one method to its current dependency
  set. Re-runs on invalidation. Owns its dep tear-down.
- **Tracker** — the Subscription currently set in the ContextVar.
  Reads on Reactives subscribe to the active tracker.
- **Tracking context** — the `ContextVar`-managed scope within which
  reads auto-subscribe.
- **Drift** — a mismatch between a method's `@reads` declaration and
  the Reactives it actually reads. Produces a deduplicated warning.
- **Host** (reactive sense) — the framework-side mount manager that
  wires Subscriptions, owns the dirty queue, and runs the flush
  loop. Distinct from the panel-level "host" in the contract spec
  (which is the conceptual owner of action contracts and panel
  layout); in practice the same object plays both roles.
- **Dirty queue** — the host's set of Subscriptions that have been
  invalidated but not yet re-run.
- **Flush** — the host's per-tick drain of the dirty queue.
- **Tick coalescing** — multiple invalidations within the same
  event-loop tick collapsing to a single flush.
- **Reactive field** — a `SessionContext` attribute whose
  class-level access yields a `ReactivePath` and instance-level
  access yields a `Reactive[T]`. Implemented as a descriptor.
- **Shallow reactivity** — the framework's per-cell granularity:
  `Reactive[T]` reacts to writes of T but not to mutations within T.
