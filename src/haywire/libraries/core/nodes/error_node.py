
from typing import Dict, Any, Optional
from haywire.core.node.node import BaseNode

# ============================================================================
# Error Node (returned when a node cannot be loaded)
# ============================================================================


class ErrorNode(BaseNode):
    """Special node to represent nodes that couldn't be loaded properly"""
    
    def __init__(self, node_id, graph, registry_key):
        super().__init__(node_id, graph, registry_key)
        
        # Configure identity
        self.identity.label = 'Error Node'
        self.identity.description = 'Placeholder for node that could not be loaded'
        self.identity.search_tags = ['error', 'system', 'placeholder']
        self.identity.menu = 'system/error'
        
        # Configure UI
        self.ui_config.node_renderer = 'core.error'
    
    def worker(self, context: dict) -> dict | None:
        """Error nodes don't execute - they just display error information"""
        return None
