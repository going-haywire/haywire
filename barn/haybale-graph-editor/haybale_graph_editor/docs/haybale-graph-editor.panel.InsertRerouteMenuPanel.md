# Insert Reroute

`haybale-graph-editor:panel:InsertRerouteMenuPanel` · kind: panel

## Details

- **surface**: `edge-menu`
- **order**: `20`

## Notes

Split the active edge and insert a reroute node in between.

Available for DATA and CONTROL edges only. CALLBACK edges are excluded
because the flow assembly manager reads the subscription key from the
reroute's outlet at wiring time — before any worker has run to forward
it — so the listener flow never registers correctly.
