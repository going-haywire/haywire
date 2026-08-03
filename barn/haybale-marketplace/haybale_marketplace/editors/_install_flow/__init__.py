"""Install / Update Library flow — a stepper over LibraryManager.install.

One flow for both operations: an update is an install with a different
``install_spec``. The state machine (:class:`InstallFlow`, in ``_state.py``)
is free of NiceGUI calls, so the flow is testable without a browser.

Only the installing step mutates. The resolve step before it runs
``uv pip install --dry-run`` and shows what would change; its result is
carried into the install so uv resolves once and the eviction set acted on is
the one the user approved.
"""

from __future__ import annotations

from ._state import InstallFlow, InstallSource
from .chrome import ManagerInstallSource, show_install_flow
from .copy import STEPS

__all__ = [
    "STEPS",
    "InstallFlow",
    "InstallSource",
    "ManagerInstallSource",
    "show_install_flow",
]
