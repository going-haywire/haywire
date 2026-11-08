"""Channel Merge — stacks audio blocks into one multichannel block."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.types import PortOrigin

from haybale_audio.dsp import channels as ops
from haybale_audio.value import AudioBlock

_PREFIX = "in_"


@node(
    label="Channel Merge",
    description="Stacks audio blocks into one block with all their channels",
    menu="audio/channels",
    search_tags=["audio", "channel", "merge", "combine", "stack", "join", "multichannel"],
    node_type=NodeType.DATA,
)
class ChannelMergeNode(BaseNode):
    """Joins the blocks on its inputs, in order, into one block. A single-channel input adds one
    channel; a multichannel input adds all of its channels.

    Connect an audio output to the open input at the bottom: it becomes an input of its own and a
    new open input appears below. Inputs without a block are skipped. All blocks must have the same
    sample rate and number of samples; an error names the difference.
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import ADD

        from haybale_audio.types.audio import AUDIO

        self.add(ADD[AUDIO].as_inlet(id=f"{_PREFIX}0", label="In 0", on_connect="hb_resolve"))
        self.add(AUDIO.as_outlet("merged", label="Merged"))

    def hb_resolve(self, port, edge_wrapper) -> None:
        """Turn the open input into an audio input and add a new open one below it."""
        from haywire.barn.builtin.types import ADD

        from haybale_audio.types.audio import AUDIO

        if port.type_cls is None or not issubclass(port.type_cls, ADD):
            return  # already resolved; the callback fires again whenever the edge is re-linked

        index = int(port.id[len(_PREFIX) :])
        with self.rejig(include=[port.id]):
            self.add(AUDIO.as_inlet(id=port.id, label=f"In {index}", origin=PortOrigin.RESOLVED))
        # Indices are never reused: a port id is part of the id of every edge attached to it.
        next_index = max(self._indices()) + 1
        self.add(
            ADD[AUDIO].as_inlet(
                id=f"{_PREFIX}{next_index}", label=f"In {next_index}", on_connect="hb_resolve"
            )
        )

    def worker(self, context: ExecutionContext) -> None:
        blocks = [self.value(f"{_PREFIX}{i}") for i in sorted(self._indices())]
        present = [b for b in blocks if isinstance(b, AudioBlock)]
        if not present:
            raise ValueError("no audio block on any input")
        self.out("merged", ops.merge(present))

    def _indices(self) -> list[int]:
        return [int(p.id[len(_PREFIX) :]) for p in self.get_all_ports() if p.id.startswith(_PREFIX)]
