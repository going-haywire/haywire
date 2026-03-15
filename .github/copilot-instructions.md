# Haywire Node System - AI Coding Agent Instructions

## Architecture Overview

Haywire is a Blueprint-inspired visual programming system that combines **execution flow** with **data flow** in a dual-flow architecture. Unlike pure dataflow systems, it uses explicit control connections to define execution order while maintaining data connections for value passing.

### Core Concepts

- **Dual-flow Model**: Control pins define execution order; data pins pass values
- **Node Types**: Control-nodes (with control pins) vs Data-nodes (data only)
- **Graph Structure**: Contains Variables, Edges, and Node instances
- **Assembly Process**: Graphs are assembled into executable Flows
- **Virtual Machine**: Manages state and execution context

## Project Structure (uv workspace monorepo)

```
haywire-repo/
├── pyproject.toml                          # workspace root (NOT a package)
├── uv.lock
├── tests/                                  # tests for haywire-core
├── playground/                             # scratch/experiment scripts
├── docs/
├── scripts/
├── saves/
│
├── packages/
│   ├── haywire-core/                  # core framework (publishable)
│   │   ├── pyproject.toml
│   │   └── src/haywire/                    # import as `haywire`
│   │       ├── core/                       # graph engine, DI, nodes, edges, ports
│   │       │   ├── node/                   # node architecture and base classes
│   │       │   ├── graph/                  # graph data structures and management
│   │       │   ├── library/                # node library system and registration
│   │       │   ├── data/                   # data types, specs, and enums
│   │       │   ├── adapter/                # external system adapters
│   │       │   └── di/                     # dependency injection configuration
│   │       ├── ui/                         # NiceGUI user interface
│   │       │   ├── editor_v1/              # main graph editor UI
│   │       │   └── pan_zoom/               # canvas pan/zoom functionality
│   │       └── undo/                       # undo/redo system
│   │
│   └── haywire-app/                        # application package (publishable)
│       ├── pyproject.toml                  # CLI entry: `haywire = "haywire_app:main"`
│       └── src/haywire_app/
│
└── libraries/                              # haybale plugin libraries
    ├── haybale-core/                       # standard node library
    ├── haybale-example/                    # example library with custom types/widgets
    ├── haybale-testing/                    # test nodes (edge_link_test, dynamic_port_test)
    ├── haybale-visiongraph/                # vision/camera nodes
    └── haybale-TEST_A/                     # test library
```

### Key Build & Tooling Details

- **Package manager**: `uv` (not pip/poetry)
- **Build backend**: hatchling (all packages)
- **Library discovery**: `importlib.metadata.entry_points(group='haywire.libraries')`
- **DI container**: `injector` library; config at `packages/haywire-core/src/haywire/core/di/config.py`
- **UI framework**: NiceGUI for web-based interface
- **Testing**: pytest with coverage
- **Code quality**: mypy, ruff (line-length = 109)

## Development Environment

```bash
uv sync          # Install all workspace packages + dependencies
uv run pytest    # Run tests
uv run haywire   # Run the app via CLI entry point
```

## Node Development Patterns

### Creating Nodes

Nodes inherit from `BaseNode` and use the `@node` decorator:

```python
from haywire.core.node.base_node import node, BaseNode
from haywire.core.node.elements import Inlet, Outlet
from haywire.core.node.behavior import NodeType

@node(
    label='My Node',
    description='What this node does',
    search_tags=['tag1', 'tag2'],
    menu='category/subcategory',
    node_type=NodeType.DATA  # or CONTROL, EVENT, OUTPUT, LOOPBACK
)
class MyNode(BaseNode):
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)

        # Add pins using self.add_inlet() and self.add_outlet()
```

### Node Types

Node types are mutually exclusive and determined by control port configuration:

- **NodeType.DATA**: Pure data processing (0 ctrl inlet/0 ctrl outlet)
- **NodeType.CONTROL**: Standard control flow (1 ctrl inlet/1 ctrl outlet)
- **NodeType.EVENT**: Flow entry point (0 ctrl inlet/1 ctrl outlet)
- **NodeType.OUTPUT**: Flow termination (1 ctrl inlet/0 ctrl outlet)
- **NodeType.LOOPBACK**: Loop constructs (1 ctrl inlet/2+ ctrl outlets with loopback)

### Pin Configuration

- **Control Flow**: Use `FlowType.CONTROL` for execution order
- **Data Flow**: Use `FlowType.DATA` for value passing
- **Data Types**: Import from `haywire.core.data.enums.DataType`
- **Widgets**: Specify UI widgets like `'core.number'`, `'core.text'`

### Library Structure

Each library follows this pattern:
```
libraries/haybale-example/
├── haybale_example/
│   ├── __init__.py             # exports Library class
│   ├── adapters/               # external system integrations
│   ├── nodes/                  # node implementations
│   ├── renderers/              # custom UI renderers
│   └── widgets/                # custom UI widgets
├── pyproject.toml              # hatchling build, entry point registration
└── README.md
```

### Edge & Port Architecture

- **Three-tier edge lifecycle**: `link()`, `unlink()`, `detach()`
- **Two-tier port storage**: `_linked_edges` (active) + `_all_edges` (all attached)
- **Asymmetric displacement**: inlet informs outlet, outlet does NOT inform inlet
- **Lazy edges**: `is_lazy` flag on `Edge`/`EdgeWrapper` (per-edge, not per-port)
- **Port connection rules** (hardcoded in `DataPort.__post_init__`):
  - DATA outlets: `allow_multiple = True`, DATA inlets: `allow_multiple = False`
  - EXEC outlets: `allow_multiple = False`, EXEC inlets: `allow_multiple = True`
  - CALLBACK: freely configurable
  - Pooled inlets: `allow_multiple = True`

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

