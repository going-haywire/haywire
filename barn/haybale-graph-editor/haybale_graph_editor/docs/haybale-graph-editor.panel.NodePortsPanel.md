# Ports

`haybale-graph-editor:panel:NodePortsPanel` · kind: panel

## Details

- **surface**: `ports`
- **order**: `20`

## Notes

Displays the inlet, outlet, and config ports of the selected node.

Widget lifecycle note: PropertiesEditor builds a fresh panel instance on
every redraw (``panel_cls().draw(...)`` after ``content.clear()``), so the
panel cannot own widget cleanup via instance state. Instead each rendered
widget's container element carries its own teardown (see
``_anchor_cleanup_to_element``), which NiceGUI fires on both redraw
(``content.clear()``) and page close (``client.remove_all_elements``).
