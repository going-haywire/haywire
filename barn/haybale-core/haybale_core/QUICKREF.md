# haybale-core — component index (v0.2.4)

## node
- `haybale-core:node:BeginPlayNode` — Begin Player — Triggered once when execution starts  _tags: start, init, begin, event_
- `haybale-core:node:ControlSwitch` — Control Switch — Switches control flow based on condition  _tags: switch, control, flow, event_
- `haybale-core:node:FloatNumberNode` — Float Number — A number box that sends a decimal number, and shows the one it is fed  _tags: float, number, value, widget, control, stage_
- `haybale-core:node:FloatSliderNode` — Float Slider — A slider that sends a decimal number, and shows the one it is fed  _tags: float, slider, widget, control, stage_
- `haybale-core:node:ForLoopNode` — For Loop — Iterate with start, end, and step control  _tags: loop, for, iterate, index, range_
- `haybale-core:node:IntNumberNode` — Int Number — A number box that sends a whole number, and shows the one it is fed  _tags: int, integer, number, value, widget, control, stage_
- `haybale-core:node:IntSliderNode` — Int Slider — A slider that sends a whole number, and shows the one it is fed  _tags: int, integer, slider, widget, control, stage_
- `haybale-core:node:LoggerNode` — Logger — Log a message to the Python logging system at a configurable severity
- `haybale-core:node:MenuNode` — Menu — A drop-down that sends the item picked, and shows the item it is fed  _tags: menu, dropdown, select, choice, widget, control, stage_
- `haybale-core:node:PrintNode` — Print — Print to the haywire UI console
- `haybale-core:node:ShutdownNode` — Shutdown — Triggered when execution is shutting down  _tags: stop, end, cleanup, event_
- `haybale-core:node:TextNode` — Text — A text field that sends its text on Enter, and shows the text it is fed  _tags: text, string, field, widget, control, stage_
- `haybale-core:node:TickEmitNode` — Tick Emit — Emits tick callbacks at a configurable framerate  _tags: tick, frame, loop, emit, fps, timer_
- `haybale-core:node:TickEventNode` — Tick — Triggered periodically by a connected TickEmitNode  _tags: frame, update, loop, event, tick_
- `haybale-core:node:ToggleNode` — Toggle — An on/off switch that sends true or false, and shows the value it is fed  _tags: toggle, switch, bool, boolean, widget, control, stage_

## type
- `haybale-core:type:ArrayType` — Array — Homogeneous typed array
- `haybale-core:type:BYTES` — Bytes — Binary data
- `haybale-core:type:DICT` — Dictionary — Key-value pairs
- `haybale-core:type:LIST` — List — Ordered collection
- `haybale-core:type:PooledType` — Pooled — Multi-source aggregation

## adapter
- `haybale-core:adapter:ArrayArrayAdapter` — Array to Array — Transform array elements (ArrayType[X] → ArrayType[Y])

## widget
- `haybale-core:widget:ArrayWidget` — ArrayWidget — List editor — one row per item, each drawn by the item type's widget

## skin
- `haybale-core:skin:WidgetNodeSkin` — Widget Node — The control alone, with the node label on its left — for widget nodes on a stage
