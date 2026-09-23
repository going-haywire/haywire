# Macro

`haywire-core:node:MacroNode` · kind: node

A card standing for a macro: a Subgraph that lives in its own file.

## Notes

One placement of a macro template.

Differs from a Group's card in what owns the interior: a Group's Subgraph
lives in the host file and is the card's alone, while a macro's lives in
its own file and is shared by every placement as a template. The card still
owns its port values.
