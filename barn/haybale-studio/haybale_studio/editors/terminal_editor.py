# packages/haywire-app/src/haywire_studio/editors/console_editor.py
"""
ConsoleEditor — scrollable log output panel.

Displays application log messages using NiceGUI's ui.log widget.
Subscribed to the Python root logger via a logging.Handler.

Log records are buffered and flushed to the UI in batches (default
every 100 ms) so that high-frequency logging (e.g. 60 messages/s from
execution nodes) does not overwhelm the browser with DOM updates.
"""

import logging
import threading
from collections import deque
from typing import TYPE_CHECKING, Optional

from nicegui import ui
from nicegui.timer import Timer

from haywire.ui import elements as hui
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from nicegui.element import Element


class _LogHandler(logging.Handler):
    """Buffers log records and flushes them to a NiceGUI ui.log element on a timer.

    ``emit()`` is called from arbitrary threads (execution, file-watcher, …).
    It only appends the formatted message to a thread-safe buffer.
    A NiceGUI ``ui.timer`` calls ``flush()`` at a fixed interval to push
    the buffered messages into the UI in a single batch.
    """

    _FLUSH_INTERVAL = 0.1  # seconds between UI flushes
    _MAX_BUFFERED = 200  # drop oldest messages if buffer exceeds this

    def __init__(self, log_element):
        super().__init__()
        self._log = log_element
        self._buffer: deque[str] = deque(maxlen=self._MAX_BUFFERED)
        self._lock = threading.Lock()
        self._timer: Optional[Timer] = ui.timer(self._FLUSH_INTERVAL, self.flush)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            with self._lock:
                self._buffer.append(msg)
        except Exception:
            pass

    def flush(self) -> None:
        """Push all buffered messages into the ui.log element at once."""
        with self._lock:
            if not self._buffer:
                return
            batch = list(self._buffer)
            self._buffer.clear()

        try:
            for msg in batch:
                self._log.push(msg)
        except Exception:
            pass

    def close(self) -> None:
        """Stop the timer and flush remaining messages."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.flush()
        super().close()


@editor(
    label="Terminal",
    icon=hui.icon.terminal,
    default_slot="bottom",
    description="Application log output. Captures Python logging messages.",
)
class TerminalEditor(BaseEditor):
    """
    Renders a scrollable log panel capturing Python log output.

    Uses a logging.Handler attached to the root logger so it receives
    all log messages from the application, regardless of origin.
    """

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._log_element = None
        self._handler: _LogHandler | None = None

    def draw(self, context: "SessionContext", container: "Element") -> None:
        with container:
            self._log_element = (
                ui.log(max_lines=500)
                .classes("w-full h-full font-mono text-xs p-2")
                .style("background: var(--hw-console-bg); color: var(--hw-console-text);")
            )
        self._handler = _LogHandler(self._log_element)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
        )
        logging.getLogger().addHandler(self._handler)
        logging.getLogger().info("Console editor connected.")

    def cleanup(self) -> None:
        if self._handler is not None:
            logging.getLogger().removeHandler(self._handler)
            self._handler.close()
            self._handler = None
        self._log_element = None
