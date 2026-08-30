# haybale-example — component index (v0.1.3)

## node
- `haybale-example:node:CustomCallbackNode` — Custom Callback — Listens for custom callbacks from other flows  _tags: callback, listen, event, custom_
- `haybale-example:node:EmitCallbackNode` — Emit Callback — Emits a callback to trigger event nodes in other flows  _tags: callback, emit, trigger, event_
- `haybale-example:node:FillDemoNode` — Fill Demo —   _tags: fill, gradient, colour, color, css, example_
- `haybale-example:node:MathOP` — Math Operation —   _tags: math, value, single, basic, operation_  **DEPRECATED**
- `haybale-example:node:MergeCallbackNode` — Merge Callback — Listens for a specified number of callbacks from other flows  _tags: callback, listen, event, custom_

## type
- `haybale-example:type:FILL` — Fill — Solid colour or gradient background
- `haybale-example:type:MapsStringType` — Array — Map with key type string
- `haybale-example:type:MathOPSelector` — Simple Operations — Simple mathematical operations for one or two float values
- `haybale-example:type:Temperature` — Temperature — Temperature data types

## adapter
- `haybale-example:adapter:MapsStringArrayAdapter` — MapsString to Array — Transform MapsString elements (MapsStringType[str, X] → ArrayType[Y])

## widget
- `haybale-example:widget:FillWidget` — FillWidget — Background fill editor (solid / linear / radial)
- `haybale-example:widget:KnobWidget` — KnobWidget — knob widget
- `haybale-example:widget:TemperatureWidget` — TemperatureWidget — Temperature with unit conversion
- `haybale-example:widget:ValidatedNumberWidget` — ValidatedNumberWidget — Number widget with range clamping
