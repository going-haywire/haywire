"""Step Array — go through an array one item per `Next`, at whatever pace the graph sets."""

from typing import Any, Optional

from haybale_core.array_ports import array_element_type, array_of
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node

MODES = ("once", "loop", "palindrome")


@node(
    label="Step Array",
    description="Goes through an array one item at a time, each time Next runs",
    menu="core/control/loops",
    search_tags=["step", "array", "next", "sequence", "slideshow", "playlist", "iterate"],
    node_type=NodeType.LOOPBACK,
)
class StepArrayNode(BaseNode):
    """Goes through an array one item at a time, each time `Next` runs.

    Unlike Loop Array, which goes through the whole array at once, Step Array moves
    on only when told to, so the graph sets the pace: drive `Next` from a Tick Event
    whose Tick Emit runs at 0.5 FPS and every item shows for 2 seconds.

    - `Start` reads the array, goes to the first item and runs `Step`.
    - `Next` goes to the following item and runs `Step`. Before the first `Start`,
      and after the array has run out in `once` mode, it does nothing.
    - `Stop` forgets the array; `Next` does nothing until the next `Start`.

    `Mode` decides what happens at the end of the array:

    - `once`: after the last item, `Next` runs `Completed`.
    - `loop`: after the last item comes the first again (0 1 2 0 1 2 …).
    - `palindrome`: the items go back and forth, without showing an end twice
      (0 1 2 1 0 1 …).

    In `loop` and `palindrome` every return to the first item runs `Completed` and
    then `Step`, so `Completed` counts the rounds. An empty array runs `Completed`
    at `Start`. `Item` takes the type of the array's items; `Index` is the item's
    position in the array and `Total` the array's length.

    ```text
    Begin Play → List Files → Step Array.Start      (Array = Files)
    Tick Event → Step Array.Next → Load Image → View Image
    ```
    """

    _items: Optional[list[Any]]
    _pending: Optional[int]

    def init(self) -> None:
        from haywire.barn.builtin.types import EXEC, INT, STRING
        from haywire.barn.builtin.widgets import SelectWidget

        self.add(
            EXEC.as_inlet("start", label="Start", description="Reads the array and steps to its first item")
        )
        self.add(EXEC.as_inlet("next", label="Next", description="Steps to the next item"))
        self.add(
            EXEC.as_inlet(
                "stop", label="Stop", description="Forgets the array; Next does nothing until Start"
            )
        )
        self._add_array_ports(None)
        self.add(
            STRING.as_inlet(
                "mode",
                label="Mode",
                default="once",
                widget=SelectWidget.config(properties={"options": list(MODES)}),
                description="At the end: once stops, loop starts over, palindrome turns back",
            )
        )

        self.add(EXEC.as_outlet("step", label="Step", description="Runs with each item"))
        self.add(
            INT.as_outlet(
                "index", label="Index", default=0, description="Position of the current item, from 0"
            )
        )
        self.add(INT.as_outlet("total", label="Total", default=0, description="Number of items"))
        # needs_loopback: after the Completed branch the node runs Step for the first item again.
        self.add(
            EXEC.as_outlet(
                "completed",
                label="Completed",
                description="Signal the array ran out (once) or a round ended (loop, palindrome)",
                needs_loopback=True,
            )
        )

    def post_init(self) -> None:
        self._reset()

    def on_startup(self, context: ExecutionContext) -> None:
        """Start every run without an array."""
        self._reset()

    def on_frame_end(self, context: ExecutionContext) -> None:
        """Drop a Step the frame did not get to, as after a bail."""
        self._pending = None

    def hb_adopt_array(self, port: Any, edge_wrapper: Any) -> None:
        """Type `Array` and `Item` after the array wired in."""
        element = array_element_type(edge_wrapper)
        if element is None or element is getattr(self, "_element", None):
            return
        with self.rejig(include=["array", "item"]):
            self._add_array_ports(element)

    def _add_array_ports(self, element: Optional[Any]) -> None:
        """Add `Array` and `Item`: open slots until an array is wired in."""
        from haywire.barn.builtin.types import ADD

        self._element = element
        if element is None:
            self.add(
                ADD.as_inlet(
                    "array",
                    label="Array",
                    on_connect="hb_adopt_array",
                    description="The items to step through",
                )
            )
            self.add(ADD.as_outlet("item", label="Item", description="The current item"))
            return
        self.add(
            array_of(element).as_inlet(
                "array", label="Array", on_connect="hb_adopt_array", description="The items to step through"
            )
        )
        self.add(element.as_outlet("item", label="Item", description="The current item"))

    def worker(self, context: ExecutionContext) -> Optional[str]:
        pin = context.control_pin
        if pin == "start":
            return self._start()
        if pin == "stop":
            self._reset()
            return None
        if pin == "next":
            return self._next() if self._items is not None else None
        if self._pending is not None:  # back from the Completed branch of a new round
            index, self._pending = self._pending, None
            return self._emit(index)
        return None

    def _reset(self) -> None:
        self._items = None
        self._index = 0
        self._direction = 1
        self._pending = None

    def _start(self) -> str:
        value = self.value("array")
        if value is None:
            value = []
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"Array expects a list of items, got {type(value).__name__}")
        self._reset()
        if not value:
            return "completed"
        self._items = list(value)
        return self._emit(0)

    def _next(self) -> str:
        assert self._items is not None
        total = len(self._items)
        mode = self.value("mode")
        if mode == "loop":
            index = (self._index + 1) % total
        elif mode == "palindrome":
            if total == 1:
                index = 0
            else:
                if not 0 <= self._index + self._direction < total:
                    self._direction = -self._direction
                index = self._index + self._direction
        else:
            index = self._index + 1
            if index >= total:
                self._items = None
                return "completed"
        if index == 0:
            self._pending = 0
            return "completed"
        return self._emit(index)

    def _emit(self, index: int) -> str:
        assert self._items is not None
        self._index = index
        self.out("item", self._items[index])
        self.out("index", index)
        self.out("total", len(self._items))
        return "step"
