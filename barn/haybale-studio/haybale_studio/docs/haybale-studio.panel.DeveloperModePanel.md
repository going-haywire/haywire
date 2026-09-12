# Developer mode

`haybale-studio:panel:DeveloperModePanel` · kind: panel

## Details

- **surface**: `account`
- **order**: `50`

## Notes

Toggles ``ctx.developer_mode`` for THIS session.

Developer mode reveals affordances that expose the studio's own
implementation rather than the user's graph — a settings row's "open this
bag's source" entry, for one. It belongs on the account menu rather than
the Debug settings tab because it is session state, not a stored setting:
every panel on ``DebugSurface`` renders a persisted registry value through
``render_schema``, so a switch that vanishes on restart would be the one
control there a user reasonably expects to stick.

VIEW rather than EDIT: the flag only decides whether an affordance is
drawn, never whether it may be used. Opening a component's source still
goes through the editor's own access check, and ComponentSourceEditor
refuses to write a non-editable library regardless — so gating the toggle
higher would hide a read-only view from the principals most likely to want
it, and buy no safety.

The row does not close the menu, so the checkmark is the only feedback a
click gives and it has to move under the pointer. The menu is rebuilt on
every open (see BaseContextMenuProvider._open_menu), but that only fixes
the state on the NEXT open — the row already on screen is a drawn element
nothing redraws, so the icon is swapped in place here. Same pattern, and
the same defensive child lookup, as SelectionCollapsePanel's expand/
collapse row in haybale-graph-editor.
