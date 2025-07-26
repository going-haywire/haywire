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

The Haywire Graph is a data structure that describes the flow of data and control between nodes. As such, it is a collection of Parameters, Variables, Connections and instantiations of Nodes and Graph-nodes. All are described further down in their respective sections.

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

## Connections

There are three types of connections:

- **Control-connections** are used to control the flow of execution between nodes.
- **Data-connections** are used to transfer data between nodes.
- **Callback-connections** are used to trigger an Event-node from another Flow. Contrary to Control- and Data-connections, Callback-connections are only used during the Assembly step to connect Flows through events.

A connection is a simple data structure that contains the outlet-pins node-id and pin-id and the inlets-pin node-id and pin-id.

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

- **Parameters** to configure its behavior. Has default values can be overridden by the user. Are read only accessible by the Worker-function.
- **Variables** to maintain or orchestrate its functionality. Can be read and written by the Worker-function.
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

- **Loopback-node**
  The Loopback-node is a Control-node that tells the VM to loop back execution within the Control-flow to itself if the branch ends without an Output-node. Loopback-nodes are for example For-Loops, While-Loops, Sequences and other Control-flow constructs that allow *sequential* branching of the Control-flow. Switches or If-Statements are not Loopback-nodes since they do *conditional* branching.

### Parameters
Parameters configure the behaviour / functionality of the node. They are read-only during evaluation.

- Parameters can only be of specified datatypes that makes them editable through the user interface.
- They have **no** default value
- Their values are set on creation or changed via the user interface
- Their settings can have an effect on the node's appearance
  - They can enable/disable DataIns, DataOuts and other Parameters.
- They **can** have pin-outlets but have **no** pin-inlets.
- They are only read accessible by the internal Worker-function
- When a Graph is stored to file, the value is stored.

### Variables
Variables are used to enhance functionality of the node.

- Variables can be of specified datatypes.
- Variables have a default value that can be set on creation or by the user via the user interface.
- They are read/write accessible by the internal Worker-function
- For Graph-node its Variables are made accessible to its child nodes so they can be manipulated by getter and setter nodes.
- They are not directly accessible by pins. (only inside a Graph-node via getter or setter nodes and their respective pins)
- When a Graph is stored to file, only the default value is stored.

### DataIns
DataIns are used receive data into a node.

- DataIns are of specified datatypes.
- DataIns can have a default value that can be set on creation or by the user via the user interface.
- They are only read accessible by the internal Worker-function
- They can be directly set by Data-pin-inlets.
- They can be set to required or optional to be connected to a Data-pin-outlet.
- When a Graph is stored to file, only the default value is stored.

### DataOuts
DataOuts are used to send data out of a node.

- DataOuts are of specified datatypes.
- DataOuts are **required** to be set by the internal Worker-function. This assures a consistent behavior.
- They are only write accessible by the internal Worker-function.

**The implementation of DataOuts is not yet defined.**

### Overview of Nodes Configurables

| Types          | Function        | Default | Stores  | Inlets | Outlets | Visible  | Enable   | Required |
| -------------- | --------------- | ------- | ------- | ------ | ------- | -------- | -------- | -------- |
| Parameters     | Configuration   |   no    | value   |   no   |  maybe  |  on/off  |  on/off  |  None    |
| Variables      | Runtime Storage |   yes   | default |   no   |   no    |  off     |  on      |  None    |
| DataIns        | Input Data      |   yes   | default |   yes  |   no    |  on/off  |  on/off  |  Maybe   |
| DataOuts       | Output Data     |   no    |  none   |   no   |   yes   |  on/off  |  on/off  |  None    |

none = can not be set / has no effect
Default = has default value
Stores = data that is stored to file and is loaded.
Visible = can be set by the user to be visible in the node UI.
Enable = can be set to be on/off by a Parameter.
Required = can be set to be required.

### Pins
Pins are the way to connect to and from a node. Pins have a selection of different settings that define their behaviour:

- **Flow-type** defines if it is a control, data or callback pin
- **Socket-type** defines if the pin is an inlet (for getting event/data in) or an outlet (for sending event/data out)
- **Data-type** defines the data type the pin is associated with. And which other pins a pin can connect or not connect to.
- **Link-type** defines how many connections can be made on the pin. This is either one or many.

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
- **Control-pin-outlet** can have only one link, since it must be clear which the next node is that needs to be executed.
- **Control-pin-inlet** can have many links, since there might be mulitple execution paths that lead to this node.
- **Data-pin-outlet** can have many links, since multiple nodes might be interested in this data
- **Data-pin-inlet** there are two link-types possible, depending on the needed data. in case of many the provided data is in form of a list of values in the specified data-type.
- **Callback-pin-inlet** can have multiple links, since multiple Event-nodes can require the same callback.
- **Callback-pin-outlet** can have multiple links, since the Event-node might be interested in multiple callbacks.

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

### Data-types

TBD - More research is needed to figure out how this can be handled.


# General Implementation



# Python Implementation

## Examples of other node systems:

### Data-types

#### ComfyUI
has just a enumeration of data types:

