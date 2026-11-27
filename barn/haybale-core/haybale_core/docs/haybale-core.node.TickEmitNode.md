# Tick Emit

`haybale-core:node:TickEmitNode` · kind: node

Emits tick callbacks at a configurable framerate

## Ports

| id | direction | type | description |
|---|---|---|---|
| `start` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `target_fps` | inlet | `haywire-core:type:FLOAT` | Targeted Frames per second - needs a start signal to be applied |
| `callback_names` | inlet | `haybale-core:type:POOLED` | Multi-source aggregation |
| `started` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `size` | backlog | `16` | How many events wait while every pooled listener is busy. |
| `full` | backlog | `'Drop oldest'` | Drop oldest makes room by losing the oldest waiting event. Wait holds the emitter up to 5 s for room, then loses the new event. |

## Notes

Emits tick callbacks at a configurable framerate from an internal thread.

Wire from BeginPlayEventNode to start ticking. Connect TickEventNodes via
the callback inlet to receive ticks.

Inputs:
    start: Begin emitting ticks
    stop: Stop emitting ticks
    target_fps: Target frames per second (default 60)
    callback_names: Callback edge inlet for connected TickEventNodes

Outputs:
    started: Control flow after tick thread starts
    stopped: Control flow after tick thread stops

Tick Events set to Pooled share the ticks: the next free one runs each tick, and
Backlog Size ticks wait while all are busy (When Full decides the rest).
