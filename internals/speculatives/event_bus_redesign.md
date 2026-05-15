# Event Bus Redesign — Design Summary

**Status:** speculative / design-in-progress
**Driver:** [`PropertiesEditor`](../../barn/haybale-studio/haybale_studio/editors/properties_editor.py) bug — its `_RELEVANT_SIGNALS = (SelectionMoved, ActiveGraphMoved, GraphDataMutated)` is hardcoded on the editor, but it hosts third-party panels that may react to events the editor doesn't know about. The editor cannot statically know what signals its registered panels need.

## Problem

Today's signal dispatch is **broadcast-with-receiver-filter**, not pub/sub:

- [`Session`](../../packages/haywire-core/src/haywire/core/session/session.py) holds a single `_signal_callback` slot.
- AppShell registers itself as the callback and iterates every editor in every slot on every signal.
- Each editor filters with `isinstance` in `redraw_on_signal` / `on_signal`.

This means an editor's filter must be **closed over the editor's own knowledge** — fine for editors with fixed responsibilities, broken for host editors like `PropertiesEditor` whose content is contributed by third-party libraries.

## Goal

Replace the broadcast-and-filter model with **typed pub/sub** where:

- Editors and panels declare what they care about; framework dispatches only to subscribers.
- Host editors' effective subscriptions union with their registered panels'.
- Author-facing surface preserves what works today (typed `ContextSignal` classes, `session.signal()`/`subscribe()` shape, `cross_session` opt-in).

## Locked Design Decisions

### Scope (Q1–Q2)

- Fix `PropertiesEditor` by redesigning dispatch, not patching its filter.
- `PropertiesEditor` is the validation case for the new design.

### Event Identity (Q3, Q12, Q13)

- **Class-typed events.** Keep [`ContextSignal`](../../packages/haywire-core/src/haywire/core/session/signals_and_lifecycle.py) as the vehicle. No string topics, no enum dispatch.
- **Shallow hierarchy allowed.** Intermediate base classes (e.g. `SelectionEvent`) added on demand when a real grouping subscription appears. No upfront taxonomy.
- **Hand-rolled typed bus.** Not blinker / PyPubSub. ~50–100 lines, full type checking, classes as identity throughout.

### Emission (Q4)

- **Hybrid mutator-driven.** Mutators emit explicit events for coarse domain moves. No reactive-field auto-emission, no proxy-wrapped state. Status quo emission pattern preserved.

### Subscription Model (Q5–Q6, Q14, Q15, Q16, Q18)

#### Editors

Method-level decorators, two flavors. The author writes methods with whatever names they want and decorates them; the framework discovers handlers via decorator metadata. **`BaseEditor` does not expose abstract `on_redraw_event` / `on_side_event` / `redraw_on_signal` / `on_signal` methods — the decorator is the contract.**

```python
@editor(label="Properties")
class PropertiesEditor(BaseEditor):

    @redraw_on(SelectionMoved, GraphDataMutated)
    def _refresh_on_selection_change(self, ctx, event): ...
    # Fires only when this editor is the active wrapper.
    # Framework calls handler, then redraws.

    @react_on(EntityRemoved, GraphClosed)
    def _close_if_my_entity_gone(self, ctx, event): ...
    # Fires regardless of active state (backgrounded editors still receive).
    # Pure side-effect — author is responsible for any wrapper action
    # (force_close, mark-stale, cache clear).
```

- Method names are author-chosen; the decorator is the only marker.
- Multiple `@redraw_on` / `@react_on` methods per class allowed; each declares its own event-type set.
- Framework introspects the class at registration time (walking the MRO to pick up inherited decorated methods), indexes `(event_type → handler_method)`.
- If multiple `@redraw_on` methods match the same event, all fire; framework redraws once total.
- Subclassing: redefining an inherited decorated method without re-decorating silently removes that subscription (treated as a regular method override). To inherit-and-extend, the subclass declares its own decorated method alongside.

#### Panels

Class-level field on `@panel(...)` decorator:

```python
@panel(action=PropsActions, focus=NodeFocus, label="Node",
       redraw_on=(SelectionMoved, GraphDataMutated))
class NodePanel(BasePanel):
    def draw(self, ctx, layout, actions): ...
```

- Panels declare types only — no panel-side handler dispatch.
- Asymmetric with editors *by design*: panels don't have an independent redraw cycle. They're re-mounted as part of editor redraw.
- No `react_on=` on panels (deferred — no concrete case yet).
- Panel `poll()` unchanged; subscription is about *when to redraw*, `poll()` is about *whether to mount*.

### Effective Subscription Set (Q7)

For each editor, the framework computes:

```
effective_set = (own @redraw_on event types)
              ∪ (own @react_on event types)
              ∪ ⋃ (panel.redraws_on for panel in panels_registered_against_editor)
```

