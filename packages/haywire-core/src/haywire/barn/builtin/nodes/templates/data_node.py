"""The Data node template: the starting point for a node that computes a value."""

from haywire.barn.builtin.types import FLOAT
from haywire.barn.builtin.widgets import NumberWidget
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node


@node(
    label="Data Node",
    description="Computes a value from its inputs each time the graph runs.",
    menu="custom",
    node_type=NodeType.DATA,
    template=True,
)
class DataNodeTemplate(BaseNode):
    """A data node: one number in, one number out.

    Start here for a node that turns inputs into outputs. To make it yours:

    - Declare your ports in `init()`. Each `self.add(...)` adds one inlet or
      outlet; the id you give it (`"x"`, `"result"`) is how the worker names it.
    - Compute in `worker()`. Every inlet arrives as a keyword argument of the
      same name. Send each result with `self.out("<outlet id>", value)`.
    - Keep `node_type=NodeType.DATA` for a node that only computes. A data node
      needs at least one data outlet.

    ```python
    def worker(self, context, x: float = 0.0) -> None:
        self.out("result", x * 2)
    ```
    """

    def init(self):
        self.add(FLOAT.as_inlet("x", label="X", widget=NumberWidget.config(), default=0.0))
        self.add(FLOAT.as_outlet("result", label="Result"))

    def worker(self, context: ExecutionContext, x: float = 0.0) -> None:
        self.out("result", x)
