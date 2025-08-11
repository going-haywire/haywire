
from typing import Dict, Any, Optional
from haywire.core.node.node import BaseNode

# ============================================================================
# Error Node (returned when a node cannot be loaded)
# ============================================================================


class ErrorNode(BaseNode):
    """Special node to represent nodes that couldn't be loaded properly"""
    
    node_label = 'Error Node'
    node_description = 'Placeholder for node that could not be loaded'
    node_search_tags = ['error', 'system', 'placeholder']
    node_menu = 'system/error'
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        self.renderer = 'core.error'
