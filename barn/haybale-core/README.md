# Core

<!-- marketstall:share-url:start -->
*Subscribe URL not yet published — run `haywire share --save`.*
<!-- marketstall:share-url:end -->

Fundamental components for haywire graphs

## Nodes
### Core
- **Begin Player** — Triggered once when execution starts
- **Control Switch** — Switches control flow based on condition
- **Create Folder** — Creates a folder inside a volume, including any folders above it
- **Float Number** — A number box that sends a decimal number, and shows the one it is fed
- **Float Slider** — A slider that sends a decimal number, and shows the one it is fed
- **For Each File** — Runs the loop body once for each file in a folder that matches the pattern
- **For Loop** — Iterate with start, end, and step control
- **Int Number** — A number box that sends a whole number, and shows the one it is fed
- **Int Slider** — A slider that sends a whole number, and shows the one it is fed
- **List Files** — Lists the files in a folder that match the pattern, each time it runs
- **Logger** — Log a message to the Python logging system at a configurable severity
- **Loop Array** — Runs the loop body once for each item of an array
- **Menu** — A drop-down that sends the item picked, and shows the item it is fed
- **Output Path** — Builds a file path from a folder, a subfolder, a stem and an extension
- **Path Exists?** — Continues on Exists or Missing, depending on whether a file or folder is there
- **Print** — Print to the haywire UI console
- **Resolve Path** — Gives the absolute location of a path on this machine, as text
- **Run Button** — A button on the card that triggers connected Tick Event flows while the graph runs
- **Shutdown** — Triggered when execution is shutting down
- **Split Path** — Splits a path into its volume, base, subfolder, stem and extension
- **Step Array** — Goes through an array one item at a time, each time Next runs
- **Text** — A text field that sends its text on Enter, and shows the text it is fed
- **Tick** — Triggered by a connected emitter (Tick Emit, Run Button)
- **Tick Emit** — Emits tick callbacks at a configurable framerate
- **Toggle** — An on/off switch that sends true or false, and shows the value it is fed

## Types
- **Array** — Homogeneous typed array
- **Bytes** — Binary data
- **Dictionary** — Key-value pairs
- **Drain** — Every value its edge delivers, queued until the node takes them
- **List** — Ordered collection
- **Pooled** — Multi-source aggregation

## Adapters
- **Array to Array** — Transform array elements (ArrayType[X] → ArrayType[Y])

## Widgets
- **ArrayWidget** — List editor — one row per item, each drawn by the item type's widget

## Skins
- **Widget Node** — The control alone, with the node label on its left — for widget nodes on a stage
