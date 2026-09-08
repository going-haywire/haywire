---
name: show-widget-strategy
description: ShowWidgetStrategy enum gives each DataPort explicit per-direction control over inline widget visibility vs. link state, replacing one hardcoded rule
status: accepted
level: architectural
---

# `ShowWidgetStrategy` — per-port control of widget visibility vs. link state

A `DataPort` may carry an inline editing **widget** (a slider, a text field, a dict editor). Until now the node skin decided whether to render that widget with one hardcoded rule:

```python
if not port.allow_multiple_links and port.widget_key:
    self.render_widget(...)
```

— i.e. *always show the widget if the port has one and isn't multi-link*, regardless of whether the pin is connected. This ADR introduces `ShowWidgetStrategy`, a per-port enum that lets the port author declare what should happen to the widget when the pin is linked, and drops the `allow_multiple_links` guard so visibility becomes an explicit authoring decision rather than a side-effect of connection cardinality.

## The problem

A connected inlet's widget is misleading: the value the user sees in the widget is no longer the value the port uses — the upstream edge overrides it. The classic Blueprint behavior is to **hide the widget once the pin is connected**. The old rule could not express this: a widget was either always rendered (single-link ports) or never rendered (multi-link ports), with no relationship to link state and no per-port override.

We want the full matrix — hidden always, shown-when-unlinked, shown-when-linked, shown-always — and we want a *type* to be able to assign one widget that does the right thing on both inlets and outlets without per-port wiring.

## The enum: plain `Enum`, not `IntFlag`

```python
class ShowWidgetStrategy(Enum):
    NEVER       = "never"        # widget never rendered on the node
    NOT_LINKED  = "not_linked"   # shown only when the pin is NOT linked
    WHEN_LINKED = "when_linked"  # shown only when the pin IS linked
    ALWAYS      = "always"       # always rendered
```

The sibling enum `StoreStrategy` is an `IntFlag` with a `NONE = 0` sentinel and OR-combinable members, because storage has **genuinely orthogonal triggers** (`HAS_WIDGET`, `WHEN_LINKED`, `NODE_SET` can each independently be true and are combined with OR).

Widget visibility has **no such orthogonal dimension**. Link state is a single boolean; the widget shows in the linked state, the unlinked state, both, or neither — four mutually-exclusive outcomes. `ALWAYS` already *is* "linked or unlinked" and `NEVER` is the empty case, so there is nothing left to combine. Making it an `IntFlag` would:

- re-introduce a redundant `NONE` member (the empty sentinel) distinct from `NEVER` (the explicit "hidden") — the original proposal carried both `NONE` and `NEVER`, which behave identically;
- make nonsensical combinations representable (`NOT_LINKED | WHEN_LINKED` is just `ALWAYS` spelled a second way);
- push the skin onto bitwise resolution (`ss & NOT_LINKED and not linked …`) for no expressive gain.

So a plain `Enum` with four members models the decision honestly, and `NEVER` absorbs the proposed `NONE`. Choosing `IntFlag` here would be cargo-culting `StoreStrategy`'s *shape* without its underlying reason.

## Direction-based defaults — and why outlets default to `NEVER`

The default is **not** a single field value; it depends on port direction, injected via `kwargs.setdefault("show_widget", ...)` in `as_inlet` / `as_outlet` / `as_config` — the same seam `store_strategy` already uses, so an author override in `**kwargs` wins naturally and serialization round-trips.

| Port type | default `show_widget` | rationale |
|-----------|----------------------|-----------|
| inlet     | `NOT_LINKED`         | a connected inlet's widget is misleading → hide on connect (Blueprint behavior) |
| outlet    | `NEVER`              | an outlet's value is produced by the node, not entered by a user → no editable widget |
| config    | `ALWAYS`             | a config port has no pin and can never be linked → always-visible by nature |

The outlet default of `NEVER` is the non-obvious one, and it is deliberate. A `widget_key` can be assigned **once at the type level** (`DataTypeIdentity.widget_key`), and that same type is used to build both inlets and outlets. With these defaults, a type that assigns a widget gets the right behavior for free: editable when entering data (inlet, `NOT_LINKED`), suppressed when emitting it (outlet, `NEVER`). The type author writes the widget once; direction does the rest.

Visibility is *only* a per-direction default. A type does **not** get to centrally override `show_widget` (there is no `_resolve_show_widget` mirroring `_resolve_store_strategy`) — the type assigns the `widget_key`; anything other than the per-direction default is overridden per-port when the port is added.

