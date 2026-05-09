"""
Shutdown Event Node.

Triggered when the interpreter is shutting down, allowing for cleanup operations.
"""
from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType

@node(
    label="Shutdown",
    description="Triggered when execution is shutting down",
    menu="event/runtime",
    search_tags=["stop", "end", "cleanup", "event"],
    node_type=NodeType.EVENT,
)
class ShutdownNode(BaseNode):
    """
    Triggered when execution is shutting down.

    Use this node to perform cleanup operations before the interpreter stops.
    For example:
    - Close file handles
    - Save state
    - Release resources
    - Log shutdown information

    The node is triggered by SHUTDOWN system events, typically dispatched when:
    - User stops the interpreter loop
    - Application is closing
    - System is shutting down

    Outputs:
        exec: Control flow
        timestamp: Time when shutdown was triggered (seconds since epoch)

    Examples:
        Shutdown → SaveState → PrintMessage("Cleanup complete")

        .. code-block:: python

            # In graph
            shutdown = graph.create_node_wrapper('shutdown')
            save = graph.create_node_wrapper('save_state')
            print_msg = graph.create_node_wrapper('print_message')

            # Connect shutdown flow
            graph.create_edge_wrapper(
                shutdown.node_id, 'exec',
                save.node_id, 'exec'
            )
            graph.create_edge_wrapper(
                save.node_id, 'done',
                print_msg.node_id, 'exec'
            )
    """

    def init(self):
        from haybale_core.types import EXEC, FLOAT
        # Control output
        self.add(EXEC.as_outlet("exec", label="Execute"))

        # Data output - timestamp of shutdown
        self.add(FLOAT.as_outlet("timestamp", label="Shutdown Time"))

    def post_init(self):
        """Register for SHUTDOWN system events."""
        self.event_subscription = SystemEvent(SystemEventType.SHUTDOWN)

    def worker(self, context: ExecutionContext) -> str | None:
        """
        Execute when shutdown event is received.

        Outputs the current timestamp and continues execution flow
        to allow downstream cleanup nodes to execute.

        Args:
            context: Execution context

        Returns:
            'exec' to continue execution flow
        """
        import time

        current_time = time.time()
        self.out("timestamp", current_time)

        return "exec"
