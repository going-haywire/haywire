# haybale-example — component index (v0.6.6)

## node
- `haybale-example:node:CallbackEmitNode` — Callback Emit — Emits a callback to trigger event nodes in other flows  _tags: callback, emit, trigger, event_
- `haybale-example:node:CallbackEventNode` — Callback Event — Listens for custom callbacks from other flows  _tags: callback, listen, event, custom_
- `haybale-example:node:FillDemoNode` — Fill Demo — Edits a solid/linear/radial fill and outputs it as a CSS value.  _tags: fill, gradient, colour, color, css, example_
- `haybale-example:node:MathOperationNode` — Math Operation — Applies the chosen operation (add, subtract, multiply, divide) to two float values.  _tags: math, value, single, basic, operation_  **DEPRECATED**
- `haybale-example:node:MergedCallbackEventNode` — Merged Callback Event — Listens for a specified number of callbacks from other flows  _tags: callback, listen, event, custom_
- `haybale-example:node:PathDemoNode` — Path Demo — Picks files and folders inside volumes and shows where they are on this machine.  _tags: path, file, folder, volume, picker, example_
- `haybale-example:node:ProgressDemoNode` — Progress Demo — Simulates slow work and shows its progress on the card: overall, per job, final stage.  _tags: progress, busy, bar, example_

## macro
- `haybale-example:macro:NewMacroGroup` — NewMacroGroup — TestMacroGroup to see how macros work

## type
- `haybale-example:type:FILL` — Fill — Solid colour or gradient background
- `haybale-example:type:MATH_OPERATION` — Math Operation — Simple mathematical operations for one or two float values
- `haybale-example:type:STRING_MAP` — String Map — Map with key type string
- `haybale-example:type:TEMPERATURE` — Temperature — Temperature data types

## adapter
- `haybale-example:adapter:MapsStringArrayAdapter` — MapsString to Array — Transform MapsString elements (STRING_MAP[str, X] → ARRAY[Y])

## widget
- `haybale-example:widget:FillWidget` — FillWidget — Background fill editor (solid / linear / radial)
- `haybale-example:widget:KnobWidget` — KnobWidget — knob widget
- `haybale-example:widget:TemperatureWidget` — TemperatureWidget — Temperature with unit conversion
- `haybale-example:widget:ValidatedNumberWidget` — ValidatedNumberWidget — Number widget with range clamping
