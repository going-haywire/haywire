# haybale-haystack — component index (v0.1.3)

## setting
- `haybale-haystack:setting:HaystackSettings` — Haystack — 

## farmhand
- `haybale-haystack:farmhand:close_graph` — Close graph — Close an open graph entry. NEVER deletes the file on disk.
- `haybale-haystack:farmhand:compile_graph` — Compile graph — Compile without starting; returns compile diagnostics.
- `haybale-haystack:farmhand:create_graph` — Create graph — Create a new untitled graph (appears in open browser sessions).
- `haybale-haystack:farmhand:list_graphs` — List graphs — Open haystack entries plus .haywire files on disk in the workspace.
- `haybale-haystack:farmhand:open_graph` — Open graph — Open a .haywire file (idempotent per path).
- `haybale-haystack:farmhand:rename_graph` — Rename graph — Rename an open graph's file on disk and rekey it.
- `haybale-haystack:farmhand:save_graph` — Save graph — Save an open graph; save_as writes to a new path.
- `haybale-haystack:farmhand:start_graph` — Start graph — Compile and start execution. Destructive: nodes perform real I/O.
- `haybale-haystack:farmhand:stop_graph` — Stop graph — Stop a running graph (bounded grace, then teardown).

## state
- `haybale-haystack:state:HaystackState` — Haystack State — 

## panel
- `haybale-haystack:panel:GraphRunSettingsPanel` — Run Settings — 
- `haybale-haystack:panel:OpenInHaystackMenuPanel` — Open in Haystack — 

## editor
- `haybale-haystack:editor:HaystackEditor` — Haystack — All open graphs. Click to switch; "+" to create a new graph.
