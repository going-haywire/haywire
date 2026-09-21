"""Promote to Macro flow — a stepper over the promote pipeline.

The state machine (:class:`PromoteFlow`, in ``_state.py``) is free of NiceGUI
calls: every ``advance_from_*`` does one step's work and updates ``step`` /
``error``, and the render functions (``chrome.py``, ``panels.py``) read that
state. That split is what makes the flow testable without a browser.

Only the second step mutates. The name and plan steps read — the name rule,
the target folder, and what the document would contain — so a user who opens
the flow, sees the path, and closes it has changed nothing.
"""

from __future__ import annotations

from ._state import PromoteFlow, PromoteSource
from .chrome import EditorPromoteSource, show_promote_flow
from .copy import STEPS

__all__ = [
    "STEPS",
    "EditorPromoteSource",
    "PromoteFlow",
    "PromoteSource",
    "show_promote_flow",
]
