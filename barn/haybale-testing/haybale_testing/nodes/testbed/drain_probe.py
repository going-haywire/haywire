import threading

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Drain Producer Probe",
    description="Test-only control node writing 0, 1, 2, ... to its outlet, one value per run",
    menu="testing/testbed",
    search_tags=["test", "drain", "producer"],
    node_type=NodeType.CONTROL,
)
class DrainProducerProbeNode(BaseNode):
    """Test-only producer: each run writes the next count to `value`, starting at 0.

    The test reads `written`, the number of values written so far, and `threads`, the
    names of the threads it ran on.
    """

    def init(self):
        from haywire.barn.builtin.types import EXEC, FLOAT

        self.add(EXEC.as_inlet("exec_in"))
        self.add(FLOAT.as_outlet("value"))
        self.add(EXEC.as_outlet("exec_out"))

    def post_init(self):
        self.written = 0
        self.threads: set[str] = set()

    def worker(self, context: ExecutionContext) -> str | None:
        self.threads.add(threading.current_thread().name)
        self.out("value", float(self.written))
        self.written += 1
        return "exec_out"


@node(
    label="Drain Consumer Probe",
    description="Test-only control node taking everything queued on its drain inlet, once per run",
    menu="testing/testbed",
    search_tags=["test", "drain", "consumer"],
    node_type=NodeType.CONTROL,
)
class DrainConsumerProbeNode(BaseNode):
    """Test-only consumer: each run takes the `queue` drain inlet.

    The test reads `taken`, every value taken in order, `batches`, how many values each
    run took, `dropped`, the total the inlet discarded to its limit, and `threads`, the
    names of the threads it ran on.
    """

    def init(self):
        from haybale_core.types import DRAIN
        from haywire.barn.builtin.types import EXEC, FLOAT

        self.add(EXEC.as_inlet("exec_in"))
        self.add(DRAIN[FLOAT].as_inlet("queue", default={"max_len": 1024}))
        self.add(EXEC.as_outlet("exec_out"))

    def post_init(self):
        self.taken: list[float] = []
        self.batches: list[int] = []
        self.dropped = 0
        self.threads: set[str] = set()

    def worker(self, context: ExecutionContext) -> str | None:
        self.threads.add(threading.current_thread().name)
        batch = self.drain("queue")
        self.taken.extend(batch)
        self.batches.append(len(batch))
        self.dropped += batch.dropped
        return "exec_out"
