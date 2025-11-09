"""
Test Data Creator Node

This node creates TestData instances for testing.
"""

from haywire.core.node.base_node import node, BaseNode
from haywire.core.node.elements import Inlet, Outlet
from haywire.core.data.enums import DataType, FlowType
from haywire.core.data.fields import SingleField

# Import the custom type from this library
from test_a.types.data import TestData


@node(
    label='Test Data Creator',
    description='Creates TestData instances',
    search_tags=['test', 'create', 'data'],
    menu='test_a/generators'
)
class TestDataCreatorNode(BaseNode):
    """
    Node that creates TestData custom type instances.
    
    Generates TestData that can be consumed by nodes in other libraries.
    """
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # Configure behavior
        self.behavior.is_data_node = True
        self.behavior.is_control_node = False
        
        # Input: Value to store
        self.add_inlet(
            Inlet(
                id='value',
                label='Value',
                flow_type=FlowType.DATA,
                data=SingleField(DataType.FLOAT, 'single', 0.0),
                widget='core.number'
            )
        )
        
        # Input: Label
        self.add_inlet(
            Inlet(
                id='label',
                label='Label',
                flow_type=FlowType.DATA,
                data=SingleField(DataType.STRING, 'single', 'Test Data'),
                widget='core.text'
            )
        )
        
        # Output: Created TestData
        self.add_outlet(
            Outlet(
                id='test_data',
                flow_type=FlowType.DATA,
                label='Test Data',
                data=SingleField(DataType.CUSTOM, 'single', None)
            )
        )
    
    def worker(self, context: dict) -> dict | None:
        """
        Create a TestData instance.
        
        Args:
            context: Execution context with input values
            
        Returns:
            Dictionary with the created TestData
        """
        value = context.get('value', 0.0)
        label = context.get('label', 'Test Data')
        
        # Create TestData instance
        test_data = TestData(
            value=value,
            label=label,
            metadata={
                "created_by": "test_a.test_data_creator",
                "node_id": self.node_id
            }
        )
        
        print(f"Test Data Creator [{self.node_id}]: Created {test_data}")
        
        return {
            'test_data': test_data
        }
