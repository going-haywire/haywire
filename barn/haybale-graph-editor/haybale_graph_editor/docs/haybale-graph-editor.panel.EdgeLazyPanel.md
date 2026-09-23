# Propagation

`haybale-graph-editor:panel:EdgeLazyPanel` · kind: panel

## Details

- **surface**: `edge`
- **order**: `10`

## Notes

Switch the active edge between eager and lazy propagation.

Writes ``EdgeWrapper.is_lazy`` directly, like ``EdgeStatsPanel`` and
``EdgePathPanel`` read it — ``EdgeInspector`` declares no ``provides``, so
its panels have no action host to route the write through.
