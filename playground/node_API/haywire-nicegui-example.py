"""
Haywire NiceGUI Integration Example
===================================
Shows how the UI-agnostic node data structure integrates with NiceGUI
"""

from nicegui import ui
from typing import Optional
import weakref
from abc import abstractmethod

# Import from the haywire_node_data module
# In practice, this would be: from haywire_node_data import ...
# For this example, we'll define the minimal required classes

from haywire_node_data import (
    NodeData, HaywireNode, UIBinding, DataType, DataCategory, 
    DataField, Config, Property, Inlet, Outlet, FlowType
)


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
        self.ui_binding = UIBinding(node)
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
            
            # Render properties (that are enabled)
            visible_props = [
                p for p in self.node.properties.values() 
                if p.is_visible and p.is_enabled
            ]
            if visible_props:
                with ui.expansion('Properties', value=True):
                    for prop in visible_props:
                        self._render_element('property', prop)
            
            # Show inlet/outlet status
            with ui.row().classes('w-full justify-between'):
                ui.label(f'↓ {len(self.node.inlets)}').classes('text-caption')
                ui.label(f'↑ {len(self.node.outlets)}').classes('text-caption')
    
    def _render_element(self, element_type: str, element):
        """Render a single config or property element"""
        if not element.data:
            return
        
        data_type = element.data.type
        ui_hint = element.metadata.get('ui_hint')
        
        # Determine UI element type
        ui_type = self.UI_ELEMENTS.get((data_type, ui_hint))
        if not ui_type:
            ui_type = self.UI_ELEMENTS.get((data_type, None), 'input')
        
        # Create appropriate UI element
        if ui_type == 'slider':
            self._create_slider(element_type, element)
        elif ui_type == 'number':
            self._create_number(element_type, element)
        elif ui_type == 'checkbox':
            self._create_checkbox(element_type, element)
        elif ui_type == 'switch':
            self._create_switch(element_type, element)
        elif ui_type == 'input':
            self._create_input(element_type, element)
        elif ui_type == 'select':
            self._create_select(element_type, element)
        elif ui_type == 'knob':
            self._create_knob(element_type, element)
        # Add more UI types as needed
    
    def _create_slider(self, element_type: str, element):
        """Create a slider element"""
        min_val = element.metadata.get('min', 0)
        max_val = element.metadata.get('max', 100)
        
        slider = ui.slider(
            min=min_val,
            max=max_val,
            value=element.data.get_value()
        ).props('label')
        
        # Label showing current value
        label = ui.label(f'{element.name}: {element.data.get_value()}')
        
        # Bind changes both ways
        def on_ui_change(e):
            self.ui_binding.update_from_ui(element_type, element.id, e.value)
            label.set_text(f'{element.name}: {e.value}')
        
        def on_data_change(value):
            slider.set_value(value)
            label.set_text(f'{element.name}: {value}')
        
        slider.on('update:model-value', on_ui_change)
        self.ui_binding.bind_property(element.id, on_data_change)
        
        self.ui_elements[element.id] = slider
    
    def _create_number(self, element_type: str, element):
        """Create a number input element"""
        min_val = element.metadata.get('min')
        max_val = element.metadata.get('max')
        
        number = ui.number(
            label=element.name,
            value=element.data.get_value(),
            min=min_val,
            max=max_val
        )
        
        # Bind changes
        def on_ui_change(e):
            self.ui_binding.update_from_ui(element_type, element.id, e.value)
        
        def on_data_change(value):
            number.set_value(value)
        
        number.on('update:model-value', on_ui_change)
        self.ui_binding.bind_property(element.id, on_data_change)
        
        self.ui_elements[element.id] = number
    
    def _create_checkbox(self, element_type: str, element):
        """Create a checkbox element"""
        checkbox = ui.checkbox(
            element.name,
            value=element.data.get_value()
        )
        
        def on_ui_change(e):
            self.ui_binding.update_from_ui(element_type, element.id, e.value)
        
        def on_data_change(value):
            checkbox.set_value(value)
        
        checkbox.on('update:model-value', on_ui_change)
        self.ui_binding.bind_property(element.id, on_data_change)
        
        self.ui_elements[element.id] = checkbox
    
    def _create_switch(self, element_type: str, element):
        """Create a switch element"""
        switch = ui.switch(
            element.name,
            value=element.data.get_value()
        )
        
        def on_ui_change(e):
            self.ui_binding.update_from_ui(element_type, element.id, e.value)
        
        def on_data_change(value):
            switch.set_value(value)
        
        switch.on('update:model-value', on_ui_change)
        self.ui_binding.bind_property(element.id, on_data_change)
        
        self.ui_elements[element.id] = switch
    
    def _create_input(self, element_type: str, element):
        """Create a text input element"""
        input_field = ui.input(
            label=element.name,
            value=element.data.get_value()
        )
        
        def on_ui_change(e):
            self.ui_binding.update_from_ui(element_type, element.id, e.value)
        
        def on_data_change(value):
            input_field.set_value(value)
        
        input_field.on('update:model-value', on_ui_change)
        self.ui_binding.bind_property(element.id, on_data_change)
        
        self.ui_elements[element.id] = input_field
    
    def _create_select(self, element_type: str, element):
        """Create a dropdown select element"""
        options = element.metadata.get('options', [])
        
        select = ui.select(
            options,
            label=element.name,
            value=element.data.get_value()
        )
        
        def on_ui_change(e):
            self.ui_binding.update_from_ui(element_type, element.id, e.value)
        
        def on_data_change(value):
            select.set_value(value)
        
        select.on('update:model-value', on_ui_change)
        self.ui_binding.bind_property(element.id, on_data_change)
        
        self.ui_elements[element.id] = select
    
    def _create_knob(self, element_type: str, element):
        """Create a knob element"""
        min_val = element.metadata.get('min', 0)
        max_val = element.metadata.get('max', 1)
        
        # Normalize value to 0-1 range for knob
        normalized = (element.data.get_value() - min_val) / (max_val - min_val)
        
        knob = ui.knob(normalized, show_value=True)
        label = ui.label(f'{element.name}: {element.data.get_value():.2f}')
        
        def on_ui_change(e):
            # Denormalize value
            actual_value = min_val + (e.value * (max_val - min_val))
            self.ui_binding.update_from_ui(element_type, element.id, actual_value)
            label.set_text(f'{element.name}: {actual_value:.2f}')
        
        def on_data_change(value):
            # Normalize for knob
            normalized = (value - min_val) / (max_val - min_val)
            knob.set_value(normalized)
            label.set_text(f'{element.name}: {value:.2f}')
        
        knob.on('update:model-value', on_ui_change)
        self.ui_binding.bind_property(element.id, on_data_change)
        
        self.ui_elements[element.id] = knob


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
            ui_hint='slider',
            min=0,
            max=10
        ))
        
        self.add_config(Config(
            'mode',
            'Processing Mode',
            DataField(DataType.STR, DataCategory.SCALAR, 'fast'),
            ui_hint='dropdown',
            options=['fast', 'balanced', 'quality']
        ))
        
        self.add_property(Property(
            'scale',
            'Scale Factor',
            data=DataField(DataType.FLOAT, DataCategory.SCALAR, 1.0),
            ui_hint='knob',
            min=0.1,
            max=10.0
        ))
        
        self.add_property(Property(
            'invert',
            'Invert Result',
            data=DataField(DataType.BOOL, DataCategory.SCALAR, False),
            ui_hint='switch'
        ))
        
        self.add_property(Property(
            'threshold',
            'Threshold',
            data=DataField(DataType.FLOAT, DataCategory.SCALAR, 0.5),
            ui_hint='number',
            min=0.0,
            max=1.0
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
        invert = self.properties['invert'].data.get_value()
        threshold = self.properties['threshold'].data.get_value()
        
        # Process
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


# Demo application
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
            inlet.set_connected(not inlet.is_connected)
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
            result = node.worker({})
            output = node.outlets['result_out'].data.get_value()
            ui.notify(f"Worker executed. Result: {output}")
        
        ui.button('Execute Worker', on_click=run_worker)
        
        def print_state():
            print("\nNode State:")
            print(f"Node: {node.node_name} v{node.node_version}")
            print(f"Configs: {[(k, v.data.get_value()) for k, v in node.configs.items()]}")
            print(f"Properties: {[(k, v.data.get_value()) for k, v in node.properties.items()]}")
            print(f"Single inlet: {node.get_inlet_value('value_in')}")
            print(f"Multi inlet dict: {node.get_inlet_value('multi_in')}")
            print(f"Multi inlet list: {node.get_inlet_values_list('multi_in')}")
        
        ui.button('Print State', on_click=print_state)
    
    ui.run()


if __name__ in {'__main__', '__mp_main__'}:
    main()
