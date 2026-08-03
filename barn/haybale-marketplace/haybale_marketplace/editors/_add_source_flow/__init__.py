"""Add Source flow — a stepper over the marketplace subscription path.

The state machine (:class:`AddSourceFlow`, in ``_state.py``) is free of
NiceGUI calls, so the flow is testable without a browser.

Nothing is written until the user has seen what the source offers and settled
any name collisions. That inverts the old dialog, which subscribed first and
asked afterwards — so cancelling its conflict prompt left a live subscription
behind, and an unreachable source was subscribed anyway.
"""

from __future__ import annotations

from ._state import AddSourceFlow, AddSourceTarget
from .chrome import MarketplaceAddSourceTarget, build_target, show_add_source_flow
from .copy import STEPS

__all__ = [
    "STEPS",
    "AddSourceFlow",
    "AddSourceTarget",
    "MarketplaceAddSourceTarget",
    "build_target",
    "show_add_source_flow",
]
