# Builtin

Framework-owned primitive types and adapters

## Nodes
### Core
- **Core Error Node** — Placeholder for node that could not be loaded

## Types
- **Boolean** — True or False
- **Choices** — A string constrained to a set of options (options live per-use in widget_config)
- **Color** — Hex or rgba color string
- **Float** — Decimal numberer
- **Integer** — Whole number
- **String** — Text data
- **Vec2f** — 2D float vector
- **Vec2i** — 2D integer vector
- **Vec3f** — 3D float vector
- **Vec3i** — 3D integer vector
- **Vec4f** — 4D float vector
- **Vec4i** — 4D integer vector

## Adapters
- **BoolToIntAdapter** — Convert bool to integer
- **FloatToIntAdapter** — Convert float to integer
- **FloatToStringAdapter** — Convert float to integer
- **IntToFloatAdapter** — Convert integer to float
- **StringToChoicesAdapter** — String into a choices slot

## Widgets
- **CheckboxWidget** — checkbox widget
- **ColorWidget** — Color picker widget
- **NumberWidget** — Fast number input widget
- **SelectWidget** — select widget
- **SimpleLabelWidget** — Simple label for display only
- **SliderWidget** — slider widget
- **SwitchWidget** — switch widget
- **TextWidget** — Fast text input widget
- **VecWidget** — Vector component editor widget