### Hot-Reload System

- File watcher + dependency graph + snapshot/rollback for live class reloading
- Libraries discovered via entry points (`haywire.libraries` group)
- `library.disable()`/`library.enable()` + unregister already functional
- Placeholder/error nodes for missing libraries already in place

## Development Workflow

### Running Applications

```bash
uv run haywire                              # via CLI entry point
uv run python -m haywire_app                # via module
uv run python playground/app_graph_canvas.py # playground script (still works)
```

### Adding New Features

1. **Nodes**: Create in `libraries/[library]/nodes/`
2. **UI Components**: Add to `packages/haywire-core/src/haywire/ui/`
3. **Core Logic**: Extend `packages/haywire-core/src/haywire/core/`
4. **Tests**: Add to `tests/`

### Testing Notes

- `create_node_wrapper()` leaves pending `NODE_ADDED` (priority 90) in dirty queue
- Lower-priority marks like `NODE_HOT_RELOADED` (80) get silently dropped
- Tests must call `force_immediate_validation()` after setup to flush before testing

## Critical Implementation Details

### Node Registration

Nodes auto-register through folder scanning in `FolderScanMixin`. The registry creates unique keys combining library and node IDs.

### State Management

- **Graph Variables**: Persistent state between executions
- **Undo System**: Action-based with `BaseAction` implementations
- **Session Data**: Per-client UI state with shared graph data

### Lazy Propagation

- Unified dirty model: both eager and lazy edges defer `on_change` to execution time
- Pipes own all data transport: eager push + lazy `pull_lazy()` (always-latest semantics)
- `resolve_dirty_data()`: pulls lazy pipes, then fires deferred `on_change` once
- `_execute()` resolves dirty ports for ALL node types

## Code Style: Line Length (109 character limit)

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

# Python Docstring Instructions

For Python docstrings follow these best practices:

## Structure

1. **One-line summary**: Brief description ending with period
2. **Blank line**
3. **Detailed description**: Explain behavior, design decisions, context
4. **Blank line**
5. **Args section**: Document parameters (if any)
6. **Returns section**: Document return value (if any)
7. **Raises section**: Document exceptions (if any)
8. **Note/Warning sections**: Important caveats (if needed)
9. **Examples section**: Show usage patterns (always include)

## Details

Only add details / examples / notes
* if the information is not obvious from the signature or context.
* if the function has non-trivial behavior.
* if the function has important side effects or design considerations.

## Formatting Rules

### Summary Line
- One sentence, ending with period
- Imperative mood ("Get the value" not "Gets the value")
- No type information (use type hints in signature instead)

### Args Section
```
Args:
    param_name (type, optional): Description of parameter.
        Defaults to default_value if not provided.
    another_param: Description without type (if hint in signature).
```

- Indent param descriptions 4 spaces
- Continuation lines indent 8 spaces
- Use "optional" in type for optional params
- Mention defaults when relevant

### Returns Section
```
Returns:
    Description of return value

    OR

Returns:
    - None  # for no return
    - str  # outlet ID
    - List[DataPort]  # sorted ports
```

- Use bullet format for multiple possible return types
- Include inline comments for clarity

### Raises Section
```
Raises:
    ValueError: When this specific error occurs.
    KeyError: When that specific error occurs.
```

### Examples Section
- Always include at least one example
- Use `.. code-block:: python` directive
- Show common use cases first, then advanced
- Include inline comments for clarity
- Show both simple and complex usage

```
Examples:
    Simple usage:

    .. code-block:: python

        result = node.value('input')  # Returns: 42.0

    Advanced usage with options:

    .. code-block:: python

        with self.group(GROUP.as_inlet('advanced')):
            self.add(FLOAT.as_inlet('param'))
```

## Style Guidelines

1. **Blank lines**: Always separate sections with blank line
2. **Indentation**: Use 4-space indentation consistently
3. **Line length**: Keep under 109 characters, break naturally
4. **Type hints**: In function signature, not docstring (except optional note)
5. **Active voice**: Prefer active voice in descriptions
6. **Present tense**: Use present tense for current behavior
7. **Specificity**: Be specific about behavior, edge cases, defaults

## Common Patterns

### For Methods
```python
def method_name(self, param: str, optional: int = 0) -> Result:
    """
    One-line summary of what method does.

    Detailed explanation of behavior, design decisions,
    and how the method fits into the larger system.

    Args:
        param: Description of required parameter.
        optional: Description of optional parameter.
            Defaults to 0.

    Returns:
        Description of what is returned

    Raises:
        ValueError: When validation fails.

    Examples:
        Basic usage:

        .. code-block:: python

            result = obj.method_name('value')

        With optional parameter:

        .. code-block:: python

            result = obj.method_name('value', optional=5)
    """
```

### For Classes
```python
class ClassName:
    """
    One-line summary of class purpose.

    Detailed description of what the class represents,
    its responsibilities, and how it fits into the system.

    Key design decisions or architectural notes should
    be mentioned here.

    Attributes:
        attr1: Description of attribute.
        attr2: Description of attribute.

    Examples:
        Creating and using the class:

        .. code-block:: python

            obj = ClassName(param1, param2)
            obj.method()
    """
```

## What to Avoid

- Don't repeat type information (it's in type hints)
- Don't write "This method..." (implied by context)
- Don't use past tense ("This method created..." -> "Create...")
- Don't omit examples (always include at least one)
- Don't forget blank lines between sections
- Don't write multi-paragraph Args descriptions (extract to main description)
- Don't include implementation details unless architecturally relevant

## IDE Rendering

Ensure docstrings render properly in IDEs:
- Use proper ReStructuredText directives (`.. code-block::`)
- Include blank lines before code blocks
- Keep consistent indentation
- Test that examples display correctly in hover tooltips
