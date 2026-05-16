# haybale-graph-editor

Visual graph editor library for Haywire. Provides:

- `GraphContainer` (Protocol) — what a graph-source library must implement
- `GraphAppState` (AppState) — shared registry of open graph containers, keyed by `binding_id`
- `GraphEditor` (BaseEditor) — the canvas-hosting editor surface

Source libraries (e.g. `haybale-haystack`) register containers; this library renders them.
