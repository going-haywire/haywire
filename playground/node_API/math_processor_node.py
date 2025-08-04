# --- New Haywire Core Imports ---
import os
import sys

# Add the project root to the Python path to allow imports from the 'haywire' package.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from haywire.core.node.node import HaywireNode
from haywire.core.node.elements import Inlet, Outlet, Config
from haywire.core.data.specs import DataFieldSpec
from haywire.core.data.enums import DataType, FlowType

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
            element_id='precision',
            label='Precision',
            init=DataFieldSpec(DataType.INT, value=2),
            widget='slider',
            ui={'properties': {'min': 0, 'max': 10}}
        ))
        
        self.add_config(Config(
            element_id='mode',
            label='Processing Mode',
            init=DataFieldSpec(DataType.STRING, value='fast'),
            widget='select',
            ui={'properties': {'options': ['fast', 'balanced', 'accurate']}}
        ))
        
        # Add inlets with default values (these were previously properties)
        self.add_inlet(Inlet(
            element_id='scale',
            label='Scale Factor',
            flow_type=FlowType.DATA,
            init=DataFieldSpec(DataType.FLOAT, value=1.0),
            widget='knob', 
            ui={'properties': {'min': 0.1, 'max': 10.0}}
        ))
        
        self.add_inlet(Inlet(
            element_id='invert',
            label='Invert Result',
            flow_type=FlowType.DATA,
            init=DataFieldSpec(DataType.BOOL, value=False),
            widget='switch',
        ))
        
        self.add_inlet(Inlet(
            element_id='threshold',
            label='Threshold',
            flow_type=FlowType.DATA,
            init=DataFieldSpec(DataType.FLOAT, value=0.5),
            widget='number',
            ui={'properties': {'min': 0.0, 'max': 1.0}}
        ))
        
        # Add inlets/outlets
        self.add_inlet(Inlet(
            element_id='ctrl_in',
            label='Execute',
            flow_type=FlowType.CTRL
        ))
        
        self.add_inlet(Inlet(
            element_id='value_in',
            label='Input Value',
            flow_type=FlowType.DATA,
            init=DataFieldSpec(DataType.FLOAT)
        ))
        
        self.add_inlet(Inlet(
            element_id='multi_values',
            label='Multiple Values',
            flow_type=FlowType.DATA,
            init=DataFieldSpec(DataType.FLOAT, is_pooled=True), 
        ))
        
        self.add_outlet(Outlet(
            element_id='ctrl_out',
            label='Next',
            flow_type=FlowType.CTRL,
            init=DataFieldSpec(DataType.OBJECT)
        ))
        
        self.add_outlet(Outlet(
            element_id='result_out',
            label='Result',
            flow_type=FlowType.DATA,
            init=DataFieldSpec(DataType.FLOAT)
        ))
    
    def on_precision_changed(self):
        """Handle precision config change"""
        precision = self.configs['precision'].data.get_value()
        print(f"Precision changed to: {precision}")
    
    def worker(self, context: dict):
        """Process the node"""
        # Direct access to all data
        input_value = self.get_inlet_value('value_in')
        multi_values = self.get_inlet_values_list('multi_values')
        
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
