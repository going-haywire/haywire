
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node
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
    
    def init(self):        
        # Configure UI
        self.ui.config.node_renderer = 'core:renderer:ErrorNodeRenderer'
    
    def worker(self, context: ExecutionContext) -> str | None:
        """Error nodes don't execute - they just display error information"""
        return None
