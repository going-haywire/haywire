---
status: accepted
---

# Ports Panel renders live port Widgets as an always-on secondary surface

The node Ports Panel now renders each port's live, editable Widget — the same
control the node card shows — in addition to (not instead of) the in-node
rendering. The same port may have a live Widget instance in both the node card
(via the Skin) and the Ports Panel at once, each with its own
`port.on_changed` subscription. The motivating case is Skins that deliberately
omit inline widgets (e.g. a flow-direction skin laying nodes out top-to-bottom):
the panel keeps those ports editable.

## Why this shape

- **Always-on secondary surface, not a skin-driven fallback.** Whether a Skin
  renders a widget is a private Skin decision and is not queryable; coupling the
  panel to it would be fragile. The panel instead renders unconditionally and
  honours the port's own `should_show_widget()` (ADR 0003) — the same predicate
  the Skin uses. A Skin that omits a widget does so by not calling
  `render_widget` in `render()`, which is orthogonal to `should_show_widget()`,
  so the panel surfaces the omitted widget for free without knowing the active
  Skin.
- **Panel owns widget lifecycle.** `BaseWidget.render()` subscribes to
  `port.on_changed` and only unsubscribes in the final, idempotent `cleanup()`.
  The panel re-mounts on every `redraw_on` signal and selection change, so it
  stores the instances it creates and disposes the prior batch at the top of
  every `draw()`, plus a one-time client-disconnect sweep. This is contained in
  the panel; the shared panel framework gained no new teardown hook.
- **Namespaced factory tracking key.** The singleton `WidgetFactory` tracks
  `widget_key -> {node_ids}` for hot-reload and purges by `node_id` in
  `unregister_widget_for_node`. The panel registers its widgets under
  `panel:<node_id>` so the Skin tearing down the node card cannot clobber the
  panel's tracking entry, and vice versa.
- **Factory reached via `IProjectState`.** The panel obtains the factory as
  `ctx.app.widget_factory`, mirroring how it already reaches `node_factory` and
  `panel_registry`. Chosen over a module-level global-injector accessor to keep
  the access typed and consistent with the established `ctx.app.<service>`
  pattern, and to avoid introducing global-injector usage in the UI layer.

## Considered alternatives

- **Skin-driven fallback** (panel shows a widget only for ports the Skin hid):
  rejected — Skin render decisions are private and not queryable; would couple
  the panel to internal Skin state. Honouring `should_show_widget()` achieves
  the same user-visible outcome without the coupling.
- **Panel ignores `should_show_widget()` and renders every widget:** rejected —
  shows dead controls for linked inlets / outlets (the edge or display semantics
  make editing meaningless), adding noise.
- **A new panel teardown hook on `BasePanel`:** rejected for now — the
  top-of-`draw()` dispose pattern is sufficient and keeps the shared framework
  unchanged.
- **Global-injector accessor for the factory:** rejected in favour of
  `IProjectState` exposure (typed, consistent with existing service access).

## Consequences

- Any `GraphDataMutated` re-mounts all display panels (existing behaviour) and
  rebuilds every Ports-panel widget instance. Accepted as consistent with the
  existing `node_settings.py` panel; a heavy/stateful widget on an `ALWAYS`/
  config port would rebuild on unrelated edits.
- Panel widgets are **not** hot-reload-live: a widget-library reload re-renders
  the node card's instances but not the panel's until the panel next redraws.
  Deferred follow-up.
- `IProjectState` gains a `widget_factory` attribute; `LibrarySystemService`
  gains `get_widget_factory()`.
