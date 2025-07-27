# Haywire node system - Specification v1.0.0

## Credits

created by Martin Fröhlich (aka maybites) (c) July 2025

## License

released under [CC-BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/4.0/)

## Introduction

Haywire is a Blueprint inspired node system that follows the principle of an execution flow system.

Notable open source projects that realize something similar but with different use cases in mind:

- [Floppy](https://github.com/JLuebben/Floppy) based on python
- [Box](https://github.com/p-ranav/box) based on python
- [CablesGL](https://cables.gl/) based on javascript

### Execution Flow vs Data Flow

Unlike pure dataflow systems ([ComfyUI](https://github.com/comfyanonymous/ComfyUI), [Langflow](https://github.com/langflow-ai/langflow), [ChaiNNer](https://github.com/chaiNNer-org/chaiNNer), [Ryven](https://github.com/leon-thomm/Ryven), [etc.](../research/nodes/_Execution_Classification.md)) that primarily pass data between nodes, Haywire uses an execution flow model in combination with a data flow model:

- Connections between Control-pins specifiy the order of operations
- Connections between Data-pins pass values between nodes
- This dual-pin system allows for imperative-style programming within a visual graph
- Nodes with Control-pins are called Control-nodes, those without are Data-nodes
- The graph that is discribed by the connections between Control-pins is called Control-graph and assembled into the Control-flow
- the graph that is discribed by the connections between Data-pins is called Data-graph and assembled into a Data-flow

This combination of explicit Control-flow, Data-flow, state management, and just in time Assembly strategies allows Haywires to support more complex execution patterns than simple dataflow systems while maintaining visual clarity.

## State Machine Architecture

Haywires graph don't execute as a simple tree traversal. Instead, they use a state machine approach:

- Each node can have multiple execution states (pending, executing, completed)
- The Haywire Virtual Machine (VM) maintains an execution stack
- Nodes can pause execution and resume later, enabling complex control flows

The Haywire Virtual Machine handles the complex orchestration:

### Execution Context Management:

- Maintains the current execution state and call stack
- Tracks which node should execute next based on Control-pin connections
- Manages local variables and parameter passing between nodes

### Control Flow Translation:

- Branch nodes become conditional jumps in the VM
- Loop nodes become loop constructs with iteration state
- Sequence nodes become ordered function call chains

### State Preservation:

- The VM can pause execution (for async operations like delays)
- Maintains execution context across frame boundaries
- Handles re-entrant execution for things like event callbacks

## Loop and Branch Handling

For loops and conditionals, Haywire use specialized Control-flow nodes:

- Branch nodes evaluate conditions and direct execution down different paths
- Loop nodes (ForLoop, WhileLoop) maintain internal state and can re-execute connected sub-control-graphs
- The VM tracks loop iteration state and manages the evaluation context

## Event-Driven Execution

Haywires uses an event-driven model:

- Execution begins at Event-nodes (BeginPlay, Tick, input events)
- Multiple execution chains (called Flows) can run independently
- The system can handle asynchronous operations and callbacks

## The Graph

The Haywire Graph is a data structure that describes the flow of data and control between nodes. As such, it is a collection of Settings, Parameters, Variables, Connections and instantiations of Nodes and Graph-nodes. All are described further down in their respective sections.

- A Graph can contain multiple disconnected node-trees that are assembled into individual Flows.
- A Graph cannot be executed directly. Only Flows can be executed.

### The Graph-node: A graph is also a node

A Graph can be treated like a node and thus can be used as such within another graph: a Graph-node.

There are three different ways a Graph-node can be implemented:

- **Subgraph** is a graph that is used only once and inside its parent Graph.
- **Abstraction** is a graph that can be used in multiple instances within its parent Graph.
- **Module** is a graph that can be used in multiple instances within any Graph.

**Subgraphs** and **Abstractions** are stored with their parent graphs. **Modules** are stored on the local file system and are treated like custom nodes.

As with nodes, a Graph-node can be of the type control or data, depending if it contains a Control-pin.

Requirements:

- A Graph-node **must** contain one Source-node and one Sink-node and **cannot** have any other Event- or Output-nodes.

## On Connections, Edges, Links and Pipes
To distinguish clearly between the visual representation of a Graph and the functional representation of a Flow, Haywire makes a clear distinction between the two on the level of connections, too. And in order to keep terms clear, when "connection(s)" is used in this text it is meant in a colloquial manner, while Edges, Links, and Pipes are used to describe the effective data representation of the connections. So pay attention to the context in which "connections" are used:

On the Graph level, the connections between the Control- and Data-nodes describe also Edges.
On the Control-Flow level, the connections between the Control-nodes describe also Links.
On the Data-Flow level, the connections between the Data-nodes describe also Pipes.

Links and Pipes come only into existence during the Assembly step and are only used in the orchestration of Control- and Data-Flows.

To summarize, for each Edge there is either a corresponding Link or Pipe and all of them can be called "connections".

### Edges
Edges define the connections between nodes in a Graph.

There are three types of edges:

- **Control-edges** are used to control the flow of execution between nodes.
- **Data-edges** are used to transfer data between nodes.
- **Callback-edges** are used to trigger an Event-node from another Flow. Contrary to Control- and Data-edges, Callback-edges are only used during the Assembly step to connect Flows through events.

An Edge is a simple data structure that contains the
* output-node's
  * node-id
  * outlet-pin-id
  * outlet-pin-data-type
* input-node's
  * node-id
  * inlet-pin-id
  * inlet-pin-data-type

Usually, only pins of the same type can be connected. But Haywire allows for connection between Data-pins of different types if there are compatible adapters available. For Control-pins, there are no data-types and such restrictions are not necessary.

### Control-edges -> Links
TBD

### Data-edges -> Pipes
After the Assembly Process, each Data-pin-outlet that has one/many connections will hold the same number of Pipes. Each Pipe holds within it self the reference to the connected Data-pin-inlet's value. If the outlet-pin-data-type is different from the inlet-pin-data-type, the Pipe also contains an adapter that will automatically transform the data.

The idea: when the nodes worker function is finished and the data-pin-outlet is set, all its containing Pipes will be updated with the new value and automatically cascade the change to the connected data-pin-inlets and set them to dirty.

If an adapter is not available, the Editor should have shown an error when the edge was created. At the latest, the Assembly Process would have thrown an error, too.

### Cycles
Cycles are connections between nodes that form a loop.

- Cycles are allowed for Control-connections.
- Cycles are **NOT** allowed for Data-connections.
  - There is an exception though: if the data-connection-cycle is passing through a Control-node, it is allowed. This is because Control-nodes are not evaluated within a localized data flow.

## Flows
Flows are used to organize and execute a sequence of nodes. A Flow is assembled by the Assembler from a Graph. A Flow has always at least one Event-node as an entry point.

Each Flow keeps a reference of the Graph it is assembled from and uses the Graphs instantiations of Nodes, Subgraphs etc to execute/evaluate the nodes. Thus, during the Interpretation of a Flow, the Graph is used as the database of the Flow. Once the Interpretation is finished, the Graphs nodes are reset to their default state.

### Control-flow vs Data-flow
Haywire uses a Control- (also known as an Execution-) flow model in combination with a Data-flow model.

- Control-connections specify the order of operations
- Data-connections pass values between nodes
- The graph that is discribed by the Control-connections is called Control-graph and assembled into the Control-flow
- the graph that is discribed by the Data-connections is called Data-graph and assembled into a Data-flow

During the Assembly, the Control-connections are traversed and the Control-flow is assembled. Then from each Control-node, the Data-graph is traversed and the localized Data-flow is assembled.

### Control-flow
- Start at Event-nodes (BeginPlay, Tick, InputAction, etc.)
- Follow Control-connections from Control-node to Control-node
- Each control connection is essentially a "goto next instruction"

### localized Data-flow: localized dependency resolution
- Analyze the local graph around an Control-node to identify a local node-related dependency tree of Data-nodes
- Create evaluation sequence based on these data dependencies called a localized Data-flow
- Everytime a Control-node is executed, its localized Data-flow is evaluated.

## The node
A Haywire node is arguably the most central element of the system. A node consists of

- **Settings** configure the structure / behaviour / functionality of the node
- **Parameters** to configure its behavior.
- **DataIns** and **DataOuts** to store data to and from other nodes.
- **Pins** to connect to and from other nodes.
- **Worker-function** that contains its main logic.

### Node Types
These are the basic building blocks of a Haywire graph:

- **Control-nodes**
  Control-nodes are nodes that are generally used to control the flow of execution within the graph. They are defined by having both at least one Control-pin-inlet and one Control-pin-outlet.

- **Data-nodes**
  Data-nodes are nodes that are used to process data within the graph. They are defined by having no Control-pins at all.

- **Graph-nodes**
  Graph-nodes are nodes that are used to encapsulate a subgraph within the graph. They can have Control-pins and/or Data-pins, Thus they can come on two flavors: **Control-graph-nodes** and **Data-graph-nodes**. Like their siblings, **Control-node** and **Data-node**, they are assembled and executed/evaluated in the same fashion. Like other nodes, they can have variables.

- **Event-nodes**
  Event-nodes are a special kind of Control-nodes used to trigger execution within the Graph. They are defined by having no pin-inlets at all. With the exception of the Source-node, Event-nodes are not allowed inside of Graph-nodes.

- **Output-nodes**
  Output-nodes are a special kind of Control-nodes used to terminate execution within the Graph. They are defined by having no pin-outlets at all. With the exception of the Sink-node, output-nodes are not allowed inside of Graph-nodes.

- **Source-node**
  The Source-node is a special kind of Event-node used only inside Graph-nodes to start the execution of the Graph-node. The Source-node's pin-outlets are dynamically configured by its Graph-node defined pin-inlets.

- **Sink-node**
  The Sink-node is a special kind of output-node used to only inside Graph-nodes to exit the execution of the Graph-node. The Sink-node's pin-inlets are dynamically configured by its Graph-node defined pin-outlets.

- **Loopback-node** Flag
  The Loopback-node is a Control-node with a flag that tells the VM to loop back execution within the Control-flow to itself if the branch ends without an Output-node. Loopback-nodes are for example For-Loops, While-Loops, Sequences and other Control-flow constructs that allow *sequential* branching of the Control-flow. Switches or If-Statements are not Loopback-nodes since they do *conditional* branching.


### Variables
Only Graphs have Variables. Variables are used to enhance functionality of the Graph and allow statefullness between nodes and execution runs.

- Variables can be of specified datatypes.
- Variables have a default value that can be set on creation or by the user via the user interface.
- They are read/write accessible by the internal Worker-function
- When a Graph is stored to file, only its settings and the default value are stored.

The reason nodes have no Variables is because they are not meant to be stateful. Nodes are meant to be stateless and their output should only depend on their input. There are exeception though, like the Loopback-nodes that need to be stateful to function properly.

### Settings
Settings define the structure / behaviour / functionality of the node.

- Settings can only be of datatypes that makes them editable through the user interface.
- Change of settings will trigger a reconfiguration of the node and reevaluation of all the Connections.
  - This can be used to add/remove/enable/disable Settings, Parameters, DataIns, DataOuts.
  - This can also lead to a removal of Connections that are not compatible with the new settings.
- They have no pins.
- They are only not meant to be accessed by the internal Worker-function

### Parameters
Parameters are values that can be set or changed only by the user through the user interface. For usecases where control through pin-inlet's are **not** desired.

- Parameters can only be of datatypes that makes them editable through the user interface.
- They have **no** default value
- They have no pins.
- They are only read accessible by the internal Worker-function
- When a Graph is stored to file, the value is stored.

### Inlets & Outlets & Pins

#### Pins
Pins are the visual icon to connect to and from a node. Pins have a selection of different settings that define their behaviour:

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
- **Control-pin-inlet** can have many couplings, since there might be mulitple execution paths that lead to this node.
- **Data-pin-outlet** can have many couplings, since multiple nodes might be interested in this data
- **Data-pin-inlet** there are two coupling-types possible, depending on the needed data. in case of many the provided data is in form of a list of values in the specified data-type.
- **Callback-pin-inlet** can have many couplings, since multiple Event-nodes can require the same callback.
- **Callback-pin-outlet** can have many couplings, since the Event-node might be interested in multiple callbacks.

#### Control Inlets
Inlets are used execute Control-flow.

#### Data Inlets
Inlets are used to receive data.

- Inlets are of specified data_types and data_categories.
- Inlets can have a default value that can be set on creation or by the user via the user interface.
- They are only read accessible by the internal Worker-function
- They can be directly set by Data-pin-inlets.
- They can be set to required or optional to be connected to a Data-pin-outlet.
- If the inlet is set to required, no widget is displayed.
- When a Graph is stored to file, only the default value is stored.
- If the Inlet has a data-type that can be edited via UI, the UI-Widget is displayed and is in effect a virtually attached Data source and sets the Data-pin-inlet like a Data-pin-outlet would.

### DataOuts
DataOuts are used to send data out of a node.

- DataOuts are of specified datatypes.
- DataOuts are **required** to be set by the internal Worker-function. This assures a consistent behavior.
- They are only write accessible by the internal Worker-function.

**The implementation of DataOuts is not yet defined.**

### Overview of Nodes Configurables

| Types          | Function        | Default | Stores  | Inlets | Outlets | Visible  | Enable   | Required |
| -------------- | --------------- | ------- | ------- | ------ | ------- | -------- | -------- | -------- |
| Settings       | Configuration   |   no    | value   |   no   |   no    |  on/off  |  on/off  |  None    |
| Parameters     | Properties      |   no    | value   |   no   |   no    |  on/off  |  on/off  |  None    |
| Inlets         | Input           |   yes   | default |   yes  |   no    |  on/off  |  on/off  |  Maybe   |
| Outlets        | Output          |   no    |  none   |   no   |   yes   |  on/off  |  on/off  |  None    |

none = can not be set / has no effect
Default = has default value
Stores = data that is stored to file and is loaded.
Visible = can be set by the user to be visible in the node UI.
Enable = can be set to be on/off by a Parameter.
Required = can be set to be required.


### Worker-function
This is where the real work is done. Each node, no matter of type, has one Worker-function. However, depending of the type of the node, the Worker-function is called through different mechanisms.

The Worker-function has access to the nodes internal Parameters, Variables, DataIns and is able to set the DataOuts.

It returns status information that is interpreted differently depending on the execution/evaluation mechanism.

#### Worker-function for Control-nodes
The VM follows the Control-pins from node to node. To recap quickly: During the Assembly of the Graph, the connections, which are stored within the graph, are transfered to the respective pins. After Assembly of the Graph, there is a Control-flow containing a reference to each connected Control-node (TBD).

0. After the VM executed the previous Control-node, its return value indicates which Control-pin-outlet it has to follow. This identifies the next to be executed Control-node.

1. Before the Control-node's Worker-function is called, it first evaluates the Control-node's localized Data-flow to update the Data-pin-inlets.

2. Then it executes the Worker-function. It provides a reference to
   - **A global context**: The global context comes in form of a dict and contains any data a dict can contain, including user specific data and references to data stored outside of the evaluation engine.
   - **A local context**: The local context comes in form of a dict and gives access to the local graph and its variables.
   - **Control-pin**: The identity of the Control-pin-input that is executed.
   - **Control-node**: The identity of the node that called.
   - etc.

3. Within the Worker-function at the end of its process,
   - it sets the repective Data-pin-outlets.

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

### Data-types and Data-category

The inlets or outlets define the Data-types and Data-category they require. This can be any python class. For the UI, Haywire provides a set of icons and colors to denote specific data-types.

The Data-types include `int`, `float`, `str`, `bool`, `bytes`, `object`
The Data-category include `scalar`, `list`, `tuple`, `set`, `array`, `map`, `dictionary`

### Lazy Evaluation

ComfyUI: https://docs.comfy.org/custom-nodes/backend/lazy_evaluation

ComfyUI has a feature for DataIns called Lazy Evaluation. This feature can make the evaluation of the Data-Flow more efficient by excluding unnecessary computations. ComfyUI follows a classical Data-Flow Evaluation model by backprogation, so quite different to how Haywire executes/evaluates the Flow.

Nevertheles, the current Haywire specification has the localized Data-Flow, which is evaluated in a strict order. Before the Control-node is executed, the current specification requires that the localized Data-Flow is evaluated.

So, in theory it is possible to expand on this: The assembler is responsible for generating the localized Data-Flow for each Control-node. If Inlets have a lazy evaluation flag and the Data-Flows can be lazyily evaluated, the VirtualMachine that lazily evaluates the Data-Flow would need some additional information beforehand. ComfyUI has the method `def check_lazy_status(self, args)` that is called before its Inlets are evaluated. In Haywire, the VirtualMachine needs also to use such a method to determine if the localized Data-Flow can be evaluated lazily or not. If this is the case, depending on which DataIns are required, only certain steps of the localized Data-Flow need to be evaluated.

Algorithm:

**Setup** of a Control-node
* Some Inlets are configured to be lazy
* A CHECK_LAZY function is defined to determine if the condition for a lazy evaluation is given.

**Setup** of a Data-node with the localized Data-Flow of this Control-node
* Some Inlets are configured to be lazy
* A CHECK_LAZY function is defined to determine if the condition for a lazy evaluation is given.

**Assembly**
* On the Control-node, the assembler creates a bit mask with a bit for each data-inlet. each data-inlet gets its own bit mask called EVAL_MASK where the bit that represents the inlet is set to 1, while all other bits are set to 0.
* On the Data-node, the CHECK_LAZY function is called to determine which Data-inlets to follow in the backpropagation.(This, by the way has a severe edge case: the CHECK_LAZY function on a Data-node should make its decision at assembly time for performance reasons. Otherwise the re-assembly of the localized Data-Flow would be required on each execution of the Control-node, which we want to avoid. But implementing Lazy Evaluation in a consistent manner for the user means that changes of Properties or Inlets that could affect this decision on the Data-node during runtime actually needs to trigger a re-assembly of the localized Data-Flow. Otherwise, the evaluation of the Data-Flow could lead to incoherent results. A slight performance penalty is preferable over an inconsistent user experience.)
* Upon generation of the localized Data-Flow, this bit mask is passed on during the backpropagation, and is binary OR'ed with other bit masks from the same Control-node if they merge at that specific Data-node. This OR'ed bit mask is then passed further during backpropagation. At the end there is a list of all the required Data-nodes and their respective OR'ed bit masks (EVAL_MASK). Then the correct sequence of Data-nodes is determined to evaluate the Data-Flow correctly. This EVAL_MASK shows which Data-inlets require the evaluation of this specific Data-node.

**Evaluation**
* On execution of the Control-node, the VM creates a bit mask called LAZY_MASK with a bit for each data-inlet, all set to 1.
* then the CHECK_LAZY function is called to determine if the Data-Flow can be evaluated lazily or not. If this is the case, it sets the bits inside LAZY_MASK representing the data-inlets that are not needed to 0, while all others stay 1.
* Then the localized Data-Flow is evaluated:
  * It goes to the next Data-node in the sequence.
  * First it checks if the Data-Nodes CHECK_LAZY function has a different result than the previous run (i.e. during Assembly).
    * If yes, the evaluation of the localized Data-Flow is stopped
      * The VM reassembles the localized Data-Flow from scratch.
      * and restarts the evaluation process.
    * If no, it continues ..
  * Second it checks if any Data-Inlets are dirty.
    * If yes, it makes a Binary AND between LAZY_MASK and EVAL_MASK.
      * if the result is bigger than 0
        * this means at least one Data-Inlet requires the evaluation of this Data-node.
        * it evaluates the node.
        * sets the dirtied Data-Inlets to clean.
    * If not..
  * continues with the next Data-node in the sequence..

It is not clear yet how fast the reassembly of the localized Data-Flow from scratch is. I hope for an efficient algorithm. Depending on the time saved by lazy evaluation, it might be worth it. Its left to the node-designer to decide if such an effort makes sense. If there is no CHECK_LAZY function defined, the algorithm should run at nominal speed. The additional binary AND operation and if statements in each step should be negligible.

This has not highest priority, since lazy evaluation would only involve Data-Nodes, which should **not** be computationally heavy to evaluate and therefore should not pose to be a serious bottleneck.

# General Implementation



### The body of a Node

on way to find and instantiate a mode:

```python
# ComfyUI instantiates nodes as needed
class_type = node["class_type"]
class_def = nodes.NODE_CLASS_MAPPINGS[class_type]
obj = class_def()  # Node instance created
```

The node in Haywire can be created in different ways. It can be loaded from a file (JSON) or created programmatically. It can be defined by a tightly programmed Subclass of the Node class. Or a flexibly configurable Subclass defined by user information.

There will be nodes with a clear set of Parameters, Variables, DataIns and DataOuts. Or a dynamic node like "Switch on String", that has only one fixed Parameter to be set: the number of switch values it listens to. When this number is raised, new Parameters are dynamically created to be set and to configure the behaviour of the node, adding DataIns and DataOuts depending on the configuration.

This needs a function that is called when a Parameter is changed that has the power to change the behaviour of the node.


```Python
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

    # defining Data inlets
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
        # checks if there is a condition that allows lazy evaluation
        return

    @classmethod
    def HAS_CHANGED(cls):
        # possible to define a custom condition to check on a parameter whose value might change out of environment (like a file)
        # rehashing large files.
        return False

    @classmethod
    def VALIDATE_PARAMETERS(cls):
        # Validate the parameters. Not clear anymore why this might be necessary. ComfyUI has this implemented..
        #
```

```console
# Initialization

1. first the node is initialized, calling __init__
2. Calling SETTINGS to set the Settings.
3. Calling SETTINGS_CHANGED to dynamically configure the node.
4. Calling PARAMETERS to set the Parameters.
5. Calling INLETS to set the Inlets.
6. Calling OUTLETS to set the Outlets.

# Assembly

1. Calling CHECK_LAZY on the Data-node to see if there are lazy Inlets to stear the backpropagation.

# Evaluation

1. Calling CHECK_LAZY on the Control-node generate the LAZY_MASK.
2. Calling CHECK_LAZY on the Data-node to see if there is the need for re-assembly.
3. Calling HAS_CHANGED on the Data-node to see if there is change that is not from UI or Upstream nodes

```

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

- The Graph is analyzed to identify execution paths, starting at Event-nodes and following Control-pins
- At each Control-node, its Data-pin node dependencies are separated into a local Data-graph with a predefined sequence of execution for each involved node called a localized Data-flow.
- whenever a the graph is manipulated (connection is added or removed), the just in time Assembly mechanism adapts the respective flow to the new graph description.

Lets first focus on a complete Assembly of a graph into flows:

We assume:

- graph is loaded from a file.
- graph loads its dependencies.
- validation to check for recursive dependencies.
- graph is instantiated.

#### Graph Validation
- Checking for graph validity
  - Node checking:
    - Checking for validity of node-types (see chapter of node types for details)
    - Checking for multiples of the same Event-nodes (not allowed since undefined which Control-flow is should have precedence)
    - Checking for source and sink nodes inside Graph-nodes (required to be functional)

#### Graph Cleaning
- Clearing all connections that are stored inside pins. (clean house)

#### Graph Preprocessing
- Storing Control-flow connections in their respective outlet-pins. This is because the Control-flow propagates in the direction from Control-pin-outlet to Control-pin-inlet. The next-to-be-executed-controlnode Control-pin-inlet doesn't need to know with what node it is connected. It is actually allowed to be connected to multiple nodes. Once the node is executed, the VM will inform the from where the Control-flow came from.
- Storing Data-flow connections in their respective inlet-pins. This is because the Data-flow is assembled through backpropagation from the Data-pin-inlets of its respective Control-node. the Data-pin-outlets doesn't need to know with which inlet-pins it is connected to at the time of Assembly. once the Data-flow is created though, the outlet-pins "know" where to send their results. (this mechanism is not yet defined and can benefit from a suitable solution)

#### Flow identification
- Identifies different Control-flows with the Graph.
  - A Control-flows needs at least one Event-node
  - A Control-flows is considered separate from another Control-flows when there is no connection (control or data) between their respective nodes-trees.
    - The only exception here is the callback-connection.

#### Flow assembly
- Stepping through each Control-node:
  - its Data-pin-inlet dependencies are separated into a localized Data-graph (containing only nodes and connections that influence the Data-pin-inlets of the Control-node in focus).
  - Checking for loops in the Data-graph (not allowed with the exception of loops that contain a Control-node)
  - the Data-graph is sorted into a predefined sequence of executions called a localized Data-flow.
  - the localized Data-flow is stored within the Control-node, ready to be executed.
- It does all of it iteratively with each Graph-node as well.
- It identifies the Event-nodes and makes them available for hooking it up with the execution mechanism of the whole haystack.

#### Just-In-Time Assembly (For a future implementation)
- This happens whenever a connection is edited.
  - This can be the case if a node is deleted, but not when a node is added.

## Interpreter
- The Interpreter is responsible for running the individual Flows in their own Threads.
- It is responsible for piping external events to trigger the Flows that have matching Event-nodes.

## Execution

### Flow Execution
Each Flow has a Scheduler that manages the execution of the Flow. It makes sure that the Flow is executed from the Event-node that matches the trigger type.

Once a Flow is executed, the scheduler locks the Flow for exclusive execution. All other Triggers are queued inside the Trigger-queue until the Flow is finished.

Depending on the Trigger-queue's configuration, the Trigger-queue can be configured to either block or drop incoming events.

Flows should allowed to be executed in parallel. Not yet clear which architecture to use.

#### Control Flow Execution
When a Flow is executed, it creates two stacks:

* The first stack is the Done-stack, which contains the nodes that have been executed.
* The second stack is the Loopback-stack, which contains the Loopback-nodes.

Once a Control-node is executed, VM pushes it onto the Done-stack, and if its a Loopback-node, its pushed onto the Loopback-stack.

Loopback-nodes are Control-nodes that have one or multiple execution branches that have to come back to the node to continue. Loopback-nodes are designated as such by a flag.

Once a branch finds its end without an Output-node (which would end the Flow), the VM checks the Loopback-stack for any Loopback-nodes that are waiting for the branch to complete. If there are no Loopback-nodes waiting, the Flow is considered complete.

If there are Loopback-nodes waiting, the VM gets the last one out of the stack and removes all the nodes in the Done-stack up to the Loopback-node.

It then continues executing the Flow from the Loopback-node.

If there are cycles in the Control-Flow that spiral into infinity, the Done-stack will eventually overflow, causing the VM to throw an error.

## Question to the model:


- [ ] Should Flows be allowed to run in parallel?
  - [ ] That would mean that each Flow needs its own reference to the Graph.
  - [ ] Only Graphs containing one Flow can run in parallel.
  - [ ] They have to be designed to be truly stateless.
  - [ ] What would be the best architecture to cover both parallel and sequential execution?

- [ ] What works with this spec?
- [ ] What does this specification desperately need to clarify the goal?
- [ ] What is the best way to implement this?
- [ ] Check the Assembly steps for missing requirements and generation steps.
