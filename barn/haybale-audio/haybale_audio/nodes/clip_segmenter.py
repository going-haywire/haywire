"""Clip Segmenter — cuts a live audio flow into clips at the pauses."""

from __future__ import annotations

import time

from haybale_audio.dsp.segmenter import Segment, Segmenter
from haybale_audio.emitter import STATUS_INTERVAL, deliver_clip_to_subscribers, set_status
from haybale_audio.value import AudioBlock
from haywire.api import (
    EXEC,
    FLOAT,
    INT,
    STRING,
    BacklogSettings,
    BaseNode,
    ExecutionContext,
    LabelWidget,
    NodeSettings,
    NodeType,
    Promotable,
    Refusal,
    bag,
    node,
    setting,
)


class SegmentingSettings(NodeSettings):
    """Where a clip starts and ends. Applies from the next block."""

    threshold = setting[FLOAT](
        0.01,
        min=0.0,
        max=1.0,
        label="Threshold",
        category="Segmenting",
        description="Level (RMS) above which a block counts as sound. The status shows the level.",
        promotable=Promotable.CONFIG,
    )
    hangover_ms = setting[INT](
        500,
        min=0,
        max=10000,
        label="Hang-over (ms)",
        category="Segmenting",
        description="Pause that ends a clip.",
        promotable=Promotable.CONFIG,
    )
    preroll_ms = setting[INT](
        200,
        min=0,
        max=5000,
        label="Pre-roll (ms)",
        category="Segmenting",
        description="Audio kept from before the first loud block, so a soft start is not cut off.",
        promotable=Promotable.CONFIG,
    )
    postroll_ms = setting[INT](
        100,
        min=0,
        max=5000,
        label="Post-roll (ms)",
        category="Segmenting",
        description=(
            "Audio kept from the pause that ends the clip, so a soft ending is not cut off. "
            "At most the Hang-over."
        ),
        promotable=Promotable.CONFIG,
    )
    min_seconds = setting[FLOAT](
        0.3,
        min=0.0,
        max=60.0,
        label="Min Seconds",
        category="Segmenting",
        description="Shortest sound sent, pre-roll and post-roll left out; shorter is discarded.",
        promotable=Promotable.CONFIG,
    )
    max_seconds = setting[FLOAT](
        30.0,
        min=0.1,
        max=600.0,
        label="Max Seconds",
        category="Segmenting",
        description="Longest clip; a longer one is cut there and the sound goes on in the next.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Clip Segmenter",
    description="Cuts a live audio flow into clips at the pauses, such as one clip per sentence",
    menu="audio/clip",
    search_tags=[
        "audio",
        "clip",
        "speech",
        "vad",
        "voice",
        "segment",
        "split",
        "pause",
        "silence",
        "live",
        "microphone",
    ],
    node_type=NodeType.CONTROL,
)
class ClipSegmenterNode(BaseNode):
    """Listens to an audio flow and sends each stretch of sound, such as a sentence, as a clip.

    The clip keeps the flow's sample rate and channels; Transcribe converts it for its model.

    A block is loud when its level (RMS) is above `Threshold`. The first loud block opens a
    segment, together with the `Pre-roll` before it, so a quiet first sound is kept. A pause
    of `Hang-over` ends the segment; its first `Post-roll` stays in the clip, so a soft ending
    is kept, and the rest is left out. Sound shorter than `Min Seconds` (a click, a cough) is
    discarded; a segment that reaches `Max Seconds` is sent at once and the next loud
    block opens a new one. `Cut` ends the open segment at once, as a pause would. The status
    shows the level, which helps to set the threshold.

    The clip goes to every Clip Event listening on `Subscribers` and arrives in a flow of its
    own, so a slow step, such as a speech model, runs outside the audio flow:

    ```text
    Device In → Audio Event → Clip Segmenter (Add)
    Clip Segmenter (Subscribers) ← Clip Event → Clip Ready → Transcribe → Print
    ```

    The Clip Event's `Clip` is the clip, its `Timestamp` the start of the sound in seconds since
    the segmenter's first block, and its `Clip Number` the count of clips sent. Clip Events set to
    Pooled share the clips, the next free one taking each; `Backlog` holds the clips that wait
    while every pooled one is busy.

    The audio flow waits only when a Clip Event's queue is full: with the default Queue Mode
    (Block), a flow that falls 16 clips behind makes the segmenter wait up to 5 s, and the audio
    flow with it. For a slow step, set its Clip Event to Drop, or to Pooled: the Backlog's default
    (Drop oldest) never waits.

    Inputs:
        add: Feed the block on `audio` (wire it to an Audio Event's Block Ready)
        cut: End the open segment now and send it
        audio: The block
        callbacks: Pooled CLIP_CALLBACK subscriptions from the Clip Event nodes that get the clips

    Outputs:
        next: Control flow after the block is taken
    """

    segmenting = bag(SegmentingSettings)
    backlog = bag(BacklogSettings)

    def init(self) -> None:
        # reload: barn types are looked up fresh after a hot reload.
        from haybale_audio.types.audio import AUDIO
        from haybale_audio.types.audio_exec import AUDIO_EXEC
        from haybale_audio.types.clip_callback import CLIP_CALLBACK
        from haybale_core.types import POOLED

        self.add(AUDIO_EXEC.as_inlet("add", label="Add"))
        self.add(EXEC.as_inlet("cut", label="Cut", description="End the open segment now and send it"))
        self.add(AUDIO.as_inlet("audio", label="Audio", description="Block to listen to"))
        self.add(
            POOLED[CLIP_CALLBACK].as_inlet(
                "callbacks",
                label="Subscribers",
                description="Connect to the Clip Event nodes that get the clips.",
            )
        )
        self.add(STRING.as_config("status", default="Idle", label="Status", widget=LabelWidget.config()))
        self.add(AUDIO_EXEC.as_outlet("next", label="Next"))

    def post_init(self) -> None:
        self.hb_segmenter = Segmenter()
        self.hb_status_at = 0.0

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_reset()

    def on_teardown(self) -> None:
        self.hb_reset()

    def hb_reset(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        segmenter = getattr(self, "hb_segmenter", None)
        if segmenter is not None:
            segmenter.reset()

    def worker(self, context: ExecutionContext, audio: AudioBlock | None = None) -> str | None:
        segmenter = self.hb_segmenter
        if context.control_pin == "cut":
            self.hb_send(context, segmenter.cut())
            return None
        if audio is None:
            raise Refusal("Clip Segmenter has no block to add: connect an Audio Event's Audio to Audio.")
        settings = self.segmenting
        segmenter.threshold = float(settings.threshold)
        segmenter.hangover = max(0, int(settings.hangover_ms)) / 1000
        segmenter.preroll = max(0, int(settings.preroll_ms)) / 1000
        segmenter.postroll = min(max(0, int(settings.postroll_ms)) / 1000, segmenter.hangover)
        segmenter.min_length = float(settings.min_seconds)
        segmenter.max_length = max(float(settings.max_seconds), audio.duration)
        self.hb_send(context, segmenter.feed(audio))
        return "next"

    def hb_send(self, context: ExecutionContext, segment: Segment | None) -> None:
        if segment is None:
            self.hb_report()
            return
        subscribers = self.value("callbacks")
        deliver_clip_to_subscribers(
            context, subscribers, segment.audio, self.hb_segmenter.sent, segment.start, backlog=self.backlog
        )
        self.hb_report(force=True, note=f"sent {segment.duration:.1f} s" if subscribers else "no subscriber")

    def hb_report(self, force: bool = False, note: str = "") -> None:
        now = time.monotonic()
        if not force and now - self.hb_status_at < STATUS_INTERVAL:
            return
        self.hb_status_at = now
        segmenter = self.hb_segmenter
        state = f"Speaking {segmenter.seconds:.1f} s" if segmenter.speaking else "Listening"
        text = (
            f"{state}, level {segmenter.level:.3f}, sent {segmenter.sent}, discarded {segmenter.discarded}"
        )
        set_status(self, f"{text} ({note})" if note else text)
