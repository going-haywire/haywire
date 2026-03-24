"""
Interactive Interpreter Loop Manager.

Emits TICK events at a configurable framerate.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from threading import Thread, Event
import time
import logging

if TYPE_CHECKING:
    from haywire.core.execution.interpreter import Interpreter

from haywire.core.execution.event_source import SystemEventType

logger = logging.getLogger(__name__)


class InterpreterLoopManager:
    """
    Emits BEGIN_PLAY, TICK, and SHUTDOWN events at a target framerate.
    """

    def __init__(self, interpreter: "Interpreter", target_fps: float = 60.0):
        self.interpreter = interpreter
        self.target_fps = target_fps
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._last_time: float = 0.0
        self.frame_count: int = 0
        self._delta_diff: float = 0.0
        self._start_time: float = 0.0
        self._smoothing: float = 0.4

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running:
            return

        self._stop_event.clear()
        self._last_time = time.perf_counter()
        self._start_time = self._last_time
        self.frame_count = 0

        self.interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)

        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if not self.is_running:
            return

        self._stop_event.set()
        self._thread.join(timeout=1.0)
        self.interpreter.dispatch_system_event(SystemEventType.SHUTDOWN)

    def _run(self):
        interval = 1.0 / self.target_fps

        while not self._stop_event.wait(timeout=interval - self._delta_diff):
            now = time.perf_counter()
            delta = now - self._last_time
            self._last_time = now
            self.frame_count += 1

            # print(f"Tick: Frame {self.frame_count}, Delta: {delta:.4f}s, "
            #       f"Target Interval: {interval:.4f}s, Delta Diff: {self._delta_diff:.4f}s")
            self.interpreter.dispatch_system_event(SystemEventType.TICK, payload={"delta_time": delta})
            new_delta_diff = self._delta_diff + (delta - interval)
            self._delta_diff = self._delta_diff * (1.0 - self._smoothing) + new_delta_diff * self._smoothing

    def get_stats(self) -> dict:
        """
        Get performance statistics.

        Thread-safe - can be called from any thread.

        Returns:
            Dictionary with current loop state and performance metrics
        """
        elapsed_time = time.perf_counter() - self._start_time
        avg_fps = self.frame_count / elapsed_time if elapsed_time > 0 else 0.0

        return {
            "is_running": self.is_running,
            "target_fps": self.target_fps,
            "actual_fps": avg_fps,
            "frame_count": self.frame_count,
        }
