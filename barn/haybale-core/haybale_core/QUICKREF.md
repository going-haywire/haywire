# core — component index (v0.0.30)

## node
- `core:node:BeginPlayNode` — Begin Player — Triggered once when execution starts  _tags: start, init, begin, event_
- `core:node:ControlSwitch` — Control Switch — Switches control flow based on condition  _tags: switch, control, flow, event_
- `core:node:ForLoopNode` — For Loop — Iterate with start, end, and step control  _tags: loop, for, iterate, index, range_
- `core:node:LoggerNode` — Logger — Log a message to the Python logging system at a configurable severity  _tags: add, sub, math, vector_
- `core:node:PrintNode` — Print — Print to the haywire UI console  _tags: add, sub, math, vector_
- `core:node:ShutdownNode` — Shutdown — Triggered when execution is shutting down  _tags: stop, end, cleanup, event_
- `core:node:TickEmitNode` — Tick Emit — Emits tick callbacks at a configurable framerate  _tags: tick, frame, loop, emit, fps, timer_
- `core:node:TickEventNode` — Tick — Triggered periodically by a connected TickEmitNode  _tags: frame, update, loop, event, tick_

## type
- `core:type:ArrayType` — Array — Homogeneous typed array
- `core:type:BYTES` — Bytes — Binary data
- `core:type:CALLBACK` — Callback Signal — Signal for callback execution between nodes
- `core:type:DICT` — Dictionary — Key-value pairs
- `core:type:EXEC` — Execution Signal — Signal for controlling execution flow between nodes
- `core:type:GROUP` — Group — Inlet group
- `core:type:LIST` — List — Ordered collection
- `core:type:PooledType` — Pooled — Multi-source aggregation

## adapter
- `core:adapter:ArrayArrayAdapter` — Array to Array — Transform array elements (ArrayType[X] → ArrayType[Y])
