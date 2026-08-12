---
name: ports-panel-widget-rendering
description: Ports Panel becomes an always-on secondary surface rendering live port Widgets, mirroring the same visibility predicate the node skin uses
status: accepted
level: architectural
---

# Ports Panel renders live port Widgets as an always-on secondary surface

The Ports Panel — under its own `ports` Scope (`PortFocus`, available when a
node is selected; distinct from the singular per-pin `PinFocus` used by the
right-click menu) — now renders each port's live, editable Widget — the same
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
- **Widget cleanup is anchored to the DOM element, not the panel instance.**
  `BaseWidget.render()` subscribes to `port.on_changed` and only unsubscribes in
  the final, idempotent `cleanup()`. The panel cannot own this via instance
  state: `PropertiesEditor` builds a *fresh* panel object on every redraw
  (`panel_cls().draw(...)` after `content.clear()`), so an instance-held batch
  would never be disposed and its subscription would leak on each redraw.
  Instead each rendered widget's container element gets its `_handle_delete`
  overridden to call `widget.cleanup()`. NiceGUI fires `_handle_delete` for
  every element removed by `content.clear()` (redraw) and by
  `client.remove_all_elements()` (page close), so cleanup runs exactly when the
  DOM is torn down, regardless of which transient panel instance built it. This
  is contained in the panel; the shared panel framework gained no new teardown
  hook. (An earlier instance-owned design — dispose the prior batch at the top
  of `draw()` plus a client-disconnect sweep — was abandoned once the
  fresh-instance-per-redraw behaviour was confirmed; it never actually ran.)
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
- **Ports read from `get_visible_ports()`.** `BaseNode` keeps every port in a
  single `ports` dict and exposes direction via `is_inlet()` / `is_outlet()` /
  `is_config()`; it has no `.inlets` / `.outlets` attributes. The panel reads
  the same visible-port set the skins render (`get_visible_ports()`) and
  classifies each port the way `render_port()` does, so the panel mirrors the
  node card and hidden / section-internal ports stay out of both surfaces.
- **Section expansion persisted via `PanelLayout.state_bag`.** Because the
  panel is rebuilt each redraw, the Config / Inlets / Outlets sections persist
  their open/closed state through the editor-owned `PanelLayout.state_bag`
  dict, keyed by a node-id-free `panel_key` (`node:ports:<section>`) so expansion
  is a stable per-section-type preference rather than per-node.

## Considered alternatives

- **Skin-driven fallback** (panel shows a widget only for ports the Skin hid):
  rejected — Skin render decisions are private and not queryable; would couple
  the panel to internal Skin state. Honouring `should_show_widget()` achieves
  the same user-visible outcome without the coupling.
- **Panel ignores `should_show_widget()` and renders every widget:** rejected —
  shows dead controls for linked inlets / outlets (the edge or display semantics
  make editing meaningless), adding noise.
- **A new panel teardown hook on `BasePanel`:** rejected — anchoring cleanup to
  each widget's container element (`_handle_delete`) handles teardown without a
  framework change, so no shared hook is needed.
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
- The Ports Panel lives under a new `ports` Scope (`PortFocus`) rather than the
  `node` Scope, so the node's ports list is its own toolbar tab. The `node`
  Scope retains `NodeInfoPanel` and `NodePropertiesPanel`. The pre-existing
  per-pin context-menu scope was renamed `PortFocus` → `PinFocus` (`id="pin"`)
  to free the `PortFocus`/`port` name for this node-scoped ports list.
