# Ubiquitous Language

*Domain glossary for the Haywire visual programming system. Use these terms precisely and consistently across all code, docs, and discussions.*

---

## Graph & Structure

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Graph** | A container of nodes and edges that describes a visual program; saved as a `.haywire` JSON file | Program, blueprint, scene, diagram |
| **Node** | A discrete processing unit in a graph with declared inlets, outlets, and a worker function | Block, component, element |
| **NodeWrapper** | The live runtime instance of a node inside a running graph; wraps the user-defined node class | Node instance (ambiguous — use NodeWrapper for the runtime object, Node for the class) |
| **Edge** | A directed connection between an outlet on one node and an inlet on another | Connection, wire, link (use only as a verb: "to link an edge") |
| **EdgeWrapper** | The runtime edge object that owns the `link/unlink/detach` lifecycle and the `is_lazy` flag | — |
| **Port** | A typed, directional connection point on a node — either an inlet or an outlet | Pin (avoid for data ports), socket |
| **Inlet** | A port that receives data or control into a node | Input, sink port |
| **Outlet** | A port that emits data or control from a node | Output, source port |
| **Pin** | Acceptable synonym for an EXEC (control) port specifically | — |

---

## Flow Types & Port Kinds

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **FlowType** | The transport category of a port/edge: `DATA`, `CONTROL` (EXEC), `CALLBACK`, or `NONE` | Port type (ambiguous with data type) |
| **DATA port** | A port that carries typed values; outlets fan-out, inlets accept a single source | Value port |
| **EXEC port** | A control port that carries execution order; outlets single-target, inlets multi-source | Control pin (Pin is acceptable colloquially) |
| **CALLBACK port** | A port used for event-style signalling; no hardcoded multiplicity rules | Event port (overloaded) |
| **Pooled inlet** | An inlet that accepts multiple sources and delivers them as a `dict[node_id, value]` to the worker | Multi-inlet |
| **Pipe** | The internal transport object for a connected DATA port pair; handles eager push or lazy pull | Channel, stream |

---

## Node Behaviors

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **NodeType** | The execution role of a node (the `NodeType` enum: DATA, CONTROL, EVENT, OUTPUT, LOOPBACK), determined by its EXEC port configuration. `NodeBehavior` is the dataclass that holds this field — prefer **NodeType** in conversation | Node category |
| **DATA node** | A pure value transformer; has no EXEC ports; runs only when its outputs are demanded | Passive node |
| **CONTROL node** | A sequenced node with both EXEC inlet and EXEC outlet; runs in explicit execution order | Active node |
| **EVENT node** | A node with an EXEC outlet but no EXEC inlet; originates an execution chain (timer, callback source) | Source node (ambiguous with data source) |
| **OUTPUT node** | A terminal node with an EXEC inlet but no EXEC outlet; receives execution, produces no further control | Sink node (ambiguous with data sink) |
| **LOOPBACK node** | A CONTROL node that uses the loopback-stack in the VM to implement loops or sequences | Loop node |

---

## Execution Pipeline

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Assembly** | The process of compiling a Graph into executable Flows; performed by `FlowAssemblyManager` | Compilation, build |
| **Flow** | An executable unit produced by assembly, rooted at an EVENT node; contains a control flow DAG + per-node data flows | Execution graph, pipeline |
| **Control Flow** | The ordered sequence of CONTROL/EVENT/OUTPUT nodes visited during execution; follows EXEC edges | Execution order |
| **LocalizedDataFlow** | The per-control-node data dependency DAG, backpropagated from that node's inlets; only the nodes needed for that step | Global data flow (does not exist) |
| **VM** | The two-stack virtual machine that interprets a Flow: a done-stack (prevents re-execution) + loopback-stack (loops) | Runtime (too generic), executor |
| **Interpreter** | The component that drives the VM; owns scheduling, event dispatch, and graph load/unload | Runner |
| **Worker** | The `worker()` method on a node class; the main execution logic called by the VM per node evaluation | Execute, run, process |
| **Frame** | One full execution pass through a Flow from its entry EVENT node to completion | Tick (reserved for the Tick node event), cycle |
| **Eager push** | Data transport mode where a Pipe immediately propagates a new value downstream on write | Synchronous push |
| **Lazy pull** | Data transport mode where a Pipe defers propagation; downstream calls `pull_lazy()` at execution time to get the latest value | Deferred, on-demand (imprecise) |
| **EVAL_MASK / LAZY_MASK** | Per-inlet / per-control-node bitmasks computed during assembly to determine which DATA nodes actually run each step | — |

---

