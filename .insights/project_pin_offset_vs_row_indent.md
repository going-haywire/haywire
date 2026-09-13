# A port row's indentation must not touch its pin column

A pin is placed by `render_pin` with a negative CSS offset:

    offset_px = card_padding + pin_gutter // 2 + pin_protrusion

`card_padding` is the padding on the axis the pin crosses — the skin picks it
(`node_skin.py:623`: `CARD_V_PADDING if layout.is_vertical else CARD_H_PADDING`).

That arithmetic assumes **the pin's row begins at the card edge**. Any
indentation applied to the row as a whole falsifies it, and the pin ends up
inset from the card border by exactly the indent — silently, because the edge
layer reads pin positions with `getBoundingClientRect()` and simply follows the
pin wherever it landed. Edges keep meeting their pins; the pins are just in the
wrong place.

`StackedNodeSkin._render_group` used to do this with `pl-2 ml-1`, so every grouped
port's pin sat ~12px inside the border, and nesting compounded it per level.

**The rule:** a port row is a two-column grid (`{PIN_GUTTER}px 1fr`). Depth
insets the CONTENT column — which holds both the label and the widget — and
never the pin column. `NodeSkin._content_inset(depth)` is the one place that
computes it; `_config_indent(depth)` is its pinless counterpart.

Symptom of getting it wrong: pins drift inward from the card border the deeper a
port is nested, while edges still connect correctly. `render_pin` is not the bug
— its precondition was broken upstream.
