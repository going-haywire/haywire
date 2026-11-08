"""Channel Split — one output per channel of a block."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.types import PortOrigin

from haybale_audio.dsp import channels as ops
from haybale_audio.value import AudioBlock

_PREFIX = "ch_"


@node(
    label="Channel Split",
    description="Gives each channel of an audio block its own output",
    menu="audio/channels",
    search_tags=["audio", "channel", "split", "separate", "left", "right", "mono", "multichannel"],
    node_type=NodeType.DATA,
)
class ChannelSplitNode(BaseNode):
    """Outputs single channels of the input block. Output `Channel 0` is the first channel, `Channel 1`
    the second, and so on.

    Connect the open output at the bottom to something: it becomes the output for the next channel
    and a new open output appears below. Removing an output leaves the numbers of the others as they
    are. An error names a channel the block does not have.
    """

    def init(self) -> None:
        from haywire.barn.builtin.types import ADD

        from haybale_audio.types.audio import AUDIO

        self.add(AUDIO.as_inlet("audio", label="Audio"))
        self.add(ADD[AUDIO].as_outlet(id=f"{_PREFIX}0", label="Channel 0", on_connect="hb_resolve"))

    def hb_resolve(self, port, edge_wrapper) -> None:
        """Turn the open output into an audio output and add a new open one below it."""
        from haywire.barn.builtin.types import ADD

        from haybale_audio.types.audio import AUDIO

        if port.type_cls is None or not issubclass(port.type_cls, ADD):
            return  # already resolved; the callback fires again whenever the edge is re-linked

        index = int(port.id[len(_PREFIX) :])
        with self.rejig(include=[port.id]):
            self.add(AUDIO.as_outlet(id=port.id, label=f"Channel {index}", origin=PortOrigin.RESOLVED))
        # Indices are never reused: the number is the channel and part of every attached edge's id.
        next_index = max(self._indices()) + 1
        self.add(
            ADD[AUDIO].as_outlet(
                id=f"{_PREFIX}{next_index}", label=f"Channel {next_index}", on_connect="hb_resolve"
            )
        )

    def worker(self, context: ExecutionContext, audio: AudioBlock | None) -> None:
        from haybale_audio.types.audio import AUDIO

        if audio is None:
            raise ValueError("no audio block")
        for port in self.get_all_ports():
            if (
                port.id.startswith(_PREFIX)
                and port.type_cls is not None
                and issubclass(port.type_cls, AUDIO)
            ):
                self.out(port.id, ops.select(audio, [int(port.id[len(_PREFIX) :])]))

    def _indices(self) -> list[int]:
        return [int(p.id[len(_PREFIX) :]) for p in self.get_all_ports() if p.id.startswith(_PREFIX)]
