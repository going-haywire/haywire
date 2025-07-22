# First draft for the Haywire node system

The following draft is created by Martin Fröhlich (aka maybites) and released under [CC-BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/4.0/). (c) 2025

Haywire is a Blueprint inspired node system that follows the principle of an execution flow system.

Notable open source projects that realize something similar but with different use cases in mind:

* [Floppy](https://github.com/JLuebben/Floppy) based on python
* [Box](https://github.com/p-ranav/box) based on python
* [CablesGL](https://cables.gl/) based on javascript

## Execution Flow vs Data Flow

Unlike pure dataflow systems ([ComfyUI](https://github.com/comfyanonymous/ComfyUI), [Langflow](https://github.com/langflow-ai/langflow), [ChaiNNer](https://github.com/chaiNNer-org/chaiNNer), [Ryven](https://github.com/leon-thomm/Ryven), [etc.](../research/nodes/_Execution_Classification.md)) that primarily pass data between nodes, Haywire uses an execution flow model in combination with a data flow model:

* Connections between control-pins specifiy the order of operations
* Connections between data-pins pass values between nodes
* This dual-pin system allows for imperative-style programming within a visual graph
* Nodes with control-pins are called control-nodes, those without are data-nodes
* The graph that is discribed by the connections between control-pins is called control-graph and compiled into the control-flow
* the graph that is discribed by the connections between data-pins is called data-graph and compiled into a data-flow

This combination of explicit control-flow, data-flow, state management, and just in time compilation strategies allows Haywires to support more complex execution patterns than simple dataflow systems while maintaining visual clarity.

## Control-Flow

Haywire uses imperative execution following connection between control-pins:

* Start at event control-nodes (BeginPlay, Tick, InputAction, etc.)
* Follow control-pins from node to node
* Each control-pin connection is essentially a "goto next instruction"
* No global dependency analysis needed - the execution of the control-flow is simply the follwoing of subsequent control-pins

## Data-flow: Dependency Resolution

Nodes without control-pins use topological sorting:

* Analyze the local graph around an control-node to identify a local node-related dependency tree of data-nodes
* Create execution sequence based on these data dependencies called a localized data-flow
* Everytime a control-node is executed, its localized data-flow is evaluated.

## State Machine Architecture

Haywires graph don't execute as a simple tree traversal. Instead, they use a state machine approach:

* Each node can have multiple execution states (pending, executing, completed)
* The Haywire Virtual Machine (VM) maintains an execution stack
* Nodes can pause execution and resume later, enabling complex control flows

The Haywire Virtual Machine handles the complex orchestration:

### Execution Context Management:

* Maintains the current execution state and call stack
* Tracks which node should execute next based on control-pin connections
* Manages local variables and parameter passing between nodes

### Control Flow Translation:

* Branch nodes become conditional jumps in the VM
* Loop nodes become loop constructs with iteration state
* Sequence nodes become ordered function call chains

### State Preservation:

* The VM can pause execution (for async operations like delays)
* Maintains execution context across frame boundaries
* Handles re-entrant execution for things like event callbacks

## Loop and Branch Handling

For loops and conditionals, Haywire use specialized control-flow nodes:

* Branch nodes evaluate conditions and direct execution down different paths
* Loop nodes (ForLoop, WhileLoop) maintain internal state and can re-execute connected subgraphs
* The VM tracks loop iteration state and manages the execution context

## Event-Driven Execution

Haywires uses an event-driven model:

* Execution begins at event control-nodes (BeginPlay, Tick, input events)
* Multiple execution chains can run independently (to be seen - not sure if that can be made to work)
* The system can handle asynchronous operations and callbacks

## Just-In-Time Compilation

A Haywire-graph's core entity consist of Nodes and Connections. In a compilation step this graph is converted into executable flows. (the term compilation is here loosly used to indicate the creation of a new data structure that can be executed (flow) rather than describe (graph))

* The graph is analyzed to identify execution paths, starting at event control-nodes and following control-pins
* At each control-node, its data-pin node dependencies are separated into a local data-graph with a predefined sequence of execution for each involved node called a localized data-flow.
* whenever a the graph is manipulated (connection is added or removed), the just in time compilation mechanism adapts the respective flow to the new graph description.

## The graph

A Haywire graph is basically a collection of nodes, connections and variables.

### A graph is a node

A graph can be treated like a node and thus can be used as such within another graph.

There are three different ways a graph as a node can be used:

* **Subgraph** is a graph that is used only once and inside its parent graph.
* **Function** is a graph that can be used in multiple instances within its parent graph.
* **Module** is a graph that can be used in multiple instances within any graph.

**Subgrapsh** and **Function** are stored with its parent graphs. **Modules** are stored on the local file system and are treated like custom nodes.

## The node

A Haywire node is arguably the most central element of the system. A node consists of

* **variables** to maintain or orchestrate its functionality.
* **pins** to connect to and from other nodes.
* **executable function** that contains its main logic.

### Variables

Variables allow to be set by the user to configure the behaviour / functionality of the node.

* Variables can be of specified datatypes.
* They can be changed via the user interface
* In case of a graph (as a node) the variables are made accessible to nodes within the graph so they can be manipulated by getter and setter nodes.
* They cannot be changed or made accessible by pins.

### Pins

Pins are the way to connect to and from a node. Pins have a selection of different settings that define their behaviour:

* **flow-type** defines if it is a control or data pin
* **socket-type** defines if the pin is an inlet (for getting event/data in) or an outlet (for sending event/data out)
* **data-type** defines which other pins a pin can connect or not connect to.
* **link-type** defines how many connections can be made on the pin. This is either one or many.

The following table shows the only admissible pin configurations:

| Types              | Flow | Socket | Data | Link     |
| ------------------ | ---- | ------ | ---- | -------- |
| control-pin inlet  | ctrl | inlet  | --   | many     |
| control-pin outlet | ctrl | outlet | --   | one      |
| data-pin inlet     | data | inlet  | type | one/many |
| data-pin outlet    | data | outlet | type | many     |

#### Explanation to link-types

* **control-pin outlet** can only have one link, since it must be clear which the next node is that needs to be executed.
* **control-pin inlet** can have many links, since there might be mulitple execution paths that lead to this node.
* **data-pin outlet** can have many links, since multiple nodes might be interested in this data
* **data-pin inlet** there are two link-types possible, depending on the needed data. in case of many the provided data is in form of a list of values in the specified data-type.

### Connections

A connection is simple data structures that contain the outlet-pins node-id and pin-id and the inlets-pin node-id and pin-id.

#### Loops

* Loops are allowed for control-flows.
* Loops are **NOT** allowed for data-flows. (There is a kind of exception though: )

### Executable Function

This is where the real work is done. Each node, no matter of type, has one executable function. However, depending of the type of the node, the "function" is called through different mechanisms.

The "function" has access to the nodes internal variables (not sure if it should be read only - remark by MAF) , the data-pin-inlets values and is able to set the data-pin-outlets.

It returns status information that is interpreted differently depending on the execution mechanism.

#### Function for control-nodes

The VM follows the control-pins from node to node. To recap quickly: During the compilation of the graph, the connections, which are stored within the graph, are transfered to the respective pins. After compilation of the graph, there is a control-flow containing each connected control-node (TBD).

0. After the VM exectuted the previous control-node, its return value indicates which control-pin-outlet it has to follow. This identifies the next to be executed control-node.

1. Before the control-node's "function" is called, it first executes the control-node's localized data-flow to update the data-pin-inlets.

2. Then it executes the "function". It provides a reference to

   * **A global context**: The global context comes in form of a dict and contains any data a dict can contain, including user specific data and references to data stored outside of the evaluation engine.

   * **A local context**: The local context comes in form of a dict and gives access to the local graph and its variables.

   * **control-pin**: The identity of the control-pin-input that is executed.

   * **control-node**: The identity of the node that called.

   * etc.

3. Within the "function" at the end of its process,

   * it sets the repective data-pin-outlets.

4. then returns status information that includes the information which control-pin-outlet is to be followed.

5. The VM takes this info, identifies the next control-node

6. ...and repeats above process..

#### Function for data-nodes

To recap quickly: After compilation of the graph, there is a localized data-flow for each control-node. A localized data-flow is nothing but a sorted list of the data-nodes that need to be executed in sequence to evaluate the values for the data-pin-inlets of the control-node.

Before the exection of the "function" of a control-node, its localized data-flow is **required** to be executed first.

The execution of an individual data-node follows these steps:

Before the data-node's "function" is called, it checks first if any of its own data-pin-inlets are dirty (value has changed).

1. If this is the case:

   1. then it executes the "function". It provides a reference to

        * **A global context**: The global context comes in form of a dict and contains any data a dict can contain, including user specific data and references to data stored outside of the evaluation engine.

        * **A local context**: The local context comes in form of a dict and gives access to the local graph and its variables.

    2. Within the "function" at the end of its process,

        * it updated the data-pin-outlets so its connected data-pin-inlets are set to dirty (value has changed).

2. If there are no dirty inlets:

   * the function is not called. And no outlets are updated.

3. The sequence hopps to the next data-node.

4. .. and so it continues...

### Data-types

TBD - More research is needed to figure out how this can be handled.

### Compilation of graph

Lets first focus on a complete compilation of a graph. This happens when a graph is loaded from a file.

Once the graph is created, a compilation is necessary to have an executable control-flow.

These are the (rough) steps necessary to get an executable flow.

* Clearing all connections that are stored inside pins.
* Storing control-flow connections in their respective outlet-pins. This is because the control-flow propagates in the direction from control-pin-outlet to control-pin-inlet. The next-to-be-executed-node control-pin-inlet doesn't need to know with what node it is connected. The VM takes care of this.
* Storing data-flow connections in their respective inlet-pins. This is because the data-flow is generated from a backpropagation from the data-pin-inlets of its respective control-node. the data-pin-outlets doesn't need to know with which inlet-pins it is connected at the time of compilation. once the data-flow is created though, the inlet-pins "know" where to send their results. (this mechanism is not yet clear)
* Stepping through each control-node:
    * its data-pin-inlet dependencies are separated into a localized data-graph (containing only nodes and connections that influence the data-pin-inlets of the control-node in focus).
    * the data graph is sorted into a predefined sequence of execution called a localized data-flow.
    * the localized data-flow is stored within the control-node
* It does so iteratively with each graph-as-a-node as well.
* It identifies