https://github.com/comfyanonymous/ComfyUI/blob/master/comfy/comfy_types/node_typing.py

and it doesn't validate its adherence from node to node.

### Toplogical Sorting Implementations:

ComfyUI: https://github.com/comfyanonymous/ComfyUI/blob/master/comfy_execution/graph.py

### Custom nodes:

Definition of base classes and data types for custom nodes:
ComfyUI: https://github.com/comfyanonymous/ComfyUI/blob/master/comfy/comfy_types/node_typing.py

Example of implementation of custom nodes:
ComfyUI: https://github.com/comfyanonymous/ComfyUI/blob/master/custom_nodes/example_node.py.example

ComfyUI has a realtively simple way of defining a node:

* It defines the inputs, each identifiable by a name, through `def INPUT_TYPES(cls):`
  * with this functionit can calculate the values for the inputs, being enumerations for selections etc.
  * it returns a dictionary, separated by required and optional, of the inputs exposed through pins
    * containing the name, data type, and a default value.
    * this defines the values the executable function expects.
* It defines the name of the executable function
* It defines the outputs by creating a tuple with the datatypes
  * the executable function is expected to return this values in the exact order
* It defines the executable function
  * with its expected arguments
  * with the return values in a tuple following the structure defined for the outputs
* It allows the definition of VALIDATE_INPUTS method to check if the inputs are valid
* It allows the definition of IS_CHANGED to check if an input that doesn't come from another node (i.e. filesystem) has changed

Example
```python
class LoadVideo(ComfyNodeABC):
    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = folder_paths.filter_files_content_types(files, ["video"])
        return {"required":
                    {"file": (sorted(files), {"video_upload": True})},
                }

    CATEGORY = "image/video"

    RETURN_TYPES = (IO.VIDEO,)
    FUNCTION = "load_video"
    def load_video(self, file):
        video_path = folder_paths.get_annotated_filepath(file)
        return (VideoFromFile(video_path),)

    @classmethod
    def IS_CHANGED(cls, file):
        video_path = folder_paths.get_annotated_filepath(file)
        mod_time = os.path.getmtime(video_path)
        # Instead of hashing the file, we can just use the modification time to avoid
        # rehashing large files.
        return mod_time

    @classmethod
    def VALIDATE_INPUTS(cls, file):
        if not folder_paths.exists_annotated_filepath(file):
            return "Invalid video file: {}".format(file)

        return True
```
or here a more complicated example: https://github.com/comfyanonymous/ComfyUI/blob/0621d73a9c56fdc9e79aad87ed260135639bca50/nodes.py#L1518


### Lazy Evaluation

ComfyUI: https://docs.comfy.org/custom-nodes/backend/lazy_evaluation

ComfyUI has a feature for DataIns called Lazy Evaluation. This feature can make the evaluation of the Data-Flow more efficient by excluding unnecessary computations. ComfyUI follows a classical Data-Flow Evaluation model by backprogation, so quite different to how Haywire executes/evaluates the Flow.

Nevertheles, the current Haywire specification has the localized Data-Flow, which is evaluated in a strict order. Before the Control-node is executed, the current specification requires that the localized Data-Flow is evaluated.

So, in theory it is possible to expand on this: The assembler is responsible for generating the localized Data-Flow for each Control-node. If DataIns have a lazy evaluation flag and the Data-Flows can be lazyily evaluated, the VirtualMachine that lazily evaluates the Data-Flow would need some additional information beforehand. ComfyUI has the method `def check_lazy_status(self, args)` that is called before its Inlets are evaluated. In Haywire, the VirtualMachine can use such a method to determine if the localized Data-Flow can be evaluated lazily or not. If this is the case, depending on which DataIns are required, only certain steps of the localized Data-Flow need to be evaluated. Though the algorithm involved is not yet understood and **needs further research**.

This has not highest priority, since lazy evaluation would only involve Data-Nodes, which should **not** be computationally heavy to evaluate and therefore should not pose to be a serious bottleneck.

Conclusion: This feature is mostly interesting for node-graphs that evaluate the graph in a backpropagation manner and expects heavy computations in some nodes (which Haywire is not).

### registering, finding and instantiating a node

#### ComfyUI

Module Import (__init__.py)

Location: custom_nodes/<node_package>/__init__.py
```python
# __init__.py is executed when Comfy attempts to import the module
NODE_CLASS_MAPPINGS = {
    "MyCustomNode": MyCustomNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MyCustomNode": "My Custom Node Display Name"
}
```

Process:

* ComfyUI scans the custom_nodes directory
* Imports each module's __init__.py
* Extracts NODE_CLASS_MAPPINGS to register available node classes
* Builds internal registry of available node types

---

Location: execution.py → Node class constructors
```python
# ComfyUI instantiates nodes as needed
class_type = node["class_type"]
class_def = nodes.NODE_CLASS_MAPPINGS[class_type]
obj = class_def()  # Node instance created
```
* Nodes are instantiated when first needed during execution
* Node __init__() method is called
* Instance is cached for reuse within the workflow

---

Location: execution.py → Node's main function

