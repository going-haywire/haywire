# example — component index (v0.1.0)

## node
- `example:node:CustomCallbackNode` — Custom Callback — Listens for custom callbacks from other flows  _tags: callback, listen, event, custom_
- `example:node:EmitCallbackNode` — Emit Callback — Emits a callback to trigger event nodes in other flows  _tags: callback, emit, trigger, event_
- `example:node:MathOP` — Math Operation —   _tags: math, value, single, basic, operation_  **DEPRECATED**
- `example:node:MergeCallbackNode` — Merge Callback — Listens for a specified number of callbacks from other flows  _tags: callback, listen, event, custom_

## type
- `example:type:MapsStringType` — Array — Map with key type string
- `example:type:MathOPSelector` — Simple Operations — Simple mathematical operations for one or two float values
- `example:type:Temperature` — Temperature — Temperature data types

## adapter
- `example:adapter:MapsStringArrayAdapter` — MapsString to Array — Transform MapsString elements (MapsStringType[str, X] → ArrayType[Y])

## widget
- `example:widget:KnobWidget` — KnobWidget — knob widget
- `example:widget:TemperatureWidget` — TemperatureWidget — Temperature with unit conversion
- `example:widget:ValidatedNumberWidget` — ValidatedNumberWidget — Number widget with range clamping

## skin
- `example:skin:ExampleNodeSkin` — ExampleNodeSkin — Custom skin for nodes with special styling
