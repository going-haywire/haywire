"""Clip Queue — holds audio clips until a flow takes them, one at a time."""

from __future__ import annotations

import threading
from collections import deque

from haybale_audio.emitter import set_status
from haybale_audio.value import AudioBlock
from haywire.api import (
    CHOICES,
    EXEC,
    INT,
    STRING,
    BaseNode,
    ExecutionContext,
    LabelWidget,
    NodeSettings,
    NodeType,
    Promotable,
    bag,
    node,
    setting,
)

OLDEST_FIRST = "Oldest first"
NEWEST_FIRST = "Newest first"
NEWEST_ONLY = "Newest only"


class ClipQueueSettings(NodeSettings):
    """Which clip Pop takes, and how many clips the queue holds."""

    order = setting[CHOICES](
        OLDEST_FIRST,
        label="Order",
        category="Queue",
        description=(
            "Oldest first plays clips in the order they came. Newest first takes the latest clip. "
            "Newest only keeps just the latest clip: a Push replaces the one waiting."
        ),
        widget_config={"options": [OLDEST_FIRST, NEWEST_FIRST, NEWEST_ONLY]},
        promotable=Promotable.CONFIG,
    )
    max_clips = setting[INT](
        16,
        min=1,
        max=1024,
        label="Max Clips",
        category="Queue",
        description="How many clips the queue holds; a Push to a full queue drops the oldest clip.",
        promotable=Promotable.CONFIG,
    )


@node(
    label="Clip Queue",
    description="Holds audio clips until a flow takes them, one at a time",
    menu="audio/clip",
    search_tags=["audio", "clip", "queue", "playlist", "buffer", "speech", "fifo"],
    node_type=NodeType.CONTROL,
)
class ClipQueueNode(BaseNode):
    """Holds clips pushed in by one flow until another flow pops them, in the order chosen.

    Played one after another through a Clip Player, Clip Player's `On Finish` pops the next clip:

    ```text
    Clip Event → Clip Ready → Clip Queue (Push), Clip → Clip
    Clip Player (On Finish) ← Tick Event → Clip Queue (Pop) → Popped → Clip Player (Start)
    ```

    `Pop` on an empty queue continues on `Empty`. The chain needs a first Pop while the player is
    idle, such as from a Run Button; after that each clip's end pops the next.

    Inputs:
        push: Add the clip on `clip` to the queue
        pop: Take the next clip, by `Order`, onto the `clip` outlet
        clear: Drop every clip in the queue
        clip: The clip to push

    Outputs:
        pushed: Control flow after a push
        popped: Control flow after a pop that took a clip
        empty: Control flow after a pop on an empty queue
        cleared: Control flow after a clear
        clip_out: The clip the last pop took
        count: How many clips wait in the queue
    """

    queue = bag(ClipQueueSettings)

    def init(self) -> None:
        # reload: barn types are looked up fresh after a hot reload.
        from haybale_audio.types.audio_clip import AUDIO_CLIP

        self.add(EXEC.as_inlet("push", label="Push"))
        self.add(EXEC.as_inlet("pop", label="Pop"))
        self.add(EXEC.as_inlet("clear", label="Clear"))
        self.add(AUDIO_CLIP.as_inlet("clip", label="Clip", description="The clip to push"))
        self.add(STRING.as_config("status", default="Empty", label="Status", widget=LabelWidget.config()))
        self.add(EXEC.as_outlet("pushed", label="Pushed"))
        self.add(EXEC.as_outlet("popped", label="Popped"))
        self.add(EXEC.as_outlet("empty", label="Empty"))
        self.add(EXEC.as_outlet("cleared", label="Cleared"))
        self.add(AUDIO_CLIP.as_outlet("clip_out", label="Clip", description="The clip the last pop took"))
        self.add(INT.as_outlet("count", label="Count", description="Clips waiting in the queue"))

    def post_init(self) -> None:
        self.hb_clips = _Clips()

    def on_shutdown(self, context: ExecutionContext) -> None:
        self.hb_reset()

    def on_teardown(self) -> None:
        self.hb_reset()

    def hb_reset(self) -> None:
        # post_init() may never have run (init() failed during a reset or reload).
        clips = getattr(self, "hb_clips", None)
        if clips is not None:
            clips.clear()

    def worker(self, context: ExecutionContext, clip: AudioBlock | None = None) -> str | None:
        clips = self.hb_clips
        pin = context.control_pin
        if pin == "push":
            if clip is None:
                raise ValueError("push needs a clip")
            count = clips.push(clip, str(self.queue.order), int(self.queue.max_clips))
            outlet: str | None = "pushed"
        elif pin == "pop":
            taken, count = clips.pop(str(self.queue.order))
            if taken is not None:
                self.out("clip_out", taken)
            outlet = "popped" if taken is not None else "empty"
        elif pin == "clear":
            count = clips.clear()
            outlet = "cleared"
        else:
            return None
        self.out("count", count)
        set_status(self, f"{count} clip{'s' if count != 1 else ''} waiting ({clips.dropped} dropped)")
        return outlet


class _Clips:
    """The clips a Clip Queue holds; safe across threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clips: deque[AudioBlock] = deque()
        self.dropped = 0

    def push(self, clip: AudioBlock, order: str, max_clips: int) -> int:
        """Add ``clip``, dropping the oldest beyond ``max_clips`` (beyond one for Newest only)."""
        limit = 1 if order == NEWEST_ONLY else max(1, max_clips)
        with self._lock:
            self._clips.append(clip)
            while len(self._clips) > limit:
                self._clips.popleft()
                self.dropped += 1
            return len(self._clips)

    def pop(self, order: str) -> tuple[AudioBlock | None, int]:
        """Take the next clip by ``order``; return it, or ``None`` when empty, and the count left."""
        with self._lock:
            if not self._clips:
                return None, 0
            clip = self._clips.popleft() if order == OLDEST_FIRST else self._clips.pop()
            return clip, len(self._clips)

    def clear(self) -> int:
        """Drop every clip; return the count left, 0."""
        with self._lock:
            self._clips.clear()
            self.dropped = 0
            return 0