https://github.com/comfyanonymous/ComfyUI/blob/0621d73a9c56fdc9e79aad87ed260135639bca50/execution.py#L217C1-L234C1
```python
f = getattr(obj, func)
if inspect.iscoroutinefunction(f):
    async def async_wrapper(f, prompt_id, unique_id, list_index, args):
        with CurrentNodeContext(prompt_id, unique_id, list_index):
            return await f(**args)
    task = asyncio.create_task(async_wrapper(f, prompt_id, unique_id, index, args=inputs))
    # Give the task a chance to execute without yielding
    await asyncio.sleep(0)
    if task.done():
        result = task.result()
        results.append(result)
    else:
        results.append(task)
else:
    with CurrentNodeContext(prompt_id, unique_id, index):
        result = f(**inputs)
    results.append(result)
```
* `f = getattr(obj, func)` gets the function name that needs to be executed
* if the function has a `async` decorator, it is executed asynchronously
  * `async_wrapper` creates the instance of the function that can be executed asynchronously
  * `task = asyncio.create_task(` creates the task with the function and arguments
* otherwise it is a simple synchronous execution (which is almost always the case within comfyIU)

---

its not clear to me how comfyUI from here propagates the results to the output pins and then to the next nodes..

### Flow generation

#### ComfyUI

Location: execution.py → DynamicPrompt → ExecutionList

```python
# Workflow is converted to execution order
prompt = validate_prompt(workflow_json)
dynprompt = DynamicPrompt(prompt)
execution_list = dynprompt.get_execution_list()
```


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
    Parameters = []
    Variables = []
    ControlIns = []
    ControlOuts = []
    DataIns = []
    DataOuts = []

@abstractNode
class HaywireNode(object, metaclass=HaywireMeta):

    def __init__(self, node_id, graph):
        self.graph = graph
        self.node_id = node_id
        self.node_display_name = 'Node Name'
        self.node_description = 'Node Description'
        self.node_name = '3rdParty.custom.Node_NAME'
        self.node_library_name = '3rdPartyLibrary'
        self.node_library_url = 'https://haywire.io/docs/node-help'
        self.node_version = '0.0.0'
        self.node_author = 'Customer'
        self.node_author_url = 'https://customer.org'
        self.help_md = None
        self.help_url = None
        self.is_control_node = False # Set_automatically()
        self.is_data_node = True # Set_automatically()
        self.is_loopback_node = False
        self.is_muted = False
        self.can_be_muted = False
        self.mute_connection = ['control_in_ID', 'control_out_ID']
        self.ui_default_color = '#FFFFFF'
        self.ui_custom_color = '#000000'
        self.ui_posX = 0
        self.ui_posY = 0
        self.ui_width = 100
        self.ui_height = 100
        self.ui_width_min = -1
        self.ui_height_min = -1
        self.ui_collapsed = False
        self.ui_pinned = False
        self.ui_icon = None
        self.ui_component = 'default'
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

    def _on_parameter_changed(self, parameter):
        # Implement logic to handle parameter changes
        pass

    # defining Parameters
    Parameter(
        name: 'Parameter Name',
        id: 'parameter_id',
        description: 'Parameter Description',
        datatype: Datatype,
        value: value,
        callback: self._on_parameter_changed,
        is_visible: True,
        is_enabled: True,
        has_pin_outlet: False)

    # defining Control inlets
    ControlIns(
        name: 'Control In Name',
        id: 'control_in_ID',
        description: 'Control Description')

    # defining Control outlets
    ControlOuts (
        name: 'Control Out Name',
        id: 'control_out_ID',
        description: 'Control Description')

    # defining Data inlets
    DataIns(
        name: 'Data Name',
        id: 'data_in_ID',
        description: 'Data Description',
        datatype: DataType,
        datastruct: DataStruct,
        is_visible: True,
        is_enabled: True,
        default: default)

    # defining Data outlets
    DataOuts(
        name: 'Data Name',
        id: 'data_out_ID',
        description: 'Data Description',
        datatype: DataType,
        datastruct: DataStruct,
        is_visible: True,
        is_enabled: True)


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

-> To Be Deterimend if Flows should allowed to be executed in parallel...

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

## Question to Florian:


- [ ] What is the best mechanism to propagate the data-outlets to the connected data-inlets?
  - [ ] This problem is related to the Get node for Variables. The Get node would benefit from a mechanism that indicates whether its Variable has changed since the last time it was accessed.
- [ ] What is best mechanism to define a custom node?
- [ ] What is the best way to structure a Control-Flow? -> Partiallly answered within execution chapter
- [ ] Should Flows be allowed to run in parallel?
  - [ ] That would mean that each Flow needs its own reference to the Graph.
  - [ ] Only Graphs containing one Flow can run in parallel.
  - [ ] They have to be designed to be truly stateless.
  - [ ] What would be the best architecture to cover both parallel and sequential execution?


## Question to the model:

- [ ] What works with this spec?
- [ ] What does this specification desperately need to clarify the goal?
- [ ] What is the best way to implement this?
- [ ] Check the Assembly steps for missing requirements and generation steps.
