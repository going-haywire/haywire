"""Uninstall Library flow — a stepper over LibraryManager.uninstall_streaming.

The state machine (:class:`UninstallFlow`, in ``_state.py``) is deliberately
free of NiceGUI calls: every ``advance_from_*`` method does one step's work
and updates ``step`` / ``error`` / ``warnings``, and the render functions
(``chrome.py``, ``panels.py``) read that state. That split is what makes the
flow testable without a browser.

Only the confirm step mutates. The two steps before it read — graph usage and
pip reverse-dependencies — so a user who opens the flow, sees what the removal
would affect, and closes it has changed nothing.
"""

from __future__ import annotations

from ._state import UninstallFlow, UninstallSource
from .chrome import show_uninstall_flow
from .copy import STEPS

__all__ = [
    "STEPS",
    "UninstallFlow",
    "UninstallSource",
    "show_uninstall_flow",
]
