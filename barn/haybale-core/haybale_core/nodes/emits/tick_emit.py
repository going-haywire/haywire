import threading
import time
from typing import Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Tick Emit",
    description="Emits tick callbacks at a configurable framerate",
    menu="emit/runtime",
    search_tags=["tick", "frame", "loop", "emit", "fps", "timer"],
    node_type=NodeType.CONTROL,
)
class TickEmitNode(BaseNode):
    """
    Emits tick callbacks at a configurable framerate from an internal thread.

    Wire from BeginPlayNode to start ticking. Connect TickEventNodes via
    the callback inlet to receive ticks.

    Inputs:
        start: Begin emitting ticks
        stop: Stop emitting ticks
        target_fps: Target frames per second (default 60)
        callback_names: Callback edge inlet for connected TickEventNodes

    Outputs:
        started: Control flow after tick thread starts
        stopped: Control flow after tick thread stops
    """

    def init(self):
        from haybale_core.types import EXEC, FLOAT, CALLBACK, PooledType
        from haybale_core.widgets import NumberWidget

        # Control inputs
        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))

        # Configuration
        self.add(
            FLOAT.as_inlet(
                "target_fps",
                default=60.0,
                label="Target FPS",
                widget=NumberWidget.config(properties={"min": 0.1, "max": 240, "step": 1}),
            )
        )

        # Callback inlet — receives listener IDs from connected TickEventNodes
        self.add(PooledType[CALLBACK].as_inlet("callback_names", label="Trigger"))

        # Control outputs
        self.add(EXEC.as_outlet("started", label="Started"))
        self.add(EXEC.as_outlet("stopped", label="Stopped"))

    def post_init(self):
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._frame_count: int = 0
        self._delta_diff: float = 0.0
        self._smoothing: float = 0.4

    def on_shutdown(self, context: ExecutionContext):
        """Stop the tick thread on interpreter shutdown."""
        self._stop_thread()

    def on_teardown(self):
        """Final cleanup when node is destroyed."""
        self._stop_thread()

    def worker(self, context: ExecutionContext) -> Optional[str]:
        if context.control_pin == "start":
            return self._handle_start(context)
        elif context.control_pin == "stop":
            return self._handle_stop()
        return None

    def _handle_start(self, context: ExecutionContext) -> Optional[str]:
        if self._is_running:
            return "started"

        self._is_running = True
        self._stop_event.clear()
        self._frame_count = 0
        self._delta_diff = 0.0

        self._thread = threading.Thread(target=self._tick_loop, args=(context,), daemon=True)
        self._thread.start()
        return "started"

    def _handle_stop(self) -> Optional[str]:
        if not self._is_running:
            return None
        self._stop_thread()
        return "stopped"

    def _tick_loop(self, context: ExecutionContext):
        """Main tick loop running in a separate thread."""
        target_fps = self.value("target_fps")
        interval = 1.0 / max(0.1, target_fps)
        last_time = time.perf_counter()

        while not self._stop_event.wait(timeout=max(0.0, interval - self._delta_diff)):
            now = time.perf_counter()
            delta = now - last_time
            last_time = now
            self._frame_count += 1

            # Emit to all connected TickEventNodes
            callback_names: dict = self.value("callback_names")
            for callback in callback_names.values():
                context.emit_callback(
                    event_name=callback,
                    payload={"delta_time": delta},
                )

            # Delta smoothing for timing accuracy
            new_delta_diff = self._delta_diff + (delta - interval)
            self._delta_diff = self._delta_diff * (1.0 - self._smoothing) + new_delta_diff * self._smoothing

        with self._lock:
            self._is_running = False

    def _stop_thread(self):
        """Stop the tick thread and wait for it to exit."""
        if not self._is_running:
            return
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        with self._lock:
            self._is_running = False
        self._thread = None
