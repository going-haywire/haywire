# haybale-core — component index (v0.4.1)

## node
- `haybale-core:node:BeginPlayNode` — Begin Player — Triggered once when execution starts  _tags: start, init, begin, event_
- `haybale-core:node:ControlSwitch` — Control Switch — Switches control flow based on condition  _tags: switch, control, flow, event_
- `haybale-core:node:CreateFolderNode` — Create Folder — Creates a folder inside a volume, including any folders above it  _tags: folder, create, mkdir, directory, output, batch_
- `haybale-core:node:FloatNumberNode` — Float Number — A number box that sends a decimal number, and shows the one it is fed  _tags: float, number, value, widget, control, stage_
- `haybale-core:node:FloatSliderNode` — Float Slider — A slider that sends a decimal number, and shows the one it is fed  _tags: float, slider, widget, control, stage_
- `haybale-core:node:ForEachFileNode` — For Each File — Runs the loop body once for each file in a folder that matches the pattern  _tags: loop, for, each, file, folder, batch, iterate, glob_
- `haybale-core:node:ForLoopNode` — For Loop — Iterate with start, end, and step control  _tags: loop, for, iterate, index, range_
- `haybale-core:node:IntNumberNode` — Int Number — A number box that sends a whole number, and shows the one it is fed  _tags: int, integer, number, value, widget, control, stage_
- `haybale-core:node:IntSliderNode` — Int Slider — A slider that sends a whole number, and shows the one it is fed  _tags: int, integer, slider, widget, control, stage_
- `haybale-core:node:ListFilesNode` — List Files — Lists the files in a folder that match the pattern, each time it runs  _tags: list, files, folder, glob, batch, array, directory_
- `haybale-core:node:LoggerNode` — Logger — Log a message to the Python logging system at a configurable severity
- `haybale-core:node:LoopArrayNode` — Loop Array — Runs the loop body once for each item of an array  _tags: loop, for, each, array, list, items, iterate, batch_
- `haybale-core:node:MenuNode` — Menu — A drop-down that sends the item picked, and shows the item it is fed  _tags: menu, dropdown, select, choice, widget, control, stage_
- `haybale-core:node:OutputPathNode` — Output Path — Builds a file path from a folder, a subfolder, a stem and an extension  _tags: path, file, output, save, folder, name, stem, extension, batch_
- `haybale-core:node:PathExistsNode` — Path Exists? — Continues on Exists or Missing, depending on whether a file or folder is there  _tags: path, exists, missing, file, folder, skip, resume, branch_
- `haybale-core:node:PrintNode` — Print — Print to the haywire UI console
- `haybale-core:node:ResolvePathNode` — Resolve Path — Gives the absolute location of a path on this machine, as text  _tags: path, resolve, absolute, location, file, folder, volume_
- `haybale-core:node:RunButtonNode` — Run Button — A button on the card that triggers connected Tick Event flows while the graph runs  _tags: run, button, trigger, press, batch, emit_
- `haybale-core:node:ShutdownNode` — Shutdown — Triggered when execution is shutting down  _tags: stop, end, cleanup, event_
- `haybale-core:node:SplitPathNode` — Split Path — Splits a path into its volume, base, subfolder, stem and extension  _tags: path, split, folder, parent, name, stem, extension, volume, base_
- `haybale-core:node:StepArrayNode` — Step Array — Goes through an array one item at a time, each time Next runs  _tags: step, array, next, sequence, slideshow, playlist, iterate_
- `haybale-core:node:TextNode` — Text — A text field that sends its text on Enter, and shows the text it is fed  _tags: text, string, field, widget, control, stage_
- `haybale-core:node:TickEmitNode` — Tick Emit — Emits tick callbacks at a configurable framerate  _tags: tick, frame, loop, emit, fps, timer_
- `haybale-core:node:TickEventNode` — Tick — Triggered by a connected emitter (Tick Emit, Run Button)  _tags: frame, update, loop, event, tick_
- `haybale-core:node:ToggleNode` — Toggle — An on/off switch that sends true or false, and shows the value it is fed  _tags: toggle, switch, bool, boolean, widget, control, stage_

## type
- `haybale-core:type:ArrayType` — Array — Homogeneous typed array
- `haybale-core:type:BYTES` — Bytes — Binary data
- `haybale-core:type:DICT` — Dictionary — Key-value pairs
- `haybale-core:type:DRAIN` — Drain — Every value its edge delivers, queued until the node takes them
- `haybale-core:type:LIST` — List — Ordered collection
- `haybale-core:type:PooledType` — Pooled — Multi-source aggregation

## adapter
- `haybale-core:adapter:ArrayArrayAdapter` — Array to Array — Transform array elements (ArrayType[X] → ArrayType[Y])

## widget
- `haybale-core:widget:ArrayWidget` — ArrayWidget — List editor — one row per item, each drawn by the item type's widget

## skin
- `haybale-core:skin:WidgetNodeSkin` — Widget Node — The control alone, with the node label on its left — for widget nodes on a stage
