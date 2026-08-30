# Haystack

`haybale-haystack:editor:HaystackEditor` · kind: editor

All open graphs. Click to switch; "+" to create a new graph.

## Details

- **default_slot**: `action`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `20`

## Notes

Left-area editor that lists all graphs tracked by Haystack.

One entry per open file or new unnamed graph.  Clicking an entry fires
EDITOR_FOCUSED with reveal_editor=GraphEditor and reveal_payload=entry.binding_id.
The shell reveals the matching tab, then GraphEditor.on_focus updates
context.data[EditState].active_graph / active_graph_path and emits ``ActiveGraphMoved``.

- Click a row to make that graph active in the GraphEditor
- Click the "+" button in the header to create a new unnamed graph
- Save / load haystacks (named graph selections) via the header
- Start / stop per-graph execution via play/stop buttons on each row
- Save / Save-As / Rename / Delete graphs via per-row overflow menu
