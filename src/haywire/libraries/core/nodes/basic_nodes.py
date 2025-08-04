"""
Basic core node implementations
"""

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import the node system base class
from haywire.libraries.node_system import HaywireNode
from haywire.libraries.core.data import FLOAT, INT, STR


class ConstantNode(HaywireNode):
    """Node that outputs a constant value"""
    
    # Required metadata for node discovery
    node_display_name = 'Constant'
    node_description = 'Outputs a constant value'
    node_name = 'Constant'
    node_package = 'org.haywire.core.basic'
    node_library_name = 'Haywire Core'
    node_library_url = 'https://haywire.io/docs/core-nodes'
    node_search_tags = ['constant', 'value', 'output', 'basic']
    node_menu = 'core/basic'
    node_version = '1.0.0'
    node_author = 'Haywire System'
    node_author_url = 'https://haywire.io'
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # This would normally be set up with proper inlet/outlet definitions
        # For now, just demonstrate the structure
        self.is_data_node = True
        self.is_control_node = False
        
        # Example: This node would have a config for the constant value
        # and an outlet to provide that value
        self.constant_value = 42.0
    
    def execute(self):
        """Execute the node - return the constant value"""
        return self.constant_value


class DisplayNode(HaywireNode):
    """Node that displays input values"""
    
    # Required metadata for node discovery
    node_display_name = 'Display'
    node_description = 'Displays input values for debugging'
    node_name = 'Display'
    node_package = 'org.haywire.core.basic'
    node_library_name = 'Haywire Core'
    node_library_url = 'https://haywire.io/docs/core-nodes'
    node_search_tags = ['display', 'debug', 'output', 'basic']
    node_menu = 'core/basic'
    node_version = '1.0.0'
    node_author = 'Haywire System'
    node_author_url = 'https://haywire.io'
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # This would normally be set up with proper inlet/outlet definitions
        self.is_data_node = True
        self.is_control_node = False
        
        # Example: This node would have an inlet for the value to display
        self.display_value = None
    
    def execute(self, input_value=None):
        """Execute the node - display the input value"""
        if input_value is not None:
            self.display_value = input_value
            print(f"Display Node [{self.node_id}]: {input_value}")
        return self.display_value
