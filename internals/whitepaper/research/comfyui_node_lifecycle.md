# ComfyUI Node Lifecycle: From Instantiation to Execution

## Overview
This document details the complete lifecycle of a ComfyUI node from its initial loading to executing and passing data to subsequent nodes.

## Phase 1: Node Registration & Discovery

### 1.1 Module Import (`__init__.py`)
**Location**: `custom_nodes/<node_package>/__init__.py`

```python
# __init__.py is executed when Comfy attempts to import the module
NODE_CLASS_MAPPINGS = {
    "MyCustomNode": MyCustomNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MyCustomNode": "My Custom Node Display Name"
}
```

**Process**:
- ComfyUI scans the `custom_nodes` directory
- Imports each module's `__init__.py`
- Extracts `NODE_CLASS_MAPPINGS` to register available node classes
- Builds internal registry of available node types

### 1.2 Class Definition Analysis
**Location**: Node class definition

ComfyUI analyzes each node class to extract:
- `INPUT_TYPES()`: Input specifications and validation rules
- `RETURN_TYPES`: Output type declarations
- `FUNCTION`: Entry point method name
- `CATEGORY`: UI menu placement
- Optional methods: `VALIDATE_INPUTS`, `IS_CHANGED`

## Phase 2: Workflow Loading & Graph Construction

### 2.1 Workflow JSON Parsing
**Location**: Frontend → `server.py` → `execution.py`

```json
{
  "1": {
    "inputs": {"text": "hello world"},
    "class_type": "MyCustomNode",
    "_meta": {"title": "My Node"}
  }
}
```

**Process**:
- Frontend sends workflow JSON to server
- Server parses JSON into node graph structure
- Each node gets a unique ID and stores its configuration

### 2.2 Node Instantiation
**Location**: `execution.py` → Node class constructors

```python
# ComfyUI instantiates nodes as needed
class_type = node["class_type"]
class_def = nodes.NODE_CLASS_MAPPINGS[class_type]
obj = class_def()  # Node instance created
```

**Key Points**:
- Nodes are instantiated when first needed during execution
- Node `__init__()` method is called
- Instance is cached for reuse within the workflow

## Phase 3: Pre-Execution Validation

### 3.1 Workflow Validation
**Location**: `execution.py` → `validate_prompt()`

```python
# validate_prompt() function validates entire workflow
def validate_prompt(prompt):
    # Validates JSON structure
    # Checks node types exist
    # Calls VALIDATE_INPUTS for each node
    # Returns validation errors or success
```

### 3.2 Node-Level Validation
**Location**: Node's `VALIDATE_INPUTS` method

```python
@classmethod
def VALIDATE_INPUTS(cls, input_name, **kwargs):
    # Called ONCE per workflow execution
    # Only receives constant/widget values
    # Cannot access data from other nodes
    # Returns True or error message
    return True
```

**Process**:
- Called before any node execution begins
- Validates static inputs (widgets, constants)
- Cannot validate dynamic inputs from other nodes
- Validation failure prevents workflow execution

## Phase 4: Execution Preparation

### 4.1 Execution List Creation
**Location**: `execution.py` → `DynamicPrompt` → `ExecutionList`

```python
# Workflow is converted to execution order
prompt = validate_prompt(workflow_json)
dynprompt = DynamicPrompt(prompt)
execution_list = dynprompt.get_execution_list()
```

**Process**:
- Analyzes node dependencies
- Creates topological execution order
- Handles caching and change detection

### 4.2 Change Detection
**Location**: `execution.py` → `IsChangedCache`

```python
class IsChangedCache:
    def get(self, node_id):
        # Calls node's IS_CHANGED method if it exists
        # Compares with previous execution
        # Determines if node needs re-execution
```

**Process**:
- Calls node's `IS_CHANGED()` method with current inputs
- Compares result with previous execution
- Marks nodes that need re-execution

## Phase 5: Node Execution

### 5.1 Input Data Collection
**Location**: `execution.py` → `get_input_data()`