The defaults are also chosen to avoid a silent migration: `ALWAYS` would have preserved the old "always render" behavior, but the inlet default of `NOT_LINKED` *does* change rendering for currently-connected inlets on upgrade — their widgets now hide. This is the intended new behavior, not an accident; it is called out here because a future reader diffing saved graphs will see previously-visible widgets disappear on connected inlets.

## Dropping the `allow_multiple_links` guard

The old guard refused to render a widget on any multi-link port. We remove it. Visibility is now governed solely by `widget_key is not None` (no key → nothing to render) and `should_show_widget()`. A multi-link inlet — e.g. a Pooled type whose widget is a dict editor — may legitimately want to show a widget; the framework should not second-guess that. **It is the developer's decision.**

Consequence: data outlets are force-set to `allow_multiple_links = True` in `DataPort.__post_init__`, so the old guard hid their widgets entirely. With the guard gone, an outlet widget is suppressed by the `NEVER` *default* instead — same end result for the common case, but now an author can opt an outlet into `WHEN_LINKED`/`ALWAYS` if they have a reason.

## Resolution lives on `DataPort`

`DataPort.should_show_widget() -> bool` resolves `self.show_widget` against `self.is_linked()`:

| `show_widget` | not linked | linked |
|---------------|------------|--------|
| `NEVER`       | hide       | hide   |
| `NOT_LINKED`  | show       | hide   |
| `WHEN_LINKED` | hide       | show   |
| `ALWAYS`      | show       | show   |

It lives on the port, not as a private skin helper, because the same decision is needed in the property panel (which also renders widgets) and because it is unit-testable in core without the UI. The skin call sites collapse to `if port.widget_key is not None and port.should_show_widget():`.

## Reactivity: edge add/remove must re-render the endpoint nodes

`NOT_LINKED` and `WHEN_LINKED` are *dynamic* — they depend on live link state, so the widget must appear/disappear when the user connects or disconnects a pin. This did not happen for free.

Node redraw is driven by *node*-level reasons (`ChangeReason.requires_redraw()`); an edge add/remove carries only an *edge* reason, so the connected nodes were never re-rendered. Without a fix, `should_show_widget()` would be evaluated only at initial render and the widget would not toggle on connect — the feature would ship looking broken.

The fix lives in `EdgeWrapper`, at the point link state actually transitions. `link()`, `unlink()`, and `detach()` already orchestrate both ports and (elsewhere) already call their own `redraw()`; they now also call `_request_endpoint_redraw()`, which marks **both endpoint nodes** dirty with `NODE_REDRAW_REQUESTED` via `mark_node_dirty`. The existing `visual_layer.on_validated` node loop then re-renders them — no UI-side inference, no new visual-layer code. Both endpoints, not just the inlet side: the inlet default (`NOT_LINKED`) always needs it, and an author who sets an outlet to `WHEN_LINKED` would otherwise silently break.

Why `EdgeWrapper`, not the visual layer or the graph mutation API:

- The endpoint node ids (`source_node_id` / `sink_node_id`) are plain attributes that **survive `detach()`**, so the removal case needs no captured side-state — unlike a visual-layer or validator approach, which loses the wrapper once the graph deletes it.
- Routing through `mark_node_dirty` → `_set_reason` means a stronger node reason already in the batch wins: paste (`NODE_ADDED`) and `clear()` (`NODE_REMOVED`) both outrank `NODE_REDRAW_REQUESTED`, so the redraw never downgrades a structural change.
- It covers **every** link path, including the validator's internal relink (`ValidationManager._validate_batch` calls `edge_wrapper.link()` during a batch). Re-entrant dirty marks are safe by design — the batch snapshots and clears the dirty dicts up front under its `RLock`, so a mark added during validation is carried to the next batch (see ADR 0002). Worst case on relink is a one-batch-deferred redraw, irrelevant to user connect/disconnect.

## Considered alternatives

