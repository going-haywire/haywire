# haywire-core — component index (v0.1.3)

## node
- `haywire-core:node:ErrorNode` — Core Error Node — Placeholder for node that could not be loaded  _tags: error, system, placeholder_

## type
- `haywire-core:type:BOOL` — Boolean — True or False
- `haywire-core:type:CHOICES` — Choices — A string constrained to a set of options (options live per-use in widget_config)
- `haywire-core:type:COLOR` — Color — Hex or rgba color string
- `haywire-core:type:FLOAT` — Float — Decimal numberer
- `haywire-core:type:INT` — Integer — Whole number
- `haywire-core:type:STRING` — String — Text data
- `haywire-core:type:VEC2F` — Vec2f — 2D float vector
- `haywire-core:type:VEC2I` — Vec2i — 2D integer vector
- `haywire-core:type:VEC3F` — Vec3f — 3D float vector
- `haywire-core:type:VEC3I` — Vec3i — 3D integer vector
- `haywire-core:type:VEC4F` — Vec4f — 4D float vector
- `haywire-core:type:VEC4I` — Vec4i — 4D integer vector

## adapter
- `haywire-core:adapter:BoolToIntAdapter` — BoolToIntAdapter — Convert bool to integer
- `haywire-core:adapter:FloatToIntAdapter` — FloatToIntAdapter — Convert float to integer
- `haywire-core:adapter:FloatToStringAdapter` — FloatToStringAdapter — Convert float to integer
- `haywire-core:adapter:IntToFloatAdapter` — IntToFloatAdapter — Convert integer to float
- `haywire-core:adapter:StringToChoicesAdapter` — StringToChoicesAdapter — String into a choices slot

## widget
- `haywire-core:widget:CheckboxWidget` — CheckboxWidget — checkbox widget
- `haywire-core:widget:ColorWidget` — ColorWidget — Color picker widget
- `haywire-core:widget:NumberWidget` — NumberWidget — Fast number input widget
- `haywire-core:widget:SelectWidget` — SelectWidget — select widget
- `haywire-core:widget:SimpleLabelWidget` — SimpleLabelWidget — Simple label for display only
- `haywire-core:widget:SliderWidget` — SliderWidget — slider widget
- `haywire-core:widget:SwitchWidget` — SwitchWidget — switch widget
- `haywire-core:widget:TextWidget` — TextWidget — Fast text input widget
- `haywire-core:widget:VecWidget` — VecWidget — Vector component editor widget
