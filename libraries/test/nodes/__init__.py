"""
Test nodes for the test library
"""

import sys
import os

# Add project paths for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import the node system base class
from haywire.libraries.node_system import HaywireNode
from haywire.libraries.registry import AdapterRegistry


class TemperatureConverterNode(HaywireNode):
    """Node that converts temperature between Celsius and Fahrenheit"""
    
    # Required metadata for node discovery
    node_display_name = 'Temperature Converter'
    node_description = 'Converts temperature between Celsius and Fahrenheit'
    node_name = 'TemperatureConverter'
    node_package = 'org.test.temperature'
    node_library_name = 'Test Library'
    node_library_url = 'https://test.example.com/docs'
    node_search_tags = ['temperature', 'convert', 'celsius', 'fahrenheit']
    node_menu = 'test/temperature'
    node_version = '0.1.0'
    node_author = 'Test Author'
    node_author_url = 'https://test.example.com'
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        self.is_data_node = True
        self.is_control_node = False
        
        # Example properties
        self.input_temperature = 0.0
        self.output_temperature = 0.0
        self.conversion_mode = 'celsius_to_fahrenheit'  # or 'fahrenheit_to_celsius'
    
    def execute(self, input_temp=None, mode=None):
        """Execute the temperature conversion"""
        if input_temp is not None:
            self.input_temperature = input_temp
        
        if mode is not None:
            self.conversion_mode = mode
        
        if self.conversion_mode == 'celsius_to_fahrenheit':
            self.output_temperature = (self.input_temperature * 9/5) + 32
        elif self.conversion_mode == 'fahrenheit_to_celsius':
            self.output_temperature = (self.input_temperature - 32) * 5/9
        else:
            self.output_temperature = self.input_temperature
        
        return self.output_temperature


def register_test_nodes(node_registry):
    """Register test nodes with the node registry"""
    node_registry.register_node(TemperatureConverterNode)


__all__ = [
    'TemperatureConverterNode',
    'register_test_nodes'
]
