"""Shared pieces of the audio emitter nodes: a paced block thread and callback delivery."""

import threading
import time
from collections.abc import Callable
from typing import Any

from haywire.core.execution.execution_context import ExecutionContext

from haybale_audio.value import AudioBlock

#: Seconds behind schedule after which the pump restarts its schedule and skips the backlog.
RESYNC_AFTER = 0.5


class BlockPump:
    """Calls ``produce`` for each block and ``deliver`` at the block's time, on a daemon thread.

    The first block goes out at once; each next one a block duration after the previous.
    """

    def __init__(
        self,
        produce: Callable[[], AudioBlock | None],
        deliver: Callable[[AudioBlock, int, float], None],
        on_end: Callable[[Exception | None], None] | None = None,
    ) -> None:
        self._produce = produce
        self._deliver = deliver
        self._on_end = on_end
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
                if block is None:
                    break
                wait = deadline - time.monotonic()
                if wait > 0:
                    if self._stop.wait(wait):  # sleeps to the deadline: busy-waiting would hold the GIL
                        break
                elif wait < -RESYNC_AFTER:
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
) -> None:
    """Send ``block`` to every Audio Event subscribed on the emitter's ``CALLBACK_AUDIO`` inlet."""
    payload = {"audio": block, "timestamp": seconds, "block_number": number}
    for sub in (subscribers or {}).values():
        name = getattr(sub, "name", None)
        if name:
            context.emit_callback(event_name=name, payload=payload)


def set_status(node: Any, text: str) -> None:
    """Show ``text`` on the node's ``status`` label; a node that is going away may have no port."""
    try:
        node.ports["status"].set_value(text)
    except Exception:
        pass
