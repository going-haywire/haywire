# Haywire Node System - AI Coding Agent Instructions

## Architecture Overview

Haywire is a Blueprint-inspired visual programming system that combines **execution flow** with **data flow** in a dual-flow architecture. Unlike pure dataflow systems, it uses explicit control connections to define execution order while maintaining data connections for value passing.

### Core Concepts

- **Dual-flow Model**: Control pins define execution order; data pins pass values
- **Node Types**: Control-nodes (with control pins) vs Data-nodes (data only)
- **Graph Structure**: Contains Variables, Edges, and Node instances
- **Assembly Process**: Graphs are assembled into executable Flows
- **Virtual Machine**: Manages state and execution context

## Project Structure

```
src/haywire/
├── core/                    # Core system implementation
│   ├── node/               # Node architecture and base classes
│   ├── graph/              # Graph data structures and management
│   ├── library/            # Node library system and registration
│   ├── data/               # Data types, specs, and enums
│   ├── adapter/            # External system adapters
│   └── di/                 # Dependency injection configuration
├── ui/                     # User interface components
│   ├── editor_v1/          # Main graph editor UI
│   └── pan_zoom/           # Canvas pan/zoom functionality
├── undo/                   # Undo/redo system
└── libraries/              # Node library implementations
```

## Development Environment

**Package Manager**: Uses `uv` (not pip/poetry)
```bash
uv sync          # Install dependencies
uv sync --dev    # Install with dev dependencies
```

**UI Framework**: NiceGUI for web-based interface
**Testing**: pytest with coverage
**Code Quality**: mypy, ruff

## Node Development Patterns

### Creating Nodes

Nodes inherit from `BaseNode` and use the `@node` decorator:

```python
from haywire.core.node.base_node import node, BaseNode
from haywire.core.node.elements import Inlet, Outlet

@node(
    label='My Node',
    description='What this node does',
    search_tags=['tag1', 'tag2'],
    menu='category/subcategory'
)
class MyNode(BaseNode):
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # Configure node behavior
        self.behavior.is_data_node = True
        self.behavior.is_control_node = False
        
        # Add pins using self.add_inlet() and self.add_outlet()
```

### Pin Configuration

- **Control Flow**: Use `FlowType.CONTROL` for execution order
- **Data Flow**: Use `FlowType.DATA` for value passing
- **Data Types**: Import from `haywire.core.data.enums.DataType`
- **Widgets**: Specify UI widgets like `'core.number'`, `'core.text'`

### Library Structure

Each library follows this pattern:
```
libraries/example/
├── __init__.py
├── adapters/               # External system integrations
├── nodes/                  # Node implementations
├── renderers/             # Custom UI renderers
└── widgets/               # Custom UI widgets
```

## Key Systems

### Dependency Injection

The DI system (`haywire.core.di.config`) provides centralized service management:
- `LibrarySystemService`: Manages node libraries and registries
- `NodeRegistry`: Tracks available nodes
- `NodeFactory`: Creates node instances
- `HistoryManager`: Handles undo/redo operations

### Graph Management

- **HaywireGraph**: Container for nodes, edges, and variables
- **Edge Types**: CONTROL, DATA, CALLBACK
- **Variables**: Graph-level state accessible to Control-nodes
- **Assembly**: Graphs are compiled into executable Flows

### UI Architecture

- **GraphCanvasManager**: Handles UI interactions and rendering
- **Editor**: Manages graph editing operations
- **Pan/Zoom**: Canvas navigation in `ui/pan_zoom/`
- **Session Management**: Multi-client support with shared graph state

## Development Workflow

### Running Applications

Use the playground for testing:
```bash
cd playground
python app_graph_canvas.py    # Main development app
```

### Adding New Features

1. **Nodes**: Create in `libraries/[library]/nodes/`
2. **UI Components**: Add to `src/haywire/ui/`
3. **Core Logic**: Extend `src/haywire/core/`
4. **Tests**: Add to corresponding test directories

### File Watching

The library system includes hot-reloading via `FileWatcher` for development efficiency.

## Critical Implementation Details

### Node Registration

Nodes auto-register through folder scanning in `FolderScanMixin`. The registry creates unique keys combining library and node IDs.

### State Management

- **Graph Variables**: Persistent state between executions
- **Undo System**: Action-based with `BaseAction` implementations
- **Session Data**: Per-client UI state with shared graph data

### Performance Considerations

- **Just-in-Time Assembly**: Flows are compiled on-demand
- **Connection Updates**: `updateAllConnections()` called frequently (performance issue noted)
- **Canvas Rendering**: Many elements can impact zoom performance

## Current Development Focus

Based on `open_issues.md`:
- Coordinate transformation improvements
- BaseNode dataclass refactoring
- Connection management efficiency
- Fold/unfold detection fixes

## Testing and Quality

- Run tests with `pytest`
- Type checking with `mypy`
- Code formatting with `ruff`
- Manual testing via playground applications

## Integration Points

- **NiceGUI**: Web UI framework integration
- **JavaScript**: Client-side canvas interactions
- **File System**: Dynamic library loading and watching
- **Module System**: Python import mechanics for node discovery

This architecture prioritizes modularity, performance, and extensibility while maintaining clear separation between execution logic and UI concerns.

## Code Style: Line Length (99 character limit)

**Breaking Long Lines - Priority Order:**

1. **Imports**: One per line in parentheses
```python
   from module import (
       ClassA,
       ClassB,
   )
```

2. **Function Signatures**: Break after parameters
```python
   def my_function(
       param1: str,
       param2: int,
       param3: Optional[Dict] = None
   ) -> ReturnType:
```

3. **Function Calls**: Break after opening parenthesis
```python
   result = some_function(
       arg1="value",
       arg2=complex_expression,
       arg3=another_value
   )
```

4. **Strings**: Use implicit concatenation
```python
   message = (
       f"First part {variable} "
       f"second part {another_var} "
       "third part"
   )
```

5. **Conditionals**: Extract to named variable
```python
   is_valid = (
       condition1 
       and condition2 
       and not condition3
   )
   if is_valid:
```

6. **UI Class Chains**: Break at natural boundaries
```python
   element.classes(
       'class1 class2 class3 '
       'class4 class5 class6'
   )
```

7. **Comments**: Move inline comments to line above
```python
   # This is what the variable does
   variable = value
```

8. **Dictionaries/Lists**: One item per line
```python
   my_dict = {
       'key1': value1,
       'key2': value2,
       'key3': value3,
   }
```

9. **Ternary Expressions**: Use full if-else
```python
self.ui_properties: dict = (
    element.ui.get('properties', {}) 
    if hasattr(element, 'ui') 
    else {}
)
````

**Never sacrifice readability for line length compliance.**