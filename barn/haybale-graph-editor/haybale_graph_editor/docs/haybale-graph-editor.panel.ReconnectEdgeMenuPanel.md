# Reconnect Edge

`haybale-graph-editor:panel:ReconnectEdgeMenuPanel` · kind: panel

Removes the edge and starts a new connection drag from the anchor pin.

## Details

- **surface**: `edge-menu`
- **order**: `200`

## Notes

Removes the edge and starts a new connection drag from the anchor pin.

The provider's reconnect_active_edge action reads the active edge
and the gesture state (which end was right-clicked) from its own
_OpenMenuContext. The panel just invokes the verb. The row is greyed
when neither end of the edge has a pin to start the drag from.
