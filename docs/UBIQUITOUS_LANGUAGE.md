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
| **Interpreter** (updated) | A per-graph component that drives the VM; owns scheduling, event dispatch, and graph load/unload; each executing **GraphEntry** creates its own instance | Runner, shared interpreter (deprecated — no longer a singleton) |
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
| **FrameworkSettings** | Base class for framework/app-defined settings schemas; subclassed with `namespace=`; auto-registers via `_pending_global` at registry init; `cls._registry` is set by the registry so instances need no explicit injection | — |
| **LibrarySettings** | Base class for library plugin-defined settings schemas; subclassed with `namespace=`; registered via `BaseRegistry` hot-reload machinery; same `cls._registry` auto-wiring as `FrameworkSettings` | — |
| **setting()** | The descriptor that declares a typed, serializable field within any `Settings` subclass | option, param, prop |
| **mirrors** | A `setting()` parameter that links a node field to a `FrameworkSettings` or `LibrarySettings` field, inheriting its default with per-node override capability | shadow, reference |
| **read_only** | A `setting()` parameter (used with `mirrors=`) that makes a field a silent cache of a global value: invisible in panel, never stored, never writable per-instance | watch (avoid), computed |
| **accessor name** | The inner `NodeSettings` class name as it appears on the node instance (e.g. `class filter` → `self.filter`); must not collide with existing `BaseNode` attributes | settings name, bag name |
| **SettingsRegistry** | The central registry that holds all global setting schemas and their TOML-sourced values; used for the full resolution chain; inherits `BaseRegistry` hot-reload machinery | — |
| **Three-tier resolution** | The precedence chain for a settings value: global TOML override → workspace TOML override → local instance value → workspace TOML set → global TOML set → descriptor default | — |
| **cache** | Transient, non-serialized per-node storage for computation buffers or memoization | temp, scratch |
| **store** | Persistent, serialized per-node internal state not shown in the UI | private state |

---

## Graph Management

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **GraphEntry** | A runtime container for one open graph: holds the **Graph**, **Editor**, file path, unsaved flag, session set, and per-graph **Interpreter** | Graph slot, graph handle |
| **Haystack** | A named, curated selection of **GraphEntry**'s stored as a TOML file in `haystacks/`; records which graphs are open and which should auto-execute on load | Session (overloaded with browser sessions), workspace (overloaded with layout), setlist, graphset |
| **HaystackEditor** | The left-slot editor that lists all open graphs, provides play/stop per row, and save/load haystack actions in the header | GraphManagerEditor (renamed) |

---

