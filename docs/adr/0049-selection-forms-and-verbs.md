---
name: selection-forms-and-verbs
description: On the selection toolbar, a form needs a uniform selection and edits a neutral form for several elements; a verb acts on the subset it applies to
status: accepted
see-also: ADR-0029, ADR-0047
level: ui
---

# Selection forms and verbs

**Context.**

- The selection toolbar gained edges (an edge **Style** dropdown beside the node **Appearance** dropdown), so a selection can now hold nodes, edges, or both, and several elements of either kind.
- Miro answers a mixed selection with a filter that narrows it to one kind. That adds machinery: a filter control and a selection write.
- A settings form shows values. With several selected elements there is no one value to show without either picking an element the user cannot identify or rendering a per-field "mixed" state the settings widgets do not have.

**Decision.**

- **A form** (Appearance, Style) needs a uniform selection.
    - On a **cross-kind selection** (nodes and edges) it is hidden.
    - On a **non-uniform selection** (edges of different style classes or without a style; reroutes among nodes) it is greyed, and its tooltip gives the reason.
    - For one element it edits that element's own bag.
    - For two or more it edits a **neutral form**: a standalone bag of the shared class, opened with defaults, whose changes are written to every selected element and whose resets reset each one. For nodes the bag is attached to the graph, so graph-mirror fields show the graph's value, which is what a reset returns each node to. A header says how many elements it edits.
- **A verb** (Collapse, Copy, Delete) acts on the part of the selection it applies to, and its tooltip says how many.
- Each panel decides this in its own `poll` and `draw_disabled`; there is no filter. The properties inspector is not a selection surface and keeps editing the active element only.

**Considered options.**

- *A Miro-style filter.* Left out to keep the machinery small. It fits on top later: it only produces a uniform selection, which these rules then handle.
- *Show the active element's values in a multi-element form.* Rejected because the form would claim to be one element while editing all of them, and a marquee selection has no active element.
- *Per-field "mixed" markers.* Rejected for now: it needs a mixed state in every settings widget.

**Consequences.**

- Editing a setting in level mode `edit` is undoable: one step per edit, and an edit through the neutral form across many elements is one step (ADR 0055).
- Right-clicking an edge outside the selection now replaces the selection with that edge, as it already did for a node, so the edge menu's Style flyout always concerns that one edge.
- A toolbar icon (`hui.flyout` / `hui.dropdown`) at a host's top level counts as content once its body drew something, so a toolbar of hosting icons alone (an edge selection) still shows.
