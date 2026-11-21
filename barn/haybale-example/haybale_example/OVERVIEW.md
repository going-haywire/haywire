# Example

Example library for demonstrating multi-library support

## Nodes
### Examples
- **Callback Emit** — Emits a callback to trigger event nodes in other flows
- **Callback Event** — Listens for custom callbacks from other flows
- **Fill Demo** — Edits a solid/linear/radial fill and outputs it as a CSS value.
- **Math Operation** — Applies the chosen operation (add, subtract, multiply, divide) to two float values.
- **Merged Callback Event** — Listens for a specified number of callbacks from other flows
- **Path Demo** — Picks files and folders inside volumes and shows where they are on this machine.
- **Progress Demo** — Simulates slow work and shows its progress on the card: overall, per job, final stage.

## Macros
- **NewMacroGroup** — TestMacroGroup to see how macros work

## Types
- **Fill** — Solid colour or gradient background
- **Math Operation** — Simple mathematical operations for one or two float values
- **String Map** — Map with key type string
- **Temperature** — Temperature data types

## Adapters
- **MapsString to Array** — Transform MapsString elements (STRING_MAP[str, X] → ARRAY[Y])

## Widgets
- **FillWidget** — Background fill editor (solid / linear / radial)
- **KnobWidget** — knob widget
- **TemperatureWidget** — Temperature with unit conversion
- **ValidatedNumberWidget** — Number widget with range clamping