## UI / Workspace System

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Editor** | A full-slot UI component occupying one workspace Slot (Left, Main, Right, Bottom); one instance per slot per session | Panel (Panels are sub-components of editors), view |
| **Panel** | A context-sensitive sub-section rendered inside a panel-aware editor (e.g. Properties); appears/disappears based on `poll()`; always wrapped in `.hw-panel` container | Tab, widget (too generic) |
| **Scope** | A named tab within a panel-aware editor that groups panels (e.g. `node`, `graph`, `edge`) | Context (overloaded), category |
| **Slot** (updated) | One of the four named positions in the AppShell where an editor is mounted: Left, Main, Right, Bottom; each slot = bar + area | Area (deprecated), pane, region, zone |
| **Bar** (new) | The control strip attached to a Slot; either a tab bar (horizontal, for Main/Bottom) or an icon bar (vertical, for Left/Right) | — |
| **default_slot** (updated) | The `@editor()` decorator parameter and `EditorIdentity` field that declares which Slot an editor occupies by default; one of `'left'`, `'main'`, `'right'`, `'bottom'` | canvas_area (deprecated) |
| **SlotState** (new) | Dataclass representing the persisted state of the Left or Right slot: `active_tab_key`, `visible`, `size` | AreaState (deprecated) |
| **MainSlotState** (new) | Dataclass representing the Main slot's persisted state: a list of `TabState` tabs plus `active_tab_key` | MiddleAreaState (deprecated) |
| **BottomSlotState** (new) | Dataclass representing the Bottom slot's persisted state: tab list, `active_tab_key`, `visible`, `size` | BottomAreaState (deprecated) |
| **TabState** | Dataclass for one tab within a tabbed slot (Main or Bottom): `editor_key`, `label`, `metadata` | — |
| **active_tab_key** (new) | The unified field on all slot state dataclasses that stores which editor is currently shown in that slot | editor_key (on slot state — deprecated), left_bar_active, right_bar_active (removed) |
| **reveal_editor** (new) | An optional field on `ContextChangedEvent`. When set to an editor's registry key, the AppShell switches the hosting slot to that editor as part of the same event dispatch. Replaces the removed `main_tabs`/`bottom_tabs` `metadata` shims. | main_tabs/bottom_tabs (removed) |
| **AppShell** (updated) | The top-level layout component composed of: TopBar + ActivityBar + Left/Main/Right/Bottom Slots + ContextBar + StatusBar | Shell, frame |
| **TopBar** | The 48px bar along the top edge of the AppShell; contains the app name, workspace switcher, and global actions | Header, navbar |
| **StatusBar** | The 24px bar along the bottom edge of the AppShell; shows session info and status messages | Footer, info bar (Info Bar is a Panel pattern, not the StatusBar) |
| **ActivityBar** | The 48px icon bar on the left edge; switches editors in the Left Slot; styled with `hw-slot-bar hw-slot-bar-icons` | Left sidebar, toolbar |
| **ContextBar** | The 48px icon bar on the right edge; switches editors in the Right Slot; styled with `hw-slot-bar hw-slot-bar-icons` | Right sidebar |
| **MainTabBar** (new) | The horizontal tab bar above the Main Slot; switches between tabbed main editors; styled with `hw-slot-bar hw-slot-bar-tabs` | Middle tabs |
| **BottomTabBar** (new) | The horizontal tab bar above the Bottom Slot; switches between tabbed bottom editors; styled with `hw-slot-bar hw-slot-bar-tabs` | Bottom tabs (use only for the metadata key) |
| **hw-slot-bar** (new) | CSS base class for all slot bars (both icon bars and tab bars) | hw-tabs (deprecated) |
| **hw-slot-bar-tabs** (new) | CSS modifier for horizontal tabbed slot bars (MainTabBar, BottomTabBar) | hw-tabs (deprecated) |
| **hw-slot-bar-icons** (new) | CSS modifier for vertical icon slot bars (ActivityBar, ContextBar) | — |
| **ScopeToolbar** | The vertical strip of 36×36px square buttons inside the PropertiesEditor that switches the active Scope | Scope bar, scope selector |
| **Session** | A per-browser-connection state object; one per connected client | Connection, client |
| **SessionContext** | The state bag passed to every editor and panel render call; contains active graph, node, edge, and theme references | Context (acceptable shorthand), state |
| **Workspace** | A named layout preset that records which editor occupies each slot; saved to `.haywire/workspace_state.json` | Layout, perspective |
| **Skin** | A `BaseSkin` subclass that renders the visual shape of a node on the Graph Canvas; operates outside the `.hw-panel` cascade and uses only `--hw-node-*` and `--hw-canvas-*` tokens | Renderer (Skin is canonical in code), style |
| **Widget** | An inline UI control rendered inside a port on the node card, bound to the port's value | Control, field input |
| **Theme** | A named set of CSS tokens (`WorkbenchTheme`) or per-node-type colour rules (`NodeTheme`); session-scoped for workbench | Style, skin (Skin is distinct) |
| **Graph Canvas** | The Vue/NiceGUI hybrid component where nodes and edges are visually displayed and edited | Canvas (acceptable shorthand), viewport |
| **hui** | The `haywire.ui.elements` wrapper module; encodes design-system rules into reusable Python functions; prefer `hui.*` over raw NiceGUI/Quasar calls for any pattern it covers | haywire.ui.elements (use `hui` as the import alias) |
| **CSS token** | A `--hw-*` CSS custom property that encodes a design-system value (colour, size, shadow); every structural colour in the app must reference a token, never a hardcoded value | CSS variable (CSS token is the project term) |
| **Compact-fields** | A container-query–based responsive layout system for dense settings/property panels; activated by the `compact-fields` CSS class on the outer column | Dense layout, settings layout |
| **Ghost pin** | The visual indicator (low-opacity colour via `--hw-ghost-pin`) on a port that is unconnected; rendered by node skins | Unconnected pin, empty pin |

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
- An **Editor** occupies one **Slot** in the **AppShell**; an **Editor** may host many **Panels** filtered by **Scope**.
- The **AppShell** is composed of: **TopBar**, **ActivityBar**, **ContextBar**, **StatusBar**, and the four **Slots** (Left, Main, Right, Bottom).
- Each **Slot** has a **Bar** and an area: Left and Right slots have icon bars (**ActivityBar**, **ContextBar**); Main and Bottom slots have tab bars (**MainTabBar**, **BottomTabBar**).
- The **ActivityBar** switches editors in the Left **Slot**; the **ContextBar** switches editors in the Right **Slot**; the **ScopeToolbar** (inside the PropertiesEditor) switches the active **Scope**.
- Each slot's state is tracked by a **SlotState** (Left/Right), **MainSlotState** (Main), or **BottomSlotState** (Bottom); all use **active_tab_key** to identify the currently-shown editor.
- A **Panel** is always rendered inside a `.hw-panel` container and must use `hui.*` wrappers for any pattern covered by the design guide.
- A **Skin** renders on the **Graph Canvas** and must use only `--hw-node-*` / `--hw-canvas-*` **CSS tokens**; it must not use `hui.*` panel wrappers.
- Every structural colour reference in the app must use a **CSS token** (`--hw-*`); hardcoded hex or rgba values are a design violation.
- A **Node** may declare one or more **NodeSettings** inner classes; each is accessible via its **accessor name** on the node instance.
- A **NodeSettings** field may `mirrors=` a **FrameworkSettings** or **LibrarySettings** field; the value resolves through the **SettingsRegistry** via **Three-tier resolution**.
- **FrameworkSettings** classes auto-register at registry init; **LibrarySettings** classes register via the **BaseRegistry** hot-reload path when their **Library** loads.
- A **GraphEntry** wraps exactly one **Graph**, one **Editor** and one **Interpreter** when it is executing; these are created/destroyed by `start_execution()` / `stop_execution()`.
- A **Haystack** references zero or more **GraphEntries** by relative file path; it also records which graph is active and which graphs should auto-execute on load.
- `workspace_state.json` stores the last-loaded **Haystack** name; on startup, **HaywireApp** auto-loads it if present.
- The **HaystackEditor** displays a **Haystack**'s entries and provides save/load **Haystack** actions and per-entry execution controls.

