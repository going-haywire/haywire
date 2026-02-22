# Haywire Node System - Specification v1.0.0

## Table of Contents

- [Haywire Node System - Specification v1.0.0](#haywire-node-system---specification-v100)
  - [Table of Contents](#table-of-contents)
  - [Credits \& License](#credits--license)
- [Overview](#overview)
    - [Key Differentiators](#key-differentiators)
    - [Related Projects](#related-projects)
- [Graph Structure](#graph-structure)
  - [The Graph as Container](#the-graph-as-container)
    - [The Graph](#the-graph)
    - [Variables](#variables)
    - [Validation Pipeline](#validation-pipeline)
  - [The Graph-node](#the-graph-node)
  - [Connection Types](#connection-types)
    - [On Connections, Edges, Hooks and Pipes](#on-connections-edges-hooks-and-pipes)
    - [Edges](#edges)
    - [Control-edges -\> Hooks](#control-edges---hooks)
    - [Data-edges -\> Pipes](#data-edges---pipes)
    - [Cycles](#cycles)
- [Node Architecture](#node-architecture)
  - [Node Types](#node-types)
    - [The node](#the-node)
    - [Control Nodes](#control-nodes)
    - [Data Nodes](#data-nodes)
    - [Event Nodes](#event-nodes)
    - [Output Nodes](#output-nodes)
    - [Graph Nodes](#graph-nodes)
    - [Source-node](#source-node)
    - [Sink-node](#sink-node)
    - [Loopback-node\*\* Flag](#loopback-node-flag)
  - [Node Components](#node-components)
    - [Ports: Inlets \& Outlets \& Pins](#ports-inlets--outlets--pins)
      - [Pins](#pins)
      - [Explanation to connection-types](#explanation-to-connection-types)
      - [Control Inlets](#control-inlets)
      - [Control Outlets](#control-outlets)
      - [Data Inlets](#data-inlets)
      - [Data Outlets](#data-outlets)
      - [Overview of Nodes Configurables](#overview-of-nodes-configurables)
    - [Worker Function](#worker-function)
    - [Data Types and Categories](#data-types-and-categories)
    - [Support Functions](#support-functions)
      - [ON\_CHANGED\_CONFIG:](#on_changed_config)
      - [ON\_VALIDATION\_LAZY:](#on_validation_lazy)
      - [ON\_CHANGED\_ASYNC:](#on_changed_async)
      - [ON\_VALIDATION\_INPUT:](#on_validation_input)
- [Advanced Features](#advanced-features)
  - [Lazy Evaluation](#lazy-evaluation)
  - [Callback System](#callback-system)
- [Flow](#flow)
  - [Overview](#overview-1)
  - [From Graph to Flow](#from-graph-to-flow)
  - [The Dual-Flow Model](#the-dual-flow-model)
    - [Control Flow](#control-flow)
    - [(localized) Data Flow](#localized-data-flow)
- [Generation](#generation)
  - [Finding and Loading available Node Libraries](#finding-and-loading-available-node-libraries)
  - [Loading Graphs from JSON and instantiating required Nodes](#loading-graphs-from-json-and-instantiating-required-nodes)
- [Assembly](#assembly)
  - [Overview](#overview-2)
  - [Assembly Steps](#assembly-steps)
    - [Graph Validation](#graph-validation)
    - [Graph Cleaning](#graph-cleaning)
    - [Graph Preprocessing](#graph-preprocessing)
    - [Flow identification](#flow-identification)
    - [Flow assembly](#flow-assembly)
    - [Just-In-Time Assembly](#just-in-time-assembly)
  - [Just-In-Time Assembly (For a future implementation)](#just-in-time-assembly-for-a-future-implementation)
- [Execution](#execution)
  - [The Virtual Machine](#the-virtual-machine)
    - [Virtual Machine Architecture](#virtual-machine-architecture)
      - [Execution Context Management](#execution-context-management)
      - [Control Flow Translation](#control-flow-translation)
      - [Data Flow Translation](#data-flow-translation)
      - [State Preservation:](#state-preservation)
  - [Flow Execution](#flow-execution)
    - [Control Flow Execution](#control-flow-execution)
    - [Worker function execution/evaluation](#worker-function-executionevaluation)
      - [for Control-nodes](#for-control-nodes)
      - [for Data-nodes](#for-data-nodes)
- [Interpreter](#interpreter)
- [Outstanding Design Questions](#outstanding-design-questions)
  - [For Author Clarification](#for-author-clarification)
  - [Suggested Enhancements](#suggested-enhancements)
- [Appendix](#appendix)
  - [Complete Edge Data Structure](#complete-edge-data-structure)
  - [Complete Port Serialization](#complete-port-serialization)
    - [Complete Node Definition Template](#complete-node-definition-template)
    - [Complete Node Initialization Sequence](#complete-node-initialization-sequence)
  - [Complete Lazy Evaluation Algorithm](#complete-lazy-evaluation-algorithm)

---

## Credits & License

Created by Martin Fröhlich (aka maybites) © July 2025
Released under [CC-BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/4.0/)

# Overview

Haywire is a Blueprint-inspired visual programming system that combines **execution flow** with **data flow** to enable imperative-style programming within a visual graph interface. Unlike pure dataflow systems, Haywire uses explicit control connections to define execution order while maintaining data connections for value passing.

### Key Differentiators

- **Dual-flow architecture**: [Control pins](#pin-system) define execution order, [data pins](#pin-system) pass values
- **State machine execution**: Complex control flows with pause/resume capabilities managed by the [Haywire Virtual Machine](#the-virtual-machine)
- **Event-driven model**: Multiple independent execution chains triggered by [Event nodes](#node-types)
- **Just-in-time assembly**: Dynamic [flow compilation](#just-in-time-assembly) for performance

### Related Projects

- [Floppy](https://github.com/JLuebben/Floppy) (Python-based)
- [Box](https://github.com/p-ranav/box) (Python-based)
- [CablesGL](https://cables.gl/) (JavaScript-based)

**Execution Flow vs Data Flow**

Unlike pure dataflow systems ([ComfyUI](https://github.com/comfyanonymous/ComfyUI), [Langflow](https://github.com/langflow-ai/langflow), [ChaiNNer](https://github.com/chaiNNer-org/chaiNNer), [Ryven](https://github.com/leon-thomm/Ryven), [etc.](../research/nodes/_Execution_Classification.md)) that primarily pass data between nodes, Haywire uses an execution flow model in combination with a data flow model:

- Connections between [Control-pins](#pin-system) specify the order of operations
- Connections between [Data-pins](#pin-system) pass values between nodes
- This dual-pin system allows for imperative-style programming within a visual graph
- Nodes with Control-pins are called [Control-nodes](#node-types), those without are [Data-nodes](#node-types)
- The graph that is described by the connections between Control-pins is called [Control-graph](#control-flow-vs-data-flow) and assembled into the Control-flow
- The graph that is described by the connections between Data-pins is called [Data-graph](#control-flow-vs-data-flow) and assembled into a Data-flow

This combination of explicit Control-flow, Data-flow, [state management](#execution-context-management), and [just in time Assembly](#just-in-time-assembly) strategies allows Haywires to support more complex execution patterns than simple dataflow systems while maintaining visual clarity.

---

# Graph Structure

## The Graph as Container

### The Graph

The Haywire Graph is a data structure that describes the flow of data and control between nodes. As such, it is a collection of [Variables](#variables), [Connections](#connection-types) and instantiations of [Nodes](#node-architecture) and [Graph-nodes](#graph-as-node-pattern). All are described further down in their respective sections.

- A Graph can contain multiple disconnected node-trees that are assembled into individual [Flows](#flow-execution-model).
- A Graph cannot be executed directly. Only [Flows](#flow-execution-model) can be executed.

### Variables

Only [Graphs](#graph-structure) have [Variables](#variables). [Variables](#variables) are used to enhance functionality of the [Graph](#graph-structure) and allow statefulness during execution runs between nodes (and subsequent execution runs).

- [Variables](#variables) can be of specified datatypes.
- [Variables](#variables) have a default value that can be set on creation or by the user via the user interface.
- They are read/write accessible by the internal [Worker-function](#worker-function-execution) of [Control-nodes](#node-types)
- When a [Graph](#graph-structure) is stored to file, the default value is stored.

The reason nodes have no [Variables](#variables) is because they are not meant to be stateful. Nodes are meant to be stateless and their output should only depend on their input. There are exception though, like the [Loopback-nodes](#node-types) that need to be stateful to function properly.

### Validation Pipeline

**Current Implementation Enhancement:** The graph includes a sophisticated validation system that ensures structural integrity and type compatibility:

- **Debounced Validation:** Changes trigger validation after a configurable delay (default 50ms) to batch rapid changes
- **Lifecycle Tracking:** Each node and edge tracks its lifecycle state (registered → validated → built → tested → linked)
- **Change Reasons:** Validation distinguishes between different change types:
  - `NODE_ADDED`, `NODE_REMOVED`: Node creation/deletion
  - `EDGE_ADDED`, `EDGE_REMOVED`: Connection changes
  - `PORT_RECONFIGURED`: Dynamic port structure changes
  - `EXTERNAL_TRIGGER`: User-initiated revalidation
- **Error Enrichment:** Validation failures include context (node ID, port ID, lifecycle stage) for precise debugging
- **Callbacks:** External systems can register callbacks to react to validation events

This validation pipeline prevents invalid graphs from reaching the Assembly stage and provides immediate feedback during graph editing.

## The Graph-node

**The [Graph-node](#node-types): A graph is also a node**

A Graph can be treated like a node and thus can be used as such within another graph: a Graph-node.

There are three different ways a Graph-node can be implemented:

- **Subgraph** is a graph that is used only once and inside its parent Graph.
- **Abstraction** is a graph that can be used in multiple instances within its parent Graph.
- **Module** is a graph that can be used in multiple instances within any Graph.

**Subgraphs** and **Abstractions** are stored with their parent graphs. **Modules** are stored on the local file system and are treated like custom nodes.

As with nodes, a Graph-node can be of the type control or data, depending if it contains a [Control-pin](#pin-system).

**Requirements:**

- A Graph-node **must** contain one [Source-node](#node-types) and one [Sink-node](#node-types) and **cannot** have any other [Event-](#node-types) or [Output-nodes](#node-types).

## Connection Types

### On Connections, Edges, Hooks and Pipes

To distinguish clearly between the visual representation of a Graph and the functional representation of a Flow, Haywire makes a clear distinction between the two on the level of connections, too. And in order to keep terms clear, when "connection(s)" is used in this text it is meant in a colloquial manner, while [Edges](#edges), [Hooks](#control-edges---hooks), and [Pipes](#data-edges---pipes) are used to describe the effective data representation of the connections. So pay attention to the context in which "connections" are used:

- On the Graph level, the connections between the Control- and Data-nodes describe also [Edges](#edges).

- On the Control-Flow level, the connections between the Control-nodes describe also [Hooks](#control-edges---hooks).

- On the Data-Flow level, the connections between the Data-nodes describe also [Pipes](#data-edges---pipes).

[Hooks](#control-edges---hooks) and [Pipes](#data-edges---pipes) come only into existence during the [Assembly step](#assembly-process) and are only used in the orchestration of Control- and Data-Flows.

To summarize, for each [Edge](#edges) there is either a corresponding [Hook](#control-edges---hooks) or [Pipe](#data-edges---pipes) and all of them can be called "connections".

### Edges

[Edges](#edges) define the connections between nodes in a Graph.

There are three types of edges:

- **Control-edges** are used to control the flow of execution between nodes.
- **Data-edges** are used to transfer data between nodes.
- **Callback-edges** are used to trigger an [Event-node](#node-types) from another [Flow](#flow-execution-model). Contrary to Control- and Data-edges, Callback-edges are only used during the [Assembly step](#assembly-process) to connect [Flows](#flow-execution-model) through events.

An [Edge](#edges) is a simple data structure (see [complete structure in Appendix](#complete-edge-data-structure)) that contains the output-node's node-id, outlet-pin-id, outlet-pin-data-type and input-node's node-id, inlet-pin-id, inlet-pin-data-type.

Usually, only pins of the same type can be connected. But Haywire allows for connection between [Data-pins](#pin-system) of different types if there are compatible adapters available. For [Control-pins](#pin-system), there are no data-types and such restrictions are not necessary.

Edges are consirdered 'linked' when they are connected between two nodes and both the inlet and the outlet ports have accepted the connection.

**Current Implementation: EdgeWrapper Lifecycle**

Edges are managed through `EdgeWrapper` which handles their complete lifecycle:

1. **Registration:** Edge created with connection identifiers
2. **Validation:** Port existence and type compatibility checked
3. **Build:** Adapter chain constructed if types differ
4. **Test:** Adapter chain validated with sample data to catch runtime errors early
5. **Link:** Ports notified and connection finalized

**Adapter Chain Testing:** When connecting ports of different types, the system:
- Searches for adapter chain (e.g., `FLOAT → INT` might use `FloatToIntAdapter`)
- Creates sample data matching source port type
- Executes full adapter chain to verify no runtime errors
- Only accepts connection if chain succeeds
- Stores adapter chain keys for serialization

This proactive testing prevents type errors during execution by validating transformations at connection time rather than runtime. The adapter chain is rebuilt during hot reload if adapter code changes.

### Control-edges -> Hooks

TBD

### Data-edges -> Pipes

After the [Assembly Process](#assembly-process), each [Data-pin-outlet](#pin-system) that has one/many connections will hold the same number of [Pipes](#data-edges---pipes). Each [Pipe](#data-edges---pipes) holds within it self the reference to the connected [Data-pin-inlet's](#pin-system) value. If the outlet-pin-data-type is different from the inlet-pin-data-type, the [Pipe](#data-edges---pipes) also contains an adapter that will automatically transform the data.

The idea: when the nodes [worker function](#worker-function-execution) is finished and the [data-pin-outlet](#pin-system) is set, all its containing [Pipes](#data-edges---pipes) will be updated with the new value and automatically cascade the change to the connected [data-pin-inlets](#pin-system) and set them to dirty.

If an adapter is not available, the Editor should have shown an error when the edge was created. At the latest, the [Assembly Process](#assembly-process) would have thrown an error, too.

### Cycles

[Cycles](#cycles) are connections between nodes that form a loop.

- [Cycles](#cycles) are allowed for Control-connections.
- [Cycles](#cycles) are **NOT** allowed for Data-connections.
  - There is an exception though: if the data-connection-cycle is passing through a [Control-node](#node-types), it is allowed. This is because [Control-nodes](#node-types) are not evaluated within a localized data flow.

---

# Node Architecture

## Node Types

### The node

A Haywire node is arguably the most central element of the system. A node consists of

- **[Ports](#ports-inlets--outlets--pins)** (Inlets and Outlets) to configure behavior and transfer data to and from other nodes.
- **[Pins](#pin-system)** to connect to and from other nodes.
- **[Worker-function](#worker-function-execution)** that contains its main logic.

**Current Implementation: Node Lifecycle Management**

Nodes are managed through `NodeWrapper` which provides:

**Hot Reload System:** Automatic detection and migration when node code changes:
- File watchers detect modifications to node class files
- Node class is reimported with fresh module
- Port recipes are serialized from old instance
- New instance created and ports reconstructed from recipes
- Incompatible connections removed automatically
- Graph revalidated with new node structure

**Lifecycle States:**
1. **Registered:** Node wrapper created with registry key and ID
2. **Built:** Node instance created and ports configured
3. **Validated:** Ports checked, connections verified
4. **Ready:** Node ready for execution

**Middleware System:** NodeWrapper supports middleware plugins for:
- Custom validation rules
- Execution preprocessing/postprocessing
- Resource management
- Profiling and debugging

This wrapper architecture separates node business logic from lifecycle concerns, enabling hot reload without graph disruption.

These are the basic building blocks of a Haywire graph:

### Control Nodes

- Drive execution flow
- Process and transform data
- Have both at least one [Control-pin-inlet](#pin-system) and [Control-pin-outlet](#pin-system)
- Examples: Time-consuming algorithms, branches, loops, function calls

### Data Nodes

- Process and transform data
- Have **only** [Data-pins](#pin-system) (no control pins)
- Examples: Lightweight algorithms, math operations, data transformations


### Event Nodes

- Entry points for starting execution of flows
- Special kind of [control nodes](#node-types) with no input pins
- Not allowed inside of [Graph-nodes](#graph-as-node-pattern)
- Examples: BeginPlay, Tick, user input events

### Output Nodes

- Exit points for ending the execution of flows
- Special [control nodes](#node-types) with no output pins
- Not allowed inside of [Graph-nodes](#graph-as-node-pattern).
- Examples: End, Return, Stop

### Graph Nodes

- Nodes that encapsulate a [subgraph](#graph-as-node-pattern)
- Can have [Control-pins](#pin-system) and/or [Data-pins](#pin-system)
- Thus can be the equivalent of Control-nodes or Data-nodes depending on pin configuration
- Behave like other Control-nodes or Data-nodes
- Can have [variables](#variables) like Graphs.
- Three variants: [Subgraph, Abstraction, Module](#graph-as-node-pattern)

### Source-node

- Special kind of Event-node
- Used only inside [Graph-nodes](#graph-as-node-pattern)
- Starts the execution of the Graph-node
- Its pin-outlets are dynamically configured by its Graph-node defined pin-inlets.

### Sink-node

- Special kind of output-node
- Used to only inside [Graph-nodes](#graph-as-node-pattern)
- Exit the execution of the Graph-node
- Its pin-inlets are dynamically configured by its Graph-node defined pin-outlets.

### Loopback-node** Flag
- Control-node with the Loopback flag set
- tells the VM to loop back execution within the Control-flow to itself if the branch ends without an [Output-node](#node-types)
- Examples: For-Loops, While-Loops, Sequences and other Control-flow constructs that allow *sequential* branching of the Control-flow.
- Counterexamples: Switches or If-Statements are not Loopback-nodes since they do *conditional* branching.

## Node Components

### Ports: Inlets & Outlets & Pins

All node configurables are unified as **DataPorts** with behavior defined by flags and callbacks.

**Configuration Ports:**
- Implemented as Inlets with `flow_type = FlowType.NONE`
- Define the structure/behaviour/functionality of the node
- Changes trigger callbacks (e.g., `on_change='reconfigure_ports'`) that:
  - Can add/remove/enable/disable other Inlets and Outlets
  - May invalidate incompatible Connections
- Accessible read-only by the internal [Worker-function](#worker-function-execution)
- Serialized via "recipe" format (creation parameters, not runtime values)

**Note:** "Properties" as a separate concept have been removed. All configuration is now done through Inlets with appropriate callbacks.

**Hierarchical Port Organization (Implementation Enhancement):**

Ports support nested organization for complex nodes:

- **Groups:** Container ports that organize related ports
  - Can be collapsed/expanded in UI
  - Support nested groups for hierarchical organization
  - Context manager API: `with self.group('advanced'):`
- **Sections:** Organize ports in property panels
  - Used for UI layout (e.g., 'inputs', 'outputs', 'settings')
  - Multiple sections per node
- **Ghost Pins:** Visual indicators when groups are collapsed
  - Show connection state without revealing group contents
  - One ghost pin per collapsed group
- **Dynamic Reconfiguration:** Push/pop pattern for port changes
  - `push()`: Save current port configuration
  - Modify ports (add/remove based on config changes)
  - `pop()`: Returns list of removed port IDs for cleanup

This hierarchical system keeps complex nodes manageable while maintaining clean serialization (groups/sections are metadata, not separate node types).

#### Pins

[Pins](#pin-system) are the visual icon to connect to and from a node. [Pins](#pin-system) have a selection of different [configs](#configs) that define their behaviour:

- **Flow-type** defines if it is a control, data or callback pin
- **Socket-type** defines if the pin is an inlet (for getting event/data in) or an outlet (for sending event/data out)
- **Data-type** defines the data type the pin is associated with. And which other pins a pin can connect or not connect to.
- **Mate-type** defines how many connections can be made on the pin. This is either one or many.

The following table shows the only admissible pin configurations:

| Types               | Flow | Socket | Data | Mate     |
| ------------------- | ---- | ------ | ---- | -------- |
| Control-pin inlet   | ctrl | inlet  | --   | many     |
| Control-pin outlet  | ctrl | outlet | --   | one      |
| Data-pin inlet      | data | inlet  | type | one/many |
| Data-pin outlet     | data | outlet | type | many     |
| Callback-pin inlet  | call | inlet  | type | many     |
| Callback-pin outlet | call | outlet | type | many     |

#### Explanation to connection-types

- **Control-pin-outlet** can have only one Mate, since it must be clear which the next node is that needs to be executed.
- **Control-pin-inlet** can have many mates, since there might be multiple execution paths that lead to this node.
- **Data-pin-outlet** can have many mates, since multiple nodes might be interested in this data
- **Data-pin-inlet** there are two mate-types possible, depending on the needed data. in case of many the provided data is in form of a list of values in the specified data-type.
- **Callback-pin-inlet** can have many mates, since multiple [Event-nodes](#node-types) can require the same callback.
- **Callback-pin-outlet** can have many mates, since the [Event-node](#node-types) might be interested in multiple callbacks.

**Port Callbacks (Implementation Enhancement):**

Ports support lifecycle callbacks for dynamic behavior:

- **`on_change`**: Triggered when port value changes
  - Common use: Configuration ports that reconfigure node structure
  - Example: `on_change='reconfigure_ports'` calls `self.reconfigure_ports()`
  - Enables dynamic port addition/removal based on settings
  
- **`on_connect`**: Triggered when connection is established
  - Called with edge information (source/target ports)
  - Can reject connection by raising exception
  - Enables connection-dependent behavior (e.g., inferring types)
  
- **`on_disconnect`**: Triggered when connection is removed
  - Cleanup of connection-dependent state
  - Can trigger port reconfiguration

These callbacks enable sophisticated node behavior patterns:
- Type inference from connected ports
- Dynamic port count (e.g., variadic nodes)
- Conditional port availability
- Configuration cascades

#### Control Inlets

Control Inlets are used to execute Control-flow.

#### Control Outlets

Control Outlets are used to execute Control-flow.

#### Data Inlets

Inlets are used to receive data.

- Inlets are of specified data_types and data_categories.
- Inlets can have a default value that can be set on creation or by the user via the user interface.
- They are only read accessible by the internal [Worker-function](#worker-function-execution)
- They can be directly set by [Data-pin-inlets](#pin-system).
- They can be set to required or optional to be connected to a [Data-pin-outlet](#pin-system).
- If the inlet is set to required, no widget is displayed.
- When a [Graph](#graph-structure) is stored to file, only the default value is stored.
- If the Inlet has a data-type that can be edited via UI, the UI-Widget is displayed and is in effect a virtually attached Data source and sets the [Data-pin-inlet](#pin-system) like a [Data-pin-outlet](#pin-system) would.

#### Data Outlets

[Data Outlets](#data-outlets) are used to send data out of a node.

- [Data Outlets](#data-outlets) are of specified datatypes.
- [Data Outlets](#data-outlets) are **required** to be set by the internal [Worker-function](#worker-function-execution). This assures a consistent behavior.
- They are only write accessible by the internal [Worker-function](#worker-function-execution).
- **Current Implementation:** Outlets can have UI widgets for display/debugging purposes (e.g., to show output values).

#### Overview of Nodes Configurables

**Current Implementation:** Unified DataPort system with behavior flags.

| Port Type  | Flow Type | Function      | Default | Callback Support | Has Widget | Required |
| ---------- | --------- | ------------- | ------- | ---------------- | ---------- | -------- |
| Config     | NONE      | Configuration | yes     | yes (on_change)  | yes        | no       |
| Data Inlet | DATA      | Input         | yes     | yes (on_change, on_connect, on_disconnect) | optional | optional |
| Data Outlet| DATA      | Output        | no      | yes (on_connect, on_disconnect) | yes | no |
| Control Inlet | CONTROL | Execution | no | yes (on_connect, on_disconnect) | no | no |
| Control Outlet | CONTROL | Execution | no | yes (on_connect, on_disconnect) | no | no |

**Key Changes:**
- **Outlets can have widgets:** For display/debugging output values
- **Callback system:** Ports have `on_change`, `on_connect`, `on_disconnect` callbacks
- **Serialization:** Ports use "recipe" format (creation parameters) rather than storing runtime values

### Worker Function

This is where the real work is done. Each node, no matter of type, has one [Worker-function](#worker-function-execution). However, depending of the type of the node, the [Worker-function](#worker-function-execution) is called through different mechanisms.

The [Worker-function](#worker-function-execution) has access to the nodes internal Data Inlets (including configuration ports), [Variables](#variables) (for Control-nodes), and is able to set the [Data Outlets](#data-outlets).

It returns status information that is interpreted differently depending on the execution/evaluation mechanism.

More details can by found under [Worker function execution/evaluation](#worker-function-execution/evaluation)

### Data Types and Categories

The inlets or outlets define the Data-types and Data-category they require. This can be any python class. For the UI, Haywire provides a set of icons and colors to denote specific data-types.

The Data-types include `int`, `float`, `str`, `bool`, `bytes`, `object`
The Data-category include `scalar`, `list`, `tuple`, `set`, `array`, `dict`

ComfyUI follows a different strategy. It has keywords for each data-type. <https://docs.comfy.org/custom-nodes/backend/datatypes>

LangFlow follows a different strategy. Its Data-type are only high level and wrapped in a dict. <https://docs.langflow.org/data-types>

Blueprints:

* Primitive types: integers, floats, booleans.
* Complex types: strings, vectors, rotators. These handle more detailed aspects of game behavior.
* Reference types: objects and assets.

### Support Functions
The support functions allow for more fine grained control over the execution of the node.

#### ON_CHANGED_CONFIG:
* handles changes to the configuration of the node.
* called whenever a Config of the node is changed.

#### ON_VALIDATION_LAZY:
* handles the validation of the lazy evaluation of the node.
* called every time before execution / evaluation of node.

#### ON_CHANGED_ASYNC:
* checks for changes that are outside of the haywire process
* called every time before execution / evaluation of node.

#### ON_VALIDATION_INPUT:
* checks for validation of the input data of the node.
* called every time before execution / evaluation of node.

---

# Advanced Features

## Lazy Evaluation

This feature makes the evaluation of the Data-Flow more efficient by excluding unnecessary computations. This is done by specifying inside the node under which conditions which Inlets can be ignored to be evaluated.

The Lazy Evaluation algorithm covers differnt areas of the haywire system, from node initialisation to execution.

The [assembler](#assembly-process) is responsible for generating the [localized Data-Flow](#control-flow-vs-data-flow) for each [Control-node](#node-types). If Inlets have a lazy evaluation flag and the Data-Flows can be lazily evaluated, the VirtualMachine that lazily evaluates the Data-Flow would need some additional information beforehand. Haywire has the method `def ON_VALIDATION_LAZY` that is called before the [localized Data-Flow](#control-flow-vs-data-flow) can be evaluated lazily or not. If this is the case, depending on which Data Inlets are required, only certain steps of the [localized Data-Flow](#control-flow-vs-data-flow) need to be evaluated.

The complete [Lazy Evaluation Algorithm](#complete-lazy-evaluation-algorithm) is detailed in the [Appendix](#appendix).

## Callback System

Callbacks are used to notify other nodes about events that have occurred. With the Haywire system, it is the mechanism that allows from within executed [Flows](#flow-execution-model) to trigger other [Flows](#flow-execution-model) within the same [Graph](#graph-structure).

Lets first disentangle the concepts of triggers, [Events-nodes](#node-types), Control-connections and Callbacks. In the context of Haywire,

**triggers** are the events that are generated by the outside system, while **[Event-node](#node-types)** are the mechanism to pass on this trigger into the flow. Once an **[Event-node](#node-types)** is triggered, it will emit through its [Control-pin-outlet](#pin-system) (and its [Data-pin-outlet](#pin-system) if so required).

**callbacks** is a mechanism to generate a **trigger** from within another flow. From the point of view of an **[Event-node](#node-types)**, this looks like an event from the outside system, since it is generated by a flow that runs within a separate thread.

**[Callback-pin-outlets](#pin-system) can only be implemented by [Event-nodes](#node-types)**, since this are the nodes that trigger flows.

On first sight, this seems to be counter-intuitive, why should an [Event-node](#node-types) have a [Callback-pin-outlet](#pin-system). It is actually listening to a trigger, so shouldn't it have a [Callback-pin-inlet](#pin-system) instead? The answer is no. The callback connection needs always be initiated by the listener, which is in this case the [Event-node](#node-types) that is listening for the event. In other words: The callback connection is used by its node to notify other nodes that it is interested in the event and is asking for a callback. Though this is a bit misleading: the callback connection is only used during the [Assembly step](#assembly-process). This means that the callback connection is not used during the execution of any of the flows involved.

Also, an [Event-node](#node-types) can by definition have no pin-inlets.

---

# Flow

## Overview

[Flows](#flow-execution-model) are used to organize and execute a sequence of nodes. A [Flow](#flow-execution-model) is assembled by the [Assembler](#assembly-process) from a [Graph](#graph-structure). A [Flow](#flow-execution-model) has always at least one [Event-node](#node-types) as an entry point.

Each [Flow](#flow-execution-model) keeps a reference of the [Graph](#graph-structure) it is assembled from and uses the Graphs instantiations of [Nodes](#node-architecture), [Subgraphs](#graph-as-node-pattern) etc to execute/evaluate the nodes. Thus, during the Interpretation of a [Flow](#flow-execution-model), the [Graph](#graph-structure) is used as the database of the [Flow](#flow-execution-model). Once the Interpretation is finished, the Graphs nodes are reset to their default state.

## From Graph to Flow

Haywire uses a Control- (also known as an Execution-) flow model in combination with a Data-flow model.

- Control-connections specify the order of operations
- Data-connections pass values between nodes
- The Graph that is described by the Control-connections is called Control-graph and assembled into the Control-flow
- The Graph that is described by the Data-connections is called Data-graph and assembled into a Data-flow

## The Dual-Flow Model

Haywire's model is separating **what executes when**, and from **what data flows where**:

During the [Assembly](#assembly-process), the Control-connections are traversed and the Control-flow is assembled. Then from each [Control-node](#node-types), the Data-graph is traversed and the localized Data-flow is assembled.

### Control Flow

- Defines the sequence of operations
- Follows Control-connections from [Control-node](#node-types) to [Control-node](#node-types)
- Each control connection is essentially a "goto next instruction"
- Connected [control pins](#pin-system) specify execution order
- Supports complex patterns: loops, branches, conditionals
- Start at [Event-nodes](#node-types) (BeginPlay, Tick, InputAction, etc.)

### (localized) Data Flow

- Passes values between nodes
- generated from local Data-graph around a [Control-node](#node-types) to be local node-related dependency tree of [Data-nodes](#node-types)
- Connects [data pins](#pin-system) to transfer information
- Evaluated locally around each control node through [localized Data-flow](#control-flow-vs-data-flow)
- Every time a [Control-node](#node-types) is executed, its localized Data-flow is evaluated.
- Supports [lazy evaluation](#lazy-evaluation) strategies

# Generation

Under Generation falls currently everything  that is involved until a complete Graph is instantiated for further processing.

This includes

## Finding and Loading available Node Libraries

loading nodes from filesystem: [ComfyUI/nodes.py at 78672d0ee6d20d8269f324474643e5cc00f1c348 ? comfyanonymous/ComfyUI ? GitHub](https://github.com/comfyanonymous/ComfyUI/blob/78672d0ee6d20d8269f324474643e5cc00f1c348/nodes.py#L2168)

## Loading Graphs from JSON and instantiating required Nodes

this example shows a first approach on how to load a graph from json, find, version check and instantiate the required nodes from a central registry: [node_discovery_system.py](../../playground/node_API/node_discovery_system.py)

---

# Assembly

## Overview

As mentioned, [Graphs](#graph-structure) core entity consist of [Nodes](#node-architecture) and Connections. The [Assembly](#assembly-process) converts a [Graph](#graph-structure) into executable [Flows](#flow-execution-model). This is realized with the creation of a new data structure that can be executed ([Flow](#flow-execution-model)) rather than be descriptive ([Graph](#graph-structure))

- The [Graph](#graph-structure) is analyzed to identify execution paths, starting at [Event-nodes](#node-types) and following [Control-pins](#pin-system)
- At each [Control-node](#node-types), its [Data-pin](#pin-system) node dependencies are separated into a local Data-graph with a predefined sequence of execution for each involved node called a [localized Data-flow](#control-flow-vs-data-flow).
- whenever a the graph is manipulated (connection is added or removed), the [just in time Assembly](#just-in-time-assembly) mechanism adapts the respective flow to the new graph description.

Lets first focus on a complete [Assembly](#assembly-process) of a graph into flows:

We assume:

- graph is loaded from a file.
- graph loads its dependencies.
- validation to check for recursive dependencies.
- graph is instantiated.

## Assembly Steps

### Graph Validation

- Checking for graph validity
  - Node checking:
    - Checking for validity of node-types (see chapter of [node types](#node-types) for details)
    - Checking for multiples of the same [Event-nodes](#node-types) (not allowed since undefined which Control-flow is should have precedence)
    - Checking for [source](#node-types) and [sink nodes](#node-types) inside [Graph-nodes](#graph-as-node-pattern) (required to be functional)

### Graph Cleaning

- Clearing all connections that are stored inside pins. (clean house)

### Graph Preprocessing

- Storing Control-flow connections in their respective outlet-pins. This is because the Control-flow propagates in the direction from [Control-pin-outlet](#pin-system) to [Control-pin-inlet](#pin-system). The next-to-be-executed-controlnode [Control-pin-inlet](#pin-system) doesn't need to know with what node it is connected. It is actually allowed to be connected to multiple nodes. Once the node is executed, the VM will inform the from where the Control-flow came from.
- Storing Data-flow connections in their respective inlet-pins. This is because the Data-flow is assembled through backpropagation from the [Data-pin-inlets](#pin-system) of its respective [Control-node](#node-types). the [Data-pin-outlets](#pin-system) doesn't need to know with which inlet-pins it is connected to at the time of [Assembly](#assembly-process). once the Data-flow is created though, the outlet-pins "know" where to send their results. (this mechanism is not yet defined and can benefit from a suitable solution)

### Flow identification

- Identifies different Control-flows with the [Graph](#graph-structure).
  - A Control-flows needs at least one [Event-node](#node-types)
  - A Control-flows is considered separate from another Control-flows when there is no connection (control or data) between their respective nodes-trees.
    - The only exception here is the [callback-connection](#callback-system).

### Flow assembly

- Stepping through each [Control-node](#node-types):
  - its [Data-pin-inlet](#pin-system) dependencies are separated into a localized Data-graph (containing only nodes and connections that influence the [Data-pin-inlets](#pin-system) of the [Control-node](#node-types) in focus).
  - Checking for loops in the Data-graph (not allowed with the exception of loops that contain a [Control-node](#node-types))
  - the Data-graph is sorted into a predefined sequence of executions called a [localized Data-flow](#control-flow-vs-data-flow).
  - the [localized Data-flow](#control-flow-vs-data-flow) is stored within the [Control-node](#node-types), ready to be executed.
- It does all of it iteratively with each [Graph-node](#graph-as-node-pattern) as well.
- It identifies the [Event-nodes](#node-types) and makes them available for hooking it up with the execution mechanism of the whole haystack.

### Just-In-Time Assembly

## Just-In-Time Assembly (For a future implementation)

- This happens whenever a connection is edited.
  - This can be the case if a node is deleted, but not when a node is added.

# Execution

## The Virtual Machine

### Virtual Machine Architecture

The Haywire Virtual Machine (VM) maintains two control-flow- stacks

- **Done-stack**: Tracks completed nodes
- **Loopback-stack**: Manages nodes requiring return execution (loops, sequences)

#### Execution Context Management

- Tracks which node should execute next based on [Control-pin](#pin-system) connections
- Manages global (from the outside) and local [variables](#variables) and passing them between nodes

#### Control Flow Translation

- Each control connection is essentially a "goto next instruction"
- [Loopback nodes](#node-types) (ForLoop, WhileLoop) maintain internal state and can re-execute connected branches
- [Branch nodes](#node-types) evaluate conditions and direct execution down different paths- Infinite loop protection via stack overflow detection (via the Done-stack)
- The VM tracks loop iteration state and manages the evaluation context

#### Data Flow Translation

- [Data nodes](#node-types) are executed sequentialy defined by the localized Data-Flow
- The Engine supports [Lazy Evaluation](#lazy-evaluation)

#### State Preservation:

- The VM can pause execution (for async operations like delays)
- Maintains execution context

## Flow Execution

Each [Flow](#flow-execution-model) has a Scheduler that manages the execution of the [Flow](#flow-execution-model). It makes sure that the [Flow](#flow-execution-model) is executed from the [Event-node](#node-types) that matches the trigger type.

Once a [Flow](#flow-execution-model) is executed, the scheduler locks the [Flow](#flow-execution-model) for exclusive execution. All other Triggers are queued inside the Trigger-queue until the [Flow](#flow-execution-model) is finished.

Depending on the Trigger-queue's configuration, the Trigger-queue can be configured to either block or drop incoming events.

[Flows](#flow-execution-model) should allowed to be executed in parallel. Not yet clear which architecture to use.

### Control Flow Execution

When a [Flow](#flow-execution-model) is executed, it creates two stacks:

- The first stack is the Done-stack, which contains the nodes that have been executed.
- The second stack is the Loopback-stack, which contains the [Loopback-nodes](#node-types).

Once a [Control-node](#node-types) is executed, VM pushes it onto the Done-stack, and if its a [Loopback-node](#node-types), its pushed onto the Loopback-stack.

[Loopback-nodes](#node-types) are [Control-nodes](#node-types) that have one or multiple execution branches that have to come back to the node to continue. [Loopback-nodes](#node-types) are designated as such by a flag.

Once a branch finds its end without an [Output-node](#node-types) (which would end the [Flow](#flow-execution-model)), the VM checks the Loopback-stack for any [Loopback-nodes](#node-types) that are waiting for the branch to complete. If there are no [Loopback-nodes](#node-types) waiting, the [Flow](#flow-execution-model) is considered complete.

If there are [Loopback-nodes](#node-types) waiting, the VM gets the last one out of the stack and removes all the nodes in the Done-stack up to the [Loopback-node](#node-types).

It then continues executing the [Flow](#flow-execution-model) from the [Loopback-node](#node-types).

If there are cycles in the Control-Flow that spiral into infinity, the Done-stack will eventually overflow, causing the VM to throw an error.

### Worker function execution/evaluation

#### for Control-nodes

The VM follows the [Control-pins](#pin-system) from node to node. To recap quickly: During the [Assembly](#assembly-process) of the [Graph](#graph-structure), the connections, which are stored within the graph, are transferred to the respective pins. After [Assembly](#assembly-process) of the [Graph](#graph-structure), there is a Control-flow containing a reference to each connected [Control-node](#node-types) (TBD).

0. After the VM executed the previous [Control-node](#node-types), its return value indicates which [Control-pin-outlet](#pin-system) it has to follow. This identifies the next to be executed [Control-node](#node-types).

1. Before the [Control-node's](#node-types) [Worker-function](#worker-function-execution) is called, it first evaluates the [Control-node's](#node-types) [localized Data-flow](#control-flow-vs-data-flow) to update the [Data-pin-inlets](#pin-system).

2. Then it executes the [Worker-function](#worker-function-execution). It provides a reference to

   - **A global context**: The global context comes in form of a dict and contains any data a dict can contain, including user specific data and references to data stored outside of the evaluation engine.
   - **A local context**: The local context comes in form of a dict and gives access to the local graph and its [variables](#variables).
   - **Control-pin**: The identity of the [Control-pin-input](#pin-system) that is executed.
   - **Control-node**: The identity of the node that called.
   - etc.

3. Within the [Worker-function](#worker-function-execution) at the end of its process,

   - it sets the respective [Data-pin-outlets](#pin-system).

4. then returns status information that includes the information which [Control-pin-outlet](#pin-system) is to be followed.

5. The VM takes this info, identifies the next [Control-node](#node-types)

6. ...and repeats above process..

#### for Data-nodes

To recap quickly: After [Assembly](#assembly-process) of the graph, there is a [localized Data-flow](#control-flow-vs-data-flow) for each [Control-node](#node-types). A [localized Data-flow](#control-flow-vs-data-flow) is nothing but a sorted list of the [Data-nodes](#node-types) that need to be evaluated in sequence to get the values for the [Data-pin-inlets](#pin-system) of the [Control-node](#node-types).

Before the execution of the [Worker-function](#worker-function-execution) of a [Control-node](#node-types), its [localized Data-flow](#control-flow-vs-data-flow) is **required** to be evaluated first.

The evaluation of an individual [Data-node](#node-types) follows these steps:

Before the [Data-node's](#node-types) [Worker-function](#worker-function-execution) is called, it checks first if any of its own [Data-pin-inlets](#pin-system) are dirty (value has changed).

1. If this is the case:

2. then it runs the [Worker-function](#worker-function-execution). It provides a reference to

   - **A global context**: The global context comes in form of a dict and contains any data a dict can contain, including user specific data and references to data stored outside of the evaluation engine.
   - **A local context**: The local context comes in form of a dict and gives access to the local graph and its [variables](#variables).

3. Within the [Worker-function](#worker-function-execution) at the end of its process,

   - it updates the [Data-pin-outlets](#pin-system) so its connected downstream [Data-pin-inlets](#pin-system) are set to dirty (value has changed).

4. If there are no dirty inlets:

   - the [Worker-function](#worker-function-execution) is not called. And no outlets are updated.

5. The sequence hops to the next [Data-node](#node-types).

6. .. and so it continues...

---

# Interpreter

- The [Interpreter](#interpreter) is responsible for running the individual [Flows](#flow-execution-model) in their own Threads.
- It is responsible for piping external events to trigger the [Flows](#flow-execution-model) that have matching [Event-nodes](#node-types).

---

# Outstanding Design Questions

## For Author Clarification

1. **Parallel Flow Execution**: Should [flows](#flow-execution-model) run in parallel? This impacts:

   - [Graph](#graph-structure) reference management (each flow needs separate instance?)
   - Thread safety requirements
   - State management complexity
   - Only [Graphs](#graph-structure) containing one [Flow](#flow-execution-model) can run in parallel.
   - They have to be designed to be truly stateless.
   - What would be the best architecture to cover both parallel and sequential execution?

2. **Data-Flow Cycle Exceptions**: The specification mentions data cycles are allowed "if passing through a [Control-node](#node-types)" - this needs clearer definition of when/how this works.

3. **[Data Outlets](#data-outlets) Implementation**: Currently marked as "not yet defined" - needs specification for:

   - How outputs are validated as "required to be set"
   - Runtime behavior when outputs aren't set
   - Integration with [pipe system](#data-edges---pipes)

4. **Variable Scope**: [Variables](#variables) are [Graph](#graph-structure)-only, but some nodes (like loops) seem to need state. How is this resolved?

5. **What works with this spec?**

6. **What does this specification desperately need to clarify the goal?**

7. **What is the best way to implement this?**

8. **Check the [Assembly steps](#complete-assembly-steps) for missing requirements and generation steps.**

## Suggested Enhancements

**?�� Performance Monitoring**: Add execution profiling to identify bottlenecks in complex graphs

**?�� Debug Infrastructure**: Visual execution tracing, breakpoint support, step-through debugging

**?�� Module System**: Standardized packaging/distribution for custom nodes and abstractions

**?�� Error Handling**: Comprehensive error propagation and recovery strategies

---

# Appendix

## Complete Edge Data Structure

**Specification:**

An [Edge](#edges) is a simple data structure that contains the:

- **Connection identifiers:**
  - `output_node_id`: Source node identifier
  - `outlet_port_id`: Source port identifier
  - `input_node_id`: Target node identifier
  - `inlet_port_id`: Target port identifier
  - `edge_type`: FlowType (CONTROL, DATA, CALLBACK)
  - `adapter_chain_keys`: List of adapter registry keys
  - `uuid`: Unique edge identifier

**Implementation:**

Edges are managed by `EdgeWrapper` which stores:

- **Adapter chain:**
  - `adapter_chain_keys`: List of adapter registry keys for type transformation
  - Built during edge validation to convert between incompatible types
  - Example: `['adapter.float_to_int', 'adapter.scale']`

- **State tracking:**
  - Lifecycle state (registered, validated, built, tested, linked)
  - Error information for each lifecycle stage
  - References to source/target port objects

## Complete Port Serialization

**Recipe-Based Serialization**

Ports use a "recipe" format that stores the **creation parameters** rather than runtime values. This allows ports to be reconstructed with their exact configuration:

**Key Features:**

1. **Type Identity Storage:**
   - `type_cls`: Registry key for the IType class
   - `element_type_cls`: For compound types (e.g., ArrayType[FLOAT])
   - Allows reconstruction of exact type hierarchy

2. **Default Values:**
   - Stored in type-appropriate format via DataField
   - Only creation defaults, not runtime state

3. **Callbacks:**
   - `on_change`: Method name to call on value change
   - `on_connect`: Method name to call on connection
   - `on_disconnect`: Method name to call on disconnection

4. **Hierarchical Structure:**
   - `parent_group`: ID of parent group port
   - `section`: Property panel section name
   - `is_group`, `is_section`, `is_ghost`: Organizational flags

5. **Widget Configuration:**
   - `widget_key`: Registry key for UI widget
   - `widget_config`: Additional widget parameters

This recipe-based approach enables:
- Hot reload: Ports can be rebuilt from recipes after code changes
- Version migration: Recipes can be transformed during graph loading
- Minimal storage: Only essential creation parameters are saved

### Complete Node Definition Template

see [Haywire_node_definition.md](./Haywire_node_definition.md)

### Complete Node Initialization Sequence

```console
# Initialization
1. first the node is initialized, calling __init__
2. Calling SETTINGS to set the Configs.
3. Calling ON_CHANGED_CONFIG to dynamically configure the node.
4. Calling PARAMETERS to set the Properties.
5. Calling INLETS to set the Inlets.
6. Calling OUTLETS to set the Outlets.

# Assembly
1. Checking if there are lazy Inlets on the Control-node to configure the backpropagation.
2. Checking if there are lazy Inlets on the Data-node to configure the localized Data-Flow.

# Execution Control-node
1. Calling ON_VALIDATION_LAZY on the Control-node generate the LAZY_MASK.
2. Evaluation localized Data-Flow
  2.1 Calling ON_VALIDATION_LAZY on the Data-node to see if there is the need for re-assembly.
  2.2 Calling ON_CHANGED_ASYNC on the Data-node to see if there is change that is not from UI or Upstream nodes
  2.3 Calling ON_VALIDATION_INPUT on the Data-node to validate the inputs before calling the worker FUNCTION.
  2.4 Calling the worker FUNCTION
3. Calling ON_CHANGED_ASYNC on the Data-node to see if there is change that is not from UI or Upstream nodes
4. Calling ON_VALIDATION_INPUT on the Control-node to validate the inputs before calling the worker FUNCTION.
5. Calling the worker FUNCTION
```

## Complete Lazy Evaluation Algorithm

**Algorithm:**

**Setup** of a [Control-node](#node-types)

- Some Inlets are configured to be lazy
- A ON_VALIDATION_LAZY function is defined to determine if the condition for a lazy evaluation is given.

**Setup** of a [Data-node](#node-types) with the [localized Data-Flow](#control-flow-vs-data-flow) of this [Control-node](#node-types)

- Some Inlets are configured to be lazy
- A ON_VALIDATION_LAZY function is defined to determine if the condition for a lazy evaluation is given.

**[Assembly](#assembly-process)**

- On the [Control-node](#node-types), the [assembler](#assembly-process) creates a bit mask with a bit for each data-inlet. each data-inlet gets its own bit mask called EVAL_MASK where the bit that represents the inlet is set to 1, while all other bits are set to 0.
- On the [Data-node](#node-types), the ON_VALIDATION_LAZY function is called to determine which Data-inlets to follow in the backpropagation.(This, by the way has a severe edge case: the ON_VALIDATION_LAZY function on a [Data-node](#node-types) should make its decision at assembly time for performance reasons. Otherwise the re-assembly of the [localized Data-Flow](#control-flow-vs-data-flow) would be required on each execution of the [Control-node](#node-types), which we want to avoid. But implementing [Lazy Evaluation](#lazy-evaluation) in a consistent manner for the user means that changes of [Properties](#properties) or Inlets that could affect this decision on the [Data-node](#node-types) during runtime actually needs to trigger a re-assembly of the [localized Data-Flow](#control-flow-vs-data-flow). Otherwise, the evaluation of the Data-Flow could lead to incoherent results. A slight performance penalty is preferable over an inconsistent user experience.)
- Upon generation of the [localized Data-Flow](#control-flow-vs-data-flow), this bit mask is passed on during the backpropagation, and is binary OR'ed with other bit masks from the same [Control-node](#node-types) if they merge at that specific [Data-node](#node-types). This OR'ed bit mask is then passed further during backpropagation. At the end there is a list of all the required [Data-nodes](#node-types) and their respective OR'ed bit masks (EVAL_MASK). Then the correct sequence of [Data-nodes](#node-types) is determined to evaluate the Data-Flow correctly. This EVAL_MASK shows which Data-inlets require the evaluation of this specific [Data-node](#node-types).

**Evaluation**

- On execution of the [Control-node](#node-types), the VM creates a bit mask called LAZY_MASK with a bit for each data-inlet, all set to 1.
- then the ON_VALIDATION_LAZY function is called to determine if the Data-Flow can be evaluated lazily or not. If this is the case, it sets the bits inside LAZY_MASK representing the data-inlets that are not needed to 0, while all others stay 1.
- Then the [localized Data-Flow](#control-flow-vs-data-flow) is evaluated:
  - It goes to the next [Data-node](#node-types) in the sequence.
  - First it checks if the [Data-Nodes](#node-types) ON_VALIDATION_LAZY function has a different result than the previous run (i.e. during [Assembly](#assembly-process)).
    - If yes, the evaluation of the [localized Data-Flow](#control-flow-vs-data-flow) is stopped
      - The VM reassembles the [localized Data-Flow](#control-flow-vs-data-flow) from scratch.
      - and restarts the evaluation process.
    - If no, it continues ..
  - Second it checks if any Data-Inlets are dirty.
    - If yes, it makes a Binary AND between LAZY_MASK and EVAL_MASK.
      - if the result is bigger than 0
        - this means at least one Data-Inlet requires the evaluation of this [Data-node](#node-types).
        - it evaluates the node.
        - sets the dirtied Data-Inlets to clean.
    - If not it continues. The [Data-node](#node-types) has not been evaluated yet, so if downstream a [Control-node](#node-types) with a different [localized Data-Flow](#control-flow-vs-data-flow) encounters this node, it will only then be evaluated.
  - continues with the next [Data-node](#node-types) in the sequence..

It is not clear yet how fast the reassembly of the [localized Data-Flow](#control-flow-vs-data-flow) from scratch is. I hope for an efficient algorithm. Depending on the time saved by lazy evaluation, it might be worth it. Its left to the node-designer to decide if such an effort makes sense. If there is no ON_VALIDATION_LAZY function defined, the algorithm should run at nominal speed. The additional binary AND operation and if statements in each step should be negligible.
