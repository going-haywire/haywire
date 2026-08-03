"""The Uninstall Library flow's state machine, free of NiceGUI calls.

Four steps, of which only the third mutates:

    selected  what is about to be removed, and how it was installed  -> Check
    impact    graphs that use it, pip packages that need it          -> Continue
    confirm   the destructive step                                   -> Uninstall
    removed   terminal

The impact step never blocks. Direct ``@library`` dependents are already a
hard gate on the Uninstall button upstream (see LibraryOverviewEditor), so by
the time this flow opens that class of breakage is impossible. What remains —
graph usage and pip reverse-dependencies — is the user's call about their own
venv, so it is shown plainly and confirmed explicitly rather than forbidden.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional, Protocol

from haywire.ui.components.popup import Popup
from haywire.ui.components.stepper import StepFlow

from haybale_marketplace.uninstall_impact import (
    UninstallImpact,
    find_graph_usage,
    find_pip_dependents,
)

from .copy import STEP_TITLES, STEPS

logger = logging.getLogger(__name__)


class UninstallSource(Protocol):
    """The slice of :class:`LibraryManager` this flow drives.

    Narrowed to a protocol so the flow depends on three methods rather than on
    the manager and everything it carries (registry, venv detection, DI) —
    which also lets the tests drive it without a library system.
    """

    def get_library_distribution_name(self, library_id: str) -> str | None: ...

    def get_library_install_type(self, library_id: str) -> str: ...

    async def uninstall_streaming(self, library_id: str, on_output) -> tuple[bool, str, object]: ...


class UninstallFlow(StepFlow):
    """Linear, resumable state machine for the Uninstall Library flow."""

    STEPS = STEPS
    STEP_TITLES = STEP_TITLES

    def __init__(
        self,
        *,
        source: UninstallSource,
        library_id: str,
        label: str,
        workspace_root: Optional[Path] = None,
        popup: Optional[Popup] = None,
    ) -> None:
        super().__init__()
        self.source = source
        self.library_id = library_id
        self.label = label
        self.workspace_root = workspace_root
        self.popup = popup

        self.impact: UninstallImpact | None = None
        self.succeeded: bool = False
        self.message: str = ""
        self.hints: object | None = None

    async def advance_from_selected(self) -> None:
        """Scan graphs and installed distributions. Read-only.

        Both scans walk the filesystem — the graph glob over a whole workspace
        and importlib.metadata over every installed distribution — so they run
        in a thread rather than starving NiceGUI's heartbeat.
        """
        self.retry()
        try:
            self.impact = await asyncio.to_thread(self._collect_impact)
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        self.step = "impact"

    def _collect_impact(self) -> UninstallImpact:
        """Blocking half of the impact step. Runs in a thread."""
        dist_name = self.source.get_library_distribution_name(self.library_id) or ""
        impact = UninstallImpact(
            library_id=self.library_id,
            dist_name=dist_name,
            install_type=self.source.get_library_install_type(self.library_id) or "",
        )
        if self.workspace_root is not None:
            impact.graphs = find_graph_usage(self.workspace_root, self.library_id)
        else:
            # No project open: say so rather than implying zero graphs use it.
            impact.graphs_scanned = False
        impact.pip_dependents = find_pip_dependents(dist_name)
        return impact

    async def advance_from_impact(self) -> None:
        """Move to the confirmation. Never blocks — see the module docstring."""
        self.retry()
        self.step = "confirm"

    async def advance_from_confirm(self) -> None:
        """Remove the library from the venv. The only step that mutates."""
        self.retry()
        try:
            success, message, hints = await self.source.uninstall_streaming(self.library_id, self.push_log)
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        self.succeeded = success
        self.message = message
        self.hints = hints
        if not success:
            # Stay on confirm so Retry re-runs the uninstall rather than
            # stranding the user on a "done" step that did nothing.
            self.error = message
            return
        impact = self.impact
        if impact is not None and impact.is_editable:
            self.warnings.append(
                f"{self.label} was an editable install — it is gone from the environment, "
                "but its source folder is still on disk."
            )
        self.step = "removed"