---

## Example Dialogue

> **Dev:** "I want to add a node that reads from a camera and fires a new frame event."
> **Domain expert:** "That's an **EVENT node** — it has an EXEC **outlet** but no EXEC **inlet**. It originates the **Flow**."
> **Dev:** "So the camera frames go out of a DATA **outlet** on the same node?"
> **Domain expert:** "Yes — the DATA **outlet** connects via an **Edge** to downstream **CONTROL nodes**. The **Pipe** on that **Edge** can be eager or lazy depending on whether you want immediate push or always-latest pull."
> **Dev:** "When I add this to a **Library**, how does it get discovered?"
> **Domain expert:** "Declare it in `register_components()` with `scan_nodes(...)`, and the **entry_point** in `pyproject.toml` makes the whole **Library** discoverable at startup."
> **Dev:** "And if the user is in the **Graph Canvas** and selects the node, what shows in the right **Slot**?"
> **Domain expert:** "The **Properties Editor** queries the **PanelRegistry** for all **Panels** whose `poll()` returns `True` for the `node` **Scope**. Each matching **Panel** renders inside a collapsible section. The **ContextBar** icon tells you which editor is active in the right **Slot**."

---

### Haystack dialogue

> **Dev:** "I want to save the set of graphs I'm working on so I can come back to it later."
> **Domain expert:** "Save a **Haystack** — it's a named TOML file in `haystacks/` that records which graphs are open. Use the save button in the **HaystackEditor** header."
> **Dev:** "What if one of my graphs is currently executing? Does the **Haystack** capture that?"
> **Domain expert:** "Yes — each graph entry in the **Haystack** has an `execute` flag. When you load the **Haystack** later, any graph marked `execute = true` will auto-start its **Interpreter**."
> **Dev:** "And unsaved graphs — do they go into the **Haystack**?"
> **Domain expert:** "No. A **Haystack** only stores paths to saved `.haywire` files. Unsaved **GraphEntries** (ones with no file path) are ephemeral — save the graph to disk first if you want it in a **Haystack**."
> **Dev:** "When I load a **Haystack**, what happens to the graphs I already have open?"
> **Domain expert:** "It's a full replace. If any current **GraphEntries** have unsaved changes, you'll get a confirmation dialog before they're discarded."

---

### Settings dialogue