- **All registered panels**, not just currently-mounted (active focus / `poll()`-passing). Stable set; doesn't churn as user switches focus.
- The set is what determines bus *subscription*. Routing per-event to specific handler methods is a separate concern.
- Wasted redraws (event matched, panel not currently visible) are acceptable cost — `poll()` re-evaluated on redraw and unaffected panels still re-mount cheaply.

### Subscription Lifecycle (Q14)

- **Subscribe at editor instantiation**, unsubscribe at `cleanup()` / hot-reload eviction.
- Backgrounded editors stay subscribed. Preserves today's `on_signal`-style side effects (mark-stale, force-close on entity removal).
- Subscription handles are framework-internal; no public author API for imperative subscribe/unsubscribe (deferred).

### Bus Scope and Mechanics (Q10, Q11, Q20)

- **Per-session bus is primary.** `Session.publish(event)` / `Session.subscribe(EventType, handler)`. Bus mechanics are internal; consumers see only the `Session` surface.
- **App-level bus exists for cross-session.** Driven by the existing `cross_session: ClassVar[bool]` flag on event classes. Same opt-in pattern as today.
- **Cross-session dispatch lives in `Session.publish()`.** On call, `publish()` inspects `type(event).cross_session`; if true, delegates to `SessionManager.broadcast_signal(event, origin_id=self.session_id)` which iterates sessions, stamps `Subject.peer(origin_id)` on non-origin sessions, and calls each session's local dispatch. If false, fan out locally. Preserves today's `Session.signal()` routing rule unchanged.
- **Within a session, dispatch order is registration order; error-isolated per handler.** Each handler runs in `try/except`; a raising handler is logged and the next handler fires. Authors should not rely on cross-handler ordering for correctness — fix the data dependency, don't paper over it with ordering primitives.
- **Handlers are sync only in v1.** Author method signature: `def handler(self, ctx, event) -> None`. Authors needing async work spawn it explicitly (`asyncio.ensure_future`, NiceGUI timer patterns). Aligns with today's sync `redraw_on_signal` / `on_signal` and avoids the NiceGUI async / slot-stack footgun (see `feedback_nicegui_async.md`). Async-aware dispatch can be added later as a strict superset if a real case appears.

### Dispatch Loop Semantics (Q22)

Slots use `ui.tab_panels` with `keep-alive`: every wrapper's container stays mounted in the DOM regardless of which tab is active. A `wrapper.redraw()` on a backgrounded editor does invisible work (container clear + `draw()` into a hidden panel) — the user sees nothing until they focus the tab. The active-only filter in today's `redraw_on_signal` was a cost optimization that paid for itself with a correctness footgun (missed events while backgrounded → manual catch-up logic in `on_focus`, e.g. `HaystackEditor._notify_data_mutated`).

**The new model drops the active-only filter.** Both `@redraw_on` and `@react_on` fire regardless of active state. The only difference is whether the framework triggers a redraw after the handler returns.

At handler-registration time, the framework tags each decorated method with its kind: `redraw_on` (framework redraws after) or `react_on` (handler does its own thing). At dispatch time, for each editor with matched handlers:

```python
needs_redraw = False
for handler, kind in matched_handlers_for_this_editor:
    try:
        handler(ctx, event)
    except Exception:
        logger.exception(...)   # error-isolated per Q20b
        continue
    if kind == "redraw_on":
        needs_redraw = True

if needs_redraw:
    wrapper.redraw()
```

Invariants:

1. **Both kinds fire regardless of active state.** Backgrounded editors stay current; on focus they're already drawn correctly. No dirty-bit tracking, no catch-up logic on focus.
2. **Multiple `redraw_on` handlers matching the same event trigger exactly one redraw** at end of pass — not one redraw per handler. Implementation: collect handler results, then `wrapper.redraw()` once if any `redraw_on` handler ran.
3. **`react_on` handlers never trigger auto-redraw** — author is responsible for any explicit `wrapper.redraw()` / `wrapper.force_close()` / `session.lifecycle(...)` calls inside the handler body. Side-effect-only by definition.

Consequence: editors today that manually re-emit signals from `on_focus` solely to force a catch-up redraw (e.g. `HaystackEditor._notify_data_mutated`) lose that workaround as part of the migration — `on_focus` returns to its documented purpose (claim ownership of session state, broadcast `ActiveGraphMoved`, etc.).

### Channel Boundaries (Q9, Q18)

Three independent channels coexist; explicitly **do not** unify:

