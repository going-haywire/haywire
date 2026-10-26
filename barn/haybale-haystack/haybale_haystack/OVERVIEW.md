# Haystack

File-centric multi-graph manager

## Settings
- **Haystack** — Per-workspace settings for haystack scalars.

## Farmhands
- **Close graph** — Close an open graph entry. NEVER deletes the file on disk.
- **Compile graph** — Compile without starting; returns compile diagnostics.
- **Create graph** — Create a new untitled graph (appears in open browser sessions).
- **List graphs** — Open haystack entries plus .haywire files on disk in the workspace.
- **Open graph** — Open a .haywire file (idempotent per path).
- **Rename graph** — Rename an open graph's file on disk and rekey it.
- **Save graph** — Save an open graph; save_as writes to a new path.
- **Start graph** — Compile and start execution. Destructive: nodes perform real I/O.
- **Stop graph** — Stop a running graph (bounded grace, then teardown).

## States
- **Haystack State** — In-memory registry of open graphs, one entry per file path.

## Panels
- **Edit Macro** — Open the document behind a macro placement, in its own editor tab.
- **Graph Settings** — Renders the GraphRunSettings for the currently active graph.
- **Load into Haystack** — Load a .haywire graph file into the Haystack (does not open an editor tab).
- **Update Macro** — Send a modified instance's changes back to the macro it came from.

## Editors
- **Haystack** — All open graphs. Click to switch; "+" to create a new graph.
