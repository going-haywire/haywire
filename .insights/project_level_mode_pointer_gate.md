# The level-mode pointer gate: five traps

Below level mode `edit`, `canvas.vue` stops card content taking pointer input with
one CSS gate, keyed on the canvas root's `data-hw-level-mode`. It gates only
elements that are neither exempt nor inside an exempt element:

    view:    .graph-canvas[data-hw-level-mode="view"] .ui-node-slot
                 *:not([data-hw-readable]):not([data-hw-readable] *) { pointer-events: none !important }
    operate: the same, plus :not([data-hw-operable]):not([data-hw-operable] *)
    :where(<the exempt roots of the current mode>) { pointer-events: auto }

`data-hw-readable` marks a read-only affordance that takes input in every mode (the
diagnostics badge and its menu, the comment badge, a pin carrying its own tooltip);
`data-hw-operable` marks a control that takes input from `operate` on.

Each part of it is load-bearing, and each failure is quiet.

1. **Key on `.ui-node-slot *`, not on `[data-node-id]`.** Pins carry `data-node-id`
   too, so a `[data-node-id]` selector would gate the pins, and, worse, the card
   root. The card root and the slot must keep taking presses: a double-click on a
   card body is Enter (needs `operate`). The gate takes the descendants only.
2. **It needs `!important`.** `.connection-pin` sets `pointer-events: all !important`,
   and without `!important` plus the extra selectors a pin that is not readable (a
   ghost pin) stays live below `edit`.
3. **`pointer-events` inherits, so an exempt root needs its `auto` back.** The gate
   sets `none` on the exempt element's ancestors inside the slot, and the element
   inherits it. The `:where()` rule gives the exempt root `auto` at zero
   specificity: without it every operate widget is dead, and with any specificity
   it would override a widget's own rule. Never re-enable with `* { auto !important }`
   on the subtree either: that overrides widget internals, such as a disabled
   widget's `none`.
4. **`pointer-events` leaves keyboard focus alone.** Tab still reaches an input
   inside a gated card and a key still edits it. The route is the refusal that
   counts (ADR 0055); the gate is a second layer against accidents that also
   covers the few writes still bypassing the route (fold toggle, annotation text
   edit, until 5b-4). It is not access control, and never test the gate alone as
   if it were the refusal. A readable element must not offer a write: `view`
   reaches it.
5. **The Vue default for `levelMode` is `view`, and the manager must push its mode
   at construction.** A canvas is built before any lock toggle, so without the push
   a locked `edit` principal's new stage canvas, or a canvas mounted after the lock
   was set, starts at the default and never hears the mode. `GraphCanvasManager`
   calls `set_level_mode` when it is built and from `refresh_mode()` thereafter.
   `view` as the default fails closed: a canvas that never hears a mode is inert,
   not editable.

Operable elements opt back in with `data-hw-operable`: `BaseSkin.render_widget`
stamps every operable card widget (the fold header is one). Readable ones carry `data-hw-readable`:
`add_pin_tooltip` stamps a pin that triggers its own tooltip (a separate trigger,
such as a widget, keeps its own rule), and the studio skin stamps its two badges.
`handleMouseDown` lets a press on either through below `edit` (operable only in
`operate`) without arming a drag or a selection; any other press on a card arms a
click that selects and drags nothing (selection works in every mode). A press on a
readable pin still starts no edge, since `_enterActiveEdge` refuses below `edit`.
