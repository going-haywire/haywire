# builtin — component index (v0.0.0)

## node
- `builtin:node:ErrorNode` — Core Error Node — Placeholder for node that could not be loaded  _tags: error, system, placeholder_

## type
- `builtin:type:BOOL` — Boolean — True or False
- `builtin:type:CHOICES` — Choices — A string constrained to a set of options (options live per-use in widget_config)
- `builtin:type:COLOR` — Color — Hex or rgba color string
- `builtin:type:FLOAT` — Float — Decimal numberer
- `builtin:type:INT` — Integer — Whole number
- `builtin:type:STRING` — String — Text data
- `builtin:type:VEC2F` — Vec2f — 2D float vector
- `builtin:type:VEC2I` — Vec2i — 2D integer vector
- `builtin:type:VEC3F` — Vec3f — 3D float vector
- `builtin:type:VEC3I` — Vec3i — 3D integer vector
- `builtin:type:VEC4F` — Vec4f — 4D float vector
- `builtin:type:VEC4I` — Vec4i — 4D integer vector

## adapter
- `builtin:adapter:BoolToIntAdapter` — BoolToIntAdapter — Convert bool to integer
- `builtin:adapter:FloatToIntAdapter` — FloatToIntAdapter — Convert float to integer
- `builtin:adapter:FloatToStringAdapter` — FloatToStringAdapter — Convert float to integer
- `builtin:adapter:IntToFloatAdapter` — IntToFloatAdapter — Convert integer to float
- `builtin:adapter:StringToChoicesAdapter` — StringToChoicesAdapter — String into a choices slot

## widget
- `builtin:widget:CheckboxWidget` — CheckboxWidget — checkbox widget
- `builtin:widget:ColorWidget` — ColorWidget — Color picker widget
- `builtin:widget:NumberWidget` — NumberWidget — Fast number input widget
- `builtin:widget:SelectWidget` — SelectWidget — select widget
- `builtin:widget:SimpleLabelWidget` — SimpleLabelWidget — Simple label for display only
- `builtin:widget:SliderWidget` — SliderWidget — slider widget
- `builtin:widget:SwitchWidget` — SwitchWidget — switch widget
- `builtin:widget:TextWidget` — TextWidget — Fast text input widget
- `builtin:widget:VecWidget` — VecWidget — Vector component editor widget
