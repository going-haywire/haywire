"""Shared pieces of the audio emitter nodes: a paced block thread and callback delivery."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from haybale_audio.value import AudioBlock
from haywire.api import BacklogSettings, ExecutionContext

#: Seconds between status updates of a running node; one per block would flood the UI.
STATUS_INTERVAL = 0.5
#: Seconds behind schedule after which the pump restarts its schedule and skips the backlog.
RESYNC_AFTER = 0.5


class BlockPump:
    """Calls ``produce`` for each block and ``deliver`` at the block's time, on a daemon thread.

    The first block goes out at once; each next one a block duration after the previous. With
    ``paced=False`` each block goes out as soon as ``produce`` returns it: for a source whose
    ``produce`` waits on a clock of its own, such as a sound device.
    """

    def __init__(
        self,
        produce: Callable[[], AudioBlock | None],
        deliver: Callable[[AudioBlock, int, float], None],
        on_end: Callable[[Exception | None], None] | None = None,
        paced: bool = True,
    ) -> None:
        self._produce = produce
        self._deliver = deliver
        self._on_end = on_end
        self._paced = paced
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.resyncs = 0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="audio-pump", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _run(self) -> None:
        error: Exception | None = None
        try:
            started = deadline = time.monotonic()
            number = 0
            while not self._stop.is_set():
                block = self._produce()
                if block is None or self._stop.is_set():
                    break
                wait = deadline - time.monotonic() if self._paced else 0.0
                if wait > 0:
                    if self._stop.wait(wait):  # sleeps to the deadline: busy-waiting would hold the GIL
                        break
                elif self._paced and wait < -RESYNC_AFTER:
                    deadline = time.monotonic()
                    self.resyncs += 1
                self._deliver(block, number, time.monotonic() - started)
                number += 1
                deadline += block.duration
        except Exception as exc:
            error = exc
        if self._on_end is not None:
            self._on_end(error)


def deliver_to_subscribers(
    context: ExecutionContext,
    subscribers: dict[str, Any] | None,
    block: AudioBlock,
    number: int,
    seconds: float,
    backlog: BacklogSettings | None = None,
) -> None:
    """Send ``block`` to every Audio Event subscribed on the emitter's ``AUDIO_CALLBACK`` inlet.

    One emit carries every subscriber's name, so Audio Events set to Pooled share the blocks.
    ``backlog`` is the emitter's own ``BacklogSettings``, where blocks wait while every pooled
    Audio Event is busy; ``None`` holds 16 and drops the oldest.
    """
    payload = {"audio": block, "timestamp": seconds, "block_number": number}
    names = [name for sub in (subscribers or {}).values() if (name := getattr(sub, "name", None))]
    if names:
        context.emit_callback(event_name=names, payload=payload, backlog=backlog)


def deliver_clip_to_subscribers(
    context: ExecutionContext,
    subscribers: dict[str, Any] | None,
    clip: AudioBlock,
    number: int,
    seconds: float,
    backlog: BacklogSettings | None = None,
) -> None:
    """Send ``clip`` to every Clip Event subscribed on the emitter's ``CLIP_CALLBACK`` inlet.

    One emit carries every subscriber's name, so Clip Events set to Pooled share the clips;
    ``backlog`` is the emitter's own ``BacklogSettings``, as for ``deliver_to_subscribers``.
    """
    payload = {"clip": clip, "timestamp": seconds, "clip_number": number}
    names = [name for sub in (subscribers or {}).values() if (name := getattr(sub, "name", None))]
    if names:
        context.emit_callback(event_name=names, payload=payload, backlog=backlog)


def set_status(node: Any, text: str) -> None:
    """Show ``text`` on the node's ``status`` label; a node that is going away may have no port."""
    try:
        node.ports["status"].set_value(text)
    except Exception:
        pass
