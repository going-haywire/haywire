"""Channel Select — picks, reorders or repeats the channels of a block."""

from haywire.barn.builtin.types import STRING
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node

from haybale_audio.dsp import channels as ops
from haybale_audio.value import AudioBlock


@node(
    label="Channel Select",
    description="Picks, reorders or repeats the channels of an audio block",
    menu="audio/channels",
    search_tags=["audio", "channel", "select", "route", "map", "left", "right", "stereo", "mono"],
    node_type=NodeType.DATA,
)
class ChannelSelectNode(BaseNode):
    """Builds a block from the channels named in `Channels`, in that order.

    `Channels` is a list of channel numbers from 0 and inclusive ranges: `0` is the first channel,
    `1, 0` swaps a stereo pair, `0, 0` makes mono into stereo, `2-3` takes the third and fourth.
    An error names a channel the block does not have.
    """

    def init(self) -> None:
        from haybale_audio.types.audio import AUDIO

        self.add(AUDIO.as_inlet("audio", label="Audio"))
        self.add(
            STRING.as_config(
                "channels",
                default="0, 1",
                label="Channels",
                description="Channel numbers from 0, like 0, 2-3",
            )
        )
        self.add(AUDIO.as_outlet("selected", label="Selected"))

    def worker(self, context: ExecutionContext, audio: AudioBlock | None, channels: str = "0, 1") -> None:
        if audio is None:
            raise ValueError("no audio block")
        self.out("selected", ops.select(audio, ops.parse_channels(channels)))
