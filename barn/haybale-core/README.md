# Core

<!-- marketstall:share-url:start -->
*Subscribe URL not yet published — run `haywire share --save`.*
<!-- marketstall:share-url:end -->

Haywire's core library with types, nodes, widgets, and renderers

## Nodes
### Core
- **Begin Player** — Triggered once when execution starts
- **Control Switch** — Switches control flow based on condition
- **For Loop** — Iterate with start, end, and step control
- **Logger** — Log a message to the Python logging system at a configurable severity
- **Print** — Print to the haywire UI console
- **Shutdown** — Triggered when execution is shutting down
- **Tick** — Triggered periodically by a connected TickEmitNode
- **Tick Emit** — Emits tick callbacks at a configurable framerate

## Types
- **Array** — Homogeneous typed array
- **Bytes** — Binary data
- **Callback Signal** — Signal for callback execution between nodes
- **Dictionary** — Key-value pairs
- **Execution Signal** — Signal for controlling execution flow between nodes
- **Group** — Inlet group
- **List** — Ordered collection
- **Pooled** — Multi-source aggregation

## Adapters
- **Array to Array** — Transform array elements (ArrayType[X] → ArrayType[Y])
