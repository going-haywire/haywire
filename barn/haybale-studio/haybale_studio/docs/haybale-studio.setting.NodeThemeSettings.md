# Node Theme

`haybale-studio:setting:NodeThemeSettings` · kind: setting

## Notes

Global settings controlling the active node theme.

Shadows the framework's ``studio_node_theme``, which is what the graph and
node tiers mirror in turn — so this one setting is the top of the chain
``framework < graph < node``. It used to be a free STRING defaulting to
"default", resolved against nothing; a value picked here changed no pixel.
