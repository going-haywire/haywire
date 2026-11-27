"""Clip Player — plays an audio clip as audio blocks, in real time."""

from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np

from haybale_audio.emitter import BlockPump, deliver_to_subscribers, set_status
from haybale_audio.value import AudioBlock
from haywire.api import (
    BOOL,
    CALLBACK,
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
    """Plays an audio clip as blocks, paced at its sample rate, to every Audio Event listening.

    The clip, such as a spoken sentence, is cut into blocks. Its own sample rate and channel count
    are kept: Device Out and the Audio Mixer convert it, and Resample does for any other node.

    `On Finish` runs the Tick Events wired to it when a clip has played to its end (with
    `Keep Running`, when its silence begins); a Stop runs none. Wire it to a Clip Queue's Pop to
    play queued clips one after another.

    A Start while a clip plays switches to the clip now on `Clip`, from its first block and without a
    gap. A new value on `Clip` alone changes nothing until the next Start.

    `Keep Running` sends silent blocks after the clip until Stop. Turn it on when the player feeds an
    Audio Mixer: otherwise each clip's end counts as a stall in the mixer's status, and each clip
    starts only once the mixer's prefill is queued again.

    Inputs:
        start / stop: Begin playing the clip on `clip`, or end playback
        clip: The audio clip to play
        callbacks: Pooled AUDIO_CALLBACK subscriptions from Audio Event nodes
        finish_callbacks: Pooled CALLBACK subscriptions from the Tick Events to run at a clip's end

    Outputs:
        started / stopped: Control flow after the matching input
    """

    playback = bag(ClipPlayerSettings)

    def init(self) -> None:
        # reload: barn types are looked up fresh after a hot reload.
        from haybale_audio.types.audio_clip import AUDIO_CLIP
        from haybale_audio.types.callback import AUDIO_CALLBACK
        from haybale_core.types import POOLED

        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(AUDIO_CLIP.as_inlet("clip", label="Clip", description="Audio clip to play"))
        self.add(
            POOLED[AUDIO_CALLBACK].as_inlet(
                "callbacks", label="Subscribers", description="Connect to an Audio Event node."
            )
        )
        self.add(
            POOLED[CALLBACK].as_inlet(
                "finish_callbacks",
                label="On Finish",
                description="Tick Event Listen outlets whose flows run when a clip has played to its end",
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
        # The status first: a short clip's end may be reported before this method returns.
        set_status(self, f"Playing {clip.duration:.1f} s, {clip.channels} ch at {clip.sample_rate} Hz")
        running = self.hb_pump is not None and self.hb_pump.running
        if not (running and self.hb_reader is not None and self.hb_reader.play(clip)):
            self.hb_stop()
            reader = _ClipReader(
                clip,
                int(self.playback.block_size),
                loop=bool(self.playback.loop),
                keep_running=bool(self.playback.keep_running),
            )
            reader.on_clip_end = lambda: reader.finish(
                lambda: self.hb_finished(context, "Silence until the next clip")
            )
            self.hb_reader = reader
            self.hb_pump = BlockPump(
                produce=reader.read_block,
                deliver=lambda block, number, seconds: deliver_to_subscribers(
                    context, self.value("callbacks"), block, number, seconds
                ),
                on_end=lambda error: self.hb_on_end(context, reader, error),
            )
            self.hb_pump.start()
        return "started"

    def hb_on_end(self, context: ExecutionContext, reader: _ClipReader, error: Exception | None) -> None:
        if error is not None:
            set_status(self, f"Error: {error}")
        elif reader.ended:  # played to its end; a Stop leaves the reader running
            reader.finish(lambda: self.hb_finished(context, "Finished"))

    def hb_finished(self, context: ExecutionContext, status: str) -> None:
        """Show ``status`` and run the Tick Events wired to `On Finish`."""
        set_status(self, status)
        names = [name for name in (self.value("finish_callbacks") or {}).values() if name]
        if names:
            context.emit_callback(event_name=names, payload=None)

    def hb_stop(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        reader = getattr(self, "hb_reader", None)
        if reader is not None:
            reader.stop()  # first: a clip running out as Stop arrives runs no On Finish
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

    With ``keep_running`` the clip's end is reported as its last block goes out, not when the
    silence starts, so a next clip switched in by then follows without a silent block between.
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
        self.on_clip_end = on_clip_end
        self._lock = threading.Lock()
        self._finish_lock = threading.Lock()  # orders a finish report against stop()
        self._stopped = False
        self._reported = False
        self._ended = False
        self._clip = clip
        self._position = 0
        self._silence = self._silence_for(clip)

    @property
    def ended(self) -> bool:
        """Whether the clip has played to its end and the reader returned ``None``."""
        with self._lock:
            return self._ended

    def stop(self) -> None:
        """Mark the reader stopped: from now on :meth:`finish` reports nothing."""
        with self._finish_lock:
            self._stopped = True

    def finish(self, report: Callable[[], None]) -> None:
        """Run ``report`` for the clip's end unless the reader was stopped first."""
        with self._finish_lock:
            if not self._stopped:
                report()

    def play(self, clip: AudioBlock) -> bool:
        """Switch to ``clip`` from its first block; return ``False`` once the reader has ended."""
        with self._lock:
            if self._ended:
                return False
            self._clip = clip
            self._position = 0
            self._reported = False
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
                block = self._silence
            else:
                end = min(self._position + self._block_size, frames)
                data = np.ascontiguousarray(self._clip.data[:, self._position : end])
                block = AudioBlock(data, self._clip.sample_rate)
                self._position = end
            if self._keep_running and not self._loop and self._position >= frames and not self._reported:
                self._reported = True  # the clip's end is reported once, as its last block goes out
                clip_ended = True
        if clip_ended and self.on_clip_end is not None:
            self.on_clip_end()
        return block

    def _silence_for(self, clip: AudioBlock) -> AudioBlock:
        return AudioBlock.silence(clip.channels, self._block_size, clip.sample_rate)
