# Graph Editor

`haybale-graph-editor:editor:GraphEditor` · kind: editor

Visual node graph editor for wiring data processing pipelines.

## Details

- **default_slot**: `edit`
- **opens**: `OpenBehavior.ON_PAYLOAD`
- **order**: `100`

## Notes

The graph canvas editor.

Wraps GraphCanvasManager inside a thin chrome that includes a header bar
with the open file name and a Save button.

Signals consumed:
    ``GraphDataMutated`` — sync canvas from another session.
    ``RevealGraphInstance`` — select a node/edge if this tab's graph matches.

Signals emitted:
    ``ActiveGraphMoved`` — on tab focus, via on_focus().
    ``SelectionMoved``   — node / edge selection.
    ``GraphDataMutated`` — graph structure changes.

The ``context.app`` object provided by haywire-app must expose:
    .skin_factory           (SkinFactory)
    .node_factory           (NodeFactory)
    .panel_registry         (PanelRegistry)
    .workspace_root         (str | Path)

Open graphs are read from ``app_data[GraphAppState]`` — a registry
populated by source libraries (haystack, future cloud-graph libs)
whose internal structure this editor does not know about.
