# Haywire Node System - Specification v1.0.0

## Table of Contents

- [Haywire Node System - Specification v1.0.0](#haywire-node-system---specification-v100)
  - [Table of Contents](#table-of-contents)
  - [Credits \& License](#credits--license)
- [Overview](#overview)
    - [Key Differentiators](#key-differentiators)
    - [Related Projects](#related-projects)
- [Core Architecture](#core-architecture)
  - [The Dual-Flow Model](#the-dual-flow-model)
  - [Node Classification](#node-classification)
  - [The Graph](#the-graph)
  - [Assembly: From Graph to Flow](#assembly-from-graph-to-flow)
  - [Control-flow vs Data-flow](#control-flow-vs-data-flow)
  - [The Virtual Machine](#the-virtual-machine)
    - [Event-Driven Execution](#event-driven-execution)
    - [Virtual Machine Architecture](#virtual-machine-architecture)
    - [Loop and Branch Handling](#loop-and-branch-handling)
    - [Execution Context Management](#execution-context-management)
- [Graph Structure](#graph-structure)
  - [The Graph as Container](#the-graph-as-container)
    - [The Graph](#the-graph-1)
    - [Variables](#variables)
  - [The Graph-node](#the-graph-node)
  - [Connection Types](#connection-types)
    - [On Connections, Edges, Links and Pipes](#on-connections-edges-links-and-pipes)
    - [Edges](#edges)
    - [Control-edges -\> Links](#control-edges---links)
    - [Data-edges -\> Pipes](#data-edges---pipes)
    - [Cycles](#cycles)
- [Node Architecture](#node-architecture)
  - [Node Types](#node-types)
  - [Node Components](#node-components)
    - [Settings](#settings)
    - [Parameters](#parameters)
    - [Inlets \& Outlets \& Pins](#inlets--outlets--pins)
      - [Pins](#pins)
      - [Explanation to connection-types](#explanation-to-connection-types)
      - [Control Inlets](#control-inlets)
      - [Data Inlets](#data-inlets)
      - [Data Outlets](#data-outlets)
      - [Overview of Nodes Configurables](#overview-of-nodes-configurables)
    - [Worker Function Execution](#worker-function-execution)
    - [Data Types and Categories](#data-types-and-categories)
- [Advanced Features](#advanced-features)
  - [Lazy Evaluation](#lazy-evaluation)
  - [Callback System](#callback-system)
- [Generation](#generation)
  - [Finding and Loading available Node Libraries](#finding-and-loading-available-node-libraries)
  - [Loading Graphs from JSON and instantiating required Nodes](#loading-graphs-from-json-and-instantiating-required-nodes)
- [Assembly](#assembly)
  - [Overview](#overview-1)
  - [Assembly Steps](#assembly-steps)
      - [Graph Validation](#graph-validation)
      - [Graph Cleaning](#graph-cleaning)
      - [Graph Preprocessing](#graph-preprocessing)
      - [Flow identification](#flow-identification)
      - [Flow assembly](#flow-assembly)
    - [Just-In-Time Assembly](#just-in-time-assembly)
  - [Just-In-Time Assembly (For a future implementation)](#just-in-time-assembly-for-a-future-implementation)
- [Execution](#execution)
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

# Core Architecture

## The Dual-Flow Model

Haywire's model is separating **what executes when**, and from **what data flows where**:

**Control Flow (Execution Flow)**

- Defines the sequence of operations
- Connects [control pins](#pin-system) to specify execution order
- Managed by the [Haywire Virtual Machine](#the-virtual-machine)
- Supports complex patterns: loops, branches, conditionals

**Data Flow**

- Passes values between nodes
- Connects [data pins](#pin-system) to transfer information
- Evaluated locally around each control node through [localized Data-flow](#control-flow-vs-data-flow)
- Supports [lazy evaluation](#lazy-evaluation) strategies

## Node Classification

**Control Nodes**

- Have both control input and output pins
- Drive execution flow
- Examples: branches, loops, function calls

**Data Nodes**  

- Have only data pins (no control pins)
- Process and transform data
- Examples: math operations, data transformations

**Event Nodes**

- Special [control nodes](#node-types) with no input pins
- Entry points for execution flows
- Examples: BeginPlay, Tick, user input events

**Output Nodes**

- Special [control nodes](#node-types) with no output pins  
- Exit points for execution flows
- Examples: End, Return, Stop

**Graph Nodes**

- Nodes that encapsulate a [subgraph](#graph-as-node-pattern)
- Can be Control or Data type based on pin configuration
- Three variants: [Subgraph, Abstraction, Module](#graph-as-node-pattern)

These are the most important Node Types. More are defined under [Node Types](#node-types)

## The Graph

The Graph is the data container that describes the structure of the graph and stores the current state of the execution.

## Assembly: From Graph to Flow

[Flows](#flow-execution-model) are used to organize and execute a sequence of nodes. A [Flow](#flow-execution-model) is assembled by the [Assembler](#assembly-process) from a [Graph](#graph-structure). A [Flow](#flow-execution-model) has always at least one [Event-node](#node-types) as an entry point.

Each [Flow](#flow-execution-model) keeps a reference of the [Graph](#graph-structure) it is assembled from and uses the Graphs instantiations of [Nodes](#node-architecture), [Subgraphs](#graph-as-node-pattern) etc to execute/evaluate the nodes. Thus, during the Interpretation of a [Flow](#flow-execution-model), the [Graph](#graph-structure) is used as the database of the [Flow](#flow-execution-model). Once the Interpretation is finished, the Graphs nodes are reset to their default state.

## Control-flow vs Data-flow

Haywire uses a Control- (also known as an Execution-) flow model in combination with a Data-flow model.

- Control-connections specify the order of operations
- Data-connections pass values between nodes
- The graph that is described by the Control-connections is called Control-graph and assembled into the Control-flow
- The graph that is described by the Data-connections is called Data-graph and assembled into a Data-flow

During the [Assembly](#assembly-process), the Control-connections are traversed and the Control-flow is assembled. Then from each [Control-node](#node-types), the Data-graph is traversed and the localized Data-flow is assembled.

**Control-flow**

- Start at [Event-nodes](#node-types) (BeginPlay, Tick, InputAction, etc.)
- Follow Control-connections from [Control-node](#node-types) to [Control-node](#node-types)
- Each control connection is essentially a "goto next instruction"

**localized Data-flow: localized dependency resolution**

- Analyze the local graph around a [Control-node](#node-types) to identify a local node-related dependency tree of [Data-nodes](#node-types)
- Create evaluation sequence based on these data dependencies called a localized Data-flow
- Every time a [Control-node](#node-types) is executed, its localized Data-flow is evaluated.

## The Virtual Machine

### Event-Driven Execution

Haywires uses an [event-driven](#Flow-execution-model) model:

- Execution begins at [Event-nodes](#node-types) (BeginPlay, Tick, input events)
- Multiple execution chains (called [Flows](#flow-execution-model)) can run independently
- The system can handle asynchronous operations and callbacks

### Virtual Machine Architecture

Haywires graph don't execute as a simple tree traversal. Instead, they use a virtual machine approach:

- The Haywire Virtual Machine (VM) maintains two [execution stacks](#execution-context-management)
- Nodes can pause execution and resume later, enabling complex control flows

The Haywire Virtual Machine handles the complex orchestration:

**Execution Context Management:**

- Maintains the current execution state and loopback-stack
- Tracks which node should execute next based on [Control-pin](#pin-system) connections
- Manages local [variables](#variables) and parameter passing between nodes

**Control Flow Translation:**

- [Branch nodes](#node-types) become conditional jumps in the VM
- [Loop nodes](#node-types) become loop constructs with iteration state
- Sequence nodes become ordered function call chains

**Data Flow Translation:**

- [Data nodes](#node-types) are executed sequentialy defined by the localized Data-Flow
- The Engine supports [Lazy Evaluation](#lazy-evaluation)

**State Preservation:**

- The VM can pause execution (for async operations like delays)
- Maintains execution context

### Loop and Branch Handling

For loops and conditionals, Haywire use specialized [Control-flow nodes](#node-types):

- [Branch nodes](#node-types) evaluate conditions and direct execution down different paths
- [Loop nodes](#node-types) (ForLoop, WhileLoop) maintain internal state and can re-execute connected sub-control-graphs
- The VM tracks loop iteration state and manages the evaluation context

### Execution Context Management

The VM maintains execution through two stacks:

**Execution Stacks:**

- **Done-stack**: Tracks completed nodes
- **Loopback-stack**: Manages nodes requiring return execution (loops, sequences)

**Loop Handling:**

- [Loopback nodes](#node-types) can re-execute connected sub-graphs
- VM manages iteration state and loop termination
- Infinite loop protection via stack overflow detection (via the Done-stack)

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
- When a [Graph](#graph-structure) is stored to file, only its [settings](#settings) and the default value are stored.

The reason nodes have no [Variables](#variables) is because they are not meant to be stateful. Nodes are meant to be stateless and their output should only depend on their input. There are exception though, like the [Loopback-nodes](#node-types) that need to be stateful to function properly.

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

### On Connections, Edges, Links and Pipes

To distinguish clearly between the visual representation of a Graph and the functional representation of a Flow, Haywire makes a clear distinction between the two on the level of connections, too. And in order to keep terms clear, when "connection(s)" is used in this text it is meant in a colloquial manner, while [Edges](#edges), [Links](#control-edges---links), and [Pipes](#data-edges---pipes) are used to describe the effective data representation of the connections. So pay attention to the context in which "connections" are used:

- On the Graph level, the connections between the Control- and Data-nodes describe also [Edges](#edges).

- On the Control-Flow level, the connections between the Control-nodes describe also [Links](#control-edges---links).

- On the Data-Flow level, the connections between the Data-nodes describe also [Pipes](#data-edges---pipes).

[Links](#control-edges---links) and [Pipes](#data-edges---pipes) come only into existence during the [Assembly step](#assembly-process) and are only used in the orchestration of Control- and Data-Flows.

To summarize, for each [Edge](#edges) there is either a corresponding [Link](#control-edges---links) or [Pipe](#data-edges---pipes) and all of them can be called "connections".

### Edges

[Edges](#edges) define the connections between nodes in a Graph.

There are three types of edges:

- **Control-edges** are used to control the flow of execution between nodes.
- **Data-edges** are used to transfer data between nodes.
- **Callback-edges** are used to trigger an [Event-node](#node-types) from another [Flow](#flow-execution-model). Contrary to Control- and Data-edges, Callback-edges are only used during the [Assembly step](#assembly-process) to connect [Flows](#flow-execution-model) through events.

An [Edge](#edges) is a simple data structure (see [complete structure in Appendix](#complete-edge-data-structure)) that contains the output-node's node-id, outlet-pin-id, outlet-pin-data-type and input-node's node-id, inlet-pin-id, inlet-pin-data-type.

Usually, only pins of the same type can be connected. But Haywire allows for connection between [Data-pins](#pin-system) of different types if there are compatible adapters available. For [Control-pins](#pin-system), there are no data-types and such restrictions are not necessary.

### Control-edges -> Links

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

**The node**

A Haywire node is arguably the most central element of the system. A node consists of

- **[Settings](#settings)** configure the structure / behaviour / functionality of the node
- **[Parameters](#parameters)** to configure its behavior.
- **[DataIns](#inlets--outlets--pins)** and **[Data Outlets](#data-outlets)** to store data to and from other nodes.
- **[Pins](#pin-system)** to connect to and from other nodes.
- **[Worker-function](#worker-function-execution)** that contains its main logic.

These are the basic building blocks of a Haywire graph:

- **Control-nodes**
  Control-nodes are nodes that are generally used to control the flow of execution within the graph. They are defined by having both at least one [Control-pin-inlet](#pin-system) and one [Control-pin-outlet](#pin-system).

- **Data-nodes**
  Data-nodes are nodes that are used to process data within the graph. They are defined by having no [Control-pins](#pin-system) at all.

- **Event-nodes**
  Event-nodes are a special kind of Control-nodes used to trigger execution within the [Graph](#graph-structure). They are defined by having no pin-inlets at all. With the exception of the [Source-node](#node-types), Event-nodes are not allowed inside of [Graph-nodes](#graph-as-node-pattern).

- **Output-nodes**
  Output-nodes are a special kind of Control-nodes used to terminate execution within the [Graph](#graph-structure). They are defined by having no pin-outlets at all. With the exception of the [Sink-node](#node-types), output-nodes are not allowed inside of [Graph-nodes](#graph-as-node-pattern).

- **Graph-nodes**
  
  Graph-nodes are nodes that are used to encapsulate a [subgraph](#graph-as-node-pattern) within the graph. They can have [Control-pins](#pin-system) and/or [Data-pins](#pin-system), Thus they can come on two flavors: **Control-graph-nodes** and **Data-graph-nodes**. Like their siblings, **Control-node** and **Data-node**, they are assembled and executed/evaluated in the same fashion. Like other nodes, they can have [variables](#variables).

- **Source-node**
  The Source-node is a special kind of Event-node used only inside [Graph-nodes](#graph-as-node-pattern) to start the execution of the Graph-node. The Source-node's pin-outlets are dynamically configured by its Graph-node defined pin-inlets.

- **Sink-node**
  The Sink-node is a special kind of output-node used to only inside [Graph-nodes](#graph-as-node-pattern) to exit the execution of the Graph-node. The Sink-node's pin-inlets are dynamically configured by its Graph-node defined pin-outlets.

- **Loopback-node** Flag
  The Loopback-node is a [Control-node](#node-types) with a flag that tells the VM to loop back execution within the Control-flow to itself if the branch ends without an [Output-node](#node-types). Loopback-nodes are for example For-Loops, While-Loops, Sequences and other Control-flow constructs that allow *sequential* branching of the Control-flow. Switches or If-Statements are not Loopback-nodes since they do *conditional* branching.

## Node Components

### Settings

[Settings](#settings) define the structure / behaviour / functionality of the node.

- [Settings](#settings) can only be of datatypes that makes them editable through the user interface.
- Change of [settings](#settings) will trigger a reconfiguration of the node and reevaluation of all the Connections.
  - This can be used to add/remove/enable/disable [Settings](#settings), [Parameters](#parameters), [DataIns](#inlets--outlets--pins), [Data Outlets](#data-outlets).
  - This can also lead to a removal of Connections that are not compatible with the new [settings](#settings).
- They have no pins.
- They are only not meant to be accessed by the internal [Worker-function](#worker-function-execution)

### Parameters

[Parameters](#parameters) are values that can be set or changed only by the user through the user interface. For use cases where control through pin-inlet's are **not** desired.

- [Parameters](#parameters) can only be of datatypes that makes them editable through the user interface.
- They have **no** default value
- They have no pins.
- They are only read accessible by the internal [Worker-function](#worker-function-execution)
- When a [Graph](#graph-structure) is stored to file, the value is stored.

### Inlets & Outlets & Pins

#### Pins

[Pins](#pin-system) are the visual icon to connect to and from a node. [Pins](#pin-system) have a selection of different [settings](#settings) that define their behaviour:

- **Flow-type** defines if it is a control, data or callback pin
- **Socket-type** defines if the pin is an inlet (for getting event/data in) or an outlet (for sending event/data out)
- **Data-type** defines the data type the pin is associated with. And which other pins a pin can connect or not connect to.
- **Coupling-type** defines how many connections can be made on the pin. This is either one or many.

The following table shows the only admissible pin configurations:

| Types               | Flow | Socket | Data | Coupling |
| ------------------- | ---- | ------ | ---- | -------- |
| Control-pin inlet   | ctrl | inlet  | --   | many     |
| Control-pin outlet  | ctrl | outlet | --   | one      |
| Data-pin inlet      | data | inlet  | type | one/many |
| Data-pin outlet     | data | outlet | type | many     |
| Callback-pin inlet  | call | inlet  | type | many     |
| Callback-pin outlet | call | outlet | type | many     |

#### Explanation to connection-types

- **Control-pin-outlet** can have only one coupling, since it must be clear which the next node is that needs to be executed.
- **Control-pin-inlet** can have many couplings, since there might be multiple execution paths that lead to this node.
- **Data-pin-outlet** can have many couplings, since multiple nodes might be interested in this data
- **Data-pin-inlet** there are two coupling-types possible, depending on the needed data. in case of many the provided data is in form of a list of values in the specified data-type.
- **Callback-pin-inlet** can have many couplings, since multiple [Event-nodes](#node-types) can require the same callback.
- **Callback-pin-outlet** can have many couplings, since the [Event-node](#node-types) might be interested in multiple callbacks.

#### Control Inlets

Inlets are used execute Control-flow.

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

#### Overview of Nodes Configurables

| Types      | Function      | Default | Stores  | Inlets | Outlets | Visible | Enable | Required |
| ---------- | ------------- | ------- | ------- | ------ | ------- | ------- | ------ | -------- |
| Settings   | Configuration | no      | value   | no     | no      | on/off  | on/off | None     |
| Parameters | Properties    | no      | value   | no     | no      | on/off  | on/off | None     |
| Inlets     | Input         | yes     | default | yes    | no      | on/off  | on/off | Maybe    |
| Outlets    | Output        | no      | none    | no     | yes     | on/off  | on/off | None     |

none = can not be set / has no effect
Default = has default value
Stores = data that is stored to file and is loaded.
Visible = can be set by the user to be visible in the node UI.
Enable = can be set to be on/off by a [Parameter](#parameters).
Required = can be set to be required.

### Worker Function Execution

This is where the real work is done. Each node, no matter of type, has one [Worker-function](#worker-function-execution). However, depending of the type of the node, the [Worker-function](#worker-function-execution) is called through different mechanisms.

The [Worker-function](#worker-function-execution) has access to the nodes internal [Parameters](#parameters), [Variables](#variables), DataIns and is able to set the [Data Outlets](#data-outlets).

It returns status information that is interpreted differently depending on the execution/evaluation mechanism.

More details can by found under [Worker function execution/evaluation](#worker-function-execution/evaluation)

### Data Types and Categories

The inlets or outlets define the Data-types and Data-category they require. This can be any python class. For the UI, Haywire provides a set of icons and colors to denote specific data-types.

The Data-types include `int`, `float`, `str`, `bool`, `bytes`, `object`
The Data-category include `scalar`, `list`, `tuple`, `set`, `array`, `map`, `dictionary`

ComfyUI follows a different strategy. It has keywords for each data-type. <https://docs.comfy.org/custom-nodes/backend/datatypes>

---

# Advanced Features

## Lazy Evaluation

This feature makes the evaluation of the Data-Flow more efficient by excluding unnecessary computations. This is done by specifying inside the node under which conditions which Inlets can be ignored to be evaluated.

The Lazy Evaluation algorithm covers differnt areas of the haywire system, from node initialisation to execution.

The [assembler](#assembly-process) is responsible for generating the [localized Data-Flow](#control-flow-vs-data-flow) for each [Control-node](#node-types). If Inlets have a lazy evaluation flag and the Data-Flows can be lazily evaluated, the VirtualMachine that lazily evaluates the Data-Flow would need some additional information beforehand. Haywire has the method `def CHECK_LAZY` that is called before the [localized Data-Flow](#control-flow-vs-data-flow) can be evaluated lazily or not. If this is the case, depending on which Data Inlets are required, only certain steps of the [localized Data-Flow](#control-flow-vs-data-flow) need to be evaluated.

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

# Generation

Under Generation falls currently everything  that is involved until a complete Graph is instantiated for further processing.

This includes

## Finding and Loading available Node Libraries

loading nodes from filesystem: [ComfyUI/nodes.py at 78672d0ee6d20d8269f324474643e5cc00f1c348 ? comfyanonymous/ComfyUI ? GitHub](https://github.com/comfyanonymous/ComfyUI/blob/78672d0ee6d20d8269f324474643e5cc00f1c348/nodes.py#L2168)

## Loading Graphs from JSON and instantiating required Nodes

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

#### Graph Validation

- Checking for graph validity
  - Node checking:
    - Checking for validity of node-types (see chapter of [node types](#node-types) for details)
    - Checking for multiples of the same [Event-nodes](#node-types) (not allowed since undefined which Control-flow is should have precedence)
    - Checking for [source](#node-types) and [sink nodes](#node-types) inside [Graph-nodes](#graph-as-node-pattern) (required to be functional)

#### Graph Cleaning

- Clearing all connections that are stored inside pins. (clean house)

#### Graph Preprocessing

- Storing Control-flow connections in their respective outlet-pins. This is because the Control-flow propagates in the direction from [Control-pin-outlet](#pin-system) to [Control-pin-inlet](#pin-system). The next-to-be-executed-controlnode [Control-pin-inlet](#pin-system) doesn't need to know with what node it is connected. It is actually allowed to be connected to multiple nodes. Once the node is executed, the VM will inform the from where the Control-flow came from.
- Storing Data-flow connections in their respective inlet-pins. This is because the Data-flow is assembled through backpropagation from the [Data-pin-inlets](#pin-system) of its respective [Control-node](#node-types). the [Data-pin-outlets](#pin-system) doesn't need to know with which inlet-pins it is connected to at the time of [Assembly](#assembly-process). once the Data-flow is created though, the outlet-pins "know" where to send their results. (this mechanism is not yet defined and can benefit from a suitable solution)

#### Flow identification

- Identifies different Control-flows with the [Graph](#graph-structure).
  - A Control-flows needs at least one [Event-node](#node-types)
  - A Control-flows is considered separate from another Control-flows when there is no connection (control or data) between their respective nodes-trees.
    - The only exception here is the [callback-connection](#callback-system).

#### Flow assembly

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

# Interpreter

- The [Interpreter](#interpreter) is responsible for running the individual [Flows](#flow-execution-model) in their own Threads.
- It is responsible for piping external events to trigger the [Flows](#flow-execution-model) that have matching [Event-nodes](#node-types).

---

## Outstanding Design Questions

### For Author Clarification

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

### Suggested Enhancements

**?�� Performance Monitoring**: Add execution profiling to identify bottlenecks in complex graphs

**?�� Debug Infrastructure**: Visual execution tracing, breakpoint support, step-through debugging

**?�� Module System**: Standardized packaging/distribution for custom nodes and abstractions

**?�� Error Handling**: Comprehensive error propagation and recovery strategies

---

# Appendix

## Complete Edge Data Structure

An [Edge](#edges) is a simple data structure that contains the:

- **output-node's**
  - node-id
  - outlet-pin-id
  - outlet-pin-data-type
- **input-node's**
  - node-id
  - inlet-pin-id
  - inlet-pin-data-type

## Complete Node Definition Template

```python
class HaywireMeta(type):
    """
    Meta class for the HaywireNode class. Makes node declaration objects available in the class's scope
    """
    Settings = []
    Parameters = []
    Inlets = []
    Outlets = []

@abstractNode
class HaywireNode(object, metaclass=HaywireMeta):

    def __init__(self, node_id, graph):
        self.graph = graph
        self.node_id = node_id
        self.node_display_name = 'Node Name'
        self.node_description = 'Node Description'
        self.node_name = 'Node_NAME'
        self.node_package = 'org.github.maybites.haywire.nodes'
        self.node_library_name = '3rdPartyLibrary'
        self.node_library_url = 'https://haywire.io/docs/node-help'
        self.node_search_tags = ['add', 'sub', 'math', 'vector']
        self.node_menu = 'misc/custom'
        self.node_version = '0.0.0'
        self.node_author = 'Customer'
        self.node_author_url = 'https://customer.org'
        self.help_md = None
        self.help_url = 'https://haywire.io/docs/node-help'
        self.is_control_node = False # Set_automatically()
        self.is_data_node = True # Set_automatically()
        self.is_loopback_node = False
        self.can_be_muted = True
        self.is_muted = False
        self.mute_connection = ['control_in_ID', 'control_out_ID']
        self.ui_default_color = '#FFFFFF'
        self.ui_custom_color = '#000000'
        self.ui_posX = 0
        self.ui_posY = 0
        self.ui_width = 100
        self.ui_height = 100
        self.ui_width_min = -1
        self.ui_height_min = -1
        self.ui_is_collapsable = True
        self.ui_is_collapsed = False
        self.ui_is_condensable = True
        self.ui_is_condensed = False
        self.ui_is_pinned = False
        self.ui_icon = None
        self.ui_component = None
        self.allows_variables = False


class BaseNode(HaywireNode):

    def __init__(self, *args, **kwargs):
        super(BaseNode, self).__init__(*args, **kwargs)
        self.node_name = 'Node_NAME'
        self.node_library_module = 'Custom'
        self.node_library_name = 'Custom'
        self.node_library_url = 'https://haywire.io/docs/node-help'
        self.node_version = '0.0.0'
        self.node_author = 'Customer'
        self.node_display_name = 'Node Name'
        self.node_description = 'Node Description'
        self.help_md = './node_id/node_help.md'
        self.help_url = 'https://haywire.io/docs/node-help'

    @classmethod
    def Settings(cls):
        # some code
        return{
            {
                name: 'Settings Name',
                id: 'settings_id',
                description: 'Settings Description',
                data_type: Datatype,
                data_category: SCALAR,
                value: value,
                callback: self._on_parameter_changed,
                is_visible: True,
                is_enabled: True,
            }
        }

    # defining Parameters
    @classmethod
    def Parameter(cls):
        # some code
        return {
            {
                name: 'Parameter Name',
                id: 'parameter_id',
                description: 'Parameter Description',
                datatype: Datatype,
                value: value,
                callback: self._on_parameter_changed,
                is_visible: True,
                is_enabled: True
            }
        }


    # defining Data inlets
    @classmethod
    def Inlets(cls):
        # some code
        return {
            {
                flow_type: 'ctrl',
                coupling_type: MANY,
                name: 'Control Name',
                id: 'ctrl_in_ID',
                description: 'Control Description',
            },
            {
                flow_type: 'data',
                coupling_type: ONE,
                coupling_mode: REQUIRED,
                name: 'Data Name',
                id: 'data_in_ID',
                description: 'Data Description',
                data_type: int,
                data_cat: SCALAR,
                is_visible: True,
                is_enabled: True,
                is_lazy: True,
                default: default
            },
        }

    # defining Data outlets
    Outlets(
        {
            flow_type: 'ctrl',
            coupling_type: One,
            name: 'Control Name',
            id: 'ctrl_out_ID',
            description: 'Control Description',
        },
        {
            flow_type: 'data',
            coupling_type: MANY,
            name: 'Data Name',
            id: 'data_out_ID',
            description: 'Data Description',
            data_type: int,
            data_cat: SCALAR,
            is_visible: True,
            is_enabled: True,
        },
    )

    # defining worker function
    def worker(self, global_data: dict, local_data: dict, control_node_id: str, control_pin_outlet_id: str):
        # Implement your worker logic here
        # ...

        return {
            global_data: global_data,
            local_data: local_data,
            node_id: node_id,
            node_pin_id: node_pin_id
        }

    def SETTINGS_CHANGED(cls):
        # Implement logic to handle settings changes
        pass

    @classmethod
    def CHECK_LAZY(cls):
        # checks if there is a condition that allows lazy evaluation. If this is the case, it sets the LAZY_MASK
        # return True is
        return False

    @classmethod
    def HAS_CHANGED(cls):
        # Method to check if a reference to the outside of the system (like a file) has changed.
        # returns True if it has changed, otherwise false.
        return False

    @classmethod
    def VALIDATE_INPUTS(cls):
        # Validate the parameters. Not clear anymore why this might be necessary. ComfyUI has this implemented..
        #
        return True
```

### Complete Node Initialization Sequence

```console
# Initialization

1. first the node is initialized, calling __init__
2. Calling SETTINGS to set the Settings.
3. Calling SETTINGS_CHANGED to dynamically configure the node.
4. Calling PARAMETERS to set the Parameters.
5. Calling INLETS to set the Inlets.
6. Calling OUTLETS to set the Outlets.

# Assembly

1. Calling CHECK_LAZY on the Data-node to see if there are lazy Inlets to steer the backpropagation.

# Evaluation localized Data-Flow

1. Calling CHECK_LAZY on the Control-node generate the LAZY_MASK.
2. Calling CHECK_LAZY on the Data-node to see if there is the need for re-assembly.
3. Calling HAS_CHANGED on the Data-node to see if there is change that is not from UI or Upstream nodes
4. Calling VALIDATE_INPUTS on the Data-node to validate the inputs before calling the worker FUNCTION.
5. Calling the worker FUNCTION on

# Execution Control-node

1. Calling VALIDATE_INPUTS on the Control-node to validate the inputs before calling the worker FUNCTION.
2. Calling the worker FUNCTION on
```

## Complete Lazy Evaluation Algorithm

**Algorithm:**

**Setup** of a [Control-node](#node-types)

- Some Inlets are configured to be lazy
- A CHECK_LAZY function is defined to determine if the condition for a lazy evaluation is given.

**Setup** of a [Data-node](#node-types) with the [localized Data-Flow](#control-flow-vs-data-flow) of this [Control-node](#node-types)

- Some Inlets are configured to be lazy
- A CHECK_LAZY function is defined to determine if the condition for a lazy evaluation is given.

**[Assembly](#assembly-process)**

- On the [Control-node](#node-types), the [assembler](#assembly-process) creates a bit mask with a bit for each data-inlet. each data-inlet gets its own bit mask called EVAL_MASK where the bit that represents the inlet is set to 1, while all other bits are set to 0.
- On the [Data-node](#node-types), the CHECK_LAZY function is called to determine which Data-inlets to follow in the backpropagation.(This, by the way has a severe edge case: the CHECK_LAZY function on a [Data-node](#node-types) should make its decision at assembly time for performance reasons. Otherwise the re-assembly of the [localized Data-Flow](#control-flow-vs-data-flow) would be required on each execution of the [Control-node](#node-types), which we want to avoid. But implementing [Lazy Evaluation](#lazy-evaluation) in a consistent manner for the user means that changes of [Properties](#parameters) or Inlets that could affect this decision on the [Data-node](#node-types) during runtime actually needs to trigger a re-assembly of the [localized Data-Flow](#control-flow-vs-data-flow). Otherwise, the evaluation of the Data-Flow could lead to incoherent results. A slight performance penalty is preferable over an inconsistent user experience.)
- Upon generation of the [localized Data-Flow](#control-flow-vs-data-flow), this bit mask is passed on during the backpropagation, and is binary OR'ed with other bit masks from the same [Control-node](#node-types) if they merge at that specific [Data-node](#node-types). This OR'ed bit mask is then passed further during backpropagation. At the end there is a list of all the required [Data-nodes](#node-types) and their respective OR'ed bit masks (EVAL_MASK). Then the correct sequence of [Data-nodes](#node-types) is determined to evaluate the Data-Flow correctly. This EVAL_MASK shows which Data-inlets require the evaluation of this specific [Data-node](#node-types).

**Evaluation**

- On execution of the [Control-node](#node-types), the VM creates a bit mask called LAZY_MASK with a bit for each data-inlet, all set to 1.
- then the CHECK_LAZY function is called to determine if the Data-Flow can be evaluated lazily or not. If this is the case, it sets the bits inside LAZY_MASK representing the data-inlets that are not needed to 0, while all others stay 1.
- Then the [localized Data-Flow](#control-flow-vs-data-flow) is evaluated:
  - It goes to the next [Data-node](#node-types) in the sequence.
  - First it checks if the [Data-Nodes](#node-types) CHECK_LAZY function has a different result than the previous run (i.e. during [Assembly](#assembly-process)).
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

It is not clear yet how fast the reassembly of the [localized Data-Flow](#control-flow-vs-data-flow) from scratch is. I hope for an efficient algorithm. Depending on the time saved by lazy evaluation, it might be worth it. Its left to the node-designer to decide if such an effort makes sense. If there is no CHECK_LAZY function defined, the algorithm should run at nominal speed. The additional binary AND operation and if statements in each step should be negligible.
