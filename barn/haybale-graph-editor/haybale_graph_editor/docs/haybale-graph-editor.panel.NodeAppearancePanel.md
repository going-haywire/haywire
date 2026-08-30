# Node Appearance

`haybale-graph-editor:panel:NodeAppearancePanel` · kind: panel

## Details

- **surface**: `node-appearance`
- **order**: `10`

## Notes

The appearance slice of the active node's props bag, live-editable.

Scoped to the primary (active) node, like ``NodeErrorsSelectionMenuPanel``:
``EditState.active_node`` is the selection's primary, so a multi-node
selection styles the one that was right-clicked rather than silently
editing several bags.

The ``hw-panel`` wrapper is load-bearing. A dropdown is a ``QMenu`` and
portals to ``<body>``, outside the toolbar popup's own ``hw-panel``, so
without it every ``.hw-panel``-scoped field rule in the shell CSS misses
these rows — the same portal trap that gave menus three different colours.
