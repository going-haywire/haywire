# The level-mode gate (ADR 0060): four traps

`AccessGate` (`haywire/ui/components/access_gate/`, shell-mounted) owns the gate CSS for
canvases and panels; `canvas.vue` owns none. Every element says what it needs with
`data-hw-requires="view|operate|edit"` (`stamp_requires`, derived from `required_mode`).

    canvas: [data-hw-level-mode] .ui-node-slot * : negative (unmarked = edit), pointer-events none !important
    panel : [data-hw-mode-scope="session"] [data-hw-requires=...] : positive, opacity 0.5 + none
    :where(<exempt roots of the mode>) { pointer-events: auto }

1. **Unmarked card content is `edit`.** A hand-made control on a card is dead below `edit`
   until stamped. Panels are the opposite: only stamped writers are gated.
2. **`!important` vs `.connection-pin`.** `.connection-pin` sets `pointer-events: all
   !important`; a pin that is not stamped `view` (a ghost pin) stays live without it.
3. **`pointer-events` inherits.** The gate sets `none` on an exempt root's ancestors; the
   exempt root gets `auto` back through a zero-specificity `:where()`. Never re-enable with
   `* { auto !important }`: it overrides a disabled widget's own `none`. Key on
   `.ui-node-slot *`, not `[data-node-id]` (pins carry it; the card root must keep input for
   a double-click Enter).
4. **CSS and `isGated` must agree.** `pointer-events` leaves keyboard focus alone, so a capture
   `focusin` listener blurs a gated target using `window.hwAccess.isGated`, and a
   MutationObserver blurs a focused card input when a mode drop gates it. The CSS exempts if
   ANY ancestor stamp is exempt, `isGated` reads the NEAREST: they differ only for a gated
   stamp nested inside an exempt one (none today). `test_css_and_isGated_agree` guards it;
   change one, change both.

Also: `canvas.vue`'s `levelMode` prop defaults to `view` and `gestureRequires` to `{}` (refuses
everything), so a manager must push both at construction. A canvas's gestures come from the server's handler table (`set_gesture_requires`,
`{event_type: mode}`); a canvas built without a manager must call it or every gesture is
refused, and an unknown type is a `console.error` and refused. `canvas.vue` names each gesture by its `GraphEvents.UserInteractions` constant, never a string literal (a test resolves them). A number widget briefly enters
its edit state on focus before the blur in `view` (nothing written). The gate is a second layer;
the edit route is the refusal that counts (ADR 0055).
