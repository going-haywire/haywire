"""The step-flow state machine base, free of NiceGUI calls.

A :class:`StepFlow` subclass owns the transitions; the render helpers in
``chrome.py`` read the state it exposes. That split is what makes a flow
testable without a browser — the same posture the Share Project wizard
established.

Failure posture: a failed step stays put with an inline error and is
retryable in place. Nothing is rolled back, because a well-built flow does
not mutate until its final step — every precondition is checkable without
mutation, so the user can abandon a flow at any read-only step and leave
nothing behind.
"""

from __future__ import annotations

import logging
from typing import Callable, ClassVar, Optional, Sequence

from nicegui.elements.log import Log

logger = logging.getLogger(__name__)


class StepFlow:
    """Linear, resumable state machine for a multi-step UI flow.

    Subclasses declare :attr:`STEPS` and :attr:`STEP_TITLES` and implement one
    ``async def advance_from_<step>()`` per step. Each such method should:

      1. call :meth:`retry` first (clears the previous error),
      2. do its work — blocking calls belong in ``asyncio.to_thread`` so the
         NiceGUI heartbeat keeps running,
      3. call :meth:`fail` and return early on a known error type,
      4. set :attr:`step` to the next step only on success.

    The final entry in :attr:`STEPS` is the terminal step; the progress bar
    renders one segment per non-terminal step.
    """

    #: Ordered step names. The last one is terminal (no segment drawn for it).
    STEPS: ClassVar[Sequence[str]] = ()
    #: Human-readable title per step name, shown under the progress bar.
    STEP_TITLES: ClassVar[dict[str, str]] = {}

    def __init__(self) -> None:
        if not self.STEPS:
            raise ValueError(f"{type(self).__name__} must declare a non-empty STEPS")
        self.step: str = self.STEPS[0]
        self.error: str | None = None
        self.manual_command: str | None = None
        self.warnings: list[str] = []
        self.log_lines: list[str] = []

        self.on_render: Callable[[], None] | None = None
        self._log_element: Optional[Log] = None

    # ── state transitions ────────────────────────────────────────────────────

    def retry(self) -> None:
        """Clear the error so the current step can be attempted again.

        Warnings are kept deliberately: a warning describes a condition that a
        retry does not change (a stale lock file is still stale).
        """
        self.error = None
        self.manual_command = None

    def fail(self, exc: BaseException) -> None:
        """Record a failure without advancing. Keeps the user on the step."""
        logger.exception("%s step %r failed", type(self).__name__, self.step)
        self.error = str(exc)
        self.manual_command = getattr(exc, "manual_command", None)

    def push_log(self, line: str) -> None:
        """Collect a streamed output line, mirroring it into the log element.

        Modifying an existing element from a background task is always safe (no
        slot context needed) — see .insights/feedback_nicegui_async.md case 3 —
        so the log element is updated directly when one is attached.
        """
        self.log_lines.append(line)
        log = self._log_element
        if log is not None:
            log.push(line)

    def attach_log(self, log: Log) -> None:
        """Bind a ``ui.log`` element so :meth:`push_log` streams into it."""
        self._log_element = log
