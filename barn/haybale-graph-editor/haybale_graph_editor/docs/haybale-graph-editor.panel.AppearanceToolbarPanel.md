# Appearance

`haybale-graph-editor:panel:AppearanceToolbarPanel` · kind: panel

## Details

- **surface**: `toolbar`
- **hosts**: `['node-appearance']`
- **order**: `30`

## Notes

The ⧉ icon that drops the appearance fields below the toolbar.

Unlike its neighbours it *does* declare a ``poll``: ``SelectionToolbar``
gates on "something is selected", which an edges-only selection satisfies,
and there is nothing to style without a node.

It pipes, like every other hosting panel here — ``NodeAppearance``
declares no ``provides``, so the host travels on unexamined.
