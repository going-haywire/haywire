---
name: the-default-skins-live-in-the-graph-editor
description: The default node skins (NodeSkin, Stacked, Split, Error), their geometry settings and the Skin panel ship in haybale-graph-editor, the only library that draws node cards; a stored haybale-studio skin key renders the error card
status: accepted
see-also: ADR-0056
level: library
---

# The default skins live in the graph editor

**Context.**

- The default node skins (`NodeSkin` and its subclasses Stacked, Split and Error), `NodeSkinSettings` and the Skin settings panel shipped in haybale-studio. Only haybale-graph-editor draws node cards: it is the only user of `SkinFactory`.
- The Inset (editor modes slice 6) is a `NodeSkin` subclass that builds the graph editor's `UINode`s, so it has to live in haybale-graph-editor. haybale-graph-editor stays independent of haybale-studio.

**Decision.**

- **The family moves to haybale-graph-editor:** `NodeSkin`, `StackedNodeSkin` (the default skin), `SplitNodeSkin`, `ErrorNodeSkin`, `NodeSkinSettings` and `NodeSkinSettingsPanel`. Import them from `haybale_graph_editor.skins.*` and `haybale_graph_editor.settings.node_skin_settings`.
- **Keys change, namespaces do not.** The registry keys become `haybale-graph-editor:skin:*` and `haybale-graph-editor:panel:NodeSkinSettingsPanel`. `NodeSkinSettings` keeps the namespace `ui.node.skin`, so stored geometry values still apply. The registry picks the default and error skins by flag (`_is_default`, `_is_error`), so it needs no change.
- **No alias.** A stored `haybale-studio:skin:*` key (a node's `skin`/`stage_skin`, a graph default, `studio_skin`/`studio_stage_skin`) renders the error card, "Failed to use skin …", the framework's normal signal for a missing skin. Picking the skin again fixes it.
- **Direction of references.** haybale-graph-editor may import builtin types and surfaces (`haywire.barn.builtin`) like any library. Builtin references nothing outside core. `NodeDefaultSkinSettings` and its panel stay where they are: core and haybale-studio.

**Considered.**

- *Moving `NodeSkin` into core (`haywire.ui.skin`).* Core would grow by about 860 lines of card layout and a library settings bag that only the graph editor reads.
- *haybale-graph-editor depending on haybale-studio.* It breaks the graph editor's independence, which is what keeps it usable without the studio library.
- *An alias table from old to new keys.* It would be permanent special-case machinery for a one-off move. No tracked graph or settings file held an old key.

**Consequences.**

- haybale-graph-editor draws node cards without haybale-studio installed.
- A third-party skin that subclasses `NodeSkin` depends on haybale-graph-editor.
- A graph or settings file that names a `haybale-studio:skin:*` key shows error cards until the skin is picked again.
