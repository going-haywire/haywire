
from typing import Dict, Any, Optional
from haywire.core.inventory.registry.node_reg import node
from haywire.core.node.node import BaseNode

# ============================================================================
# Error Node (returned when a node cannot be loaded)
# ============================================================================

@node(
    label='Error Node',
    description='Placeholder for node that could not be loaded',
    search_tags=['error', 'system', 'placeholder'],
    menu='system/error',
    is_error=True
)
class ErrorNode(BaseNode):
    """Special node to represent nodes that couldn't be loaded properly"""
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # Configure UI
        self.ui_config.node_renderer = 'core.error'
    
    def worker(self, context: dict) -> dict | None:
        """Error nodes don't execute - they just display error information"""
        return None
