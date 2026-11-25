---
name: A Quasar field moves every attribute but class and style off its root
description: Props written on a ui.select / ui.input root (data-* markers, stamps) land on an inner element, so a CSS rule or closest() that expects them on the root silently misses; only class and style stay on the root.
type: feedback
---

# A Quasar field moves every attribute but `class` and `style` off its root

`ui.select`, `ui.input`, `ui.number`, `ui.textarea` and the other `QField`-based
components render a `label.q-field` root. NiceGUI's wrapper (`select.js`) lets every prop
fall through to the Quasar component, and Quasar's `useSplitAttrs` then keeps only
`class` and `style` for the root: **every other attribute goes to the inner native
element** (`div.q-field__native`, or the `<input>` with `use-input`).

So `element.props["data-x"] = "1"` on a select root ends up on `.q-field__native`.
Nothing warns. Measured in Chromium on a chip select root (2026-11-25): the root
carried `class` and `style` only; `data-hw-widget-inline-box`, `data-hw-requires` and
the port's `data-hw-tip*` were all on `.q-field__native`.

Consequences:

- A CSS rule that needs a class **and** an attribute on the same element
  (`.widget-container[data-...]`) never matches. This is why the size-box markers
  (`haywire/ui/widget/sizing.py`) are classes.
- A `closest('[data-...]')` lookup from an event target finds the stamp only when
  the target is inside `.q-field__native`. A press on the field's other parts
  (label, append icons such as the dropdown arrow, the control's padding) misses it.

**How to apply:** anything that must sit on a widget's root element is a class or a
style (custom property). When an attribute is unavoidable, put it on a plain
element around the field, or check where it lands in a browser test: a Python test
of `element.props` passes either way.
