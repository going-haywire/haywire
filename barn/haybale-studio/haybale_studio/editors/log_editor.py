"""
LogEditor — scrollable application output panel.

Shows both Python `logging` records and `print()` / `console_print()` output,
merged into one buffer and flushed to the UI on a single timer. Two producers
feed the same deque:

- `_LogHandler`, attached to the root logger, formats and appends log records;
- a sink registered with the process-wide `StdoutTee` appends stdout lines.

A single buffer/timer pair (rather than one per producer) keeps the two
sources interleaved in the order they actually happened.
"""

import logging
import threading
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Optional

from nicegui import ui
from nicegui.timer import Timer

from haywire.ui import elements as hui
from haywire.ui.console_bridge import get_stdout_tee
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from haywire.ui.editor.base import BaseEditor

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from nicegui.element import Element


class _LogHandler(logging.Handler):
    """Formats log records and appends them into the editor's shared buffer.

    ``emit()`` is called from arbitrary threads (execution, file-watcher, …).
    It only formats and appends — LogEditor owns the timer that flushes the
    buffer into the UI.
    """

    def __init__(self, append: Callable[[str], None]):
        super().__init__()
        self._append = append

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._append(self.format(record))
        except Exception:
            pass


@editor(
    label="Log",
    registry_id="TerminalEditor",  # PINNED — see below. Do not remove.
    icon=hui.icon.terminal,
    default_slot=SlotName.INFO,
    description="Application output. Captures Python logging and print() output.",
)
class LogEditor(BaseEditor):
    """
    Renders a scrollable log panel capturing both Python logging and stdout.

    `registry_id` must stay pinned to the old "TerminalEditor" class name: it
    defaults to the class name and `registry_key` derives from it, and slot
    layout is persisted by that wire string in `.haywire/workspace_state.json`.
    Dropping the pin would silently orphan every existing user's bottom-slot
    layout.
    """

    _FLUSH_INTERVAL = 0.1  # seconds between UI flushes
    _MAX_BUFFERED = 500  # mirrors ui.log's max_lines, so Copy stays WYSIWYG against it

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._log_element = None
        # Persistent mirror of everything currently rendered — Copy/Clear act on this,
        # not on the DOM. `_pending` is the separate not-yet-pushed-to-UI queue that
        # `_flush` drains; the two must stay decoupled or Copy would race a near-empty
        # buffer between flush ticks.
        self._buffer: deque[str] = deque(maxlen=self._MAX_BUFFERED)
        self._pending: list[str] = []
        self._lock = threading.Lock()
        self._handler: Optional[_LogHandler] = None
        self._timer: Optional[Timer] = None
        self._detach_stdout: Optional[Callable[[], None]] = None

    def draw(self, context: "SessionContext", container: "Element") -> None:
        with container:
            with ui.column().classes("w-full h-full gap-0"):
                self._render_header()
                self._log_element = (
                    ui.log(max_lines=500)
                    .classes("w-full flex-1 font-mono text-xs p-2")
                    .style("background: var(--hw-console-bg); color: var(--hw-console-text);")
                )

        for line in get_stdout_tee().get_history_text().splitlines():
            self._append(self._prefix_stdout(line))

        self._handler = _LogHandler(self._append)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
        )
        logging.getLogger().addHandler(self._handler)

        self._detach_stdout = get_stdout_tee().add_sink(lambda line: self._append(self._prefix_stdout(line)))

        self._timer = ui.timer(self._FLUSH_INTERVAL, self._flush)
        logging.getLogger().info("Log editor connected.")

    def _render_header(self) -> None:
        with (
            ui.row()
            .classes("w-full items-center px-3 gap-2 flex-shrink-0 border-b")
            .style("min-height: 32px; background: var(--hw-bg-surface);")
        ):
            ui.space()
            (
                ui.button(icon=hui.icon.copy, on_click=self._copy)
                .props("flat dense size=sm")
                .tooltip("Copy log to clipboard")
            )
            (
                ui.button(icon=hui.icon.clear, on_click=self._clear)
                .props("flat dense size=sm")
                .tooltip("Clear log")
            )

    @staticmethod
    def _prefix_stdout(line: str) -> str:
        return f"{datetime.now():%H:%M:%S} [stdout] {line}"

    def _append(self, msg: str) -> None:
        with self._lock:
            self._buffer.append(msg)
            self._pending.append(msg)

    def _flush(self) -> None:
        with self._lock:
            if not self._pending:
                return
            batch = self._pending
            self._pending = []

        try:
            for msg in batch:
                self._log_element.push(msg)
        except Exception:
            pass

    def _copy(self) -> None:
        with self._lock:
            text = "\n".join(self._buffer)
        ui.run_javascript(f"navigator.clipboard.writeText({text!r})")

    def _clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._pending.clear()
        if self._log_element is not None:
            self._log_element.clear()
        get_stdout_tee().clear_history()

    def cleanup(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._handler is not None:
            logging.getLogger().removeHandler(self._handler)
            self._handler.close()
            self._handler = None
        if self._detach_stdout is not None:
            self._detach_stdout()
            self._detach_stdout = None
        self._log_element = None
