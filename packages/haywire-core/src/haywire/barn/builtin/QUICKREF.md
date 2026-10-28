# haywire-core — component index (v0.2.4)

## node
- `haywire-core:node:AnnotationNode` — Annotation — A box of text for diagrams; links to other annotations with styled arrows  _tags: note, comment, diagram, arrow, annotation_
- `haywire-core:node:ErrorNode` — Core Error Node — Placeholder for node that could not be loaded  _tags: error, system, placeholder_

## type
- `haywire-core:type:ADD` — Add — Grows a new port from whatever connects to it
- `haywire-core:type:ANNOTATION` — Annotation — A link between annotation nodes; carries no value
- `haywire-core:type:BOOL` — Boolean — True or False
- `haywire-core:type:CALLBACK` — Callback Signal — Signal for callback execution between nodes
- `haywire-core:type:CHOICES` — Choices — A string constrained to a set of options (options live per-use in widget_config)
- `haywire-core:type:COLOR` — Color — Hex or rgba color string
- `haywire-core:type:EXEC` — Execution Signal — Signal for controlling execution flow between nodes
- `haywire-core:type:FLOAT` — Float — Decimal number
- `haywire-core:type:FOLD` — Fold — Hides or shows the ports inside it
- `haywire-core:type:INT` — Integer — Whole number
- `haywire-core:type:OPTIONAL` — Optional — A value of the wrapped type, or absence
- `haywire-core:type:PROGRESS` — Progress — Whether a node is busy, how far it is, and what it is doing
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
- `haywire-core:widget:ArrowHeadWidget` — ArrowHeadWidget — Arrow head picker
- `haywire-core:widget:CheckboxWidget` — CheckboxWidget — checkbox widget
- `haywire-core:widget:ColorWidget` — ColorWidget — Color picker widget
- `haywire-core:widget:FoldWidget` — FoldWidget — Fold header
- `haywire-core:widget:NoteTextWidget` — NoteTextWidget — Note text
- `haywire-core:widget:NumberWidget` — NumberWidget — Fast number input widget
- `haywire-core:widget:OptionalWidget` — OptionalWidget — Optional value — the wrapped type's widget, plus an absence state
- `haywire-core:widget:ProgressWidget` — ProgressWidget — Progress bar
- `haywire-core:widget:SelectWidget` — SelectWidget — select widget
- `haywire-core:widget:SimpleLabelWidget` — SimpleLabelWidget — Simple label for display only
- `haywire-core:widget:SliderWidget` — SliderWidget — slider widget
- `haywire-core:widget:SwitchWidget` — SwitchWidget — switch widget
- `haywire-core:widget:TextWidget` — TextWidget — Fast text input widget
- `haywire-core:widget:VecWidget` — VecWidget — Vector component editor widget

## setting
- `haywire-core:setting:debug` — debug — 
- `haywire-core:setting:editor.pan_zoom` — editor.pan_zoom — 
- `haywire-core:setting:farmhand.activity` — farmhand.activity — 
- `haywire-core:setting:tools` — tools — 
- `haywire-core:setting:ui.canvas` — ui.canvas — 
- `haywire-core:setting:ui.debug_overlay` — ui.debug_overlay — 
- `haywire-core:setting:ui.edge.default` — ui.edge.default — 
- `haywire-core:setting:ui.minimap` — ui.minimap — 
- `haywire-core:setting:ui.node.default.skin` — ui.node.default.skin — 
- `haywire-core:setting:undo` — undo —
