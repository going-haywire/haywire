from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode

# ============================================================================
# Error Node (returned when a node cannot be loaded)
# ============================================================================


@node(
    label="Core Error Node",
    description="Placeholder for node that could not be loaded",
    search_tags=["error", "system", "placeholder"],
    menu="system/error",
    _is_error=True,
)
class ErrorNode(BaseNode):
    """Special node to represent nodes that couldn't be loaded properly"""

    def init(self):
        self.props.skin =  "core:skin:ErrorNodeSkin"

    def worker(self, context: ExecutionContext) -> str | None:
        """Error nodes don't execute - they just display error information"""
        return None
