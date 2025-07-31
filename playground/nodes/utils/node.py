"""
Node model definitions for the Node Graph Editor
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
import uuid

class NodeType(Enum):
    """Enumeration of available node types"""
    INPUT = "input"
    OUTPUT = "output"
    COMMENT = "comment"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    AND = "and"
    OR = "or"
    NOT = "not"
    COMPARE = "compare"
    DISPLAY = "display"
    CHART = "chart"
    EXPORT = "export"

@dataclass
class NodePort:
    """Represents an input or output port on a node"""
    id: str
    name: str
    data_type: str = "any"
    is_input: bool = True
    connected_to: List[str] = field(default_factory=list)
    value: Any = None

@dataclass
class Node:
    """Represents a node in the graph"""
    id: str
    node_type: NodeType
    name: str
    x: float = 100.0
    y: float = 100.0
    width: float = 150.0
    height: float = 100.0
    inputs: List[NodePort] = field(default_factory=list)
    outputs: List[NodePort] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    selected: bool = False
    
    def __post_init__(self):
        """Initialize default ports based on node type"""
        if not self.inputs and not self.outputs:
            self._setup_default_ports()
    
    def _setup_default_ports(self):
        """Setup default input/output ports based on node type"""
        port_configs = {
            NodeType.INPUT: {
                'outputs': [('output', 'any')]
            },
            NodeType.OUTPUT: {
                'inputs': [('input', 'any')]
            },
            NodeType.COMMENT: {
                'inputs': [],
                'outputs': []
            },
            NodeType.ADD: {
                'inputs': [('a', 'number'), ('b', 'number')],
                'outputs': [('result', 'number')]
            },
            NodeType.SUBTRACT: {
                'inputs': [('a', 'number'), ('b', 'number')],
                'outputs': [('result', 'number')]
            },
            NodeType.MULTIPLY: {
                'inputs': [('a', 'number'), ('b', 'number')],
                'outputs': [('result', 'number')]
            },
            NodeType.DIVIDE: {
                'inputs': [('a', 'number'), ('b', 'number')],
                'outputs': [('result', 'number')]
            },
            NodeType.AND: {
                'inputs': [('a', 'boolean'), ('b', 'boolean')],
                'outputs': [('result', 'boolean')]
            },
            NodeType.OR: {
                'inputs': [('a', 'boolean'), ('b', 'boolean')],
                'outputs': [('result', 'boolean')]
            },
            NodeType.NOT: {
                'inputs': [('input', 'boolean')],
                'outputs': [('result', 'boolean')]
            },
            NodeType.COMPARE: {
                'inputs': [('a', 'any'), ('b', 'any')],
                'outputs': [('result', 'boolean')]
            },
            NodeType.DISPLAY: {
                'inputs': [('input', 'any')],
                'outputs': []
            },
            NodeType.CHART: {
                'inputs': [('data', 'array')],
                'outputs': []
            },
            NodeType.EXPORT: {
                'inputs': [('data', 'any')],
                'outputs': []
            }
        }
        
        config = port_configs.get(self.node_type, {'inputs': [], 'outputs': []})
        
        # Create input ports
        for port_name, data_type in config.get('inputs', []):
            port_id = f"{self.id}_{port_name}_in"
            self.inputs.append(NodePort(
                id=port_id,
                name=port_name,
                data_type=data_type,
                is_input=True
            ))
        
        # Create output ports
        for port_name, data_type in config.get('outputs', []):
            port_id = f"{self.id}_{port_name}_out"
            self.outputs.append(NodePort(
                id=port_id,
                name=port_name,
                data_type=data_type,
                is_input=False
            ))
    
    @classmethod
    def create(cls, node_type: NodeType, name: str, x: float = 100, y: float = 100) -> 'Node':
        """Factory method to create a new node"""
        node_id = str(uuid.uuid4())
        return cls(
            id=node_id,
            node_type=node_type,
            name=name,
            x=x,
            y=y
        )
    
    def get_input_port(self, name: str) -> Optional[NodePort]:
        """Get input port by name"""
        for port in self.inputs:
            if port.name == name:
                return port
        return None
    
    def get_output_port(self, name: str) -> Optional[NodePort]:
        """Get output port by name"""
        for port in self.outputs:
            if port.name == name:
                return port
        return None
    
    def set_position(self, x: float, y: float):
        """Update node position"""
        self.x = x
        self.y = y
    
    def get_bounds(self) -> Dict[str, float]:
        """Get node bounding box"""
        return {
            'left': self.x,
            'top': self.y,
            'right': self.x + self.width,
            'bottom': self.y + self.height
        }

@dataclass
class Connection:
    """Represents a connection between two node ports"""
    id: str
    source_port_id: str
    target_port_id: str
    
    @classmethod
    def create(cls, source_port_id: str, target_port_id: str) -> 'Connection':
        """Factory method to create a new connection"""
        connection_id = str(uuid.uuid4())
        return cls(
            id=connection_id,
            source_port_id=source_port_id,
            target_port_id=target_port_id
        )
