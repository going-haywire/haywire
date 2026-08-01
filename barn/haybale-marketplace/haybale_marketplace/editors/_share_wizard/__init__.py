"""Share Project wizard — a stepper over :class:`SharePipeline`.

The state machine (:class:`ShareWizard`, in ``_state.py``) is deliberately
free of NiceGUI calls: every ``advance_from_*`` method drives the pipeline
and updates ``step`` / ``error`` / ``warnings``, and the render functions
(``chrome.py``, ``panels.py``) read that state. That split is what makes the
flow testable without a browser.

Failure posture mirrors the pipeline's: a failed step stays put with an
inline error and is retryable in place. Nothing is rolled back, because
nothing was mutated past the point of failure — every precondition is
checkable without mutation.
"""

from __future__ import annotations

from .chrome import show_share_wizard
from .copy import _DRIFT_EXPLANATIONS, _DRIFT_OPTIONS, STEPS
from ._state import ShareWizard

__all__ = [
    "STEPS",
    "ShareWizard",
    "_DRIFT_EXPLANATIONS",
    "_DRIFT_OPTIONS",
    "show_share_wizard",
]
