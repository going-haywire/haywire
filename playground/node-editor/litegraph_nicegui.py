import json
from typing import Any, Dict, List, Optional, Callable
from nicegui import ui
from nicegui.element import Element


class LiteGraphEditor(Element):
    """
    A NiceGUI component that integrates LiteGraph.js as a node editor with 
    bidirectional communication between JavaScript and Python.
    """
    
    def __init__(self, 
                 width: int = 800, 
                 height: int = 400,
                 node_types: Optional[Dict[str, Dict[str, Any]]] = None,
                 on_node_added: Optional[Callable] = None,
                 on_node_removed: Optional[Callable] = None,
                 on_connection_changed: Optional[Callable] = None,
                 on_node_selected: Optional[Callable] = None,
                 **kwargs) -> None:
        """
        Initialize the LiteGraph editor component.
        
        Args:
            width: Canvas width in pixels
            height: Canvas height in pixels
            on_node_added: Callback when a node is added
            on_node_removed: Callback when a node is removed
            on_connection_changed: Callback when connections change
            on_node_selected: Callback when a node is selected
        """
        super().__init__('div', **kwargs)
        
        self._width = width
        self._height = height
        self._graph_data = None
        self._node_types = node_types or {}
        self._callbacks = {
            'node_added': on_node_added,
            'node_removed': on_node_removed, 
            'connection_changed': on_connection_changed,
            'node_selected': on_node_selected
        }
        
        # Add LiteGraph.js library from a more reliable CDN
        ui.add_head_html('''
            <script src="https://unpkg.com/litegraph.js@0.7.15/build/litegraph.min.js"></script>
            <link href="https://unpkg.com/litegraph.js@0.7.15/css/litegraph.css" rel="stylesheet">
        ''')
        
        # Initialize the component
        self._setup_component()
    
    def _setup_component(self) -> None:
        """Setup the Vue component with LiteGraph integration."""
        
        # Create the canvas element with the correct ID
        with self:
            ui.html(f'''
                <canvas 
                    id="canvas_{self.id}"
                    ref="graphCanvas" 
                    width="{self._width}" 
                    height="{self._height}"
                    style="border: 1px solid #ccc; background: #333;">
                </canvas>
            ''')
        
        # Add the Vue component script
        component_script = f'''
        // LiteGraph NiceGUI Component
        (function() {{
            const canvasId = 'canvas_{self.id}';
            console.log('Looking for canvas with ID:', canvasId);
            
            // Wait for LiteGraph to be loaded
            function initializeLiteGraph() {{
                if (typeof LiteGraph === 'undefined') {{
                    console.log('LiteGraph not loaded yet, retrying...');
                    setTimeout(initializeLiteGraph, 100);
                    return;
                }}
                
                const canvas = document.getElementById(canvasId);
                console.log('Canvas found:', canvas);
                if (!canvas) {{
                    console.log('Canvas not found, retrying...');
                    setTimeout(initializeLiteGraph, 100);
                    return;
                }}
                
                // Create graph and canvas
                const graph = new LiteGraph.LGraph();
                const graphCanvas = new LiteGraph.LGraphCanvas(canvas, graph);
                
                // Store references
                window.lgEditor_{self.id} = {{
                    graph: graph,
                    canvas: graphCanvas,
                    canvasElement: canvas
                }};
                console.log('Stored editor in window.lgEditor_{self.id}:', window.lgEditor_{self.id});
                
                // Configure canvas
                graphCanvas.background_image = null;
                graphCanvas.render_shadows = false;
                graphCanvas.render_canvas_border = false;
                
                // Setup event listeners
                graph.onNodeAdded = function(node) {{
                    emitEvent('node_added', {{
                        node_id: node.id,
                        node_type: node.type,
                        position: node.pos,
                        properties: node.properties
                    }});
                }};
                
                graph.onNodeRemoved = function(node) {{
                    emitEvent('node_removed', {{
                        node_id: node.id,
                        node_type: node.type
                    }});
                }};
                
                graph.onConnectionChange = function(node) {{
                    const connections = [];
                    for (let i in graph._nodes) {{
                        const n = graph._nodes[i];
                        if (n.inputs) {{
                            for (let j = 0; j < n.inputs.length; j++) {{
                                const input = n.inputs[j];
                                if (input.link != null) {{
                                    const link = graph.links[input.link];
                                    if (link) {{
                                        connections.push({{
                                            from_node: link.origin_id,
                                            from_slot: link.origin_slot,
                                            to_node: link.target_id,
                                            to_slot: link.target_slot
                                        }});
                                    }}
                                }}
                            }}
                        }}
                    }}
                    emitEvent('connection_changed', {{ connections: connections }});
                }};
                
                graphCanvas.onNodeSelected = function(node) {{
                    if (node) {{
                        emitEvent('node_selected', {{
                            node_id: node.id,
                            node_type: node.type,
                            properties: node.properties,
                            position: node.pos
                        }});
                    }}
                }};
                
                // Start rendering
                graph.start();
                
                // Register node types
                console.log('About to register node types...');
                {self._register_node_types()}
                console.log('Node types registered successfully');
                
                console.log('LiteGraph editor initialized for element', elementId);
            }}
            
            initializeLiteGraph();
        }})();
        '''
        
        ui.add_body_html(f'<script>{component_script}</script>')
        
        # Register event handlers
        for event_name, callback in self._callbacks.items():
            if callback:
                ui.on(event_name, callback)
    
    def add_node_type(self, node_type: str, node_class: Dict[str, Any]) -> None:
        """
        Register a new node type with LiteGraph.
        
        Args:
            node_type: The name of the node type
            node_class: Dictionary defining the node class structure
        """
        self._node_types[node_type] = node_class
        print(f"Added node type '{node_type}' to component. Total types: {len(self._node_types)}")
    
    def _register_single_node_type(self, node_type: str, node_class: Dict[str, Any]) -> None:
        """Register a single node type by deferring execution until UI is ready."""
        js_class = json.dumps(node_class)
        js_function_name = node_type.replace('/', '_').replace('-', '_')
        
        js_code = f'''
        function {js_function_name}() {{
            const nodeClass = {js_class};
            
            // Set up inputs using LiteGraph's addInput method
            if (nodeClass.inputs) {{
                for (let input of nodeClass.inputs) {{
                    this.addInput(input.name, input.type);
                }}
            }}
            
            // Set up outputs using LiteGraph's addOutput method
            if (nodeClass.outputs) {{
                for (let output of nodeClass.outputs) {{
                    this.addOutput(output.name, output.type);
                }}
            }}
            
            // Set up properties
            if (nodeClass.properties) {{
                this.properties = Object.assign({{}}, nodeClass.properties);
            }}
            
            // Set size if specified
            if (nodeClass.size) {{
                this.size = nodeClass.size;
            }}
            
            // Copy other properties from the class definition
            for (let key in nodeClass) {{
                if (key !== 'inputs' && key !== 'outputs' && key !== 'properties' && key !== 'size') {{
                    this[key] = nodeClass[key];
                }}
            }}
        }}
        
        {js_function_name}.title = "{node_class.get('title', node_type)}";
        {js_function_name}.desc = "{node_class.get('description', '')}";
        
        console.log('About to register node type: {node_type}');
        console.log('LiteGraph available:', typeof LiteGraph !== 'undefined');
        
        if (typeof LiteGraph !== 'undefined') {{
            try {{
                console.log('Registering function for {node_type}:', {js_function_name});
                LiteGraph.registerNodeType("{node_type}", {js_function_name});
                console.log('Successfully registered node type: {node_type}');
                console.log('Available node types after registration:', Object.keys(LiteGraph.registered_node_types || {{}}));
            }} catch (error) {{
                console.error('Error registering node type {node_type}:', error);
            }}
        }} else {{
            console.log('LiteGraph not available yet for registering: {node_type}');
        }}
        '''
        
        # Use a timer to defer execution until the UI event loop is ready
        def register_when_ready():
            try:
                ui.run_javascript(js_code)
                print(f"Successfully registered node type '{node_type}' via JavaScript")
            except Exception as e:
                print(f"Failed to register node type '{node_type}': {e}")
        
        ui.timer(0.1, register_when_ready, once=True)
        
    def _register_node_types(self) -> str:
        """Generate JavaScript code to register all stored node types."""
        print(f"Registering {len(self._node_types)} node types: {list(self._node_types.keys())}")
        if not self._node_types:
            return ""
            
        js_parts = []
        for node_type, node_class in self._node_types.items():
            js_class = json.dumps(node_class)
            # Create JavaScript-safe function name
            js_function_name = node_type.replace('/', '_').replace('-', '_')
            
            js_code = f'''
            function {js_function_name}() {{
                const nodeClass = {js_class};
                
                // Set basic properties
                this.title = nodeClass.title || "{node_type}";
                this.size = nodeClass.size || [200, 100];
                this.properties = nodeClass.properties || {{}};
                
                // Add inputs
                if (nodeClass.inputs) {{
                    for (let input of nodeClass.inputs) {{
                        this.addInput(input.name, input.type || "");
                    }}
                }}
                
                // Add outputs  
                if (nodeClass.outputs) {{
                    for (let output of nodeClass.outputs) {{
                        this.addOutput(output.name, output.type || "");
                    }}
                }}
                
                // Add widgets
                if (nodeClass.widgets) {{
                    for (let widget of nodeClass.widgets) {{
                        this.addWidget(widget.type, widget.name, widget.value || null);
                    }}
                }}
            }}
            
            {js_function_name}.title = "{node_class.get('title', node_type)}";
            {js_function_name}.desc = "{node_class.get('description', '')}";
            
            LiteGraph.registerNodeType("{node_type}", {js_function_name});
            console.log('Registered node type: {node_type}');
            '''
            js_parts.append(js_code)
            
        return '\n'.join(js_parts)
    
    def add_node(self, node_type: str, position: List[int] = [100, 100], properties: Dict = None) -> None:
        """
        Add a node to the graph programmatically.
        
        Args:
            node_type: Type of node to add
            position: [x, y] position for the node
            properties: Dictionary of node properties
        """
        js_code = f'''
        console.log('add_node called for type: {node_type}');
        const editor = window.lgEditor_{self.id};
        console.log('Editor found:', editor);
        if (editor && editor.graph) {{
            console.log('Graph found, attempting to create node...');
            const node = LiteGraph.createNode("{node_type}");
            console.log('createNode result:', node);
            if (node) {{
                node.pos = {position};
                if ({json.dumps(properties or {})} && Object.keys({json.dumps(properties or {})}).length > 0) {{
                    Object.assign(node.properties, {json.dumps(properties or {})});
                }}
                editor.graph.add(node);
                console.log('Successfully added node:', node);
            }} else {{
                console.error('Failed to create node of type: {node_type}');
                console.log('Available node types:', Object.keys(LiteGraph.registered_node_types || {{}}));
            }}
        }} else {{
            console.error('Editor or graph not found. Editor:', editor);
        }}
        '''
        
        ui.run_javascript(js_code)
    
    def remove_node(self, node_id: int) -> None:
        """Remove a node by ID."""
        js_code = f'''
        const editor = window.lgEditor_{self.id};
        if (editor && editor.graph) {{
            const node = editor.graph.getNodeById({node_id});
            if (node) {{
                editor.graph.remove(node);
            }}
        }}
        '''
        
        ui.run_javascript(js_code)
    
    def get_graph_data(self) -> None:
        """Get the current graph data (triggers callback with the data)."""
        js_code = f'''
        const editor = window.lgEditor_{self.id};
        if (editor && editor.graph) {{
            const graphData = editor.graph.serialize();
            emitEvent('graph_data', {{ data: graphData }});
        }}
        '''
        
        ui.run_javascript(js_code)
    
    def load_graph_data(self, graph_data: Dict) -> None:
        """Load graph data into the editor."""
        js_code = f'''
        const editor = window.lgEditor_{self.id};
        if (editor && editor.graph) {{
            editor.graph.configure({json.dumps(graph_data)});
            console.log('Loaded graph data');
        }}
        '''
        
        ui.run_javascript(js_code)
    
    def clear_graph(self) -> None:
        """Clear all nodes from the graph."""
        js_code = f'''
        const editor = window.lgEditor_{self.id};
        if (editor && editor.graph) {{
            editor.graph.clear();
        }}
        '''
        
        ui.run_javascript(js_code)
    
    def zoom_in(self) -> None:
        """Zoom in on the canvas."""
        js_code = f'''
        const editor = window.lgEditor_{self.id};
        if (editor && editor.canvas) {{
            editor.canvas.setZoom(editor.canvas.ds.scale * 1.2);
        }}
        '''
        
        ui.run_javascript(js_code)
    
    def zoom_out(self) -> None:
        """Zoom out on the canvas."""
        js_code = f'''
        const editor = window.lgEditor_{self.id};
        if (editor && editor.canvas) {{
            editor.canvas.setZoom(editor.canvas.ds.scale * 0.8);
        }}
        '''
        
        ui.run_javascript(js_code)
    
    def center_view(self) -> None:
        """Center the view on the graph."""
        js_code = f'''
        const editor = window.lgEditor_{self.id};
        if (editor && editor.canvas) {{
            editor.canvas.centerOnNode();
        }}
        '''
        
        ui.run_javascript(js_code)


