# The graph canvas never takes browser focus

**Symptom.** A keyboard shortcut meant for the graph editor goes to the wrong
editor, or to none: after clicking a node or the empty canvas,
`document.activeElement` is still `<body>` (or whatever text field held focus
before), so nothing in the DOM says which editor the user is working in.

**Cause.** The canvas gestures in `graph/canvas.vue` (node drag, marquee,
pan, edge drag) call `preventDefault()` on their `mousedown`. That is what
stops text selection and native drag during a gesture, and it also cancels the
browser's default focus move. A click on the canvas therefore never focuses
anything inside it, and adding `tabindex` to the canvas does not change that.

**What to do instead.** The target editor is tracked by pointer-down, not by
focus. `KeymapListener` (`haywire/ui/components/keymap/keymap_listener.vue`)
listens for `pointerdown` in the capture phase, walks up to the nearest
`[data-hw-binding]` editor root, remembers that binding and reports it to
Python as `hw-target`. Key presses resolve against that remembered root
(falling back to the first visible editor in the default slot). Capture phase
matters: a gesture handler that stops propagation still cannot hide the press
from the listener.

**Rules.**

- Never decide "which editor is in use" from `document.activeElement` or
  `:focus`. Use the remembered target (`SessionContext.target_binding_id` on
  the Python side).
- `activeElement` is still the right test for one narrower question: whether
  a native text control owns the key (the native-key selector
  `input, textarea, select, [contenteditable], .cm-editor, [data-hw-native-keys]`).
- A new editor gets keyboard commands by carrying `data-hw-binding` on its
  root, not by being focusable.
