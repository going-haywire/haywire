"""
Node Editor component for individual node rendering and interaction
"""

from typing import Dict, Any
from nicegui import ui, events
from utils.node import Node, NodePort

class NodePanel:
    """Handles rendering and interaction for individual nodes"""
    
    def __init__(self, node: Node, node_graph):
        self.node = node
        self.node_graph = node_graph
        self.ui_element = None
        # Local dragging state
        self._is_dragging = False
        self._drag_offset = (0, 0)
        self._drag_start_pos = (0, 0)
        
    def render(self) -> ui.element:
        """Render the node as a UI element"""
        # Use a card to represent the node
        with ui.card().tight().classes(
            f'absolute node-card node-{self.node.node_type.value}'
        ).style(
            f'left: {self.node.x}px; '
            f'top: {self.node.y}px; '
            f'width: {self.node.width}px; '
            f'min-height: {self.node.height}px; '
            f'background: {self._get_node_color()}; '
            f'border: {"2px solid #1976d2" if self.node.selected else "1px solid #ccc"}; '
            'cursor: grab; '
            'user-select: none; '
            'z-index: 1;'
        ).props(f'data-node-id="{self.node.id}"') as self.node_card:
            
            # Node header with drag handle
            with ui.row().classes('w-full items-center justify-between q-pa-xs drag-handle').style('cursor: grab;'):
                ui.icon('drag_indicator').classes(
                        'text-grey-6'
                    ).on(
                        'mousedown', 
                        self._on_mouse_down, 
                        args=[
                            'clientX', 
                            'clientY', 
                            'offsetX', 
                            'offsetY', 
                            'button'
                        ]
                    )
                ui.label(self.node.name).classes('text-subtitle2 font-weight-bold')
                
                # Close button
                ui.button(
                    icon='close',
                    on_click=lambda: self.node_graph.remove_node(self.node.id)
                ).props('flat dense size=sm').classes('text-red')
            
            ui.separator()
            
            # Node content area
            with ui.row().classes('w-full justify-start q-pa-xs'):
                self._render_node_content()
            
            # Input ports
            if self.node.inputs:
                for port in self.node.inputs:
                    self._render_input_port(port)
            
            # Output ports
            if self.node.outputs:
                for port in self.node.outputs:
                    self._render_output_port(port)
            
            # Add drag and click handlers using NiceGUI's event system
            self.node_card.on('click', self._on_click)
            
            self.ui_element = self.node_card
            
        return self.node_card
    
    def _render_node_content(self):
        """Render node-specific content"""
        # Different content based on node type
        if self.node.node_type.value == 'comment':
            ui.textarea(
                placeholder='Enter comment...',
                value=self.node.properties.get('comment', '')
            ).classes('w-full').props('dense outlined')
            
        elif self.node.node_type.value == 'input':
            with ui.column().classes('w-full'):
                ui.label('Value:').classes('text-caption')
                ui.input(
                    value=str(self.node.properties.get('value', '')),
                    on_change=lambda e: self._update_property('value', e.value)
                ).classes('w-full').props('dense outlined')
                
        elif self.node.node_type.value in ['add', 'subtract', 'multiply', 'divide']:
            ui.label(f'Operation: {self.node.node_type.value.upper()}').classes('text-caption')
            
        elif self.node.node_type.value == 'display':
            result = self.node.properties.get('result', 'No data')
            ui.label(f'Output: {result}').classes('text-caption')
            
        else:
            # Default content
            ui.label(f'Type: {self.node.node_type.value}').classes('text-caption')
    
    def _render_input_port(self, port: NodePort):
        """Render an input port"""
        color = self._get_port_color(port.data_type)
        
        with ui.row().classes('w-full items-center justify-start'):
            # Port connector
            ui.element('div').classes(
                f'port input-port port-{port.data_type}'
            ).style(
                f'width: 12px; height: 12px; '
                f'background: {color}; '
                f'border: 2px solid white; '
                f'border-radius: 50%; '
                f'margin-right: 4px; '
                f'cursor: crosshair;'
            ).props(f'data-port-id="{port.id}"')
            
            # Port label
            ui.label(port.name).classes('text-caption')
    
    def _render_output_port(self, port: NodePort):
        """Render an output port"""
        color = self._get_port_color(port.data_type)
        
        with ui.row().classes('w-full items-center justify-end'):
            # Port label
            ui.label(port.name).classes('text-caption')
            
            # Port connector
            ui.element('div').classes(
                f'port output-port port-{port.data_type}'
            ).style(
                f'width: 12px; height: 12px; '
                f'background: {color}; '
                f'border: 2px solid white; '
                f'border-radius: 50%; '
                f'margin-left: 4px; '
                f'cursor: crosshair;'
            ).props(f'data-port-id="{port.id}"')
    
    def _get_node_color(self) -> str:
        """Get the background color for the node based on its type"""
        colors = {
            'input': '#e8f5e8',
            'output': '#ffe8e8',
            'comment': '#fff8e1',
            'add': '#e3f2fd',
            'subtract': '#e3f2fd', 
            'multiply': '#e3f2fd',
            'divide': '#e3f2fd',
            'and': '#f3e5f5',
            'or': '#f3e5f5',
            'not': '#f3e5f5',
            'compare': '#f3e5f5',
            'display': '#fce4ec',
            'chart': '#fce4ec',
            'export': '#fce4ec'
        }
        return colors.get(self.node.node_type.value, '#f5f5f5')
    
    def _get_port_color(self, data_type: str) -> str:
        """Get the color for a port based on its data type"""
        colors = {
            'number': '#2196f3',
            'string': '#4caf50', 
            'boolean': '#ff9800',
            'array': '#9c27b0',
            'any': '#757575'
        }
        return colors.get(data_type, '#757575')
    
    def _update_property(self, key: str, value: Any):
        """Update a node property"""
        self.node.properties[key] = value
        self.node_graph.update_node_property(self.node.id, key, value)
    
    def _on_mouse_down(self, e):
        """Handle mouse down event to start dragging"""
        # Only handle left mouse button
        if e.args.get('button', 0) != 0:
            return
            
        client_x = e.args.get('clientX', 0)
        client_y = e.args.get('clientY', 0)
        
        # Start local dragging
        self._start_local_drag(client_x, client_y)
        
        # Change cursor to indicate dragging
        self.node_card.style('cursor: grabbing;')
        # Note: Removed direct ui.notify call - notifications should be handled by higher layers

    def _on_click(self, e):
        """Handle node click for selection"""
        # Only select if we're not dragging
        if not self._is_dragging:
            self.node_graph.select_node(self.node.id, multi_select=False)
            # Note: Removed direct ui.notify call - notifications should be handled by higher layers
    
    def update_position(self, x: float, y: float):
        """Update the visual position of the node"""
        self.node.x = x
        self.node.y = y
        # Update the visual position immediately
        if self.node_card:
            self.node_card.style(
                f'left: {self.node.x}px; '
                f'top: {self.node.y}px; '
                f'width: {self.node.width}px; '
                f'min-height: {self.node.height}px; '
                f'background: {self._get_node_color()}; '
                f'border: {"2px solid #1976d2" if self.node.selected else "1px solid #ccc"}; '
                'cursor: grab; '
                'user-select: none; '
                'z-index: 1;'
            )
    
    def update_selection(self):
        """Update the visual selection state"""
        if self.ui_element:
            border_style = "2px solid #1976d2" if self.node.selected else "1px solid #ccc"
            # In a production app, you'd need more sophisticated style management
            pass
    
    # Local dragging methods
    def _start_local_drag(self, client_x: float, client_y: float):
        """Start local dragging"""
        self._is_dragging = True
        self._drag_start_pos = (client_x, client_y)
        self._drag_offset = (client_x - self.node.x, client_y - self.node.y)
        
        # Notify node graph that dragging started
        self.node_graph.on_node_drag_started(self.node.id)
    
    def update_drag_position(self, client_x: float, client_y: float):
        """Update position during drag"""
        if not self._is_dragging:
            return
        
        # Calculate new position
        new_x = client_x - self._drag_offset[0]
        new_y = client_y - self._drag_offset[1]
        
        # Apply constraints (stay within bounds)
        new_x = max(0, new_x)
        new_y = max(0, new_y)
        
        # Update the node model
        self.node.set_position(new_x, new_y)
        
        # Update visual position immediately
        self._update_visual_position()
        
        # Notify node graph of position change
        self.node_graph.on_node_position_changed(self.node.id, new_x, new_y)
    
    def end_local_drag(self):
        """End local dragging"""
        if self._is_dragging:
            self._is_dragging = False
            self._drag_offset = (0, 0)
            self._drag_start_pos = (0, 0)
            
            # Reset cursor
            if self.node_card:
                self.node_card.style('cursor: grab;')
            
            # Notify node graph that dragging ended
            self.node_graph.on_node_drag_ended(self.node.id)
    
    def _update_visual_position(self):
        """Update the visual position of the node"""
        if self.node_card:
            self.node_card.style(
                f'left: {self.node.x}px; '
                f'top: {self.node.y}px; '
                f'width: {self.node.width}px; '
                f'min-height: {self.node.height}px; '
                f'background: {self._get_node_color()}; '
                f'border: {"2px solid #1976d2" if self.node.selected else "1px solid #ccc"}; '
                'cursor: grabbing; '
                'user-select: none; '
                'z-index: 1;'
            )
    
    def is_dragging(self) -> bool:
        """Check if this node is currently being dragged"""
        return self._is_dragging
