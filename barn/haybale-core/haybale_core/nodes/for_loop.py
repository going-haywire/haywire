"""
ForLoop Node - Standard loop construct for iteration.

Executes loop body a specified number of times with index tracking.
"""

from haywire.core.node import node, BaseNode, NodeType
from haywire.core.execution.execution_context import ExecutionContext


@node(
    label="For Loop",
    description="Iterate with start, end, and step control",
    menu="control/loops",
    search_tags=["loop", "for", "iterate", "index", "range"],
    node_type=NodeType.LOOPBACK,
)
class ForLoopNode(BaseNode):
    """
    Standard for-loop iteration node.

    Executes loop body from start index to end index with specified step.

    Inputs:
        execute: Start loop execution
        start: Starting index (inclusive)
        end: Ending index (exclusive)
        step: Increment per iteration
        break_loop: Control inlet to break out of loop

    Outputs:
        loop_body: Execute on each iteration
        index: Current iteration index
        completed: Execute when loop finishes
    """

    def init(self):
        from ..types.specs import EXEC, INT
        from ..widgets.basic_widgets import NumberWidget

        # Control input - starts the loop
        self.add(EXEC.as_inlet("execute", label="Execute"))

        # Loop parameters
        self.add(INT.as_inlet("start", default=0, label="Start", widget=NumberWidget.config()))

        self.add(
            INT.as_inlet(
                "end",
                default=10,
                label="End",
                widget=NumberWidget.config(),
            )
        )

        self.add(INT.as_inlet("step", default=1, label="Step", widget=NumberWidget.config()))

        # Control input - break out of loop
        self.add(EXEC.as_inlet("break_loop", label="Break"))

        # Loop body outlet - executes on each iteration
        # needs_loopback=True tells the VM this is the loop body
        self.add(
            EXEC.as_outlet(
                "loop_body",
                label="Loop Body",
                needs_loopback=True,  # This outlet expects control to return
            )
        )

        # Current index outlet
        self.add(INT.as_outlet("index", label="Index", default=0))

        # Completed outlet - executes when loop finishes
        self.add(EXEC.as_outlet("completed", label="Completed"))

    def post_init(self):
        # Initialize loop state
        # Loop state variables
        self._current_index = 0
        self._loop_end = 0
        self._loop_step = 1
        self._loop_initialized = False

    def worker(self, context: ExecutionContext, start: int = 0, end: int = 10, step: int = 1) -> str | None:
        """
        Execute loop iteration.

        The VM will:
        1. Call worker with execute pin
        2. Get loop_body outlet
        3. Execute loop body flow
        4. Return to this node
        5. Call worker again (iteration continues)
        6. Repeat until loop completes or breaks

        Args:
            context: Execution context
            start: Starting index
            end: Ending index (exclusive)
            step: Step increment

        Returns:
            - 'loop_body' with index for next iteration
            - 'completed' when loop finishes
        """
        # Check which control pin triggered us
        control_pin = context.control_pin

        # Initialize loop state on first execution
        if control_pin == "execute":
            # Store loop state in node attributes
            self._current_index = start
            self._loop_end = end
            self._loop_step = step
            self._loop_initialized = True
            current_index = start
        elif control_pin == "break_loop":
            # Break out of loop immediately
            self._loop_initialized = False
            return "completed"
        else:
            # Continuing from loop body return
            # Increment index
            current_index = self._current_index

            # Move to next iteration
            current_index += self._loop_step
            self._current_index = current_index

        # Check loop condition
        if self._loop_step > 0:
            # Forward iteration
            if current_index >= self._loop_end:
                self._loop_initialized = False
                return "completed"
        elif self._loop_step < 0:
            # Backward iteration
            if current_index <= self._loop_end:
                self._loop_initialized = False
                return "completed"
        else:
            # Step is 0 - infinite loop protection
            self._loop_initialized = False
            return "completed"

        # Continue loop - output current index
        self.out("index", current_index)
        return "loop_body"
