"""Mix to Mono — averages all channels of a block."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node

from haybale_audio.dsp import channels as ops
from haybale_audio.value import AudioBlock


@node(
    label="Mix to Mono",
    description="Averages all channels of an audio block into one",
    menu="audio/channels",
    search_tags=["audio", "mono", "mix", "downmix", "average", "stereo"],
    node_type=NodeType.DATA,
)
class MixToMonoNode(BaseNode):
    """Outputs one channel that is the average of the input's channels, which keeps the level of a
    stereo pair that carries the same signal on both sides."""

    def init(self) -> None:
        from haybale_audio.types.audio import AUDIO

        self.add(AUDIO.as_inlet("audio", label="Audio"))
        self.add(AUDIO.as_outlet("mono", label="Mono"))

    def worker(self, context: ExecutionContext, audio: AudioBlock | None) -> None:
        if audio is None:
            raise ValueError("no audio block")
        self.out("mono", ops.to_mono(audio))
