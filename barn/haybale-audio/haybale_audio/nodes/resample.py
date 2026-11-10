"""Resample — converts audio blocks to another sample rate."""

from haywire.barn.builtin.types import CHOICES, INT, STRING
from haywire.barn.builtin.widgets import SimpleLabelWidget
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, bag, setting

from haybale_audio.dsp.resample import StreamResampler
from haybale_audio.emitter import deliver_to_subscribers, set_status
from haybale_audio.value import AudioBlock

_QUALITY = {"Fast": "sinc_fastest", "Medium": "sinc_medium", "Best": "sinc_best", "Linear (cheap)": "linear"}


class ResampleSettings(NodeSettings):
    """The rate it delivers and how carefully it converts. Applies on the next start."""

    target_rate = setting[INT](
        48000,
        min=8000,
        max=192000,
        label="Sample Rate",
        category="Resample",
        description="Samples per second of the delivered blocks.",
        promotable=Promotable.CONFIG,
    )
    quality = setting[CHOICES](
        "Fast",
        label="Quality",
        category="Resample",
        description="Fast costs about 0.25% of real time for stereo and is clean for speech and music.",
        widget_config={"options": list(_QUALITY)},
        promotable=Promotable.CONFIG,
    )


@node(
    label="Resample",
    description="Converts audio blocks to another sample rate and delivers them to Audio Event nodes",
    menu="audio/convert",
    search_tags=["audio", "resample", "sample rate", "convert", "44100", "48000", "16000"],
    node_type=NodeType.CONTROL,
)
class ResampleNode(BaseNode):
    """Converts each block that reaches `Write` to `Sample Rate` and delivers it to every Audio Event
    listening. The filter keeps its state between blocks, so the joins are seamless. The first block
    after a start or a format change can come out shorter or not at all while the filter fills.

    Block sizes change with the rate (a 441-sample block at 44.1 kHz gives about 480 at 48 kHz); put a
    Reblock after it where a fixed size is needed.

    Use cases:

    - Feed a model that wants one rate. Speech-to-text models usually take 16 kHz mono: resample
      to 16000, then a Mix to Mono, then a Reblock to the model's block size.
    - Record or send at a set rate. A Recorder writes, and an OMT send transmits, the rate of the
      blocks it gets. Resample in front when the file or the receiver expects another one, for
      example a 44.1 kHz MP3 played into a 48 kHz show.
    - Match sources before a node that does not convert. A Channel Merge needs blocks of one
      sample rate; resample the odd one out first.

    ```text
    File Player → Audio Event → Resample (16000) → Audio Event → Mix to Mono → …
    ```

    An Audio Mixer and a Device Out convert to their own rate themselves, and they also follow a source
    whose clock runs slightly fast or slow, so neither needs a Resample in front. Resample uses a
    fixed ratio and does not do that.

    Inputs:
        write: Convert the block on `audio`
        audio: The block to convert
        callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

    Outputs:
        next: Control flow after the block is taken in
    """

    resample = bag(ResampleSettings)

    def init(self) -> None:
        from haybale_core.types import PooledType
        from haybale_audio.types.audio import AUDIO
        from haybale_audio.types.callback import CALLBACK_AUDIO
        from haybale_audio.types.exec_audio import EXEC_AUDIO

        self.add(EXEC_AUDIO.as_inlet("write", label="Write"))
        self.add(AUDIO.as_inlet("audio", label="Audio", description="Block to convert"))
        self.add(
            PooledType[CALLBACK_AUDIO].as_inlet(
                "callbacks", label="Subscribers", description="Connect to an Audio Event node."
            )
        )
        self.add(
            STRING.as_config("status", default="Idle", label="Status", widget=SimpleLabelWidget.config())
        )
        self.add(EXEC_AUDIO.as_outlet("next", label="Next"))

    def post_init(self) -> None:
        self.hb_resampler: StreamResampler | None = None
        self.hb_delivered = 0
        self.hb_seconds = 0.0

    def on_startup(self, context: ExecutionContext) -> None:
        self.hb_resampler = self._make_resampler()
        self.hb_delivered = 0
        self.hb_seconds = 0.0

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_resampler = None

    def worker(self, context: ExecutionContext, audio: AudioBlock | None = None) -> str | None:
        if audio is None:
            raise ValueError("no audio block to resample")
        if self.hb_resampler is None:
            self.hb_resampler = self._make_resampler()
        converted = self.hb_resampler.process(audio)
        if converted is not None:
            deliver_to_subscribers(
                context, self.value("callbacks"), converted, self.hb_delivered, self.hb_seconds
            )
            self.hb_delivered += 1
            self.hb_seconds += converted.duration
        set_status(self, f"{audio.sample_rate} to {self.resample.target_rate} Hz")
        return "next"

    def _make_resampler(self) -> StreamResampler:
        return StreamResampler(
            int(self.resample.target_rate), _QUALITY.get(str(self.resample.quality), "sinc_fastest")
        )