> **Dev:** "I want my node to respect the library's default quality setting, but let users override it per-node."
> **Domain expert:** "Declare a **NodeSettings** inner class with a field that `mirrors=` the **LibrarySettings** field. The **accessor name** is whatever you call the inner class — `self.output`, say."
> **Dev:** "What if I just want to read a global flag silently, without showing it in the panel?"
> **Domain expert:** "Add `read_only=True` to the same `mirrors=` field. It becomes a silent cache — invisible in the panel, never stored, never writable per-instance. The value updates automatically when the **FrameworkSettings** source changes."
> **Dev:** "Where does the actual value come from when the node runs?"
> **Domain expert:** "**Three-tier resolution**: global TOML override wins, then workspace TOML override, then the node's local instance value, then workspace SET, then global SET, then the descriptor default. The **SettingsRegistry** owns that chain."
> **Dev:** "And the framework's own `ExecutionSettings` — does it need to be registered manually?"
> **Domain expert:** "No — **FrameworkSettings** subclasses self-register via `_pending_global` at registry init. **LibrarySettings** come in through the **BaseRegistry** hot-reload machinery when the **Library** loads."

---

## Flagged Ambiguities (updated 2026-04-13)

- **"pin"** appears in the codebase and docs as both the colloquial name for the icon port and a general synonym for any port. Canonical terms are **Inlet** / **Outlet**; **Pin** is acceptable only for EXEC ports.
- **"connection"** is used loosely to mean both the act of connecting (verb) and the edge itself (noun). Prefer **Edge** for the object, and **link** for the action.
- **"context"** is overloaded: `ExecutionContext` (passed to worker), `SessionContext` (UI state), and `context=` string in older panel decorators (now replaced by **Scope**). Always qualify: ExecutionContext, SessionContext, or Scope.
- **"flow"** appears as both the general concept (data flow, control flow) and the specific assembled object (`LocalizedDataFlow`, `Flow`). Capitalize **Flow** when referring to the assembled execution unit.
- **"NodeBehavior" vs "NodeType"**: `NodeType` is the enum (`DATA`, `CONTROL`, `EVENT`, `OUTPUT`, `LOOPBACK`); `NodeBehavior` is the dataclass that holds `node_type: NodeType` plus other flags. The glossary term **NodeType** is canonical for the execution role. "Node type" (lowercase) is used consistently in docs and code for this concept only.
- **"sidebar"** is overloaded: the CSS token prefix `--hw-sidebar-*` refers specifically to the **ActivityBar** and **ContextBar** (the narrow 48px icon strips). It does NOT refer to the Left or Right **Slots** (the wider editor panels). Always qualify: use **ActivityBar**, **ContextBar**, or **Slot** for structural names; "sidebar" only appears as a CSS token prefix.
- **"info bar"** appears in two distinct senses: `hui.info_bar()` is a Panel-level metadata bar pattern (§8.2 of the design guide); **StatusBar** is a shell-level bar at the bottom of the AppShell. They are different things — never use "info bar" to mean the StatusBar.
- **"panel"** in CSS token names (`--hw-panel-*`) refers to the `.hw-panel` editor container, not the **Panel** sub-component concept. The CSS token `--hw-panel-bg` is the background of the editor container, not a per-Panel background.
- **"area" vs "slot"**: As of 2026-04-12, **Slot** is the canonical term for workspace positions. **Area** and **canvas_area** are deprecated. The term "area" now refers only to the content region within a slot (the part next to the bar). Each slot = bar + area; use **Slot** for the whole position, "area" (lowercase, informal) only for the content pane if disambiguation is needed.
- **"middle" vs "main"**: The slot formerly called "middle" is now **Main**. Use `default_slot='main'` in code. "Middle" is deprecated and will cause deserialization failures in `workspace_state.json`.
- **"hw-tabs" vs "hw-slot-bar-tabs"**: The CSS class `hw-tabs` is deprecated. Use `hw-slot-bar` (base) + `hw-slot-bar-tabs` (horizontal tab bars) or `hw-slot-bar-icons` (vertical icon bars).
- **"session" vs "haystack"**: "Session" in Haywire means a per-browser-connection state object (**Session**, **SessionContext**). A named selection of graphs to work on is a **Haystack**, not a "session" — despite IDE conventions. Do not use "session" to mean a saved graph selection.
- **"interpreter"**: Each **GraphEntry** owns its own **Interpreter** instance. References to "the interpreter" should be qualified: "the graph's Interpreter" or "entry.interpreter". The app-level `self.interpreter` is removed.
