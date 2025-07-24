# First draft for the Haywire node system

The following draft is created by Martin Fröhlich (aka maybites) and released under [CC-BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/4.0/). (c) 2025

Haywire is a Blueprint inspired node system that follows the principle of an execution flow system.

Notable open source projects that realize something similar but with different use cases in mind:

* [Floppy](https://github.com/JLuebben/Floppy) based on python
* [Box](https://github.com/p-ranav/box) based on python
* [CablesGL](https://cables.gl/) based on javascript

### Execution Flow vs Data Flow

Unlike pure dataflow systems ([ComfyUI](https://github.com/comfyanonymous/ComfyUI), [Langflow](https://github.com/langflow-ai/langflow), [ChaiNNer](https://github.com/chaiNNer-org/chaiNNer), [Ryven](https://github.com/leon-thomm/Ryven), [etc.](../research/nodes/_Execution_Classification.md)) that primarily pass data between nodes, Haywire uses an execution flow model in combination with a data flow model:

* Connections between Control-pins specifiy the order of operations
* Connections between Data-pins pass values between nodes
* This dual-pin system allows for imperative-style programming within a visual graph
* Nodes with Control-pins are called Control-nodes, those without are Data-nodes
* The graph that is discribed by the connections between Control-pins is called Control-graph and assembled into the Control-flow
* the graph that is discribed by the connections between Data-pins is called Data-graph and assembled into a Data-flow

This combination of explicit Control-flow, Data-flow, state management, and just in time Assembly strategies allows Haywires to support more complex execution patterns than simple dataflow systems while maintaining visual clarity.

## State Machine Architecture

Haywires graph don't execute as a simple tree traversal. Instead, they use a state machine approach:

* Each node can have multiple execution states (pending, executing, completed)
* The Haywire Virtual Machine (VM) maintains an execution stack
* Nodes can pause execution and resume later, enabling complex control flows

The Haywire Virtual Machine handles the complex orchestration:

### Execution Context Management:
* Maintains the current execution state and call stack
* Tracks which node should execute next based on Control-pin connections
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
For loops and conditionals, Haywire use specialized Control-flow nodes:

* Branch nodes evaluate conditions and direct execution down different paths
* Loop nodes (ForLoop, WhileLoop) maintain internal state and can re-execute connected sub-control-graphs
* The VM tracks loop iteration state and manages the evaluation context

## Event-Driven Execution
Haywires uses an event-driven model:

* Execution begins at Event-nodes (BeginPlay, Tick, input events)
* Multiple execution chains (called Flows) can run independently
* The system can handle asynchronous operations and callbacks

## The Graph
The Haywire graph is a data structure that describes the flow of data and control between nodes. As such, it is a collection of Parameters, Variables, and instantiations of Nodes, Connections, Subgraphs and Abstractions. All are described further down in their respective sections.

* A Graph can contain multiple disconnected node-trees that are assembled into individual Flows.
* A Graph cannot be executed directly. Only Flows can be executed.

### The Graph-node: A graph is also a node
A graph can be treated like a node and thus can be used as such within another graph: a Graph-node.

There are three different ways a Graph-node can be implemented:

* **Subgraph** is a graph that is used only once and inside its parent graph.
* **Abstraction** is a graph that can be used in multiple instances within its parent graph.
* **Module** is a graph that can be used in multiple instances within any graph.

**Subgraphs** and **Abstractions** are stored with their parent graphs. **Modules** are stored on the local file system and are treated like custom nodes.

As with nodes, a Graph-node can be of the type control or data, depending if it contains a Control-pin.

Requirements:

* A Graph-node **must** contain one Source-node and one Sink-node and **cannot** have any other Event- or Output-nodes.

## Connections
There are three types of connections:

* **Control-connections** are used to control the flow of execution between nodes.
* **Data-connections** are used to transfer data between nodes.
* **Callback-connections** are used to trigger an Event-node from another flow. Contrary to Control- and Data-connections, Callback-connections are only used during the Assembly step to connect flows through events.

A connection is simple data structure that contains the outlet-pins node-id and pin-id and the inlets-pin node-id and pin-id.

### Cycles
Cycles are connections between nodes that form a loop.

* Cycles are allowed for Control-connections.
* Cycles are **NOT** allowed for Data-connections.
  * There is an exception though: if the data-connection-cycle is passing through a Control-node, it is allowed. This is because Control-nodes are not evaluated within a localized data flow.

## Flows
Flows are used to organize and execute a sequence of nodes. A Flow is assembled by the Assembler from a Graph. A Flow has always at least one Event-node as an entry point.

Each Flow keeps a reference of the Graph it is assembled from and uses its instantiations of Nodes, Subgraphs etc to execute/evaluate the nodes. Thus, during the Interpretation of a Flow, the Graph is used as the database of the Flow. Once the Interpretation is finished, the Graph is reset to its default state.

### Control-flow vs Data-flow
Haywire uses a Control- (also known as an Execution-) flow model in combination with a Data-flow model.

* Control-connections specify the order of operations
* Data-connections pass values between nodes
* The graph that is discribed by the Control-connections is called Control-graph and assembled into the Control-flow
* the graph that is discribed by the Data-connections is called Data-graph and assembled into a Data-flow

During the Assembly, the control-graph is traversed and the Control-flow is assembled. From each Control-node, the Data-graph is traversed and the localized Data-flow is assembled.

### Control-flow
* Start at Event-nodes (BeginPlay, Tick, InputAction, etc.)
* Follow Control-connections from Control-node to Control-node
* Each control connection is essentially a "goto next instruction"

### localized Data-flow: localized dependency resolution
* Analyze the local graph around an Control-node to identify a local node-related dependency tree of Data-nodes
* Create evaluation sequence based on these data dependencies called a localized Data-flow
* Everytime a Control-node is executed, its localized Data-flow is evaluated.

## The node
A Haywire node is arguably the most central element of the system. A node consists of

* **Parameters** to configure its behavior. Has default values can be overridden by the user. Are read only accessible by the Worker-function.
* **Variables** to maintain or orchestrate its functionality. Can be read and written by the Worker-function.
* **Pins** to connect to and from other nodes.
* **Worker-function** that contains its main logic.

### Node Types
These are the basic building blocks of a Haywire graph:

* **Control-nodes**
Control-nodes are nodes that are used to control the flow of execution within the graph. They are defined by having both at least one Control-pin-inlet and one Control-pin-outlet.

* **Data-nodes**
Data-nodes are nodes that are used to process data within the graph. They are defined by having no Control-pins at all.

* **Graph-nodes**
Graph-nodes are nodes that are used to encapsulate a subgraph within the graph. They can have Control-pins and/or Data-pins, Thus they can come on two flavors: **control-Graph-nodes** and **Data-graph-nodes**. Like their siblings, **Control-node** and **Data-node**, they are compiled and executed in the same fashion. Like other nodes, they can have variables.

* **Event-nodes**
Event-nodes are a special kind of Control-nodes used to trigger execution within the graph. They are defined by having no pin-inlets at all. With the exception of the Source-node, Event-nodes are not allowed inside of Graph-nodes.

* **Output-nodes**
Output-nodes are a special kind of Control-nodes used to terminate execution within the graph. They are defined by having no pin-outlets at all. With the exception of the Sink-node, output-nodes are not allowed inside of Graph-nodes.

* **Source-node**
The Source-node is a special kind of Event-node used to enter the graph. The Source-node's pin-outlets are dynamically configured by its parent Graph-node defined pin-inlets.

* **Sink-node**
The Sink-node is a special kind of output-node used to exit the graph. It is defined by having no pin-outlets at all. The Sink-node's pin-inlets are dynamically configured by its parent Graph-node defined pin-outlets.

### Parameters
Parameters can only be set by the user via GUI to configure the behaviour / functionality of the node. They are read only during evaluation.

* Parameters can only be of specified datatypes that makes them editable through the user interface.
* They can be changed via the user interface
* They are not accessible by pins

### Variables
Variables can be set by the user, the internal Worker-function and, in case of a Graph-node, its internal Control-nodes. They are usedto control the behaviour / functionality of the node.

* Variables can be of specified datatypes.
* Variables have a default value.
* Their default value can be set via the user interface.
* In case of a variable in a Graph-node the variables are made accessible to nodes within the graph so they can be manipulated by getter and setter nodes.
* They are not accessible by pins. (only inside a Graph-node via getter or setter nodes and their respective pins)
* When a Graph is stored to file, only the default value is stored.

### Pins
Pins are the way to connect to and from a node. Pins have a selection of different settings that define their behaviour:

* **flow-type** defines if it is a control or data pin
* **socket-type** defines if the pin is an inlet (for getting event/data in) or an outlet (for sending event/data out)
* **data-type** defines the data type the pin is associated with. And which other pins a pin can connect or not connect to.
* **link-type** defines how many connections can be made on the pin. This is either one or many.

The following table shows the only admissible pin configurations:

| Types               | Flow | Socket | Data | Link     |
| ------------------- | ---- | ------ | ---- | -------- |
| Control-pin inlet   | ctrl | inlet  | --   | many     |
| Control-pin outlet  | ctrl | outlet | --   | one      |
| Data-pin inlet      | data | inlet  | type | one/many |
| Data-pin outlet     | data | outlet | type | many     |
| Callback-pin inlet  | call | inlet  | type | many     |
| Callback-pin outlet | call | outlet | type | many     |

#### Explanation to link-types
* **Control-pin-outlet** can only have one link, since it must be clear which the next node is that needs to be executed.
* **Control-pin-inlet** can have many links, since there might be mulitple execution paths that lead to this node.
* **Data-pin-outlet** can have many links, since multiple nodes might be interested in this data
* **Data-pin-inlet** there are two link-types possible, depending on the needed data. in case of many the provided data is in form of a list of values in the specified data-type.
* **Callback-pin-inlet** can have multiple links, since multiple Event-nodes can require the same callback.
* **Callback-pin-outlet** can have multiple links, since the Event-node might be interested in multiple callbacks.

### Worker-function
This is where the real work is done. Each node, no matter of type, has one Worker-function. However, depending of the type of the node, the Worker-function is called through different mechanisms.

The Worker-function has access to the nodes internal Parameters (read only), Variables, the Data-pin-inlets values and is able to set the Data-pin-outlets.

It returns status information that is interpreted differently depending on the execution mechanism.

#### Worker-function for Control-nodes
The VM follows the Control-pins from node to node. To recap quickly: During the Assembly of the Graph, the connections, which are stored within the graph, are transfered to the respective pins. After Assembly of the Graph, there is a Control-flow containing each connected Control-node (TBD).

0. After the VM executed the previous Control-node, its return value indicates which Control-pin-outlet it has to follow. This identifies the next to be executed Control-node.

1. Before the Control-node's Worker-function is called, it first evaluates the Control-node's localized Data-flow to update the Data-pin-inlets.

2. Then it executes the Worker-function. It provides a reference to
   * **A global context**: The global context comes in form of a dict and contains any data a dict can contain, including user specific data and references to data stored outside of the evaluation engine.
   * **A local context**: The local context comes in form of a dict and gives access to the local graph and its variables.
   * **Control-pin**: The identity of the Control-pin-input that is executed.
   * **Control-node**: The identity of the node that called.
   * etc.

3. Within the Worker-function at the end of its process,
   * it sets the repective Data-pin-outlets.

4. then returns status information that includes the information which cCntrol-pin-outlet is to be followed.

5. The VM takes this info, identifies the next Control-node

6. ...and repeats above process..

#### Worker-function for Data-nodes
To recap quickly: After Assembly of the graph, there is a localized Data-flow for each Control-node. A localized Data-flow is nothing but a sorted list of the Data-nodes that need to be evaluated in sequence to get the values for the Data-pin-inlets of the Control-node.

Before the execution of the Worker-function of a Control-node, its localized Data-flow is **required** to be evaluated first.

The evaluation of an individual Data-node follows these steps:

Before the Data-node's Worker-function is called, it checks first if any of its own Data-pin-inlets are dirty (value has changed).

1. If this is the case:
  1. then it runs the Worker-function. It provides a reference to
    * **A global context**: The global context comes in form of a dict and contains any data a dict can contain, including user specific data and references to data stored outside of the evaluation engine.
    * **A local context**: The local context comes in form of a dict and gives access to the local graph and its variables.

  2. Within the Worker-function at the end of its process,
    * it updates the Data-pin-outlets so its connected downstream Data-pin-inlets are set to dirty (value has changed).

2. If there are no dirty inlets:
  * the Worker-function is not called. And no outlets are updated.

3. The sequence hopps to the next Data-node.

4. .. and so it continues...

### Data-types

TBD - More research is needed to figure out how this can be handled.

## Callback-connections
Callbacks are used to notify other nodes about events that have occurred. With the Hayire system, it is the mechanism that allows from within executed Flows to trigger other Flows within the same Graph.

Lets first disentangle the concepts of triggers, Events-nodes, Control-connections and Callbacks. In the context of Haywire,

**triggers** are the events that are generated by the outside system, while **Event-nodes** are the mechanism to pass on this trigger into the flow. Once an **Event-node** is triggered, it will emit through its Control-pin-outlet (and its Data-pin-outlet if so required).

**callbacks** is a mechanism to generate a **trigger** from within another flow. From the point of view of an **Event-node**, this looks like an event from the outside system, since it is generated by a flow that runs within a separate thread.

**Callback-pin-outlets can only be implemented by Event-nodes**, since this are the nodes that trigger flows.

On first sight, this seems to be counter-intuitive, why should an Event-node have a Callback-pin-outlet. It is actually listening to a trigger, so shouldn't it have a Callback-pin-inlet instead? The answer is no. The callback connection needs always be initiated by the listener, which is in this case the Event-node that is listening for the event. In other words: The callback connection is used by its node to notify other nodes that it is interested in the event and is asking for a callback. Though this is a bit missleading: the callback connection is only used during the Assembly step. This means that the callback connection is not used during the execution of any of the flows involved.

Also, an Event-node can by definition have no pin-inlets.

## Assembly
As mentioned, Graphs core entity consist of Nodes and Connections. The Assembly converts a Graph into executable Flows. This is realized with the creation of a new data structure that can be executed (Flow) rather than be describtive (Graph)

* The Graph is analyzed to identify execution paths, starting at Event-nodes and following Control-pins
* At each Control-node, its Data-pin node dependencies are separated into a local Data-graph with a predefined sequence of execution for each involved node called a localized Data-flow.
* whenever a the graph is manipulated (connection is added or removed), the just in time Assembly mechanism adapts the respective flow to the new graph description.

Lets first focus on a complete Assembly of a graph into flows:

We assume:
* graph is loaded from a file.
* graph loads its dependencies.
* graph is instantiated.

#### Graph Validation
* Checking for graph validity
  * Node checking:
    * Checking for validity of node-types (see chapter of node types for details)
    * Checking for multiples of the same Event-nodes (not allowed since undefined which Control-flow is should have precedence)
    * Checking for source and sink nodes inside Graph-nodes (required to be functional)

#### Graph Cleaning
* Clearing all connections that are stored inside pins. (clean house)

#### Graph Preprocessing
* Storing Control-flow connections in their respective outlet-pins. This is because the Control-flow propagates in the direction from Control-pin-outlet to Control-pin-inlet. The next-to-be-executed-controlnode Control-pin-inlet doesn't need to know with what node it is connected. It is actually allowed to be connected to multiple nodes. Once the node is executed, the VM will inform the from where the Control-flow came from.
* Storing Data-flow connections in their respective inlet-pins. This is because the Data-flow is assembled through backpropagation from the Data-pin-inlets of its respective Control-node. the Data-pin-outlets doesn't need to know with which inlet-pins it is connected to at the time of Assembly. once the Data-flow is created though, the outlet-pins "know" where to send their results. (this mechanism is not yet defined and can benefit from a suitable solution)

#### Flow identification
* Identifies different Flows with the Graph.
  * A Flow needs at least one Event-node
  * A Flow is considered separate from another Flow when there is no connection (control or data) between their respective nodes-trees.
    * The only exception is the callback-connection.

#### Flow assembly
* Stepping through each Control-node:
    * its Data-pin-inlet dependencies are separated into a localized Data-graph (containing only nodes and connections that influence the Data-pin-inlets of the Control-node in focus).
    * Checking for loops in the Data-graph (not allowed with the exception of loops that contain a Control-node)
    * the Data-graph is sorted into a predefined sequence of executions called a localized Data-flow.
    * the localized Data-flow is stored within the Control-node, ready to be executed.
* It does all of it iteratively with each Graph-node as well.
* It identifies the Event-nodes and makes them available for hooking it up with the execution mechanism of the whole haystack.

#### Just-In-Time Assembly
* This happens whenever a connection is edited. (For a future implementation)
  * This is the case if a node is deleted, but when the node is added.

## Interpreter
* The Interpreter is responsible for running the individual Flows in their own Threads.
* It is responsible for piping external events to trigger the Flows that have matching Event-nodes.

## Question to the model:
- [ ] What works with this spec?
- [ ] What does this specification desperately need to clarify the goal?
- [ ] What is the best way to implement this?
- [ ] Check the Assembly steps for missing requirements and generation steps.
