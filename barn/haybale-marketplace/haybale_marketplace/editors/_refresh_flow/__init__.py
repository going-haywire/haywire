"""Refresh Libraries flow — a stepper over the marketstall refresh pipeline.

The state machine (:class:`RefreshFlow`, in ``_state.py``) is deliberately
free of NiceGUI calls: every ``advance_from_*`` method drives one pipeline
phase and updates ``step`` / ``error`` / ``warnings``, and the render
functions (``chrome.py``, ``panels.py``) read that state. That split is what
makes the flow testable without a browser.

The three phases map one-to-one onto the steps, and only the last one writes:
fetching and resolving are read-only, so the user sees what a refresh would
change before deciding to apply it. Abandoning the flow before Apply leaves
the project cache untouched.
"""

from __future__ import annotations

from ._state import RefreshFlow
from .chrome import show_refresh_flow
from .copy import STEPS

__all__ = [
    "STEPS",
    "RefreshFlow",
    "show_refresh_flow",
]
