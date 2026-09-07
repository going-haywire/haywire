# Detach from setting

`haybale-graph-editor:panel:DetachSettingMenuPanel` · kind: panel

## Details

- **surface**: `pin`
- **order**: `30`

## Notes

Enabled only on a promoted inlet; demotes it back to a plain setting.

On any other pin it greys rather than disappearing — the platform
convention every panel on ``SelectionMenu`` already follows, and here it
is also load-bearing. This is ``PinMenu``'s only **leaf**: the "Edit" row
beside it is a hosting panel, and a hosting panel is deliberately
excluded from the popup's leaf count (ADR-0029, and the leaf counter is
reset per flyout level, so what the submenu body draws never reaches the
popup's own count). Were this panel to vanish on an unpromoted pin, the
popup would render with zero leaves and be deleted — **no pin menu at
all**, on the great majority of pins, taking the edge-drag resume that
rides on its close with it. ``draw_disabled`` is what keeps the count at
one. See ``.insights/project_surface_popup_emptiness_contract.md``.
