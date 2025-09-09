"""
GraphCanvasManager - Dedicated UI management for graph visualization

This class manages the visual representation of a graph including nodes and connections.
It handles:
- Node visual creation/removal/positioning
- Connection rendering with SVG paths
- Client-side interaction handling (drag connections, node movement)
- Synchronization with graph data model
- Integration with undo/redo system

The core principle follows condensed.md: delegate real-time interactions to client-side 
JavaScript for smooth UX, while Python manages the data model and finalized state changes.
"""

from typing import Dict, List, Optional, Tuple, Callable, Set
from nicegui import ui, events
import json
import uuid
from dataclasses import dataclass

from haywire.core.graph.graph import HaywireGraph, Edge
from haywire.core.node.node import BaseNode
from haywire.core.utils import generate_pin_id, parse_pin_id
from haywire.ui.ui_node import UINode
from haywire.ui.pan_zoom.zoom_pan_vue import ZoomPanContainer


@dataclass
class ConnectionDragState:
    """State information during connection creation."""
    is_dragging: bool = False
    start_node_id: Optional[str] = None
    start_port_name: Optional[str] = None
    start_port_type: Optional[str] = None  # 'input' or 'output'


class GraphCanvasManager:
    """
    Manages the visual representation of a graph including nodes and connections.
    
    Responsibilities:
    - Node visual creation/removal/positioning
    - Connection rendering with SVG paths
    - Client-side interaction handling (drag connections, node movement)
    - Synchronization with graph data model
    - Integration with undo/redo system
    """
    
    def __init__(
        self, 
        graph: HaywireGraph,
        node_render_factory,
        zoom_container: ZoomPanContainer,
        on_node_position_changed: Optional[Callable[[str, Tuple[float, float]], None]] = None,
        on_connection_created: Optional[Callable[[str, str, str, str], None]] = None,
        on_connection_removed: Optional[Callable[[Edge], None]] = None,
        on_node_selected: Optional[Callable[[str, bool], None]] = None
    ):
        self.graph = graph
        self.node_render_factory = node_render_factory
        self.zoom_container = zoom_container
        
        # Event callbacks
        self.on_node_position_changed = on_node_position_changed
        self.on_connection_created = on_connection_created
        self.on_connection_removed = on_connection_removed
        self.on_node_selected = on_node_selected
        
        # Store current zoom/pan state for coordinate calculations
        self.current_zoom = 1.0
        self.current_pan_x = 0.0
        self.current_pan_y = 0.0
        
        # Visual state
        self.node_panels: Dict[str, Dict] = {}  # node_id -> {ui_node, container, position}
        self.connection_paths: Dict[str, ui.element] = {}  # edge_id -> svg path element
        self.selected_nodes: Set[str] = set()
        
        # Interaction state
        self.connection_drag_state = ConnectionDragState()
        self.node_drag_state = None
        
        # UI elements
        self.canvas = None
        self.svg_canvas = None
        self.node_container = None
        
        # Setup flag
        self._js_setup_done = False
        
        self._setup_canvas()
        
        # Global callback registration for JavaScript
        self._register_python_callbacks()
    
    def _setup_canvas(self):
        """Setup the canvas with SVG overlay for connections."""
        with self.zoom_container.content_container:
            # Create the main canvas container
            with ui.element('div').classes('right-[4000px] bottom-[4000px] relative').style(
                'width: 8000px; height: 8000px; '
                'background: linear-gradient(90deg, #fff0f0 2px, transparent 2px), '
                'linear-gradient(180deg, #fff0f0 2px, transparent 2px); '
                'background-size: 50px 50px; '
                'position: relative; overflow: visible;'
            ) as self.canvas:
                
                # SVG layer for connections (background, z-index: 0)
                self.svg_canvas = ui.html('''
                <svg id="connection-svg" 
                     class="absolute top-0 left-0 w-full h-full" 
                     style="z-index: 0; pointer-events: none;"
                     xmlns="http://www.w3.org/2000/svg">
                </svg>
                ''')
                
                # Node container (foreground, z-index: 1)
                self.node_container = ui.element('div').classes('absolute top-0 left-0 w-full h-full').style(
                    'z-index: 1;'
                ).props('id="node-container"')
    
    def _register_python_callbacks(self):
        """Register Python callbacks that JavaScript can call."""
        # Store references to callbacks in a way JavaScript can access them
        # We'll use a global window object approach
        callback_id = f"canvas_manager_{uuid.uuid4().hex[:8]}"
        self._callback_id = callback_id
        
        # We'll register these when setting up JavaScript
    
    def setup_client_side_interactions(self):
        """Setup client-side JavaScript for smooth interactions."""
        if self._js_setup_done:
            return
        
        # Setup connection drag logic
        self._setup_connection_drag_js()
        
        # Setup node position observers
        self._setup_node_observers_js()
        
        self._js_setup_done = True
    
    def _setup_connection_drag_js(self):
        """Setup JavaScript for connection creation via drag and drop."""
        js_code = f"""
        // Canvas Manager: {self._callback_id}
        
        // Wait a bit for DOM to be ready, then setup
        setTimeout(() => {{
            // Store zoom/pan state globally for coordinate calculations
            window.canvasZoomPanState = {{
                zoom: {self.current_zoom},
                panX: {self.current_pan_x},
                panY: {self.current_pan_y}
            }};
            
            // Function to update zoom/pan state from Python
            window.updateCanvasZoomPanState = function(zoom, panX, panY) {{
                window.canvasZoomPanState.zoom = zoom !== undefined ? zoom : window.canvasZoomPanState.zoom;
                window.canvasZoomPanState.panX = panX !== undefined ? panX : window.canvasZoomPanState.panX;
                window.canvasZoomPanState.panY = panY !== undefined ? panY : window.canvasZoomPanState.panY;
                
                console.log('Updated zoom/pan state:', window.canvasZoomPanState);
            }};
            
            let connectionState = {{
                isDragging: false,
                startPin: null,
                tempPath: null
            }};
            
            const svg = document.querySelector('#connection-svg');
            if (!svg) {{
                console.error('SVG canvas not found');
                return;
            }}
            
            // Debug: Check for existing pins
            const existingPins = document.querySelectorAll('.connection-pin');
        
        // Helper function to get pin position relative to SVG (with caching)
        let pinPositionCache = new Map();
        let cacheValidUntil = 0;
        
        function getPinPosition(pinElement) {{
            const now = Date.now();
            const pinId = pinElement.id;
            
            // Use cache if still valid (cache for 16ms = ~60fps)
            if (now < cacheValidUntil && pinPositionCache.has(pinId)) {{
                return pinPositionCache.get(pinId);
            }}
            
            const svg = document.querySelector('#connection-svg');
            if (!svg) return {{ x: 0, y: 0 }};
            
            const pinRect = pinElement.getBoundingClientRect();
            
            let position = transformScreenToSVG(pinRect.left + pinRect.width / 2, pinRect.top + pinRect.height / 2);
                        
            // Cache the result
            pinPositionCache.set(pinId, position);
            if (now >= cacheValidUntil) {{
                cacheValidUntil = now + 16; // Cache valid for 16ms
            }}
            
            return position;
        }}
        
        // Make getPinPosition globally available
        window.getPinPosition = getPinPosition;
        
        // Enhanced coordinate transformation using current zoom/pan state
        function transformScreenToSVG(clientX, clientY) {{
            const svg = document.querySelector('#connection-svg');
            if (!svg) return {{ x: clientX, y: clientY }};
            
            const svgRect = svg.getBoundingClientRect();
            const state = window.canvasZoomPanState || {{ zoom: 1, panX: 0, panY: 0 }};
            
            // Apply inverse transform accounting for current zoom/pan
            let x = (clientX - svgRect.left) / state.zoom;
            let y = (clientY - svgRect.top) / state.zoom;
            
            return {{ x, y }};
        }}
        
        // Make transformScreenToSVG globally available
        window.transformScreenToSVG = transformScreenToSVG;
        
        // Set up observers for node changes to update connections
        function setupNodeObservers() {{
            const nodeContainer = document.getElementById('node-container');
            if (!nodeContainer) return;
            
            // ResizeObserver to detect when nodes change size (fold/unfold)
            const resizeObserver = new ResizeObserver((entries) => {{
                updateAllConnections();
            }});
            
            // MutationObserver to detect DOM changes in nodes
            const mutationObserver = new MutationObserver((mutations) => {{
                let shouldUpdate = false;
                mutations.forEach((mutation) => {{
                    if (mutation.type === 'attributes' && 
                        (mutation.attributeName === 'style' || mutation.attributeName === 'class')) {{
                        shouldUpdate = true;
                    }}
                    if (mutation.type === 'childList') {{
                        shouldUpdate = true;
                    }}
                }});
                if (shouldUpdate) {{
                    setTimeout(() => updateAllConnections(), 50);
                }}
            }});
            
            // Observe all existing nodes
            const nodes = nodeContainer.querySelectorAll('.node-widget');
            nodes.forEach(node => {{
                resizeObserver.observe(node);
                mutationObserver.observe(node, {{ 
                    attributes: true, 
                    childList: true, 
                    subtree: true,
                    attributeFilter: ['style', 'class']
                }});
            }});
            
            // Store observers globally for cleanup
            window.nodeResizeObserver = resizeObserver;
            window.nodeMutationObserver = mutationObserver;
            
            // Also observe zoom container for transform changes
            const zoomContainer = document.querySelector('.zoom-pan-container') || 
                                document.querySelector('[style*="transform"]') ||
                                document.getElementById('node-container');
            if (zoomContainer) {{
                let zoomUpdateTimeout;
                const zoomObserver = new MutationObserver((mutations) => {{
                    mutations.forEach((mutation) => {{
                        if (mutation.type === 'attributes' && 
                            mutation.attributeName === 'style') {{
                            // Debounce zoom updates with longer delay
                            clearTimeout(zoomUpdateTimeout);
                            zoomUpdateTimeout = setTimeout(() => updateAllConnections(), 100);
                        }}
                    }});
                }});
                zoomObserver.observe(zoomContainer, {{ 
                    attributes: true, 
                    attributeFilter: ['style'] 
                }});
                window.zoomObserver = zoomObserver;
            }}
        }}
        
        // Function to update all existing connections (with throttling)
        let updateConnectionsThrottled = false;
        function updateAllConnections() {{
            if (updateConnectionsThrottled) return;
            updateConnectionsThrottled = true;
            
            requestAnimationFrame(() => {{
                const paths = document.querySelectorAll('#connection-svg path:not([stroke-dasharray])');
                paths.forEach(path => {{
                    if (window.updateConnectionPath) {{
                        window.updateConnectionPath(path);
                    }}
                }});
                
                // Reset throttle after frame
                setTimeout(() => updateConnectionsThrottled = false, 16); // ~60fps
            }});
        }}
        
        // Make updateAllConnections globally available
        window.updateAllConnections = updateAllConnections;
        
        // Set up observers after a short delay to ensure DOM is ready
        setTimeout(setupNodeObservers, 100);
        
        // Helper function to create bezier curve path
        function createBezierPath(start, end) {{
            const controlOffset = Math.abs(end.x - start.x) * 0.5;
            return `M ${{start.x}} ${{start.y}} C ${{start.x + controlOffset}} ${{start.y}}, ${{end.x - controlOffset}} ${{end.y}}, ${{end.x}} ${{end.y}}`;
        }}
        
        // Helper function to check if connection is valid
        function isValidConnection(startPin, endPin) {{
            if (!startPin || !endPin || startPin === endPin) return false;
            
            const startType = startPin.dataset.portType;
            const endType = endPin.dataset.portType;
            const startNodeId = startPin.dataset.nodeId;
            const endNodeId = endPin.dataset.nodeId;
            
            // Cannot connect to same node
            if (startNodeId === endNodeId) {{
                return false;
            }}
            
            // Must connect output to input or input to output
            const valid = (startType === 'output' && endType === 'input') || 
                         (startType === 'input' && endType === 'output');
            return valid;
        }}
        
        // Mouse down on connection pin - UPDATED to work with individual pins
        document.body.addEventListener('mousedown', (e) => {{
            
            const pin = e.target.closest('.connection-pin');
            if (!pin) return;
            
            e.preventDefault();
            e.stopPropagation();
            connectionState.isDragging = true;
            connectionState.startPin = pin;
            
            const startPos = getPinPosition(pin);
            
            // Create temporary path
            connectionState.tempPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const initialPath = createBezierPath(startPos, startPos);
            connectionState.tempPath.setAttribute('d', initialPath);
            connectionState.tempPath.setAttribute('stroke', '#4A90E2');
            connectionState.tempPath.setAttribute('stroke-width', '4');
            connectionState.tempPath.setAttribute('fill', 'none');
            connectionState.tempPath.setAttribute('stroke-dasharray', '8,4');
            connectionState.tempPath.style.pointerEvents = 'none';
            
            svg.appendChild(connectionState.tempPath);
            
            // Visual feedback on start pin
            pin.style.boxShadow = '0 0 15px #4A90E2';
            pin.style.transform = 'scale(1.8)';
            pin.style.zIndex = '10003';
        }}, true); // Use capture phase to get events first
        
        // Mouse move - update temporary path
        document.body.addEventListener('mousemove', (e) => {{
            if (!connectionState.isDragging || !connectionState.tempPath) return;
            
            const startPos = getPinPosition(connectionState.startPin);
            
            // Use enhanced coordinate transformation
            const mousePos = transformScreenToSVG(e.clientX, e.clientY);
            
            const pathData = createBezierPath(startPos, mousePos);
            connectionState.tempPath.setAttribute('d', pathData);
            
            // Highlight valid drop targets
            const targetPin = e.target.closest('.connection-pin');
            document.querySelectorAll('.connection-pin').forEach(pin => {{
                pin.classList.remove('connection-valid', 'connection-invalid');
                if (pin !== connectionState.startPin) {{
                    if (targetPin === pin) {{
                        if (isValidConnection(connectionState.startPin, pin)) {{
                            pin.classList.add('connection-valid');
                        }} else {{
                            pin.classList.add('connection-invalid');
                        }}
                    }}
                }}
            }});
        }}, true); // Use capture phase
        
        // Mouse up - finalize or cancel connection
        document.body.addEventListener('mouseup', (e) => {{
            if (!connectionState.isDragging) return;
            
            const endPin = e.target.closest('.connection-pin');
            
            // Cleanup temporary visual elements
            if (connectionState.tempPath) {{
                connectionState.tempPath.remove();
                connectionState.tempPath = null;
            }}
            
            if (connectionState.startPin) {{
                connectionState.startPin.style.boxShadow = '';
                connectionState.startPin.style.transform = '';
                connectionState.startPin.style.zIndex = '';
            }}
            
            // Clear highlighting
            document.querySelectorAll('.connection-pin').forEach(pin => {{
                pin.classList.remove('connection-valid', 'connection-invalid');
            }});
            
            // Create connection if valid
            if (endPin && isValidConnection(connectionState.startPin, endPin)) {{
                const startData = connectionState.startPin.dataset;
                const endData = endPin.dataset;
                
                // Call Python callback through global function
                if (window.haywire_on_connection_created) {{
                    window.haywire_on_connection_created(
                        startData.nodeId,
                        startData.portId,  // Changed from portName to portId
                        endData.nodeId, 
                        endData.portId     // Changed from portName to portId
                    );
                }} else {{
                    console.error('❌ Python callback not available');
                }}
            }}
            
            // Reset state
            connectionState.isDragging = false;
            connectionState.startPin = null;
        }}, true); // Use capture phase
                
        }}, 500); // Close the setTimeout
        """
        
        ui.run_javascript(js_code)
    
    def _setup_node_observers_js(self):
        """Setup JavaScript observers for node position changes."""
        js_code = f"""
        // Observer for node position changes - Canvas Manager: {self._callback_id}
        const nodeObserver = new MutationObserver((mutations) => {{
            mutations.forEach(mutation => {{
                if (mutation.attributeName === 'style') {{
                    const nodeElement = mutation.target;
                    const nodeId = nodeElement.dataset.nodeId;
                    
                    if (nodeId) {{
                        // Update connected paths
                        updateConnectionsForNode(nodeId);
                        
                        // Notify Python of position change (debounced)
                        clearTimeout(nodeElement._positionTimer);
                        nodeElement._positionTimer = setTimeout(() => {{
                            const rect = nodeElement.getBoundingClientRect();
                            const containerRect = document.querySelector('#node-container').getBoundingClientRect();
                            const relativeX = rect.left - containerRect.left;
                            const relativeY = rect.top - containerRect.top;
                            
                            if (window.haywire_on_node_position_changed) {{
                                window.haywire_on_node_position_changed(nodeId, relativeX, relativeY);
                            }}
                        }}, 100);
                    }}
                }}
            }});
        }});
        
        // Helper function to update connections for a specific node
        function updateConnectionsForNode(nodeId) {{
            const svg = document.querySelector('#connection-svg');
            if (!svg) return;
            
            // Find all paths connected to this node
            svg.querySelectorAll(`path[id*="${{nodeId}}"]`).forEach(path => {{
                updateConnectionPath(path);
            }});
        }}
        
        // Helper function to update a single connection path
        function updateConnectionPath(pathElement) {{
            const pathId = pathElement.id;
            const parts = pathId.split('__');
            if (parts.length < 7) return;
            
            // Reconstruct the full pin IDs from the parts
            // Format: connection__outlet__node_id__pin_id__inlet__node_id__pin_id
            // parts: [connection, outlet, node_id, pin_id, inlet, node_id, pin_id]
            const startPortId = parts[1] + '__' + parts[2] + '__' + parts[3];  // outlet__node_id__pin_id
            const endPortId = parts[4] + '__' + parts[5] + '__' + parts[6];    // inlet__node_id__pin_id
            
            const startPin = document.getElementById(startPortId);
            const endPin = document.getElementById(endPortId);
            
            if (!startPin || !endPin) {{
                pathElement.remove();
                return;
            }}
            
            // Use the global getPinPosition function
            const startPos = window.getPinPosition ? window.getPinPosition(startPin) : {{ x: 0, y: 0 }};
            const endPos = window.getPinPosition ? window.getPinPosition(endPin) : {{ x: 0, y: 0 }};
            
            const controlOffset = Math.abs(endPos.x - startPos.x) * 0.5;
            const pathData = `M ${{startPos.x}} ${{startPos.y}} C ${{startPos.x + controlOffset}} ${{startPos.y}}, ${{endPos.x - controlOffset}} ${{endPos.y}}, ${{endPos.x}} ${{endPos.y}}`;
            
            pathElement.setAttribute('d', pathData);
        }}
        
        // Start observing existing nodes
        document.querySelectorAll('[data-node-id]').forEach(node => {{
            nodeObserver.observe(node, {{ 
                attributes: true, 
                childList: true,
                subtree: true,
                attributeFilter: ['style', 'class'] 
            }});
        }});
        
        // Also add resize observer for better detection of size changes
        if (window.ResizeObserver) {{
            const resizeObserver = new ResizeObserver(entries => {{
                entries.forEach(entry => {{
                    const nodeElement = entry.target.closest('[data-node-id]');
                    if (nodeElement) {{
                        const nodeId = nodeElement.getAttribute('data-node-id');
                        if (nodeId) {{
                            updateConnectionsForNode(nodeId);
                        }}
                    }}
                }});
            }});
            
            document.querySelectorAll('[data-node-id]').forEach(node => {{
                resizeObserver.observe(node);
            }});
            
            window.haywire_resizeObserver = resizeObserver;
        }}
        
        // Store observer globally for adding new nodes
        window.haywire_nodeObserver = nodeObserver;
        
        // Make update function globally available
        window.updateConnectionPath = updateConnectionPath;
        """
        
        ui.run_javascript(js_code)
        
        # Register Python callbacks as global JavaScript functions
        self._register_js_callbacks()
    
    def _register_js_callbacks(self):
        """Register Python callbacks as global JavaScript functions."""
        # Create hidden elements for event handling
        self.connection_event = ui.element('div').style('display: none;')
        self.position_event = ui.element('div').style('display: none;')
        
        # Set up event handlers
        self.connection_event.on('connection_created', self._handle_connection_event)
        self.position_event.on('position_changed', self._handle_position_event)
        
        ui.run_javascript(f"""
        // Register Python callbacks for canvas manager: {self._callback_id}
        window.haywire_on_connection_created = function(startNodeId, startPort, endNodeId, endPort) {{
            // Trigger NiceGUI event
            const eventData = {{
                startNodeId: startNodeId,
                startPort: startPort,
                endNodeId: endNodeId,
                endPort: endPort
            }};
            document.querySelector('[data-event-target="connection"]').dispatchEvent(
                new CustomEvent('connection_created', {{ detail: eventData }})
            );
        }};
        
        window.haywire_on_node_position_changed = function(nodeId, x, y) {{
            // Trigger NiceGUI event
            const eventData = {{
                nodeId: nodeId,
                x: x,
                y: y
            }};
            document.querySelector('[data-event-target="position"]').dispatchEvent(
                new CustomEvent('position_changed', {{ detail: eventData }})
            );
        }};
        """)
        
        # Add event target attributes after creation
        self.connection_event.props('data-event-target="connection"')
        self.position_event.props('data-event-target="position"')
    
    # JavaScript Callback Handlers
    def _handle_connection_event(self, e: events.GenericEventArguments):
        """Handle connection creation from JavaScript."""
        try:
            data = e.args['detail']
            if self.on_connection_created:
                self.on_connection_created(
                    data['startNodeId'], 
                    data['startPort'], 
                    data['endNodeId'], 
                    data['endPort']
                )
        except Exception as ex:
            print(f"Error handling connection event: {ex}")
    
    def _handle_position_event(self, e: events.GenericEventArguments):
        """Handle node position change from JavaScript."""
        try:
            data = e.args['detail']
            if self.on_node_position_changed:
                self.on_node_position_changed(data['nodeId'], (data['x'], data['y']))
        except Exception as ex:
            print(f"Error handling position event: {ex}")
    
    def handle_js_connection_created(self, start_node_id: str, start_port: str, end_node_id: str, end_port: str):
        """Handle connection creation from JavaScript."""
        if self.on_connection_created:
            self.on_connection_created(start_node_id, start_port, end_node_id, end_port)
    
    def handle_js_node_position_changed(self, node_id: str, x: float, y: float):
        """Handle node position change from JavaScript."""
        if self.on_node_position_changed:
            self.on_node_position_changed(node_id, (x, y))
    
    # Node Management
    def add_node_visual(self, node: BaseNode, position: Tuple[float, float] = (100, 100)) -> bool:
        """Add a visual representation of a node to the canvas."""
        try:
            x, y = position
            print(f"Adding node visual for {node.node_id} at position ({x}, {y})")
            
            with self.node_container:
                with ui.column().classes('absolute').style(
                    f'left: {x}px; top: {y}px; z-index: 100;'
                ).props(f'data-node-id="{node.node_id}"') as container:
                    
                    print(f"Created container for node {node.node_id}")
                    
                    # Use UINode for proper rendering
                    ui_node = UINode(node, self.node_render_factory, container)
                    ui_node.render()
                    print(f"Rendered UINode for {node.node_id}")
                    
                    # Add connection pins to rendered node
                    self._add_connection_pins_to_node(ui_node, node)
                    print(f"Added connection pins for {node.node_id}")
                    
                    # Store reference
                    self.node_panels[node.node_id] = {
                        'ui_node': ui_node,
                        'container': container,
                        'position': position
                    }
                    
                    # Setup observer for this node if JS is ready
                    if self._js_setup_done:
                        ui.run_javascript(f"""
                        if (window.haywire_nodeObserver) {{
                            const nodeEl = document.querySelector('[data-node-id="{node.node_id}"]');
                            if (nodeEl) {{
                                window.haywire_nodeObserver.observe(nodeEl, {{ 
                                    attributes: true, 
                                    attributeFilter: ['style'] 
                                }});
                            }}
                        }}
                        """)
                        print(f"Setup JS observer for {node.node_id}")
            
            print(f"Successfully added node visual for {node.node_id}")
            return True
            
        except Exception as e:
            print(f"Error adding node visual: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _add_connection_pins_to_node(self, ui_node: UINode, node: BaseNode):
        """Add connection pins to a rendered node."""
        # Since DefaultNodeRenderer now creates pins with proper connection-pin class
        # and data attributes, we don't need to create duplicate pins here.
        # Just log that the node is ready for connections.
        print(f"Node {node.node_id} rendered with connection-ready pins from DefaultNodeRenderer")
        
        # Add the CSS for connection feedback states (only once)
        if not hasattr(self, '_css_added'):
            ui.add_head_html("""
            <style>
            .connection-pin {
                transition: all 0.2s ease !important;
                pointer-events: all !important;
                position: relative !important;
                z-index: 10000 !important;
            }
            .connection-pin:hover {
                transform: scale(1.3) !important;
                filter: brightness(1.2) !important;
                z-index: 10001 !important;
            }
            .connection-pin.connection-valid {
                box-shadow: 0 0 15px #4CAF50 !important;
                border-color: #4CAF50 !important;
                transform: scale(1.5) !important;
                z-index: 10002 !important;
            }
            .connection-pin.connection-invalid {
                box-shadow: 0 0 15px #f44336 !important;
                border-color: #f44336 !important;
                transform: scale(1.2) !important;
                z-index: 10002 !important;
            }
            </style>
            """)
            self._css_added = True
    
    def _create_connection_pin(self, node_id: str, port_name: str, port_type: str, port_obj):
        """Create a connection pin element."""
        pin_id = f"pin-{node_id}-{port_name}"
        port_color = getattr(port_obj, 'color', '#4A90E2' if port_type == 'output' else '#FF6B6B')
        
        print(f"Creating connection pin: {pin_id} ({port_type})")
        
        pin = ui.element('div').classes('connection-pin').props(
            f'id="{pin_id}" '
            f'data-node-id="{node_id}" '
            f'data-port-name="{port_name}" '
            f'data-port-type="{port_type}"'
        ).style(
            f'width: 32px; height: 32px; '
            f'background: {port_color}; '
            f'border: 4px solid white; '
            f'border-radius: 50%; '
            f'cursor: crosshair; '
            f'position: relative; '
            f'display: inline-block; '
            f'margin: 8px; '
            f'box-shadow: 0 6px 12px rgba(0,0,0,0.4); '
            f'z-index: 10000; '
            f'pointer-events: all; '
        )
        
        # Add immediate test click handler to verify the pin is working (but don't interfere with drag)
        pin.on('click', lambda e, pin_id=pin_id: self._test_pin_click(pin_id))
        
        # Add CSS for connection feedback - only add once
        if not hasattr(self, '_css_added'):
            ui.add_head_html("""
            <style>
            .connection-pin {
                transition: all 0.2s ease !important;
                pointer-events: all !important;
                position: relative !important;
                z-index: 10000 !important;
            }
            .connection-pin:hover {
                transform: scale(1.5) !important;
                box-shadow: 0 8px 16px rgba(0,0,0,0.5) !important;
                z-index: 10001 !important;
            }
            .connection-pin.connection-valid {
                box-shadow: 0 0 25px #4CAF50 !important;
                border-color: #4CAF50 !important;
                transform: scale(1.7) !important;
                z-index: 10002 !important;
            }
            .connection-pin.connection-invalid {
                box-shadow: 0 0 25px #f44336 !important;
                border-color: #f44336 !important;
                transform: scale(1.4) !important;
                z-index: 10002 !important;
            }
            </style>
            """)
            self._css_added = True
        
        # Add immediate JavaScript debugging for this specific pin
        ui.run_javascript(f"""
        setTimeout(() => {{
            const pin = document.getElementById('{pin_id}');
            if (pin) {{
                // Don't add individual click handlers that might interfere with drag
                // The drag system will handle all interactions
                
                const rect = pin.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) {{
                    console.error('❌ Pin {pin_id} has zero size!', rect);
                }}
                
            }} else {{
                console.error('❌ Pin {pin_id} not found in DOM!');
            }}
        }}, 100);
        """)
        
        # Add tooltip with detailed info
        tooltip_text = f'{port_type.title()}: {port_name}'
        if hasattr(port_obj, 'label'):
            tooltip_text += f' ({port_obj.label})'
        pin.tooltip(tooltip_text)
        
        return pin
    
    def _test_pin_click(self, pin_id: str):
        """Test function to verify pin clicks work (only fires on actual clicks, not drags)"""
        print(f"🎯 Python: Pin {pin_id} clicked successfully!")
        # Only show notification for testing, don't interfere with drag operations
        # ui.notify(f'Pin {pin_id} works!', type='positive')
    
    def remove_node_visual(self, node_id: str) -> bool:
        """Remove a node's visual representation."""
        if node_id not in self.node_panels:
            return False
            
        try:
            # Remove all connected edges visually first
            edges_to_remove = []
            for edge in self.graph.edges:
                if edge.input_node_id == node_id or edge.output_node_id == node_id:
                    edge_key = self._get_edge_key(edge)
                    edges_to_remove.append(edge_key)
            
            for edge_key in edges_to_remove:
                self.remove_connection_visual(edge_key)
            
            # Remove node visual
            visual_data = self.node_panels[node_id]
            
            if 'ui_node' in visual_data:
                ui_node = visual_data['ui_node']
                if hasattr(ui_node, 'cleanup'):
                    ui_node.cleanup()
            
            visual_data['container'].delete()
            del self.node_panels[node_id]
            
            # Remove from selection
            self.selected_nodes.discard(node_id)
            
            return True
            
        except Exception as e:
            print(f"Error removing node visual: {e}")
            return False
    
    def update_node_position(self, node_id: str, position: Tuple[float, float]):
        """Update a node's visual position."""
        if node_id not in self.node_panels:
            return
            
        x, y = position
        container = self.node_panels[node_id]['container']
        container.style(f'left: {x}px; top: {y}px;')
        self.node_panels[node_id]['position'] = position
    
    # Connection Management
    def _get_edge_key(self, edge: Edge) -> str:
        """Generate a unique key for an edge."""
        return f"{edge.output_node_id}-{edge.outlet_pin_id}-{edge.input_node_id}-{edge.inlet_pin_id}"
    
    def add_connection_visual(self, edge: Edge) -> bool:
        """Add a visual connection between two nodes."""
        print(f"🔗 Python: Adding connection visual for {edge.output_node_id}:{edge.outlet_pin_id} -> {edge.input_node_id}:{edge.inlet_pin_id}")
        try:
            # Generate pin IDs using the new centralized format
            start_pin_id = generate_pin_id('outlet', edge.output_node_id, edge.outlet_pin_id)
            end_pin_id = generate_pin_id('inlet', edge.input_node_id, edge.inlet_pin_id)
            path_id = f"connection__{start_pin_id}__{end_pin_id}"
            edge_key = self._get_edge_key(edge)
            
            print(f"🔗 Python: Creating path with ID: {path_id}")
            
            # Create SVG path element using JavaScript
            ui.run_javascript(f"""
            const svg = document.querySelector('#connection-svg');
            if (svg) {{
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('id', '{path_id}');
                path.setAttribute('stroke', '#4A90E2');
                path.setAttribute('stroke-width', '2');
                path.setAttribute('fill', 'none');
                path.style.pointerEvents = 'stroke';
                path.style.cursor = 'pointer';
                svg.appendChild(path);
                
                // Store reference for click handling
                path.addEventListener('click', function() {{
                    // Could trigger a Python callback here for connection deletion
                }});
            }}
            """)
            
            # Store in our tracking dict (we'll use the edge_key as identifier)
            self.connection_paths[edge_key] = True  # Just mark as existing
            
            # Force immediate path drawing regardless of setup state
            ui.run_javascript(f"""
            setTimeout(() => {{
                const path = document.getElementById('{path_id}');
                
                if (path) {{
                    // Try both global and local function access
                    if (window.updateConnectionPath) {{
                        window.updateConnectionPath(path);
                    }} else if (window.getPinPosition) {{
                        // Manual calculation as fallback
                        const pathId = path.id;
                        const parts = pathId.split('__');
                        if (parts.length >= 7) {{
                            const startPortId = parts[1] + '__' + parts[2] + '__' + parts[3];  // outlet__node_id__pin_id
                            const endPortId = parts[4] + '__' + parts[5] + '__' + parts[6];    // inlet__node_id__pin_id
                            const startPin = document.getElementById(startPortId);
                            const endPin = document.getElementById(endPortId);
                            if (startPin && endPin) {{
                                const startPos = window.getPinPosition(startPin);
                                const endPos = window.getPinPosition(endPin);
                                const controlOffset = Math.abs(endPos.x - startPos.x) * 0.5;
                                const pathData = `M ${{startPos.x}} ${{startPos.y}} C ${{startPos.x + controlOffset}} ${{startPos.y}}, ${{endPos.x - controlOffset}} ${{endPos.y}}, ${{endPos.x}} ${{endPos.y}}`;
                                path.setAttribute('d', pathData);
                            }}
                        }}
                    }}
                }}
            }}, 200);
            """)
            
            return True
            
        except Exception as e:
            print(f"Error adding connection visual: {e}")
            return False
    
    def remove_connection_visual(self, edge_key: str) -> bool:
        """Remove a connection's visual representation."""
        if edge_key not in self.connection_paths:
            return False
            
        try:
            # Parse edge key to get connection details
            parts = edge_key.split('-')
            if len(parts) >= 4:
                output_node_id, outlet_pin_id, input_node_id, inlet_pin_id = parts[0], parts[1], parts[2], parts[3]
                
                # Generate pin IDs using the new centralized format
                start_pin_id = generate_pin_id('outlet', output_node_id, outlet_pin_id)
                end_pin_id = generate_pin_id('inlet', input_node_id, inlet_pin_id)
                path_id = f"connection__{start_pin_id}__{end_pin_id}"
                
                # Remove SVG path using JavaScript
                ui.run_javascript(f"""
                const path = document.getElementById('{path_id}');
                if (path) {{
                    path.remove();
                }}
                """)
            
            del self.connection_paths[edge_key]
            return True
        except Exception as e:
            print(f"Error removing connection visual: {e}")
            return False
    
    def _on_connection_clicked(self, edge: Edge):
        """Handle connection click events."""
        print(f"Connection clicked: {edge.output_node_id} -> {edge.input_node_id}")
        if self.on_connection_removed:
            self.on_connection_removed(edge)
    
    # Graph Synchronization
    def sync_with_graph(self):
        """Synchronize visual representation with the graph state."""
        # Sync nodes
        graph_node_ids = set(self.graph.nodes.keys())
        visual_node_ids = set(self.node_panels.keys())
        
        # Add missing nodes
        for node_id in graph_node_ids - visual_node_ids:
            node = self.graph.nodes[node_id]
            position = (
                getattr(node, 'ui_posX', 100),
                getattr(node, 'ui_posY', 100)
            )
            self.add_node_visual(node, position)
        
        # Remove extra nodes
        for node_id in visual_node_ids - graph_node_ids:
            self.remove_node_visual(node_id)
        
        # Sync connections
        graph_edge_keys = set(self._get_edge_key(edge) for edge in self.graph.edges)
        visual_edge_keys = set(self.connection_paths.keys())
        
        # Add missing connections
        for edge in self.graph.edges:
            edge_key = self._get_edge_key(edge)
            if edge_key not in visual_edge_keys:
                self.add_connection_visual(edge)
        
        # Remove extra connections
        for edge_key in visual_edge_keys - graph_edge_keys:
            self.remove_connection_visual(edge_key)
    
    def clear_all_visuals(self):
        """Clear all visual representations."""
        # Clear nodes
        for node_id in list(self.node_panels.keys()):
            self.remove_node_visual(node_id)
        
        # Clear connections
        for edge_key in list(self.connection_paths.keys()):
            self.remove_connection_visual(edge_key)
        
        # Clear selection
        self.selected_nodes.clear()
    
    # Selection Management
    def select_node(self, node_id: str, multi_select: bool = False):
        """Select a node."""
        if not multi_select:
            self.selected_nodes.clear()
        
        self.selected_nodes.add(node_id)
        
        if self.on_node_selected:
            self.on_node_selected(node_id, True)
    
    def deselect_node(self, node_id: str):
        """Deselect a node."""
        self.selected_nodes.discard(node_id)
        
        if self.on_node_selected:
            self.on_node_selected(node_id, False)
    
    def get_selected_nodes(self) -> Set[str]:
        """Get currently selected nodes."""
        return self.selected_nodes.copy()
    
    # Cleanup
    def update_zoom_pan_state(self, zoom: float = None, pan_x: float = None, pan_y: float = None):
        """Update internal zoom/pan state and trigger coordinate recalculation."""
        if zoom is not None:
            self.current_zoom = zoom
        if pan_x is not None:
            self.current_pan_x = pan_x  
        if pan_y is not None:
            self.current_pan_y = pan_y
        
        # Update JavaScript state and invalidate pin position cache
        ui.run_javascript(f"""
        // Update global zoom/pan state
        if (window.updateCanvasZoomPanState) {{
            window.updateCanvasZoomPanState({self.current_zoom}, {self.current_pan_x}, {self.current_pan_y});
        }}
        
        // Clear position cache when zoom/pan changes
        if (window.pinPositionCache) {{
            window.pinPositionCache.clear();
            window.cacheValidUntil = 0;
        }}
        
        // Update all connections with new coordinates
        if (window.updateAllConnections) {{
            window.updateAllConnections();
        }}
        """)
    
    def cleanup(self):
        """Cleanup resources."""
        self.clear_all_visuals()
        self.node_render_factory = None
        self.graph = None


# Global callback registry for JavaScript bridge
_canvas_managers: Dict[str, GraphCanvasManager] = {}

def register_canvas_manager(manager: GraphCanvasManager):
    """Register a canvas manager for JavaScript callbacks."""
    _canvas_managers[manager._callback_id] = manager

def unregister_canvas_manager(manager: GraphCanvasManager):
    """Unregister a canvas manager."""
    if manager._callback_id in _canvas_managers:
        del _canvas_managers[manager._callback_id]
