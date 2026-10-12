"""The ``WriteGate`` protocol: what a widget or a settings form asks before a user's write lands."""

from typing import Protocol


class WriteGate(Protocol):
    """Decides whether a user's edit may be written, and hears about each one that was.

    A ``BaseWidget`` with a gate asks ``allows()`` at every write and shows the
    model's value again when it refuses; ``render_settings`` does the same for
    each row it draws. Disabling the element is only the look: the gate is what
    refuses.

    Example::

        class ReadOnlyWhileRunning:
            def __init__(self, entry):
                self._entry = entry

            def allows(self) -> bool:
                return not self._entry.is_executing

            def written(self) -> None:
                self._entry.unsaved = True

        widget.write_gate = ReadOnlyWhileRunning(entry)
        render_settings(ctx, bag, gate=ReadOnlyWhileRunning(entry))
    """

    def allows(self) -> bool:
        """Return whether a write may land now.

        Called at every write, so the answer may change between two writes.
        """
        ...

    def written(self) -> None:
        """Called once after each write ``allows()`` let through."""
        ...
