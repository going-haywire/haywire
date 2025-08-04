"""
Haywire NiceGUI Integration Example
===================================
Shows how the UI-agnostic node data structure integrates with NiceGUI
"""

import sys
import os

from nicegui import ui
from typing import Any, Dict, Tuple, Optional

# Import from the haywire_node_data module
# In practice, this would be: from haywire_node_data import ...
# For this example, we'll define the minimal required classes

# --- New Haywire Core Imports ---

# Add the project root to the Python path to allow imports from the 'haywire' package.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# The following imports are from the newly refactored core library
# This demonstrates how a UI layer would consume the UI-agnostic data model
from haywire.core.data.enums import DataType
from haywire.core.node.node import NodeData

from .math_processor_node import MathProcessorNode
# --------------------------------


class NiceGUINodeRenderer:
    """Renders Haywire nodes using NiceGUI elements"""
    
    # UI element mapping based on type and hints
    UI_ELEMENTS: Dict[Tuple[DataType, Optional[str]], str] = {
        (DataType.INT, 'slider'): 'slider',
        (DataType.INT, 'number'): 'number',
        (DataType.FLOAT, 'slider'): 'slider',
        (DataType.FLOAT, 'number'): 'number',
        (DataType.FLOAT, 'knob'): 'knob',
        (DataType.BOOL, None): 'checkbox',
        (DataType.BOOL, 'switch'): 'switch',
        (DataType.BOOL, 'toggle'): 'toggle',
        (DataType.STRING, None): 'input',
        (DataType.STRING, 'textarea'): 'textarea',
        (DataType.STRING, 'dropdown'): 'select',
        (DataType.STRING, 'radio'): 'radio',
        (DataType.STRING, 'chips'): 'chips',
    }
    
    def __init__(self, node: NodeData):
        """Initialize with a node (which is also NodeData)"""
        self.node = node
        self.ui_elements = {}
    
    def render_node(self, title: str = "Node"):
        """Render complete node UI"""
        with ui.card().classes('w-full min-w-64 max-w-sm'):
            ui.label(title).classes('text-h6 w-full')
            
            # Render configs
            if self.node.configs:
                ui.label('Configuration').classes('font-bold text-sm mt-2 w-full')
                for config in self.node.configs.values():
                    ui.label(config.label).classes('text-xs')
                    self._render_element('config', config)
        
            # Render parameter inlets (inlets with UI that act as parameters)
            param_inlets = [i for i in self.node.inlets.values() if hasattr(i, 'ui') and i.ui]
            if param_inlets:
                ui.label('Parameters').classes('font-bold text-sm mt-2 w-full')
                for inlet in param_inlets:
                    with ui.column().classes('w-full gap-1'):
                        ui.label(inlet.label).classes('text-xs')
                        self._render_element('inlet', inlet)
            
            # Show inlet/outlet status
            with ui.row().classes('w-full justify-between'):
                ui.label(f'↓ {len(self.node.inlets)}').classes('text-caption')
                ui.label(f'↑ {len(self.node.outlets)}').classes('text-caption')
    
    def _render_element(self, element_type: str, element):
        """Render a single config or property element"""
        if not element.data:
            return
        
        data_type = element.data.type
        ui_widget = element.widget
        ui_props = element.ui.get('properties', {})
        
        # Create appropriate UI element
        if ui_widget == 'slider':
            self._create_slider(element_type, element, ui_props)
        elif ui_widget == 'number':
            self._create_number(element_type, element, ui_props)
        elif ui_widget == 'checkbox':
            self._create_checkbox(element_type, element, ui_props)
        elif ui_widget == 'switch':
            self._create_switch(element_type, element, ui_props)
        elif ui_widget == 'input':
            self._create_input(element_type, element, ui_props)
        elif ui_widget == 'select':
            self._create_select(element_type, element, ui_props)
        elif ui_widget == 'knob':
            self._create_knob(element_type, element, ui_props)
        else:
            # Default fallback
            self._create_input(element_type, element, {})
    
    def _create_input(self, element_type: str, element, ui_props):
        """Create an input element"""
        # Build kwargs dynamically
        input_kwargs = {
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['label', 'placeholder', 'password', 'password_toggle_button', 'autocomplete']:
            if prop in ui_props:
                input_kwargs[prop] = ui_props[prop]
        
        def update_value(e):
            element.data.set_value(e.value)

        input_element = ui.input(**input_kwargs, on_change=update_value).classes('w-full')
        
        self.ui_elements[element.id] = input_element

    def _create_number(self, element_type: str, element, ui_props):
        """Create a number input element"""
        # Build kwargs dynamically
        number_kwargs = {
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['label', 'placeholder', 'min', 'max', 'precision', 'step', 'prefix', 'suffix', 'format']:
            if prop in ui_props:
                number_kwargs[prop] = ui_props[prop]
        
        def update_value(e):
            element.data.set_value(e.value)

        number = ui.number(**number_kwargs, on_change=update_value).classes('w-full')
        
        self.ui_elements[element.id] = number

    def _create_slider(self, element_type: str, element, ui_props):
        """Create a slider element"""
        # Build kwargs dynamically
        slider_kwargs = {
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['min', 'max', 'step']:
            if prop in ui_props:
                slider_kwargs[prop] = ui_props[prop]
        
        # Set defaults if not specified
        if 'min' not in slider_kwargs:
            slider_kwargs['min'] = 0
        if 'max' not in slider_kwargs:
            slider_kwargs['max'] = 100
        
        def update_value(e):
            element.data.set_value(e.value)

        slider = ui.slider(**slider_kwargs, on_change=update_value).classes('w-full').props('label-always')
                        
        self.ui_elements[element.id] = slider

    def _create_knob(self, element_type: str, element, ui_props):
        """Create a knob element"""
        # Build kwargs dynamically
        knob_kwargs: dict[str, Any] = {
            'value': element.data.get_value(),
            'show_value': True
        }
        
        # Apply direct property mapping
        for prop in ['min', 'max', 'step', 'color', 'center_color', 'track_color', 'size', 'show_value']:
            if prop in ui_props:
                knob_kwargs[prop] = ui_props[prop]
        
        def update_value(e):
            element.data.set_value(e.value)

        with ui.row().classes('w-full justify-center'):
            knob = ui.knob(**knob_kwargs, on_change=update_value)
                
        self.ui_elements[element.id] = knob

    def _create_checkbox(self, element_type: str, element, ui_props):
        """Create a checkbox element"""
        # Build kwargs dynamically
        checkbox_kwargs = {
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['text']:
            if prop in ui_props:
                checkbox_kwargs[prop] = ui_props[prop]

        def update_value(e):
            element.data.set_value(e.value)

        checkbox = ui.checkbox(**checkbox_kwargs, on_change=update_value).classes('w-full')
        
        self.ui_elements[element.id] = checkbox
    
    def _create_switch(self, element_type: str, element, ui_props):
        """Create a switch element"""
        # Build kwargs dynamically
        switch_kwargs = {
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['text']:
            if prop in ui_props:
                switch_kwargs[prop] = ui_props[prop]
        
        def update_value(e):
            element.data.set_value(e.value)

        switch = ui.switch(**switch_kwargs, on_change=update_value).classes('w-full')
        
        self.ui_elements[element.id] = switch
    
    def _create_select(self, element_type: str, element, ui_props):
        """Create a dropdown select element"""
        # Build kwargs dynamically
        select_kwargs = {
            'options': ui_props.get('options', []),
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['options', 'clearable', 'multiple', 'with_input']:
            if prop in ui_props:
                select_kwargs[prop] = ui_props[prop]
        
        def update_value(e):
            element.data.set_value(e.value)
        
        select = ui.select(**select_kwargs, on_change=update_value).classes('w-full')
        
        self.ui_elements[element.id] = select
    

# ... (rest of the code remains the same)
def main():
    """Run the demo"""
    # Create example node (simulating graph context)
    class DummyGraph:
        pass
    
    node = MathProcessorNode('node_001', DummyGraph())
    
    # Create renderer
    renderer = NiceGUINodeRenderer(node)
    
    # Add title
    ui.label('Haywire Node UI Demo').classes('text-h4')
    
    # Render the node
    renderer.render_node(node.node_display_name)
    
    # Add some controls to demonstrate functionality
    with ui.card().classes('mt-4'):
        ui.label('Node Testing').classes('text-h6')
        
        def toggle_connection():
            inlet = node.inlets['value_in']
            inlet.is_connected = not inlet.is_connected
            ui.notify(f"Input {'connected' if inlet.is_connected else 'disconnected'}")
        
        ui.button('Toggle Input Connection', on_click=toggle_connection)
        
        def simulate_multi_input():
            """Simulate multiple inputs"""
            inlet = node.inlets['multi_values']
            inlet.set_value_from_source('pipe_1', 10.5)
            inlet.set_value_from_source('pipe_2', 20.3)
            inlet.set_value_from_source('pipe_3', 15.7)
            ui.notify(f"Added 3 multi-inputs: {inlet.data.get_values_list()}")
        
        ui.button('Simulate Multi-Input', on_click=simulate_multi_input)
        
        def run_worker():
            """Run the worker function"""
            import time
            start_time = time.perf_counter()
            result = node.worker({})
            end_time = time.perf_counter()
            execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
            output = node.outlets['result_out'].data.get_value()
            ui.notify(f"Worker executed in {execution_time:.3f}ms. Result: {output}")
        
        ui.button('Execute Worker', on_click=run_worker)
        
        def print_state():
            print("\nNode State:")
            print(f"Node: {node.node_name} v{node.node_version}")
            print(f"Configs: {[(k, v.data.get_value()) for k, v in node.configs.items()]}")
            print(f"Parameter Inlets: {[(k, v.data.get_value()) for k, v in node.inlets.items() if v.data and hasattr(v.data, 'get_value')]}")
            print(f"Single inlet: {node.get_inlet_value('value_in')}")
            print(f"Multi inlet dict: {node.get_inlet_value('multi_values')}")
            print(f"Multi inlet list: {node.get_inlet_values_list('multi_values')}")
        
        ui.button('Print State', on_click=print_state)
    
    ui.run()


if __name__ in {'__main__', '__mp_main__'}:
    main()
