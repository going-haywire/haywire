"""Test-only nodes with a swinglet: one port that may be either end of an edge."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node


@node(
    label="Swinglet Pass Probe",
    description="Test-only: a data node whose float swinglet records each run and writes ten times it.",
    menu="testing/testbed",
    search_tags=["test", "swinglet"],
    node_type=NodeType.DATA,
)
class SwingletPassProbeNode(BaseNode):
    """Data node with a float swinglet `s`. Each run records `s` in `seen`, then writes `s * 10` to it."""

    def init(self) -> None:
        from haywire.barn.builtin.types import FLOAT

        self.add(FLOAT.as_swinglet("s", default=0.0))

    def post_init(self) -> None:
        self.seen: list[float] = []

    def worker(self, context: ExecutionContext, s: float) -> str | None:
        self.seen.append(s)
        self.out("s", s * 10)
        return None


@node(
    label="Swinglet Stop Probe",
    description="Test-only: a data node whose float swinglet records each run and passes nothing on.",
    menu="testing/testbed",
    search_tags=["test", "swinglet"],
    node_type=NodeType.DATA,
)
class SwingletStopProbeNode(BaseNode):
    """Data node with a float swinglet `s`. Each run records `s` in `seen` and writes nothing."""

    def init(self) -> None:
        from haywire.barn.builtin.types import FLOAT

        self.add(FLOAT.as_swinglet("s", default=0.0))

    def post_init(self) -> None:
        self.seen: list[float] = []

    def worker(self, context: ExecutionContext, s: float) -> str | None:
        self.seen.append(s)
        return None


@node(
    label="Swinglet Control Probe",
    description="Test-only: a control node with an exec swinglet that counts its runs.",
    menu="testing/testbed",
    search_tags=["test", "swinglet", "control"],
    node_type=NodeType.CONTROL,
)
class SwingletControlProbeNode(BaseNode):
    """Control node with an `EXEC` swinglet `flow`. Each run increments `runs` and returns `flow`."""

    def init(self) -> None:
        from haywire.barn.builtin.types import EXEC

        self.add(EXEC.as_swinglet("flow"))

    def post_init(self) -> None:
        self.runs: int = 0

    def worker(self, context: ExecutionContext) -> str | None:
        self.runs += 1
        return "flow"


@node(
    label="Swinglet Visual Probe",
    description="Test-only: a data node with a swinglet on a drawn-only wire.",
    menu="testing/testbed",
    search_tags=["test", "swinglet", "visual"],
    node_type=NodeType.DATA,
)
class SwingletVisualProbeNode(BaseNode):
    """Data node with a `TEST_VISUAL` swinglet `note`."""

    def init(self) -> None:
        from haybale_testing.types import TEST_VISUAL

        self.add(TEST_VISUAL.as_swinglet("note"))

    def worker(self, context: ExecutionContext) -> str | None:
        return None


@node(
    label="Swinglet Echo Probe",
    description="Test-only: a data node whose float swinglet records an arrival and writes it plus one.",
    menu="testing/testbed",
    search_tags=["test", "swinglet", "on_change"],
    node_type=NodeType.DATA,
)
class SwingletEchoProbeNode(BaseNode):
    """Data node with a float swinglet `s`. `on_change` records each arriving value in `changes`,
    then writes that value plus one to `s`."""

    def init(self) -> None:
        from haywire.barn.builtin.types import FLOAT

        self.add(FLOAT.as_swinglet("s", default=0.0, on_change="hb_s"))

    def post_init(self) -> None:
        self.changes: list[float] = []

    def hb_s(self, port, value) -> None:
        self.changes.append(value)
        self.out("s", value + 1)

    def worker(self, context: ExecutionContext) -> str | None:
        return None
