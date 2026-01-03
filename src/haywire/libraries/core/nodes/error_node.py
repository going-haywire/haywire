
from haywire.core.node.base import node
from haywire.core.node.base import BaseNode

# ============================================================================
# Error Node (returned when a node cannot be loaded)
# ============================================================================

@node(
    label='Core Error Node',
    description='Placeholder for node that could not be loaded',
    search_tags=['error', 'system', 'placeholder'],
    menu='system/error',
    _is_error=True
)
class ErrorNode(BaseNode):
    """Special node to represent nodes that couldn't be loaded properly"""
    
    def initialize(self):        
        # Configure UI
        self.ui_config.node_renderer = 'core:renderer:error.node.renderer'
    
    def worker(self, context: dict) -> dict | None:
        """Error nodes don't execute - they just display error information"""
        return None
