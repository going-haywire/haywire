# Tick Emit

`haybale-core:node:TickEmitNode` · kind: node

Emits tick callbacks at a configurable framerate

## Ports

| id | direction | type | description |
|---|---|---|---|
| start | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| stop | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| target_fps | inlet | haywire-core:type:FLOAT | Targeted Frames per second - needs a start signal to be applied |
| callback_names | inlet | haybale-core:type:PooledType | Multi-source aggregation |
| started | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| stopped | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Emits tick callbacks at a configurable framerate from an internal thread.

Wire from BeginPlayNode to start ticking. Connect TickEventNodes via
the callback inlet to receive ticks.

Inputs:
    start: Begin emitting ticks
    stop: Stop emitting ticks
    target_fps: Target frames per second (default 60)
    callback_names: Callback edge inlet for connected TickEventNodes

Outputs:
    started: Control flow after tick thread starts
    stopped: Control flow after tick thread stops
