# haywire-core — component index (v0.4.2)

## node
- `haywire-core:node:AnnotationNode` — Annotation — A box of text for diagrams; links to other annotations with styled arrows  _tags: note, comment, diagram, arrow, annotation_
- `haywire-core:node:ErrorNode` — Core Error Node — Placeholder for node that could not be loaded  _tags: error, system, placeholder_
- `haywire-core:node:MetadataInfoNode` — Metadata Info — Lists the fields an image or bundle carries  _tags: metadata, info, field, carrier, icc, exif_
- `haywire-core:node:MetadataNode` — Metadata — Stamps fields on an image or bundle, and reads them back  _tags: metadata, field, stamp, read, carrier, bundle_
- `haywire-core:node:NewBundleNode` — New Bundle — Starts an empty bundle, for Metadata nodes to stamp values on  _tags: bundle, metadata, new, carrier_

## type
- `haywire-core:type:ADD` — Add — Grows a new port from whatever connects to it
- `haywire-core:type:ANNOTATION` — Annotation — A link between annotation nodes; carries no value
- `haywire-core:type:BOOL` — Boolean — True or False
- `haywire-core:type:BUNDLE` — Bundle — Several values travelling together as fields.
- `haywire-core:type:CALLBACK` — Callback Signal — Signal for callback execution between nodes
- `haywire-core:type:COLOR` — Color — Hex or rgba color string
- `haywire-core:type:EXEC` — Execution Signal — Signal for controlling execution flow between nodes
- `haywire-core:type:FILE_PATH` — File path — A file inside a named volume such as the project folder or `models`.
- `haywire-core:type:FLOAT` — Float — Decimal number
- `haywire-core:type:FOLDER_PATH` — Folder path — A folder inside a named volume such as the project folder or `models`.
- `haywire-core:type:INT` — Integer — Whole number
- `haywire-core:type:MAT3` — Matrix 3x3 — 3x3 matrix: a 2D transform, a homography, a camera matrix or a 3D rotation
- `haywire-core:type:MAT4` — Matrix 4x4 — 4x4 matrix: a 3D transform, a view or a projection
- `haywire-core:type:OPTIONAL` — Optional — A value of the wrapped type, or absence
- `haywire-core:type:PATH` — Path — A file or folder inside a named volume such as the project folder or `models`. The graph stores the volume and the path within it, so it keeps working on another machine.
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
- `haywire-core:adapter:PathToStringAdapter` — PathToStringAdapter — Convert a path to text: the volume's name and the path inside it
- `haywire-core:adapter:StringToChoicesAdapter` — StringToChoicesAdapter — String into a choices slot

## widget
- `haywire-core:widget:ArrowHeadWidget` — ArrowHeadWidget — Arrow head picker
- `haywire-core:widget:ButtonWidget` — ButtonWidget — button widget
- `haywire-core:widget:CheckboxWidget` — CheckboxWidget — checkbox widget
- `haywire-core:widget:ColorWidget` — ColorWidget — Color picker widget
- `haywire-core:widget:FieldListWidget` — FieldListWidget — List of fields, each a key and a type
- `haywire-core:widget:FoldWidget` — FoldWidget — Fold header
- `haywire-core:widget:MatrixWidget` — MatrixWidget — Matrix editor widget, one number per cell
- `haywire-core:widget:NoteTextWidget` — NoteTextWidget — Note text
- `haywire-core:widget:NumberWidget` — NumberWidget — Fast number input widget
- `haywire-core:widget:OptionalWidget` — OptionalWidget — Optional value — the wrapped type's widget, plus an absence state
- `haywire-core:widget:PathWidget` — PathWidget — Pick a file or folder inside a volume
- `haywire-core:widget:ProgressWidget` — ProgressWidget — Progress bar
- `haywire-core:widget:SelectWidget` — SelectWidget — select widget
- `haywire-core:widget:SimpleLabelWidget` — SimpleLabelWidget — Simple label for display only
- `haywire-core:widget:SliderWidget` — SliderWidget — slider widget
- `haywire-core:widget:SwitchWidget` — SwitchWidget — switch widget
- `haywire-core:widget:TextWidget` — TextWidget — Fast text input widget
- `haywire-core:widget:VecWidget` — VecWidget — Vector component editor widget

## setting
- `haywire-core:setting:arrange` — arrange — 
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
