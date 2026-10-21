from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode

# ============================================================================
# Error Node (returned when a node cannot be loaded)
# ============================================================================
#
# Lives in `builtin` — the framework-owned library loaded at Priority 1, before
# any entry-point plugin — so the fallback is ALWAYS registered. Previously it
# lived in haybale-core's nodes/ package, whose __init__ imports sibling node
# modules; a syntax error in ANY sibling (e.g. begin_play.py) blew up that
# package import before ErrorNode could register, defeating the very fallback
# it exists to provide. builtin/nodes/ is folder-scanned with no __init__
# import coupling, so a broken sibling can never take ErrorNode down with it.


@node(
    label="Core Error Node",
    description="Placeholder for node that could not be loaded",
    search_tags=["error", "system", "placeholder"],
    menu="core/system/error",
    _is_error=True,
)
class ErrorNode(BaseNode):
    """Stands in for a node that could not be built.

    You see it when a node's library is missing, or its class fails to build,
    for example after an edit that broke it. It shows the error, keeps the
    node's place and connections, and does not run.

    Saving the graph keeps the original node in the file, with its settings and
    values. Once the library is installed or the class is fixed, the real node
    comes back in its place.
    """

    def worker(self, context: ExecutionContext) -> str | None:
        """Error nodes don't execute - they just display error information"""
        return None
