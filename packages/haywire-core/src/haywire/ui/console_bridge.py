"""
Thread-safe console bridge for NiceGUI.

Allows worker threads to print messages that appear in the UI.
Access the shared bridge via get_bridge() or use console_print() directly.
"""

from __future__ import annotations
from threading import Lock
from queue import Queue, Empty
from nicegui import ui


class ConsoleBridge:
    """
    Thread-safe bridge between worker threads and NiceGUI log elements.

    Usage:
        # In UI setup (per session):
        bridge = get_bridge()
        log = ui.log(max_lines=100)
        bridge.register_log_with_polling(log)

        # In worker thread (e.g., Print Message node):
        from haywire.ui.console_bridge import console_print
        console_print("Hello from node!")
    """

    def __init__(self):
        self.message_queue: Queue[str] = Queue()
        self.log_elements: dict = {}  # Maps log element to its timer
        self._lock = Lock()
        self._max_messages_per_poll = 50
        self._history: list[str] = []
        self._max_history = 500

    def register_log_with_polling(self, log_element, interval: float = 0.1):
        """
        Register a ui.log element and create a dedicated timer for it.

        Each timer polls the shared queue and broadcasts to ALL log elements.
        This ensures all sessions see the same output even if only one timer
        fires (in multi-session scenarios).

        Returns:
            The timer object for cleanup by caller.
        """
        timer = ui.timer(interval, self._poll_and_broadcast)
        self.log_elements[log_element] = timer
        return timer

    def register_log(self, log_element):
        """Register a ui.log element (deprecated - use register_log_with_polling)."""
        if log_element not in self.log_elements:
            self.log_elements[log_element] = None

    def unregister_log(self, log_element):
        """Unregister a ui.log element and cancel its timer."""
        if log_element in self.log_elements:
            timer = self.log_elements[log_element]
            if timer:
                try:
                    timer.cancel()
                except Exception:
                    pass
            del self.log_elements[log_element]

    def start_polling(self, interval: float = 0.1):
        """Deprecated no-op. Use register_log_with_polling instead."""
        pass

    def stop_polling(self):
        """Deprecated no-op."""
        pass

    def _poll_and_broadcast(self):
        """Poll message queue and broadcast to ALL log elements."""
        messages = []
        with self._lock:
            for _ in range(self._max_messages_per_poll):
                try:
                    msg = self.message_queue.get_nowait()
                    messages.append(msg)
                except Empty:
                    break

        if messages:
            for log_element in list(self.log_elements.keys()):
                try:
                    for msg in messages:
                        log_element.push(msg)
                except Exception:
                    self.unregister_log(log_element)

    def write(self, message: str):
        """Queue a message for display (thread-safe)."""
        if message.strip():
            self.message_queue.put(message.rstrip())
            self._history.append(message.rstrip())
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def get_history_text(self) -> str:
        """Get all history as text for copying."""
        return "\n".join(self._history)

    def clear_history(self):
        """Clear the history buffer."""
        self._history.clear()

    def clear(self):
        """Clear the message queue."""
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except Empty:
                break


# Module-level instance — accessible from any thread without DI context.
_bridge = ConsoleBridge()


def get_bridge() -> ConsoleBridge:
    """Return the shared ConsoleBridge instance."""
    return _bridge


def console_print(*args, **kwargs):
    """
    Print to the NiceGUI console (thread-safe).

    Can be called from any thread, including node execution threads.

    Usage:
        from haywire.ui.console_bridge import console_print
        console_print("Value:", 42)
    """
    message = " ".join(str(arg) for arg in args)
    _bridge.write(message)