## Edge Lifecycle

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **link** | EdgeWrapper operation: functional edge registers at both ports; may displace an existing edge | connect, attach |
| **unlink** | EdgeWrapper operation: edge loses functionality (e.g. adapter broke); removed from active pipes but stays registered | disconnect |
| **detach** | EdgeWrapper operation: edge is explicitly deleted and fully removed from both port dictionaries | destroy, remove |
| **displacement** | When a newly linked edge takes the slot of an existing edge on a single-connection port; the displaced edge stays in `_all_edges` | override, eviction |
| **re-enablement** | When an active edge is removed and the port scans `_all_edges` FIFO for a functional candidate to restore | fallback restoration |
| **Adapter** | A converter object that transforms values between incompatible DATA port types during transport | Converter (prefer Adapter), transformer |
| **Adapter chain** | An ordered pipeline of one or more Adapters that converts a source type to a compatible sink type | — |

---

## Library & Plugin System

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Library** | A Python package that contributes nodes, types, adapters, widgets, skins, and/or themes to Haywire; declared with `@library` | Plugin (Library is the canonical term), extension |
| **Haybale** | The naming convention for a Haywire library package (e.g. `haybale-core`, `haybale-visiongraph`) | — |
| **Barn** | The monorepo folder containing all local haybale plugin libraries (`barn/`) | Library folder |
| **register_components()** | The required method on `BaseLibrary` that scans subfolders and registers all library contributions | setup, initialize |
| **Hot-reload** | The live reload of a library's components on file change without restarting the app; enabled by `file_watcher=True` | Live reload, auto-reload |
| **entry_point** | The `pyproject.toml` declaration under `haywire.libraries` that makes a package discoverable | Registration |

---

## Settings System

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **NodeSettings** | Base class for node-local settings; subclassed as an inner class on a `@node` class; class name becomes the accessor (`self.filter`, `self.output`, etc.); never registered with the global registry | Config, options, Bag, Settings (avoid bare Settings for node inner classes) |
| **GlobalSettings** | Base class for framework/app-defined settings schemas; subclassed with `namespace=`; auto-registers via `_pending_global` at registry init; `cls._registry` is set by the registry so instances need no explicit injection | — |
| **LibrarySettings** | Base class for library plugin-defined settings schemas; subclassed with `namespace=`; registered via `BaseRegistry` hot-reload machinery; same `cls._registry` auto-wiring as `GlobalSettings` | — |
| **setting()** | The descriptor that declares a typed, serializable field within any `Settings` subclass | option, param, prop |
| **mirrors** | A `setting()` parameter that links a node field to a `GlobalSettings` or `LibrarySettings` field, inheriting its default with per-node override capability | shadow, reference |
| **read_only** | A `setting()` parameter (used with `mirrors=`) that makes a field a silent cache of a global value: invisible in panel, never stored, never writable per-instance | watch (avoid), computed |
| **accessor name** | The inner `NodeSettings` class name as it appears on the node instance (e.g. `class filter` → `self.filter`); must not collide with existing `BaseNode` attributes | settings name, bag name |
| **GlobalSettingsRegistry** | The central registry that holds all global setting schemas and their TOML-sourced values; used for the full resolution chain; inherits `BaseRegistry` hot-reload machinery | — |
| **Three-tier resolution** | The precedence chain for a settings value: global TOML override → workspace TOML override → local instance value → workspace TOML set → global TOML set → descriptor default | — |
| **cache** | Transient, non-serialized per-node storage for computation buffers or memoization | temp, scratch |
| **store** | Persistent, serialized per-node internal state not shown in the UI | private state |

---

## UI / Workspace System

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Editor** | A full-area UI component occupying one workspace area (Left, Middle, Right, Bottom); one instance per area per session | Panel (Panels are sub-components of editors), view |
| **Panel** | A context-sensitive sub-section rendered inside a panel-aware editor (e.g. Properties); appears/disappears based on `poll()` | Tab, widget (too generic) |
| **Scope** | A named tab within a panel-aware editor that groups panels (e.g. `node`, `graph`, `edge`) | Context (overloaded), category |
| **AppShell** | The top-level layout component: TopBar + ActivityBar + Left/Middle/Right/Bottom areas + ContextBar + StatusBar | Shell, frame |
| **Session** | A per-browser-connection state object; one per connected client | Connection, client |
| **SessionContext** | The state bag passed to every editor and panel render call; contains active graph, node, edge, and theme references | Context (acceptable shorthand), state |
| **Workspace** | A named layout preset that records which editor occupies each area; saved to `.haywire/workspaces.json` | Layout, perspective |
| **Skin** | A visual shape/renderer assigned per node type on the canvas; controls how the node card is drawn | Renderer (Skin is canonical in code), style |
| **Widget** | An inline UI control rendered inside a port on the node card, bound to the port's value | Control, field input |
| **Theme** | A named set of CSS tokens (`WorkbenchTheme`) or per-node-type colour rules (`NodeTheme`); session-scoped for workbench | Style, skin (Skin is distinct) |
| **Graph Canvas** | The Vue/NiceGUI hybrid component where nodes and edges are visually displayed and edited | Canvas (acceptable shorthand), viewport |

---

## Relationships

