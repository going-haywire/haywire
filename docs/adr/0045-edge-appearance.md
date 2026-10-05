---
name: edge-appearance
description: Edges render through CSS custom properties; computed edges take an arrow head and width from framework < graph defaults at the end their wire type names; state colours are theme tokens; every edge end stops at its pin's edge; heads are context-stroke markers on a path shortened further by the head
status: accepted
see-also: ADR-0022, ADR-0030, ADR-0031, ADR-0042, ADR-0044
level: architectural
---

# Edge appearance

**Context.**

- An edge's look was fixed in code: width 2 sent by the server, selection and active widths 3 and 4, a hit area of 10, an invalid colour of `#EF4444`, and hard-coded fallbacks in the canvas. There were no arrow heads.
- Diagram edges (the annotation wire) need their colour, dash and heads set per edge.
- Execution edges carry information in their computed look: the pin gradient and the adapter-chain dash.

**Decision.**

- **Two kinds of edge.**
    - A **styled edge**'s wire type declares a style bag, and each edge sets the fields its bag declares.
    - A **computed edge**'s wire type declares none: data, control and callback edges. Their colour and dash stay computed, and their arrow head and width come from the **edge defaults**.
- **Edge defaults: framework < graph.**
    - The framework tier is `EdgeDefaultSettings` (`ui.edge.default`: `arrow`, `width`), a core schema.
    - The graph tier is the `GraphProperties` shadows `edge_arrow` and `edge_width` ("unset tracks, set ignores").
    - A Group interior uses its own graph props.
- **A wire type names the end of its computed head.** `WireType.arrow_at` is `INLET` by default; it can also be `OUTLET` or `NONE`. `CallbackWire` declares `OUTLET`, the listener the callback returns to. No role is checked.
- **Rendering runs on CSS custom properties.**
    - The canvas receives the graph values as props. It sets `--hw-edge-width`, `--hw-edge-head` and `--hw-edge-hit-padding` on its SVG.
    - One stylesheet rule set draws every edge.
    - A change is one write per canvas plus a client-side re-layout of its paths. There is no per-edge server work.
- **State colours are theme tokens:**

    | State | Token |
    |---|---|
    | invalid | `--hw-danger` |
    | warning glow | `--hw-warning` |
    | drop targets | `--hw-success` / `--hw-danger` |
    | selected glow | `--hw-edge-selected` |
    | active | `--hw-edge-active` |
    | a missing pin colour | `--hw-edge-default`, through `currentColor` |

- **Widths.** Selected and active widths add the optional tokens `--hw-edge-selected-extra` and `--hw-edge-active-extra` (1px, 2px). The hit area adds `CanvasSettings.edge_hit_padding`, an ergonomic studio setting rather than part of a theme.
- **Ends and heads.**
    - Every edge end stops at its pin's edge; a head adds its inset × width, so the head's tip touches the pin's edge and the line meets the head glyph's edge.
    - Fifteen heads form one vocabulary. One `context-stroke` marker per head serves both ends (`orient="auto-start-reverse"`), and heads scale with the width (`markerUnits="strokeWidth"`). Hollow heads are hollow.
    - `ArrowHeadWidget` picks a head: common arrows first, the rest behind "More".
- **Styled edges set the same vars inline** on their own path. A field their bag declares wins; one it does not declare falls through to the graph default.

**Alternatives.**

- *Colours as settings with a graph tier.* This duplicates the theme cascade, which already tiers colours.
- *Per-role defaults.* Six fields for a choice nobody asked for. They can be added without breaking anything.
- *A role check for callback heads.* A framework special case, where a fact on the wire type does the same.
- *One marker per colour.* This needs marker bookkeeping on every colour change, and `context-stroke` makes it unnecessary.
- *Masking hollow heads with the canvas background.* This hides the grid under a head.

**Consequences.**

- A graph can turn arrows on for all its execution edges.
- Themes restyle edge states live.
- No edge line runs under a pin glyph: every end stops at the pin's edge, so through a reroute dot the line stops at the dot's rim on both sides.
- 5.4 builds on the same vars: a styled edge sets them inline on its own path. The canvas code that reads the graph's width and head today (path insets, the hit area's width, the geometry check's choice of end) then needs per-edge inputs, and a start head and an end head need separate vars.
- Saved graphs carry `edge_arrow` and `edge_width` under `"props"` only when set.
