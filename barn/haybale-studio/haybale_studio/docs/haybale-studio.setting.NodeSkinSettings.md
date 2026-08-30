# Node Skin

`haybale-studio:setting:NodeSkinSettings` · kind: setting

## Notes

Settings controlling node layout and pin geometry.

These settings are consumed directly by NodeSkin and its subclasses.

Every field here must be READ by rendering logic. This bag renders straight
into a settings panel, so an unread field is worse than a missing one: the
user toggles it and nothing happens, which reads as a broken feature rather
than an absent one. ``show_node_ids`` / ``show_port_ids`` sat unread from
introduction until they were deleted — under a docstring asserting the
opposite. ``test_node_skin_settings.py`` now checks this by grepping the
skins, so the claim cannot rot again.

**What is deliberately NOT here.** Element visibility left this bag in
ADR 0032: it is per node and per graph, not one studio-wide switch, and it
now resolves through ``NodeDetail`` (see ``haywire.ui.skin.visibility``).
``show_labels`` became the FULL rank; ``show_tooltips`` was deleted
outright, because lazy tooltips had already removed its performance
rationale and — with labels at FULL — a tooltip is the only thing
identifying a port at COMPACT and STANDARD. A toggle that can render an
unreadable node is not a preference worth keeping.
