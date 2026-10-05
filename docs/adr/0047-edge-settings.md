---
name: edge-settings
description: EdgeSettings is the fifth settings flavour; a wire type names one as its style bag, and each edge holds one while it validates
status: accepted
see-also: ADR-0022, ADR-0042, ADR-0045
level: architectural
---

# Edge settings: the style bag

**Context.**

- A diagram edge needs its colour, dash, width and heads set per edge (ADR 0045's styled edge).
- Settings came in four flavours. A graph's bag (ADR 0022) is the template for a bag owned by an object instead of registered.

**Decision.**

- **`EdgeSettings` is the fifth flavour.** Per-instance cells, an `_edge` back-reference, `_node` always `None`, so promotion is off. It is never registered.
- **A wire type names its bag** in `style`. The bag's field defaults are that wire type's look. A wire type without one draws computed edges.
- **Lifetime.**
    - `EdgeWrapper.build()` binds a bag of the wire type's class once the edge passes formal validation.
    - It drops the bag when the edge fails, keeping the values unchanged until the edge validates again.
    - A new class (a hot reload, a port retyped onto another wire type) takes the old values. Keys it does not declare are skipped and gone at the next save, as in node bags.
- **Saving.** The edge saves its locally set values flat under `"style"`. Every save path goes through `EdgeWrapper.serialize()`. Paste, Subgraph instantiation, collapse and expand carry `"style"` and `"propagation"`.
- **Editing.** A style change marks `EDGE_STYLE_CHANGED`: the edge redraws and the graph records an unsaved change. The edge menu and the Edge inspector render the bag with the shared settings renderer.
- **Drawing.**
    - A declared `color` and `dash` replace the pin gradient and the chain dash in the edge's stroke.
    - A declared `width`, `arrow_start` and `arrow_end` become inline vars on the edge's path and hit area.
    - An undeclared field falls back to the graph's edge defaults: per field, and per end for heads.
    - The invalid colour and the warning glow still win.

**Alternatives.**

- *Colour and dash as inline vars too.* The stroke fields already carry them, and the state policy already ranks the overlays above them.
- *Keeping the bag on an edge that fails validation.* Its wire type may be the wrong one; the values are kept as data until it validates.

**Consequences.**

- A library defines a styled wire with two classes: an `EdgeSettings` subclass and a wire type naming it.
- Style edits are not undoable, like node and graph settings edits.
- Splitting or dissolving a reroute on a styled edge does not carry its style.
- An edge that fails validation draws unstyled until it validates again.
