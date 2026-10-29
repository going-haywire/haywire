import threading
import time
from typing import List, Optional

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Tick Emit",
    description="Emits tick callbacks at a configurable framerate",
    menu="core/emit",
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
        from haywire.barn.builtin.types import FLOAT
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import CALLBACK, EXEC
        from haywire.barn.builtin.widgets import NumberWidget

        # Control inputs
        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))

        # Configuration
        self.add(
            FLOAT.as_inlet(
                "target_fps",
                default=60.0,
                label="Target FPS",
                description="Targeted Frames per second - needs a start signal to be applied",
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
        with self._lock:
            if self._is_running:
                return "started"

            target_fps = self.value("target_fps")
            callback_names = list(self.value("callback_names").values())
            # One stop event per tick thread, so a restart never clears the
            # event an exiting thread has not seen yet.
            self._stop_event = threading.Event()
            self._is_running = True
            self._frame_count = 0
            self._delta_diff = 0.0

            self._thread = threading.Thread(
                target=self._tick_loop,
                args=(context, self._stop_event, target_fps, callback_names),
                name=f"TickEmit-{self.node_id}",
                daemon=True,
            )
            self._thread.start()
        return "started"

    def _handle_stop(self) -> Optional[str]:
        with self._lock:
            if not self._is_running:
                return None
        self._stop_thread()
        return "stopped"

    def _tick_loop(
        self,
        context: ExecutionContext,
        stop_event: threading.Event,
        target_fps: float,
        callback_names: List[str],
    ):
        """Main tick loop running in a separate thread."""
        interval = 1.0 / max(0.1, target_fps)
        last_time = time.perf_counter()

        while not stop_event.wait(timeout=max(0.0, interval - self._delta_diff)):
            now = time.perf_counter()
            delta = now - last_time
            last_time = now
            self._frame_count += 1

            # Emit to all connected TickEventNodes
            for callback in callback_names:
                context.emit_callback(
                    event_name=callback,
                    payload={"delta_time": delta},
                )

            # Delta smoothing for timing accuracy
            new_delta_diff = self._delta_diff + (delta - interval)
            self._delta_diff = self._delta_diff * (1.0 - self._smoothing) + new_delta_diff * self._smoothing

    def _stop_thread(self):
        """Stop the tick thread and wait for it to exit; safe to call from several threads at once."""
        with self._lock:
            thread, self._thread = self._thread, None
            self._is_running = False
            self._stop_event.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