1. **Event bus (this redesign).** Coarse, named, semantic state moves → editor/panel **structural** redraws (which widgets exist, what's visible). Editor/panel granularity.
2. **Settings system** (`haywire/core/settings/`). Fine-grained, value-level reactivity via `shadow()`/`watch()` descriptors → in-place **widget** updates. Also provides the rendering mechanism for setting-bound widgets inside panels.
3. **HotReload Registry channel** ([`BaseRegistry`](../../packages/haywire-core/src/haywire/core/registry/base.py) `_registry_subscribers` / `_batch_event_subscribers`). Carries `LifeCycleEvent`. Hot-reload, library install/uninstall, panel catalog mutations.

**Composition.** Panels compose channels (1) and (2) naturally: structural changes flow through the event bus (panel re-mounts); value-level changes flow through settings (widgets self-update). `redraw_on=` on a panel should be reserved for events that change *what widgets the panel shows*, not events that change the values inside existing widgets — those are settings' job.

> **Superseded by [reactive_bus_unification.md](reactive_bus_unification.md).** Reactive session states (`haywire/core/session/reactive/`) were unified with the event bus in the signal-field unification work. Field writes now emit a synthetic `Signal` on the same `SignalBus` carrying every other signal; the "Phase 2 auto-tracking" originally planned here was explicitly rejected (ContextVar conflicts with hot-reload). The settings system remains a separate, value-level reactivity channel for widget-internal state.

Firewall rules:

- Do **not** bridge registry events into the new event bus inside the framework. Editors that need registry-change notification subscribe to the registry channel directly. App may later add a bridge if a concrete cross-cutting case appears.
- Do **not** emit a `ContextSignal` as a side effect of a registry callback inside library/framework code.
- **Lifecycle commands** (`Reveal`, `Close`, `BroadcastClose`) — imperative tab mutations — stay on the separate `Session.lifecycle()` channel.

## Migration Plan (Q19)

**Staged big-bang.** Framework lands additively (both APIs work side-by-side for a bounded window), then editors migrate in a tight follow-up sweep, then the old API is removed. No long-lived coexistence.

Concrete sequence:

1. **PR #1 — Framework, additive.** Add typed bus to `Session` (`publish`/`subscribe`). Add `@redraw_on` / `@react_on` method decorators. Add `redraw_on=` keyword to `@panel(...)`. AppShell dispatches via *both* the bus (to new-style decorated methods) *and* the existing `redraw_on_signal` / `on_signal` overrides (old path preserved). Tests cover both paths. No editor changes. Nothing user-visible.
2. **PR #2 — PropertiesEditor migration + original bug fix.** Rewrite `PropertiesEditor` using the new model. Add `redraw_on=` to its registered panels (`canvas_settings.py`, `node_settings.py`, `app_panels.py`). The structural bug is fixed; PropertiesEditor becomes the validation case for the design.
3. **PR #3 — Sweep migration.** Convert the remaining ~9 editors (`graph_editor`, `haystack_editor`, `library_component_editor`, `node_source_editor`, `code_editor`, `file_viewer`, `library_browser_editor`, `library_overview_editor`, plus any new ones). Each migration is small and mechanical. Tests still pass on both paths during the sweep.
4. **PR #4 — Deprecation closeout.** Remove `redraw_on_signal` / `on_signal` from `BaseEditor`. Remove dual-dispatch logic from AppShell. Single path.

**Disciplines:**

- PR #1 must include an explicit TODO/issue tracking the closeout. "We'll get to it" without a tracked closeout is how dual-path systems rot.
- During the window, code review rejects *new* editors using the old API.

## Naming and Layout (Q21)

- **Vehicle class:** `ContextSignal` stays. No rename.
- **Publish method:** `Session.signal()` → `Session.publish(event)`. Pairs with `Session.subscribe(EventType, handler)`. ~10–20 call sites to update.
- **Decorators:** `@redraw_on(...)` (framework auto-redraws after handler) and `@react_on(...)` (side-effect-only, fires regardless of active state).
- **Bus location:** `haywire.core.session.bus` (co-located with `Session`). Bus is session-scoped; module placement reflects that.
- **Source file split:** `signals_and_lifecycle.py` → `signals.py` (event classes) + `lifecycles.py` (lifecycle commands). Import updates land in PR #1.

## Out of Scope (Deferred)

- **Lifecycle commands redesign** (`Reveal`, `Close`, `BroadcastClose`). Different semantics from signals (imperative point-to-point/fan-out routing, not pub/sub observation). The PropertiesEditor bug doesn't touch this channel. Revisit only after this redesign lands and we can ask the right question with the signal bus already working — probable answer is "no rework needed."
- **Imperative subscription surface.** Authors today can only declare subscriptions via decorators. If a real use case appears (e.g. a widget inside a panel wanting to subscribe for its own lifetime), add `session.subscribe(...)` / `session.unsubscribe(...)` as a strict superset. No retrofit cost.
- **Class-level `@redraw_on(...)` shortcut.** Only method-level subscription in v1. If empty-stub handlers (`def _refresh(...): pass` just to attach the decorator) become a common pattern in real editor code, revisit then.
- **Async handlers.** Sync only in v1. Add coroutine support later if a concrete handler needs it.
- **Priority / ordering primitives.** Registration-order dispatch only. Add if and when a real case appears.

## Subclassing / Hot-Reload Sharp Edges (To Document Before Implementation)

- Method decorators store metadata on the function object. Because there is no abstract `on_redraw_event` on `BaseEditor` to override, the classic "subclass overrides the method and strips the decoration" footgun is moot — every handler is author-named and only exists if decorated. The remaining subtlety: a subclass redefining an inherited decorated method *without* re-decorating silently removes that subscription. This matches normal Python override semantics and is usually what the author wants; document anyway in the authoring guide.
- Hot-reload of a library that defines event classes: the existing rule (declare the signal-defining library in `LibraryIdentity.dependencies`) still applies. With method-level subscriptions, the same `isinstance` staleness can occur — same mitigation.

## Concrete Fix for the Original Bug

Under this design, `PropertiesEditor` uses **two independent notification sources**: the event bus (state moves, via the new pub/sub) and the panel registry's hot-reload channel (catalog mutations, via existing `BaseRegistry` callbacks). The framework does not bridge them.

```python
@editor(label="Properties", icon=hui.icon.node_settings,
        default_slot="right", description="...")
class PropertiesEditor(BaseEditor):

    def __init__(self, wrapper):
        super().__init__(wrapper)
        # Hot-reload / library install / uninstall: PanelRegistry's
        # existing callback channel. Recompute focus toolbar and redraw.
        self._registry_unsub = panel_registry.subscribe(self._on_registry_change)

    def _on_registry_change(self, event: LifeCycleEvent) -> None:
        # Local redraw — focus toolbar and content area both rebuild.
        ...

    def cleanup(self) -> None:
        self._registry_unsub()

    # No @redraw_on / @react_on methods on the editor itself.
    # The event-bus subscription set comes entirely from registered
    # panels' `redraw_on=`, unioned by the framework.
```

Each panel that wants to redraw on selection changes declares:

```python
@panel(..., redraw_on=(SelectionMoved,))
class NodeStuffPanel(BasePanel):
    def draw(self, ctx, layout, actions): ...
```

Framework: editor's effective event-bus subscription = `union of all registered panels' redraws_on` = `{SelectionMoved, ...whatever panels need...}`. Editor subscribes to all of them on the event bus; redraws on any; panels re-mount with fresh state. Separately, the editor is also subscribed to the panel registry's lifecycle channel for catalog mutations.

The bug is gone, and `_RELEVANT_SIGNALS` is no longer something the editor author has to maintain.

## Validation Walkthrough — HaystackEditor

A second, richer validation case from the existing codebase. `HaystackEditor` overrides *both* `on_signal` (side effect: close stale tabs on `HaystackTeardown`) and `redraw_on_signal` (active-only redraw on `ActiveGraphMoved` / `GraphDataMutated` / `HaystackReloaded`), and consumes library-defined `ContextSignal` subclasses (`HaystackTeardown`, `HaystackReloaded` from `haybale_haystack.signals`).

Migration under the new model:

```python
@editor(label="Haystack", icon=hui.icon.haystack, default_slot="left", description="...")
class HaystackEditor(BaseEditor):

    @redraw_on(ActiveGraphMoved, GraphDataMutated, HaystackReloaded)
    def _redraw_on_state_move(self, ctx, event):
        pass   # empty handler — framework redraws after

    @react_on(HaystackTeardown)
    def _close_stale_tabs(self, ctx, event: HaystackTeardown):
        self._on_haystack_teardown(ctx, event)
    # `_on_haystack_teardown` issues `session.lifecycle(Close(binding_id=eid))`
    # for each vanishing entry — fires even when this editor is backgrounded.
```

What this confirms:

- **Library-defined event classes flow through the bus unchanged.** `HaystackReloaded` / `HaystackTeardown` are `ContextSignal` subclasses with `cross_session=True`; `Session.publish()` routes them through `SessionManager.broadcast_signal` exactly as today. Subscribers declare them in `@redraw_on(...)` / `@react_on(...)` like any builtin event.
- **The `react_on` / `redraw_on` split maps cleanly onto today's `on_signal` / `redraw_on_signal` split.** Backgrounded editors keep their side-effect capability (issuing lifecycle commands from `react_on` handlers works because `ctx.session` is reachable).
- **Empty-body `@redraw_on` handlers are a real pattern.** `_redraw_on_state_move` does nothing but attach the decorator. One concrete instance — not yet a pattern. If a sweep across the 10 editors finds the empty-body shape is common, revisit the class-level `@redraw_on(...)` shortcut.
- **Multi-instance editors (e.g. `GraphEditor`) work without special framework support.** A multi-instance editor that needs to filter by its own `wrapper._binding_id` just consults the binding inside its handler body — same as today's `on_signal` pattern.
