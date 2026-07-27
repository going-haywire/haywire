"""
Tees process stdout to the real stream and any number of registered line sinks.

Installed once, process-wide, before ui.run(), so every print() fans out to
whichever UI panels choose to listen. This module stays UI-framework-agnostic —
no nicegui import. Timers and ui.log elements are the caller's business, not
the tee's.
"""

from __future__ import annotations

import sys
import threading
from typing import Callable, TextIO


class StdoutTee:
    """Tees sys.stdout to the real stream AND to registered line sinks.

    Installed once, process-wide, before ui.run(). Sinks are called on whatever
    thread did the printing — a sink MUST NOT touch NiceGUI elements directly.

    NOTE: only sys.stdout is wrapped. Wrapping stderr would loop, because
    logging's default StreamHandler writes there. NOTE: with reload=True this
    would need reinstalling in the reloader child; the studio uses reload=False.
    """

    _MAX_HISTORY = 500

    def __init__(self, real: TextIO):
        self._real = real
        self._partial = ""
        self._lock = threading.Lock()
        self._sinks: list[Callable[[str], None]] = []
        self._guard = threading.local()
        self._history: list[str] = []

    def write(self, s: str) -> int:
        n = self._real.write(s)  # studio.log / terminal first, always
        if getattr(self._guard, "busy", False):
            return n  # a sink that prints must not recurse
        self._guard.busy = True
        try:
            with self._lock:
                self._partial += s
                *lines, self._partial = self._partial.split("\n")
                for line in lines:
                    self._history.append(line)
                    if len(self._history) > self._MAX_HISTORY:
                        self._history.pop(0)
                sinks = list(self._sinks)
            for line in lines:
                for sink in sinks:
                    try:
                        sink(line)
                    except Exception:
                        pass  # a broken sink never breaks print()
        finally:
            self._guard.busy = False
        return n

    def flush(self) -> None:
        self._real.flush()

    def isatty(self) -> bool:
        return self._real.isatty()

    def fileno(self) -> int:
        return self._real.fileno()

    def writable(self) -> bool:
        return True

    @property
    def encoding(self) -> str:
        return self._real.encoding

    def add_sink(self, sink: Callable[[str], None]) -> Callable[[], None]:
        """Register a line sink. Returns a detach callable for cleanup()."""
        with self._lock:
            self._sinks.append(sink)

        def detach() -> None:
            with self._lock:
                if sink in self._sinks:
                    self._sinks.remove(sink)

        return detach

    def install(self) -> None:
        """Swap self into sys.stdout. Idempotent — a second call is a no-op."""
        if isinstance(sys.stdout, StdoutTee):
            return
        sys.stdout = self  # type: ignore[assignment]

    def get_history_text(self) -> str:
        """Return buffered stdout lines as text, for seeding a freshly-opened panel."""
        with self._lock:
            return "\n".join(self._history)

    def clear_history(self) -> None:
        """Clear the stdout history buffer."""
        with self._lock:
            self._history.clear()


# Module-level instance — accessible from any thread without DI context.
_tee = StdoutTee(sys.stdout)


def get_stdout_tee() -> StdoutTee:
    """Return the shared StdoutTee instance."""
    return _tee


def console_print(*args, **kwargs) -> None:
    """
    Print to the studio log panel (thread-safe).

    Can be called from any thread, including node execution threads.

    Usage:
        from haywire.ui.console_bridge import console_print
        console_print("Value:", 42)
    """
    print(*args, **kwargs)
