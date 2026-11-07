# A canvas pin's DOM attributes carry its wire key

`render_pin` (`packages/haywire-core/src/haywire/ui/skin/pin_render.py`) writes `data-pin-wire="{pin.wire_key or ''}"`: the wire type's id, or `*` for a bare ADD slot. Ghost pins carry `data-pin-ghost`.

A pin's CSS side and its `data-pin-dir-x/y` vector must both come from `LayoutDirection`; see [project_layout_direction_pin_contract.md](project_layout_direction_pin_contract.md). The skin-authoring side is in `docs/components/skins/skin-canon.md`.
