# Builtin

Framework-owned primitive types and adapters

## Nodes
### Annotation
- **Annotation** — A box of text for diagrams; links to other annotations with styled arrows

### Core
- **Core Error Node** — Placeholder for node that could not be loaded
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
- **File path** — A file inside a named volume such as the project folder or `models`.
- **Float** — Decimal number
- **Folder path** — A folder inside a named volume such as the project folder or `models`.
- **Integer** — Whole number
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
- **FloatToStringAdapter** — Convert float to integer
- **IntToFloatAdapter** — Convert integer to float
- **PathToStringAdapter** — Convert a path to text: the volume's name and the path inside it
- **StringToChoicesAdapter** — String into a choices slot

## Widgets
- **ArrowHeadWidget** — Arrow head picker
- **ButtonWidget** — button widget
- **CheckboxWidget** — checkbox widget
- **ColorWidget** — Color picker widget
- **FieldListWidget** — List of fields, each a key and a type
- **FoldWidget** — Fold header
- **NoteTextWidget** — Note text
- **NumberWidget** — Fast number input widget
- **OptionalWidget** — Optional value — the wrapped type's widget, plus an absence state
- **PathWidget** — Pick a file or folder inside a volume
- **ProgressWidget** — Progress bar
- **SelectWidget** — select widget
- **SimpleLabelWidget** — Simple label for display only
- **SliderWidget** — slider widget
- **SwitchWidget** — switch widget
- **TextWidget** — Fast text input widget
- **VecWidget** — Vector component editor widget

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
