# Haystack

Haystack — file-centric multi-graph manager for Haywire

## Settings
- **Haystack** — 

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
