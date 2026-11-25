# Builtin

Framework-owned primitive types and adapters

## Nodes
### Annotation
- **Annotation** — A box of text for diagrams; links to other annotations with styled arrows

### Core
- **Error** — Placeholder for node that could not be loaded
- **Metadata** — Stamps fields on an image or bundle, and reads them back
- **Metadata Info** — Lists the fields an image or bundle carries
- **New Bundle** — Starts an empty bundle, for Metadata nodes to stamp values on

## Types
- **Add** — Grows a new port from whatever connects to it
- **Annotation** — A link between annotation nodes; carries no value
- **Boolean** — True or False
- **Bundle** — Several values travelling together as fields.
- **Callback Signal** — Signal for callback execution between nodes
- **Color** — Hex or rgba color string
- **Execution Signal** — Signal for controlling execution flow between nodes
- **File Path** — A file inside a named volume such as the project folder or `models`.
- **Float** — Decimal number
- **Folder Path** — A folder inside a named volume such as the project folder or `models`.
- **Integer** — Whole number
- **Matrix 3x3** — 3x3 matrix: a 2D transform, a homography, a camera matrix or a 3D rotation
- **Matrix 4x4** — 4x4 matrix: a 3D transform, a view or a projection
- **Optional** — A value of the wrapped type, or absence
- **Path** — A file or folder inside a named volume such as the project folder or `models`. The graph stores the volume and the path within it, so it keeps working on another machine.
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
- **FloatToStringAdapter** — Convert float to text
- **IntToFloatAdapter** — Convert integer to float
- **Mat3ToStringAdapter** — Convert a 3x3 matrix to text, one bracket per row
- **Mat4ToStringAdapter** — Convert a 4x4 matrix to text, one bracket per row
- **PathToStringAdapter** — Convert a path to text: the volume's name and the path inside it
- **StringToChoicesAdapter** — String into a choices slot
- **Vec2fToStringAdapter** — Convert a 2D float vector to text, (x, y)
- **Vec2iToStringAdapter** — Convert a 2D integer vector to text, (x, y)
- **Vec3fToStringAdapter** — Convert a 3D float vector to text, (x, y, z)
- **Vec3iToStringAdapter** — Convert a 3D integer vector to text, (x, y, z)
- **Vec4fToStringAdapter** — Convert a 4D float vector to text, (w, x, y, z)
- **Vec4iToStringAdapter** — Convert a 4D integer vector to text, (w, x, y, z)

## Widgets
- **AnnotationTextWidget** — Annotation text
- **ArrowHeadWidget** — Arrow head picker
- **ButtonWidget** — button widget
- **CheckboxWidget** — checkbox widget
- **ColorWidget** — Color picker widget
- **FieldListWidget** — List of fields, each a key and a type
- **FoldWidget** — Fold header
- **LabelWidget** — Label for display only
- **MatrixWidget** — Matrix editor widget, one number per cell
- **MenuWidget** — menu widget
- **NumberWidget** — Fast number input widget
- **OptionalWidget** — Optional value — the wrapped type's widget, plus an absence state
- **PathWidget** — Pick a file or folder inside a volume
- **ProgressWidget** — Progress bar
- **SliderWidget** — slider widget
- **TextWidget** — Fast text input widget
- **ToggleWidget** — toggle widget
- **VectorWidget** — Vector component editor widget

## Settings
- **arrange** — 
- **debug** — 
- **editor.pan_zoom** — 
- **farmhand.activity** — 
- **tools** — 
- **ui.canvas** — 
- **ui.debug_overlay** — 
- **ui.edge.default** — 
- **ui.minimap** — 
- **ui.node.default.skin** — 
- **undo** —
