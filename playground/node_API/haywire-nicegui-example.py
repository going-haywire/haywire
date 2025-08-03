"""
Haywire NiceGUI Integration Example
===================================
Shows how the UI-agnostic node data structure integrates with NiceGUI
"""

from nicegui import ui
from typing import Any, Optional
import weakref
from abc import abstractmethod

# Import from the haywire_node_data module
# In practice, this would be: from haywire_node_data import ...
# For this example, we'll define the minimal required classes

from haywire_node_data import (
    NodeData, DataField, HaywireNode, DataType, DataCategory, FlowType, Config, Inlet, Outlet)


class NiceGUINodeRenderer:
    """Renders Haywire nodes using NiceGUI elements"""
    
    # UI element mapping based on type and hints
    UI_ELEMENTS = {
        (DataType.INT, 'slider'): 'slider',
        (DataType.INT, 'number'): 'number',
        (DataType.FLOAT, 'slider'): 'slider',
        (DataType.FLOAT, 'number'): 'number',
        (DataType.FLOAT, 'knob'): 'knob',
        (DataType.BOOL, None): 'checkbox',
        (DataType.BOOL, 'switch'): 'switch',
        (DataType.BOOL, 'toggle'): 'toggle',
        (DataType.STR, None): 'input',
        (DataType.STR, 'textarea'): 'textarea',
        (DataType.STR, 'dropdown'): 'select',
        (DataType.STR, 'radio'): 'radio',
        (DataType.STR, 'chips'): 'chips',
    }
    
    def __init__(self, node: NodeData):
        """Initialize with a node (which is also NodeData)"""
        self.node = node
        self.ui_elements = {}
    
    def render_node(self, title: str = "Node"):
        """Render complete node UI"""
        with ui.card().classes('w-64'):
            ui.label(title).classes('text-h6')
            
            # Render configs
            if self.node.configs:
                with ui.expansion('Configuration', value=True):
                    for config in self.node.configs.values():
                        if config.is_visible:
                            self._render_element('config', config)
            
            # Render parameter inlets (inlets with UI that act as parameters)
            param_inlets = [i for i in self.node.inlets.values() if i.is_visible and i.is_enabled and hasattr(i, 'ui') and i.ui]
            if param_inlets:
                ui.label('Parameters').classes('font-bold text-sm mt-2')
                for inlet in param_inlets:
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.label(inlet.name).classes('w-20 text-xs')
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
        ui_widget = element.ui.get('widget')
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
            'label': element.name,
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['label', 'placeholder', 'password', 'password_toggle_button', 'autocomplete']:
            if prop in ui_props:
                input_kwargs[prop] = ui_props[prop]
        
        def update_value(e):
            element.data.set_value(e.value)

        input_element = ui.input(**input_kwargs, on_change=update_value)
        
        self.ui_elements[element.id] = input_element

    def _create_number(self, element_type: str, element, ui_props):
        """Create a number input element"""
        # Build kwargs dynamically
        number_kwargs = {
            'label': element.name,
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['label', 'placeholder', 'min', 'max', 'precision', 'step', 'prefix', 'suffix', 'format']:
            if prop in ui_props:
                number_kwargs[prop] = ui_props[prop]
        
        def update_value(e):
            element.data.set_value(e.value)

        number = ui.number(**number_kwargs, on_change=update_value)
        
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

        slider = ui.slider(**slider_kwargs, on_change=update_value)
                
        # Label showing current value - also bound to the data
        label = ui.label(). bind_text_from(element.data, 'value', 
                                         lambda v: f'{element.name}: {v}')
        
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

        knob = ui.knob(**knob_kwargs, on_change=update_value)
                
        self.ui_elements[element.id] = knob

    def _create_checkbox(self, element_type: str, element, ui_props):
        """Create a checkbox element"""
        # Build kwargs dynamically
        checkbox_kwargs = {
            'text': element.name,
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['text']:
            if prop in ui_props:
                checkbox_kwargs[prop] = ui_props[prop]

        def update_value(e):
            element.data.set_value(e.value)

        checkbox = ui.checkbox(**checkbox_kwargs, on_change=update_value)
        
        self.ui_elements[element.id] = checkbox
    
    def _create_switch(self, element_type: str, element, ui_props):
        """Create a switch element"""
        # Build kwargs dynamically
        switch_kwargs = {
            'text': element.name,
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['text']:
            if prop in ui_props:
                switch_kwargs[prop] = ui_props[prop]
        
        def update_value(e):
            element.data.set_value(e.value)

        switch = ui.switch(**switch_kwargs, on_change=update_value)
        
        self.ui_elements[element.id] = switch
    
    def _create_select(self, element_type: str, element, ui_props):
        """Create a dropdown select element"""
        # Build kwargs dynamically
        select_kwargs = {
            'options': ui_props.get('options', []),
            'label': element.name,
            'value': element.data.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['label', 'options', 'clearable', 'multiple', 'with_input']:
            if prop in ui_props:
                select_kwargs[prop] = ui_props[prop]
        
        def update_value(e):
            element.data.set_value(e.value)
        
        select = ui.select(**select_kwargs, on_change=update_value)
        
        self.ui_elements[element.id] = select
    

# Example custom node using inheritance
class MathProcessorNode(HaywireNode):
    """Example node that inherits from HaywireNode"""
    
    # Class metadata (from your specification)
    node_name = 'MathProcessor'
    node_display_name = 'Math Processor'
    node_package = 'com.example.math'
    node_library_name = 'ExampleLibrary'
    node_library_url = 'https://example.com'
    node_search_tags = ['math', 'processor', 'example']
    node_menu = 'Math/Processors'
    node_version = '1.0.0'
    
    def __init__(self, node_id: str, graph):
        super().__init__(node_id, graph)
        self.is_control_node = True
        self.is_data_node = False
        self._setup_node()
    
    def _setup_node(self):
        """Configure the node's inputs/outputs"""
        # Add various configs and properties
        self.add_config(Config(
            'precision',
            'Precision',
            DataField(DataType.INT, DataCategory.SCALAR, 2),
            callback=self.on_precision_changed,
            ui={'widget': 'slider', 'properties': {'min': 0, 'max': 10}}
        ))
        
        self.add_config(Config(
            'mode',
            'Processing Mode',
            DataField(DataType.STR, DataCategory.SCALAR, 'fast'),
            ui={'widget': 'select', 'properties': {'options': ['fast', 'balanced', 'quality']}}
        ))
        
        # Add inlets with default values (these were previously properties)
        self.add_inlet(Inlet(
            'scale',
            'Scale Factor',
            FlowType.DATA,
            data=DataField(DataType.FLOAT, DataCategory.SCALAR, 1.0),
            ui={'widget': 'knob', 'properties': {'min': 0.1, 'max': 10.0}}
        ))
        
        self.add_inlet(Inlet(
            'invert',
            'Invert Result',
            FlowType.DATA,
            data=DataField(DataType.BOOL, DataCategory.SCALAR, False),
            ui={'widget': 'switch'}
        ))
        
        self.add_inlet(Inlet(
            'threshold',
            'Threshold',
            FlowType.DATA,
            data=DataField(DataType.FLOAT, DataCategory.SCALAR, 0.5),
            ui={'widget': 'number', 'properties': {'min': 0.0, 'max': 1.0}}
        ))
        
        # Add inlets/outlets
        self.add_inlet(Inlet(
            'ctrl_in',
            'Execute',
            FlowType.CTRL,
            coupling_type='many'
        ))
        
        self.add_inlet(Inlet(
            'value_in',
            'Input Value',
            FlowType.DATA,
            has_default='scale',
            data=DataField(DataType.FLOAT, DataCategory.SCALAR)
        ))
        
        self.add_inlet(Inlet(
            'multi_in',
            'Multiple Values',
            FlowType.DATA,
            coupling_type='many',
            data=DataField(DataType.FLOAT, DataCategory.SCALAR)
        ))
        
        self.add_outlet(Outlet(
            'ctrl_out',
            'Next',
            FlowType.CTRL,
            DataField(DataType.OBJECT, DataCategory.SCALAR)
        ))
        
        self.add_outlet(Outlet(
            'result_out',
            'Result',
            FlowType.DATA,
            DataField(DataType.FLOAT, DataCategory.SCALAR)
        ))
    
    def on_precision_changed(self):
        """Handle precision config change"""
        precision = self.configs['precision'].data.get_value()
        print(f"Precision changed to: {precision}")
    
    def worker(self, context: dict):
        """Process the node"""
        # Direct access to all data
        input_value = self.get_inlet_value('value_in')
        multi_values = self.get_inlet_values_list('multi_in')
        
        precision = self.configs['precision'].data.get_value()
        mode = self.configs['mode'].data.get_value()
        invert = self.inlets['invert'].data.get_value()
        threshold = self.inlets['threshold'].data.get_value()
        
        # Process - handle None input_value
        if input_value is None:
            input_value = 0  # Default value when no input is connected
        result = round(input_value * 2, precision)
        
        if multi_values:
            if mode == 'fast':
                result += sum(multi_values)
            elif mode == 'balanced':
                result += sum(multi_values) / len(multi_values)
            else:  # quality
                result += sum(v for v in multi_values if v > threshold)
        
        if invert:
            result = -result
        
        # Set outputs
        self.set_outlet_value('result_out', result)
        self.mark_inlets_clean()
        
        return {'next_pin': 'ctrl_out'}

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
            inlet = node.inlets['multi_in']
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
            print(f"Multi inlet dict: {node.get_inlet_value('multi_in')}")
            print(f"Multi inlet list: {node.get_inlet_values_list('multi_in')}")
        
        ui.button('Print State', on_click=print_state)
    
    ui.run()


if __name__ in {'__main__', '__mp_main__'}:
    main()
