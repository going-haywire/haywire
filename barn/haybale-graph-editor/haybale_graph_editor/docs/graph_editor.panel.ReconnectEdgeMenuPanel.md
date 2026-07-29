# Reconnect Edge

`graph_editor:panel:ReconnectEdgeMenuPanel` · kind: panel

## Details

- **order**: `10`

## Notes

Removes the edge and starts a new connection drag from the anchor pin.

The provider's reconnect_active_edge action reads the active edge
and the gesture state (which end was right-clicked) from its own
_OpenMenuContext. The panel just invokes the verb.
