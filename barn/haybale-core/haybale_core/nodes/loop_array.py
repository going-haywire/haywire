"""Loop Array — run the loop body once for each item of an array."""

from typing import Any, Optional

from haybale_core.array_ports import array_element_type, array_of
from haybale_core.loop_settings import LoopErrors
from haywire.barn.builtin.progress import ProgressSettings, ProgressSpan, progress_field
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import bag


class LoopArrayProgress(ProgressSettings):
    """How far the loop is through the array."""

    main = progress_field("Progress")


@node(
    label="Loop Array",
    description="Runs the loop body once for each item of an array",
    menu="core/control/loops",
    search_tags=["loop", "for", "each", "array", "list", "items", "iterate", "batch"],
    node_type=NodeType.LOOPBACK,
)
class LoopArrayNode(BaseNode):
    """Runs the loop body once for each item of an array.

    Wire any array into `Array`: `Item` takes the type of its items, so a list of
    file paths gives a file path, a list of numbers a number. For each item the loop
    sets `Item`, `Index` (from 0) and `Total`.

    - `On Error`: when an iteration fails and the graph's *On Exception* setting is
      `branch`, `continue` goes on with the next item and `stop` ends the loop through
      `Stopped`. With `frame` or `run` the loop ends at the first failure, without
      `Completed` or `Stopped`.

    When the loop ends, `Failed` lists the items whose iteration failed. `Completed`
    runs when every item was gone through, also at once for an empty array;
    `Stopped` runs when `Break` (wired from the loop body) or `On Error` = `stop`
    ended the loop early. The array is read when the loop starts.

    ```text
    List Files → Loop Array (Array = Files) → Load Image → Save Image
    ```
    """

    errors = bag(LoopErrors)
    progress = bag(LoopArrayProgress)

    def init(self) -> None:
        from haywire.barn.builtin.types import EXEC, INT

        self.add(EXEC.as_inlet("execute", label="Execute", description="Starts the loop over the array"))
        self.add(
            EXEC.as_inlet("break_loop", label="Break", description="Ends the loop early, through Stopped")
        )
        self._add_array_ports(None)

        self.add(
            EXEC.as_outlet(
                "loop_body", label="Loop Body", needs_loopback=True, description="Runs once per item"
            )
        )
        self.add(
            INT.as_outlet(
                "index", label="Index", default=0, description="Position of the current item, from 0"
            )
        )
        self.add(INT.as_outlet("total", label="Total", default=0, description="Number of items"))
        self.add(
            EXEC.as_outlet(
                "completed", label="Completed", description="Runs when every item was gone through"
            )
        )
        self.add(
            EXEC.as_outlet(
                "stopped",
                label="Stopped",
                description="Runs when Break or On Error = stop ended the loop early",
            )
        )

    def post_init(self) -> None:
        self._items: list[Any] = []
        self._index = 0
        self._failed: list[Any] = []
        self._failures_seen = 0
        self._span: Optional[ProgressSpan] = None

    def hb_adopt_array(self, port: Any, edge_wrapper: Any) -> None:
        """Type `Array`, `Item` and `Failed` after the array wired in."""
        element = array_element_type(edge_wrapper)
        if element is None or element is getattr(self, "_element", None):
            return
        with self.rejig(include=["array", "item", "failed"]):
            self._add_array_ports(element)

    def _add_array_ports(self, element: Optional[Any]) -> None:
        """Add `Array`, `Item` and `Failed`: open slots until an array is wired in."""
        from haywire.barn.builtin.types import ADD

        self._element = element
        if element is None:
            self.add(
                ADD.as_inlet(
                    "array",
                    label="Array",
                    on_connect="hb_adopt_array",
                    description="The items to go through",
                )
            )
            self.add(ADD.as_outlet("item", label="Item", description="The current item"))
            self.add(ADD.as_outlet("failed", label="Failed", description="Items whose iteration failed"))
            return
        self.add(
            array_of(element).as_inlet(
                "array", label="Array", on_connect="hb_adopt_array", description="The items to go through"
            )
        )
        self.add(element.as_outlet("item", label="Item", description="The current item"))
        self.add(
            array_of(element).as_outlet("failed", label="Failed", description="Items whose iteration failed")
        )

    def worker(self, context: ExecutionContext) -> Optional[str]:
        if context.control_pin == "execute":
            self._close()
            self._begin()
            return self._emit(context)
        if self._span is None:
            return None  # no loop open: a stray loopback return
        if len(context.failures) > self._failures_seen:
            self._failed.append(self._items[self._index])
            if self.errors.on_error == "stop":
                return self._finish("stopped")
        if context.control_pin == "break_loop":
            return self._finish("stopped")
        self._index += 1
        return self._emit(context)

    def on_frame_end(self, context: ExecutionContext) -> None:
        """Close a loop the frame left open, as after a bail or a stop."""
        self._close()

    def _begin(self) -> None:
        value = self.value("array")
        if value is None:
            value = []
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"Array expects a list of items, got {type(value).__name__}")
        self._items = list(value)
        self._index = 0
        self._failed = []
        self._span = self.progress.busy("main", f"{len(self._items)} items")
        self._span.__enter__()

    def _emit(self, context: ExecutionContext) -> str:
        total = len(self._items)
        if self._index >= total:
            return self._finish("completed")
        self.out("item", self._items[self._index])
        self.out("index", self._index)
        self.out("total", total)
        assert self._span is not None
        self._span.step(self._index / total)
        self._failures_seen = len(context.failures)
        return "loop_body"

    def _finish(self, outlet: str) -> str:
        if self._element is not None:  # an open slot holds no value
            self.out("failed", list(self._failed))
        self._close()
        return outlet

    def _close(self) -> None:
        span, self._span = self._span, None
        if span is not None:
            span.__exit__(None, None, None)
        self._items = []
