---
name: Graph canvas connection system
description: Click-click connection model, edge reconnect, auto-wire, ghost pins, pause/resume, context menu pipeline for canvas.vue
type: project
---

## Status: FULLY IMPLEMENTED on branch `code_refactoring` (updated 2026-04-08)

## canvas.vue edge drag refactor (2026-04-08)

The `edgeState` object and its handlers were heavily renamed and restructured:

- `edgeState` → `edgeDrag` with `mode: 'idle' | 'active' | 'paused'` replacing three booleans
- Three transition functions own all visual side-effects: `_enterActive`, `_enterPaused`, `_returnToIdle`
- `_commitConnection` replaced `_commitOrCancelEdgeDrag`
- `SyncCancelEdgeDragEvent` added (Python→Vue): cancels active drag from Python side
- Emitted from `_try_auto_wire` in `visual_layer.py` after successful auto-wire
- Removed: `_startEdgeDrag`, `_startEdgeDragFromPin`, `_initEdgeDrag`, `_suspendEdgeDrag`, `_resumeEdgeDrag`, `_cancelEdgeDrag`, `_handleEdgeDragEnd` (old names)
- Renames applied: `anchorPin`, `previewPath`, `suggestionPaths`, `nearestCompatiblePin`, `_clearSuggestions`
- `lastMousePos: {x, y}` field added — needed so `_syncPlayPendingConnection` can resume drag at correct position after context menu closes (server event has no mouse coords)

## Click-click connection model

Two modes for creating edges (both supported simultaneously):
- **Click-drag**: mousedown on pin → hold → drag → release on target pin
- **Click-click**: mousedown on pin → release quickly (moved < 8px) → free mouse → click target pin to commit

`mode: 'active'` with `isClickMode: true` in `edgeDrag` = free-floating mode. The `moved < 8` threshold enters click-click.

## edgeDrag fields (canvas.vue, post-2026-04-08 refactor)

- `mode` — `'idle' | 'active' | 'paused'`
- `isClickMode` — click-click free-floating sub-mode (within `mode: 'active'`)
- `startPin` — the DOM pin element drag started from
- `anchorPin` — the pin element the drag is anchored to during reconnect
- `previewPath` — the live SVG bezier path following the mouse
- `suggestionPaths` — proximity-snapping suggestion paths
- `nearestCompatiblePin` — closest valid target pin
- `lastMousePos` — last known screen mouse pos (updated in `handleMouseMove`)

## Pausing a drag for context menus

When user right-clicks canvas while dragging: `_pauseEdgeDrag()` freezes the curve in place (does NOT destroy drag state). On context menu close, `SyncPlayPendingConnectionEvent` (Python→Vue) resumes drag via `_syncPlayPendingConnection()`.

`_on_close` in `SessionContextMenuProvider` checks if `pending_connection` is still in metadata — if yes, no node was created, so emits `SyncPlayPendingConnectionEvent` via `on_emit_sync_event` callback.

## Pending connection metadata

When right-clicking canvas with a pending drag, `handleContextMenu` snapshots pin data before pausing:
```
context.metadata["pending_connection"] = {
    "pin_id": ..., "node_id": ..., "pin_dir": ...,
    "flow_type": ..., "data_type": ...
}
```
`_try_auto_wire` in `VisualLayerHandlers` reads and pops this after node creation.

## Auto-wire on node create

`_try_auto_wire(wrapper)` in `visual_layer.py`:
1. Pops `pending_connection` from metadata
2. Matches typed ports by direction, flow type, data type
3. If exactly one match: auto-wire to that port
4. Otherwise: fall back to ghost pin (`root_in` or `root_out`) — creates an unlinked edge attached to ghost pin

## Ghost pins

Every node has two invisible ghost pins: `root_in` (inlet) and `root_out` (outlet).
- `data-pin-flow-type="ghost"` — excluded from compatibility checks
- `_isValidEdge` in canvas.vue bypasses flow-type check if either pin is ghost
- Used as fallback when no typed port matches during auto-wire

**Critical**: `data-pin-flow-type` must use `pin.flow_type.value` (e.g. `'data'`), NOT `str(pin.flow_type)` (which gives `'FlowType.DATA'`). Fixed in `node_skin.py`.

## Edge reconnect

`ReconnectEdgePanel` in `barn/haybale-core/haybale_core/panels/context_menu/edge_actions.py`:
- Polls when `active_edge is not None` (scope: `edge`)
- Uses `edge_reconnect_end` metadata (bool: True = clicked near inlet, anchor is outlet)
- Emits `SyncStartReconnectEvent(edge_id, anchorNodeId, anchorPinId)` via `on_emit_event`
- `process_start_reconnect` in visual_layer: pops edge from `edge_paths`, calls `cleanup()`, emits sync to Vue, removes from graph

## Key events

Python→Vue (sync):
- `SyncStartReconnectEvent` — remove edge, start drag from anchor pin
- `SyncPlayPendingConnectionEvent` — resume paused drag (no fields; canvas uses `lastMousePos`)
- `SyncCancelEdgeDragEvent` — cancel active drag (emitted after successful auto-wire in `_try_auto_wire`)

Vue→Python (user):
- `ContextMenuCanvasEvent` — includes `pendingPinId/NodeId/Dir/FlowType/DataType` fields (empty when no pending drag)
- `ContextMenuEdgeEvent` — includes `atSinkEnd: bool`
- `ContextMenuPortEvent` — includes `nodeId`, `portId`, `scope`

## SessionContextMenuProvider wiring

Constructor now takes:
- `on_emit_event` — for user events going through Python handler dispatch
- `on_emit_sync_event` — for sync events going directly to Vue (`canvas_vue.emit_sync_event`)

## Key files

- `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` — all JS logic
- `packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js` — generated constants (manually maintained alongside event_definitions.py)
- `packages/haywire-core/src/haywire/ui/graph_canvas/event_definitions.py` — Python event dataclasses
- `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py` — IContextMenuProvider, SessionContextMenuProvider
- `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/visual_layer.py` — _try_auto_wire, process_start_reconnect
- `barn/haybale-core/haybale_core/panels/context_menu/edge_actions.py` — ReconnectEdgePanel
- `barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py` — CreateNodePanel (canvas scope)