- A **Graph** contains zero or more **Nodes** and **Edges**; it is serialized as a `.haywire` file.
- An **Edge** connects exactly one **Outlet** to exactly one **Inlet**; they must share the same **FlowType** or can be cast to a different type with the help of an **Adapter chain**.
- A **Node** (class) defines **Ports** in `init()`; the **NodeWrapper** holds the live runtime state.
- Each connected DATA port pair owns exactly one **Pipe**; the Pipe's `is_lazy` flag comes from the **EdgeWrapper**, not the port.
- **Assembly** produces one **Flow** per **EVENT node** in the graph.
- A **Flow** contains one global **Control Flow** DAG and one **LocalizedDataFlow** DAG per CONTROL node.
- A **Library** scans folders in `register_components()` to populate registries (nodes, types, adapters, widgets, skins, themes).
- A **Haybale** package is always a **Library**; not all Libraries are distributed as haybale packages.
- An **Editor** occupies one workspace **Area**; an **Editor** may host many **Panels** filtered by **Scope**.
- A **Node** may declare one or more **NodeSettings** inner classes; each is accessible via its **accessor name** on the node instance.
- A **NodeSettings** field may `mirrors=` a **GlobalSettings** or **LibrarySettings** field; the value resolves through the **GlobalSettingsRegistry** via **Three-tier resolution**.
- **GlobalSettings** classes auto-register at registry init; **LibrarySettings** classes register via the **BaseRegistry** hot-reload path when their **Library** loads.

---

## Example Dialogue

> **Dev:** "I want to add a node that reads from a camera and fires a new frame event."
> **Domain expert:** "That's an **EVENT node** — it has an EXEC **outlet** but no EXEC **inlet**. It originates the **Flow**."
> **Dev:** "So the camera frames go out of a DATA **outlet** on the same node?"
> **Domain expert:** "Yes — the DATA **outlet** connects via an **Edge** to downstream **CONTROL nodes**. The **Pipe** on that **Edge** can be eager or lazy depending on whether you want immediate push or always-latest pull."
> **Dev:** "When I add this to a **Library**, how does it get discovered?"
> **Domain expert:** "Declare it in `register_components()` with `scan_nodes(...)`, and the **entry_point** in `pyproject.toml` makes the whole **Library** discoverable at startup."
> **Dev:** "And if the user is in the **Graph Canvas** and selects the node, what shows in the sidebar?"
> **Domain expert:** "The **Properties Editor** queries the **PanelRegistry** for all **Panels** whose `poll()` returns `True` for the `node` **Scope**. Each matching **Panel** renders inside a collapsible section."

---

### Settings dialogue (new)

> **Dev:** "I want my node to respect the library's default quality setting, but let users override it per-node."
> **Domain expert:** "Declare a **NodeSettings** inner class with a field that `mirrors=` the **LibrarySettings** field. The **accessor name** is whatever you call the inner class — `self.output`, say."
> **Dev:** "What if I just want to read a global flag silently, without showing it in the panel?"
> **Domain expert:** "Add `read_only=True` to the same `mirrors=` field. It becomes a silent cache — invisible in the panel, never stored, never writable per-instance. The value updates automatically when the **GlobalSettings** source changes."
> **Dev:** "Where does the actual value come from when the node runs?"
> **Domain expert:** "**Three-tier resolution**: global TOML override wins, then workspace TOML override, then the node's local instance value, then workspace SET, then global SET, then the descriptor default. The **GlobalSettingsRegistry** owns that chain."
> **Dev:** "And the framework's own `ExecutionSettings` — does it need to be registered manually?"
> **Domain expert:** "No — **GlobalSettings** subclasses self-register via `_pending_global` at registry init. **LibrarySettings** come in through the **BaseRegistry** hot-reload machinery when the **Library** loads."

---

## Flagged Ambiguities

- **"pin"** appears in the codebase and docs as both the colloquial name for the icon port and a general synonym for any port. Canonical terms are **Inlet** / **Outlet**; **Pin** is acceptable only for EXEC ports.
- **"connection"** is used loosely to mean both the act of connecting (verb) and the edge itself (noun). Prefer **Edge** for the object, and **link** for the action.
- **"context"** is overloaded: `ExecutionContext` (passed to worker), `SessionContext` (UI state), and `context=` string in older panel decorators (now replaced by **Scope**). Always qualify: ExecutionContext, SessionContext, or Scope.
- **"flow"** appears as both the general concept (data flow, control flow) and the specific assembled object (`LocalizedDataFlow`, `Flow`). Capitalize **Flow** when referring to the assembled execution unit.
- **"NodeBehavior" vs "NodeType"**: `NodeType` is the enum (`DATA`, `CONTROL`, `EVENT`, `OUTPUT`, `LOOPBACK`); `NodeBehavior` is the dataclass that holds `node_type: NodeType` plus other flags. The glossary term **NodeType** is canonical for the execution role. "Node type" (lowercase) is used consistently in docs and code for this concept only.
