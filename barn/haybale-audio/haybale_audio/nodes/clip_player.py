"""Clip Player — plays an audio clip as audio blocks, in real time."""

from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np

from haybale_audio.emitter import BlockPump, deliver_to_subscribers, set_status
from haybale_audio.value import AudioBlock
from haywire.api import (
    BOOL,
    EXEC,
    INT,
    STRING,
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


class ClipPlayerSettings(NodeSettings):
    """How the clip is played. Applies when the player starts; a Start while it plays keeps them."""

    block_size = setting[INT](
        256,
        min=16,
        max=8192,
        label="Block Size",
        category="Playback",
        description="Samples per block. The clip's own sample rate and channels are kept.",
        promotable=Promotable.CONFIG,
    )
    loop = setting[BOOL](
        False,
        label="Loop",
        category="Playback",
        description="Start again at the end of the clip instead of stopping.",
        promotable=Promotable.CONFIG,
    )
    keep_running = setting[BOOL](
        False,
        label="Keep Running",
        category="Playback",
        description=(
            "After the clip, send silent blocks until Stop instead of stopping. For a player wired to "
            "an Audio Mixer: the mixer sees one source that never ends, so a clip's end is no stall."
        ),
        promotable=Promotable.CONFIG,
    )


@node(
    label="Clip Player",
    description="Plays an audio clip as audio blocks, in real time",
    menu="audio/source",
    search_tags=["audio", "clip", "play", "speech", "voice", "emit"],
    node_type=NodeType.CONTROL,
)
class ClipPlayerNode(BaseNode):
    """Cuts an audio clip, such as a spoken sentence, into blocks and delivers them, paced at the
    clip's sample rate, to every Audio Event listening. The clip's own sample rate and channel count
    are kept: Device Out and the Audio Mixer convert it, and Resample does for any other node.

    A Start while a clip plays switches to the clip now on `Clip`, from its first block and without a
    gap. A new value on `Clip` alone changes nothing until the next Start.

    `Keep Running` sends silent blocks after the clip until Stop. Turn it on when the player feeds an
    Audio Mixer: otherwise each clip's end counts as a stall in the mixer's status, and each clip
    starts only once the mixer's prefill is queued again.

    Inputs:
        start / stop: Begin playing the clip on `clip`, or end playback
        clip: The audio clip to play
        callbacks: Pooled AUDIO_CALLBACK subscriptions from Audio Event nodes

    Outputs:
        started / stopped: Control flow after the matching input
    """

    playback = bag(ClipPlayerSettings)

    def init(self) -> None:
        # reload: barn types are looked up fresh after a hot reload.
        from haybale_audio.types.audio import AUDIO
        from haybale_audio.types.callback import AUDIO_CALLBACK
        from haybale_core.types import POOLED

        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(AUDIO.as_inlet("clip", label="Clip", description="Audio clip to play"))
        self.add(
            POOLED[AUDIO_CALLBACK].as_inlet(
                "callbacks", label="Subscribers", description="Connect to an Audio Event node."
            )
        )
        self.add(STRING.as_config("status", default="Idle", label="Status", widget=LabelWidget.config()))
        self.add(EXEC.as_outlet("started", label="Started"))
        self.add(EXEC.as_outlet("stopped", label="Stopped"))

    def post_init(self) -> None:
        self.hb_pump: BlockPump | None = None
        self.hb_reader: _ClipReader | None = None

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_stop()

    def on_teardown(self) -> None:
        self.hb_stop()

    def worker(self, context: ExecutionContext, clip: AudioBlock | None = None) -> str | None:
        if context.control_pin == "start":
            return self.hb_start(context, clip)
        if context.control_pin == "stop":
            self.hb_stop()
            set_status(self, "Stopped")
            return "stopped"
        return None

    def hb_start(self, context: ExecutionContext, clip: AudioBlock | None) -> str | None:
        if clip is None:
            raise Refusal("Clip Player has no clip to play: connect one to Clip.")
        if not (self.value("callbacks") or {}):
            set_status(self, "No subscriber")
            return None
        running = self.hb_pump is not None and self.hb_pump.running
        if not (running and self.hb_reader is not None and self.hb_reader.play(clip)):
            self.hb_stop()
            self.hb_reader = _ClipReader(
                clip,
                int(self.playback.block_size),
                loop=bool(self.playback.loop),
                keep_running=bool(self.playback.keep_running),
                on_clip_end=lambda: set_status(self, "Silence until the next clip"),
            )
            self.hb_pump = BlockPump(
                produce=self.hb_reader.read_block,
                deliver=lambda block, number, seconds: deliver_to_subscribers(
                    context, self.value("callbacks"), block, number, seconds
                ),
                on_end=self.hb_on_end,
            )
            self.hb_pump.start()
        set_status(self, f"Playing {clip.duration:.1f} s, {clip.channels} ch at {clip.sample_rate} Hz")
        return "started"

    def hb_on_end(self, error: Exception | None) -> None:
        set_status(self, f"Error: {error}" if error else "Finished")

    def hb_stop(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        pump = getattr(self, "hb_pump", None)
        if pump is not None:
            pump.stop()
            self.hb_pump = None
        self.hb_reader = None


class _ClipReader:
    """Hands out a clip block by block, for a `BlockPump`; a running reader switches to a new clip.

    The blocks keep the clip's sample rate and channels; the last block of a pass is shorter than
    ``block_size`` when the length does not divide. After the clip it loops, sends silence in the
    clip's format (``keep_running``), or ends. ``play`` and ``read_block`` may run on different threads.
    """

    def __init__(
        self,
        clip: AudioBlock,
        block_size: int,
        loop: bool = False,
        keep_running: bool = False,
        on_clip_end: Callable[[], None] | None = None,
    ) -> None:
        self._block_size = block_size
        self._loop = loop
        self._keep_running = keep_running
        self._on_clip_end = on_clip_end
        self._lock = threading.Lock()
        self._ended = False
        self._clip = clip
        self._position = 0
        self._silence = self._silence_for(clip)

    def play(self, clip: AudioBlock) -> bool:
        """Switch to ``clip`` from its first block; return ``False`` once the reader has ended."""
        with self._lock:
            if self._ended:
                return False
            self._clip = clip
            self._position = 0
            self._silence = self._silence_for(clip)
            return True

    def read_block(self) -> AudioBlock | None:
        """Return the next block, or ``None`` once the clip is over and neither looping nor running."""
        clip_ended = False
        with self._lock:
            frames = self._clip.frames
            if self._position >= frames and self._loop and frames > 0:
                self._position = 0
            if self._position >= frames:
                if not self._keep_running:
                    self._ended = True
                    return None
                clip_ended = self._position == frames
                self._position = frames + 1  # past the end: the clip's end is reported once
                block = self._silence
            else:
                end = min(self._position + self._block_size, frames)
                data = np.ascontiguousarray(self._clip.data[:, self._position : end])
                block = AudioBlock(data, self._clip.sample_rate)
                self._position = end
        if clip_ended and self._on_clip_end is not None:
            self._on_clip_end()
        return block

    def _silence_for(self, clip: AudioBlock) -> AudioBlock:
        return AudioBlock.silence(clip.channels, self._block_size, clip.sample_rate)