- **Keep five members (`NONE` + `NEVER`).** Carries a member that can never differ in behavior — see "plain `Enum`, not `IntFlag`."
- **`IntFlag` for parity with `StoreStrategy`.** Parity of shape without parity of reason; re-introduces `NONE`/`NEVER` redundancy and representable-nonsense.
- **Type-level visibility override (`_resolve_show_widget`).** The type assigns the `widget_key`; visibility stays a per-direction default, overridden per-port. A central visibility override was deemed unnecessary surface.
- **Default `ALWAYS` everywhere** (zero migration). Preserves old behavior but never delivers the motivating hide-on-connect; the direction defaults were chosen instead, accepting the documented inlet migration.
- **Refresh only the inlet-side node on connect.** Cheaper, but silently breaks an author-set `WHEN_LINKED` outlet — the exact "looks broken" bug class this design exists to kill.
- **Refresh endpoint nodes from `visual_layer.on_validated` on `EDGE_ADDED`/`EDGE_REMOVED`** (the first working version). The UI re-derives "edge change → endpoint nodes dirty," duplicating inference every subscriber would have to repeat, and the `EDGE_REMOVED` case must capture the wrapper before the graph drops it. Moved into `EdgeWrapper` so the `ValidationResult` reports the node impact honestly, once, for all subscribers.
- **CSS-only toggle in Vue** (always render the widget, flip `display:none` on a `data-linked` attribute). Keeps a dead widget instance alive and splits visibility policy across Python and Vue.
- **Hook the `on_connect`/`on_disconnect` port callbacks** to request a redraw. Those are author-facing node-method callbacks, not a framework redraw channel; hijacking them collides with user-defined callbacks.

## Consequences

- `DataPort` gains a `show_widget: ShowWidgetStrategy` field, defaulted per-direction in the `as_*` methods, overridable per-port via `**kwargs`.
- The enum serializes as its string `.value` in `to_dict` and is reconstructed in `from_spec` (alongside `FlowType` / `PortType`). Outlets, defaulted to `NEVER`, serialize the field redundantly (it differs from the field's static default); this is cosmetic.
- Node skins decide widget visibility via `port.should_show_widget()`; the `allow_multiple_links` guard is removed, so multi-link ports may now render widgets.
- Connecting/disconnecting a pin re-renders both endpoint nodes, so widget visibility toggles live.
- On upgrade, widgets on currently-connected inlets become hidden (the new `NOT_LINKED` default). This is intended.

## Amendment (2026-09-08) — a promoted port's strategy is the *user's*, not the author's

This ADR says twice that visibility is an authoring decision: "anything other than the per-direction default is overridden per-port **when the port is added**", and "It is the **developer's** decision." That still holds for every author-declared port. It does **not** hold for a **promoted** port, and the distinction is the point.

An author-declared port has a human behind its strategy — someone wrote `as_outlet(...)` and either accepted the default or overrode it. A port promoted from a setting has no such author: `promote_setting` applies a blanket per-direction rule to a port the *user* conjured at runtime, so `NEVER` on a promoted outlet is not a decision anyone made about that value. The motivating gap: a user promotes a setting to an outlet to feed it downstream, and the value they are feeding becomes uneditable and invisible on the card, with no way to ask for it back.

So `DataPort.set_show_widget()` is added as the one runtime write path, reachable only from the pin context menu ("Show widget ▸", a `PinWidgetMenu` submenu offering all four strategies, radio-marked), and offered only where `port.promoted` is true. Nothing calls it on an author-declared port.

Three consequences worth stating, because each is a place this could have been done more cheaply and worse:

- **The full enum is exposed, not a boolean.** A promoted inlet's default is `NOT_LINKED`, and a two-state toggle would have to map "on" to `ALWAYS`, silently destroying the hide-on-connect behavior this ADR exists to deliver. A menu that cannot represent a state the field holds also shows no selection on a port already in that state.
- **The choice persists in the settings bag, not the port.** A promoted port is regenerated from the bag's `promoted` record on load rather than serialized, so the record is the only thing that survives. It widened from `key -> "outlet"` to `key -> {"direction": ..., "show_widget": ...}` — graph format **v3**, migrated by `UpgradeVersionThree`. `show_widget` is written only when it differs from the direction default, so a graph names visibility exactly where a human set it, and `default_show_widget()` now holds those defaults in one place (previously restated at each `as_*` factory plus this document's table).
- **Both render surfaces stay coupled.** `should_show_widget()` remains the single predicate, so the node card and the Ports Panel (ADR 0008) continue to agree. The Properties-panel *settings row* is ungated by it, so a user who sets `NEVER` can still edit the value there — there is no way to make a promoted value uneditable.

Demoting discards the choice: the promotion record is its only storage. Freeze-on-disconnect (ADR 0014) protects *values*, which can represent real work; a view preference is one right-click to restore.
