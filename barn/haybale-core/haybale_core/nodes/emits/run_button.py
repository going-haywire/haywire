"""Run Button — a button on the card that triggers Tick Event flows in a running graph."""

import threading
import time
from typing import Any, Optional

from haywire.barn.builtin.types import BOOL
from haywire.barn.builtin.widget_keys import BUTTON_WIDGET
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, setting
from haywire.core.types.enums import PortType


@node(
    label="Run Button",
    description="A button on the card that triggers connected Tick Event flows while the graph runs",
    menu="core/emit",
    search_tags=["run", "button", "trigger", "press", "batch", "emit"],
    node_type=NodeType.CONTROL,
)
class RunButtonNode(BaseNode):
    """A button on the card that triggers connected Tick Event flows while the graph runs.

    Wire `Begin Play` to `Start`, and the `Listen` outlet of each Tick Event to
    `Trigger`. Every press of *Run* then starts each connected Tick Event's flow
    once; the Tick Event's *Delta Time* is the time since the previous press.

    ```
    Begin Play → Start                 Tick Event.Listen → Trigger
                                       Tick Event → For Each File → …
    ```

    The button works from *Start* until *Stop* or until the graph stops. Presses
    made before the node picks them up count as one. A press made while the graph
    is stopped shows as pending and is cleared when the graph starts again.
    """

    class button(NodeSettings):
        run = setting[BOOL](
            False,
            label="Run",
            description="Press to trigger the connected flows once",
            promotable=Promotable.CONFIG,
            promote_default=PortType.CONFIG,
            widget={"key": BUTTON_WIDGET, "config": {"properties": {"text": "Run", "icon": "play_arrow"}}},
        )

    def init(self) -> None:
        from haybale_core.types import PooledType
        from haywire.barn.builtin.types import CALLBACK, EXEC

        self.add(EXEC.as_inlet("start", label="Start"))
        self.add(EXEC.as_inlet("stop", label="Stop"))
        self.add(PooledType[CALLBACK].as_inlet("callbacks", label="Trigger"))
        self.add(EXEC.as_outlet("started", label="Started"))
        self.add(EXEC.as_outlet("stopped", label="Stopped"))

    def post_init(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake = threading.Event()
        self._context: Optional[ExecutionContext] = None
        self._last_emit: Optional[float] = None
        self._settings._subscribe_field("run", self._on_run_changed)

    @property
    def _settings(self) -> Any:
        return self.button

    def on_shutdown(self, context: ExecutionContext) -> None:
        """Stop the button thread when the graph stops."""
        self._stop_thread()

    def on_teardown(self) -> None:
        """Stop the button thread when the node is destroyed."""
        self._stop_thread()

    def worker(self, context: ExecutionContext) -> Optional[str]:
        if context.control_pin == "start":
            return self._handle_start(context)
        if context.control_pin == "stop":
            return self._handle_stop()
        return None

    def _on_run_changed(self, value: Any, _old: Any) -> None:
        # Runs inside the press's own write: only wake the thread, which resets and emits.
        if value is True:
            self._wake.set()

    def _handle_start(self, context: ExecutionContext) -> str:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return "started"
            self._settings.run = False
            self._context = context
            self._last_emit = None
            # One stop event per thread, so a restart never clears the event an exiting thread has not seen.
            self._stop_event = threading.Event()
            self._wake.clear()
            self._thread = threading.Thread(
                target=self._run, args=(self._stop_event,), name=f"RunButton-{self.node_id}", daemon=True
            )
            self._thread.start()
        return "started"

    def _handle_stop(self) -> Optional[str]:
        with self._lock:
            if self._thread is None:
                return None
        self._stop_thread()
        return "stopped"

    def _stop_thread(self) -> None:
        with self._lock:
            thread, self._thread = self._thread, None
            self._stop_event.set()
            self._wake.set()
            self._context = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def _run(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self._wake.wait()
            if stop_event.is_set():
                return
            self._wake.clear()
            self._consume()

    def _consume(self) -> bool:
        """Emit one trigger to every listener if *Run* is pressed, and release the button."""
        context = self._context
        if context is None or self._settings.run is not True:
            return False
        self._settings.run = False
        now = time.monotonic()
        delta = 0.0 if self._last_emit is None else now - self._last_emit
        self._last_emit = now
        for name in list(self.value("callbacks").values()):
            context.emit_callback(event_name=name, payload={"delta_time": delta})
        return True
