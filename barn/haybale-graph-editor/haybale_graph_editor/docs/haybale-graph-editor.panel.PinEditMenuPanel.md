# Edit

`haybale-graph-editor:panel:PinEditMenuPanel` · kind: panel

## Details

- **surface**: `pin`
- **hosts**: `['pin-edit']`
- **order**: `10`

## Notes

The "Edit…" row — a submenu over the components behind this pin.

A hosting panel: it draws only the row and the flyout, and pipes the
``PortActions`` host one hop further to the rows inside. Mirrors
``DetailSelectionMenuPanel``, which does the same for the detail ranks.

**The rows inside must be their own panels, not inline ``hui.menu_row``
calls.** The leaf counter that decides whether a ``hui.submenu_row`` greys
itself is bumped by ``render_panel`` — once per panel — and by nothing
else; ``hui.menu_row`` does not touch it. Drawing the rows inline
therefore leaves the body's count at 0, and ``SubmenuRow.__exit__`` greys
the anchor retroactively: a fully populated flyout that cannot be opened
(``hw-disabled``, ``pointer-events: none``), with nothing in the DOM to
say why.
