"""New Node flow — a stepper over the node-authoring pipeline.

The state machine (:class:`NewNodeFlow`, in ``_state.py``) is free of NiceGUI
calls: every ``advance_from_*`` does one step's work and updates ``step`` /
``error``, and the render functions (``chrome.py``, ``panels.py``) read that
state, so the flow is testable without a browser.

Only the planned step's Create writes. Source, details and plan read, so a
user who opens the flow, reads the generated source and closes it has
changed nothing.
"""

from __future__ import annotations

from ._state import NewNodeFlow, NewNodeHost
from .chrome import EditorNewNodeHost, new_node_flow, show_new_node_flow
from .copy import STEPS

__all__ = [
    "STEPS",
    "EditorNewNodeHost",
    "NewNodeFlow",
    "NewNodeHost",
    "new_node_flow",
    "show_new_node_flow",
]
