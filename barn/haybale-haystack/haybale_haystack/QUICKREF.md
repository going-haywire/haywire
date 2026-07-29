# haystack — component index (v0.0.30)

## setting
- `haystack:setting:HaystackSettings` — Haystack — 

## farmhand
- `haystack:farmhand:close_graph` — Close graph — Close an open graph entry. NEVER deletes the file on disk.
- `haystack:farmhand:compile_graph` — Compile graph — Compile without starting; returns compile diagnostics.
- `haystack:farmhand:create_graph` — Create graph — Create a new untitled graph (appears in open browser sessions).
- `haystack:farmhand:list_graphs` — List graphs — Open haystack entries plus .haywire files on disk in the workspace.
- `haystack:farmhand:open_graph` — Open graph — Open a .haywire file (idempotent per path).
- `haystack:farmhand:rename_graph` — Rename graph — Rename an open graph's file on disk and rekey it.
- `haystack:farmhand:save_graph` — Save graph — Save an open graph; save_as writes to a new path.
- `haystack:farmhand:start_graph` — Start graph — Compile and start execution. Destructive: nodes perform real I/O.
- `haystack:farmhand:stop_graph` — Stop graph — Stop a running graph (bounded grace, then teardown).

## state
- `haystack:state:HaystackState` — Haystack State — 

## panel
- `haystack:panel:GraphRunSettingsPanel` — Run Settings — 
- `haystack:panel:OpenInHaystackMenuPanel` — Open in Haystack — 

## editor
- `haystack:editor:HaystackEditor` — Haystack — All open graphs. Click to switch; "+" to create a new graph.