# Example usage and demo
def create_demo():
    """Create a demo of the LiteGraph editor component."""
    
    # State variables for debugging (optional - can be commented out)
    # selected_node_info = ui.json_editor({'content': {}}).classes('w-full h-32')
    # graph_data_display = ui.json_editor({'content': {}}).classes('w-full h-32')
    
    # Callback functions
    def on_node_added(e):
        ui.notify(f"Node added: {e.args['node_type']} (ID: {e.args['node_id']})")
        print(f"Node added: {e.args}")
    
    def on_node_removed(e):
        ui.notify(f"Node removed: {e.args['node_type']} (ID: {e.args['node_id']})")
        print(f"Node removed: {e.args}")
    
    def on_connection_changed(e):
        ui.notify(f"Connections updated: {len(e.args['connections'])} connections")
        print(f"Connections: {e.args['connections']}")
    
    def on_node_selected(e):
        # selected_node_info.content = e.args  # Commented out with debug editor
        ui.notify(f"Selected node: {e.args['node_type']}")
        print(f"Node selected: {e.args}")
        
    def on_graph_data(e):
        # graph_data_display.content = e.args['data']  # Commented out with debug editor
        print("Graph data received:", e.args['data'])
        
    # Define some custom node types
    math_node = {
        'title': 'Math Operation',
        'description': 'Performs basic math operations',
        'size': [200, 100],
        'inputs': [
            {'name': 'A', 'type': 'number'},
            {'name': 'B', 'type': 'number'}
        ],
        'outputs': [
            {'name': 'Result', 'type': 'number'}
        ],
        'properties': {
            'operation': '+'
        }
    }
        
    constant_node = {
        'title': 'Constant',
        'description': 'Outputs a constant value',
        'size': [120, 60],
        'outputs': [
            {'name': 'Value', 'type': 'number'}
        ],
        'properties': {
            'value': 1.0
        }
    }
        
    display_node = {
        'title': 'Display',
        'description': 'Displays the input value',
        'size': [120, 60],
        'inputs': [
            {'name': 'Input', 'type': 'number'}
        ],
        'properties': {}
    }
        
    # Create the editor with node types
    node_types = {
        'math/operation': math_node,
        'basic/constant': constant_node,
        'basic/display': display_node
    }
    
    editor = LiteGraphEditor(
        width=800,
        height=400,
        node_types=node_types,
        on_node_added=on_node_added,
        on_node_removed=on_node_removed,
        on_connection_changed=on_connection_changed,
        on_node_selected=on_node_selected
    )
        
    # Register the graph data callback
    ui.on('graph_data', on_graph_data)
        
    # Control buttons
    with ui.row().classes('gap-2 mt-4'):
        ui.button('Add Math Node', 
                 on_click=lambda: editor.add_node('math/operation', [200, 150]))
        ui.button('Add Constant', 
                 on_click=lambda: editor.add_node('basic/constant', [50, 100]))
        ui.button('Add Display', 
                 on_click=lambda: editor.add_node('basic/display', [400, 150]))
        ui.button('Clear Graph', 
                 on_click=editor.clear_graph)
    
    with ui.row().classes('gap-2 mt-2'):
        ui.button('Zoom In', on_click=editor.zoom_in)
        ui.button('Zoom Out', on_click=editor.zoom_out)
        ui.button('Center View', on_click=editor.center_view)
        ui.button('Get Graph Data', on_click=editor.get_graph_data)
    
    # Information panels (debug info removed)
    ui.separator().classes('my-4')
    
    # Instructions
    ui.separator().classes('my-4')
    ui.markdown('''
    ## Instructions:
    1. **Add Nodes**: Use the buttons above to add different types of nodes
    2. **Connect Nodes**: Drag from output slots (right side) to input slots (left side)
    3. **Select Nodes**: Click on a node to select it and see its properties
    4. **Move Nodes**: Drag nodes around the canvas
    5. **Zoom**: Use mouse wheel or zoom buttons
    6. **Get Data**: Click "Get Graph Data" to see the current graph structure
    
    ## Available Node Types:
    - **Math Operation**: Performs basic arithmetic operations
    - **Constant**: Outputs a constant numerical value  
    - **Display**: Shows the input value (terminal node)
    
    The component provides full bidirectional communication between Python and JavaScript,
    allowing you to control the node editor programmatically and receive events from user interactions.
    ''')


if __name__ in {"__main__", "__mp_main__"}:
    ui.label('LiteGraph.js Node Editor in NiceGUI').classes('text-2xl font-bold mb-4')
    create_demo()
    ui.run(title='LiteGraph Node Editor Demo', port=8080)
