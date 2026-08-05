"""Stepper component — a linear multi-step flow rendered in a popup.

The shape: each step reads and reports, the user confirms, the next step acts.
Only the last step mutates, so abandoning the flow earlier leaves nothing
behind. Blocking work runs in a thread with the step's button in a loading
state, so the wait is always attributed to the step that owns it.

Usage: subclass :class:`StepFlow` with ``STEPS``/``STEP_TITLES`` and one
``advance_from_<step>`` coroutine each, write one panel function per step,
then hand both to :func:`show_step_flow`.
"""

from .async_helpers import advance, busy_advance
from .chrome import (
    ErrorDetail,
    FlowT,
    Panel,
    render_error,
    render_progress,
    render_warnings,
    show_step_flow,
)
from .flow import StepFlow

__all__ = [
    "ErrorDetail",
    "FlowT",
    "Panel",
    "StepFlow",
    "advance",
    "busy_advance",
    "render_error",
    "render_progress",
    "render_warnings",
    "show_step_flow",
]