```python
def get_input_data(inputs, class_def, unique_id, outputs=None):
    # Collects all inputs for the node
    # Resolves connections to other nodes
    # Handles hidden inputs (PROMPT, UNIQUE_ID, etc.)
    # Returns input_data_all dictionary
```

**Process**:
- Resolves input connections to actual data
- Fetches outputs from previously executed nodes
- Handles optional inputs (only included if connected)
- Adds hidden inputs (PROMPT, UNIQUE_ID, EXTRA_PNGINFO)

### 5.2 Runtime Type Validation
**Location**: `execution.py` → Default validation logic

```python
# Runtime validation before node execution
if validate_function_inputs or validate_has_kwargs:
    # Performs type checking on connected inputs
    # Skipped if VALIDATE_INPUTS handles validation
    # Validates input types match RETURN_TYPES of source nodes
```

### 5.3 Node Function Execution
**Location**: `execution.py` → `get_output_data()` → Node's main function

```python
def get_output_data(obj, input_data_all):
    # Calls the node's main function
    function_name = obj.FUNCTION
    results = getattr(obj, function_name)(**input_data_all)
    # Returns tuple of outputs
```

**Execution Flow**:
1. **Pre-execution callback** (if defined)
2. **Main function call**: `node.my_function(**input_data)`
3. **Return tuple validation**: Ensures tuple matches `RETURN_TYPES`
4. **UI data extraction**: Handles special return values for UI
5. **Subgraph expansion**: Processes node expansion (loops, etc.)

### 5.4 Output Processing
**Location**: `execution.py` → Output caching and distribution

```python
# Process node outputs
for i, output_value in enumerate(results):
    # Cache output value
    # Make available to downstream nodes
    # Handle UI updates
    # Store in outputs cache
```

## Phase 6: Data Propagation

### 6.1 Output Caching
**Location**: `execution.py` → `HierarchicalCache`

```python
# Outputs are cached for reuse
outputs_cache.set(node_id, output_values)
# Cache key includes node state for invalidation
```

### 6.2 Downstream Node Triggering
**Location**: Execution loop continues

```python
# Execution continues to next nodes
for next_node_id in execution_list:
    if node_needs_execution(next_node_id):
        execute_node(next_node_id)
```

## Phase 7: Cleanup and Finalization

### 7.1 Memory Management
- GPU memory cleanup for tensor outputs
- Cache cleanup for completed workflows
- Resource deallocation

### 7.2 Progress Reporting
**Location**: WebSocket messages to frontend

```python
# Progress updates sent to frontend
{
    "type": "executing", 
    "data": {"node": node_id, "prompt_id": prompt_id}
}
```

## Key Code Locations

| Component | File | Function/Class |
|-----------|------|----------------|
| Node Registration | `custom_nodes/__init__.py` | `NODE_CLASS_MAPPINGS` |
| Workflow Validation | `execution.py` | `validate_prompt()` |
| Input Collection | `execution.py` | `get_input_data()` |
| Node Execution | `execution.py` | `get_output_data()` |
| Caching | `execution.py` | `HierarchicalCache` |
| Change Detection | `execution.py` | `IsChangedCache` |
| Progress Tracking | `server.py` | WebSocket handlers |

## Data Flow Summary

```
1. Node Class → Registration → Node Registry
2. Workflow JSON → Validation → Execution List
3. Execution List → Input Collection → Runtime Validation
4. Validated Inputs → Node Function → Output Tuple
5. Output Tuple → Caching → Downstream Propagation
6. Progress Updates → Frontend → User Feedback
```

## Critical Points

- **Node instances are cached** and reused within a workflow
- **VALIDATE_INPUTS runs once** per workflow, not per node execution
- **Input collection happens just before** each node's execution
- **Outputs are cached** and only re-computed when inputs change
- **Type validation occurs at multiple levels**: compile-time, pre-execution, and runtime
- **Execution order is topological** but may vary based on caching