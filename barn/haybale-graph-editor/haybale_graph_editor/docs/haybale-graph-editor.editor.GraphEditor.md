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
with the open file name and a Save button, and a level bar listing the
Groups open inside this document.

Signals consumed:
    ``GraphDataMutated`` — sync canvas from another session.
    ``RevealGraphInstance`` — select a node/edge if one of this editor's
        levels holds that graph, opening the level if it is not open yet.
    ``SubgraphNavigation`` — open a Group of one of this editor's levels.

Signals emitted:
    ``ActiveGraphMoved`` — on tab focus and on level switch.
    ``SelectionMoved``   — node / edge selection.
    ``GraphDataMutated`` — graph structure changes.
    ``Reveal``           — this document's own tab, to bring it forward.

The ``context.app`` object provided by haywire-app must expose:
    .skin_factory           (SkinFactory)
    .node_factory           (NodeFactory)
    .panel_registry         (PanelRegistry)
    .workspace_root         (str | Path)

Open graphs are read from ``app_data[GraphAppState]`` — a registry
populated by source libraries (haystack, future cloud-graph libs)
whose internal structure this editor does not know about. The
``SubgraphContainer`` for a level never goes in there: it is this editor's
own, for as long as the level is open.
