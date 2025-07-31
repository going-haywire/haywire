# Node Graph Editor

A simple node graph editor built with NiceGUI and Quasar, designed for creating and editing visual node-based workflows.

## Features

- **Visual Node Editor**: Drag-and-drop interface for creating nodes
- **Node Movement**: Multiple ways to move nodes (keyboard arrows, drag handles)
- **Node Types**: Support for various node types including:
  - Input/Output nodes
  - Math operations (Add, Subtract, Multiply, Divide)
  - Logic operations (AND, OR, NOT, Compare)
  - Display and export nodes
  - Comment nodes
- **Connection System**: Visual connections between node ports
- **Node Palette**: Organized palette of available nodes
- **Graph Management**: Save, load, and clear graph functionality
- **Responsive Design**: Works on desktop and mobile devices

## Project Structure

```
playground/nodes/
├── main.py                 # Main application entry point
├── components/
│   ├── __init__.py
│   ├── node_editor.py      # Individual node rendering and interaction
│   └── node_graph.py       # Graph canvas and overall graph management
├── models/
│   ├── __init__.py
│   └── node.py             # Node and connection data models
├── utils/
│   ├── __init__.py
│   └── graph_utils.py      # Graph management utilities
├── static/
│   ├── css/
│   │   └── styles.css      # Custom styles for the editor
│   └── js/
│       └── graph.js        # JavaScript utilities for interaction
└── README.md               # This file
```

## Getting Started

### Prerequisites

- Python 3.8+
- NiceGUI library

### Installation

1. Install NiceGUI:
```bash
pip install nicegui
```

2. Navigate to the project directory:
```bash
cd playground/nodes
```

3. Run the application:
```bash
python main.py
```

4. Open your browser and go to `http://localhost:8080`

## Troubleshooting

### Common Issues

#### Import Errors
If you see `Import "nicegui" could not be resolved`:
- Make sure NiceGUI is installed: `pip install nicegui`
- Check that you're using the correct Python environment
- Restart your IDE/editor after installation

#### Runtime Errors
If you see `TypeError: run_javascript() got an unexpected keyword argument 'respond'`:
- This was fixed in the current version
- Use `main_simple.py` for a minimal working version

#### Event Handling Errors
If you see `'GenericEventArguments' object has no attribute 'ctrlKey'`:
- This was fixed in the current version
- Make sure you're using the latest version of the code
- NiceGUI's event system is different from browser DOM events

#### Keyboard Handler Errors
If keyboard controls don't work:
- This is a known limitation with some NiceGUI versions
- Use the simplified drag interface instead
- Check the JavaScript console for errors

#### Drag and Drop Issues
If nodes jump back to their original position after dragging:
- This was fixed in the current version with proper backend synchronization
- The JavaScript now prevents backend position updates during dragging
- Position changes are saved via API endpoint after drag completion

#### Performance Issues
- Limit the number of nodes (< 50 for smooth performance)
- Close unused browser tabs
- Use Chrome or Firefox for best performance

## Usage

### Creating Nodes

1. Use the **Node Palette** on the left side to create new nodes
2. Click on any node type to add it to the canvas
3. Nodes are automatically positioned to avoid overlapping

### Moving Nodes

**Method 1: Keyboard Controls**
1. Click on a node to select it
2. Use the **arrow keys** to move the selected node in 10-pixel increments
3. Hold multiple keys for faster movement

**Method 2: Drag and Drop (Enhanced)**
1. Click and hold on the **drag handle** (⋮⋮ icon) in the node header
2. Drag the node to the desired position
3. Release to place the node
4. The node will snap to valid positions

### Connecting Nodes

1. Click on an output port (right side of nodes)
2. Drag to an input port (left side of nodes)
3. Release to create the connection
4. Connections are validated to ensure type compatibility

### Node Types

#### Basic Nodes
- **Input**: Provides input values to the graph
- **Output**: Displays final results
- **Comment**: Add documentation to your graph

#### Math Nodes
- **Add**: Adds two numbers
- **Subtract**: Subtracts two numbers
- **Multiply**: Multiplies two numbers
- **Divide**: Divides two numbers

#### Logic Nodes
- **AND**: Logical AND operation
- **OR**: Logical OR operation
- **NOT**: Logical NOT operation
- **Compare**: Compares two values

#### Output Nodes
- **Display**: Shows data values
- **Chart**: Creates visual charts
- **Export**: Exports data to files

### Graph Operations

- **New Graph**: Clear the current graph
- **Save Graph**: Export graph data (currently prints to console)
- **Load Graph**: Import graph data (placeholder)
- **Execute**: Run the graph (placeholder for execution logic)

## Architecture

### Component Overview

1. **Main Application** (`main.py`):
   - Sets up the UI layout
   - Creates the node palette
   - Initializes the graph manager

2. **Node Graph** (`components/node_graph.py`):
   - Manages the graph canvas
   - Handles node rendering updates
   - Draws connections between nodes

3. **Node Editor** (`components/node_editor.py`):
   - Renders individual nodes
   - Handles node-specific interactions
   - Manages node properties

4. **Graph Manager** (`utils/graph_utils.py`):
   - Core graph state management
   - Node and connection operations
   - Graph serialization/deserialization

5. **Data Models** (`models/node.py`):
   - Node and connection data structures
   - Port definitions and validation
   - Factory methods for creating nodes

### Key Design Patterns

- **Component-based Architecture**: Separate concerns for different UI components
- **Factory Pattern**: Node creation through factory methods
- **Observer Pattern**: Graph updates trigger UI refreshes
- **MVC Pattern**: Clear separation of models, views, and controllers

## Customization

### Adding New Node Types

1. Add the new type to `NodeType` enum in `models/node.py`
2. Update the `_setup_default_ports()` method to define ports
3. Add the node to the appropriate palette section in `main.py`
4. Add styling in `static/css/styles.css`

### Styling

The editor uses a combination of:
- **Quasar Components**: For UI elements and layout
- **Custom CSS**: For node appearance and interactions
- **CSS Grid**: For background grid pattern

### JavaScript Integration

The `static/js/graph.js` file provides:
- Enhanced drag-and-drop functionality
- Keyboard shortcuts
- Advanced connection handling
- Graph manipulation utilities

## Best Practices

1. **Node Design**:
   - Keep nodes focused on single responsibilities
   - Use clear, descriptive names
   - Provide meaningful port names

2. **Performance**:
   - Limit the number of nodes for smooth interaction
   - Use efficient update mechanisms
   - Minimize DOM manipulations

3. **User Experience**:
   - Provide visual feedback for interactions
   - Use consistent styling across node types
   - Include helpful tooltips and labels

## Extending the Editor

### Adding Execution Logic

To add actual graph execution:

1. Implement execution methods in node classes
2. Add a graph execution engine
3. Handle data flow between connected nodes
4. Provide execution status and error handling

### Adding Persistence

To save/load graphs:

1. Implement file I/O operations in `GraphManager`
2. Add graph validation and migration logic
3. Create import/export formats (JSON, XML, etc.)
4. Add version control for graph schemas

### Adding Advanced Features

Potential enhancements:
- **Undo/Redo**: Command pattern for operations
- **Minimap**: Overview of large graphs
- **Grouping**: Organize nodes into groups
- **Templates**: Reusable node configurations
- **Debugging**: Step-through execution
- **Performance Metrics**: Node execution times

## Contributing

1. Follow the existing code structure
2. Add appropriate type hints
3. Include docstrings for new functions
4. Test new features thoroughly
5. Update documentation as needed

## License

This project is part of the OpenTrackingTool and follows the same license terms.
