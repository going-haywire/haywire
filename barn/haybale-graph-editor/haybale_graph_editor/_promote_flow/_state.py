"""The Promote to Macro flow's state machine, free of NiceGUI calls.

Three steps, of which only the second mutates:

    name      the macro's name and the library to write it into   -> Plan
    planned   the file that would be written, and any refusal     -> Promote
    promoted  terminal

The plan step is read-only by construction: ``plan_promotion`` answers what
would be written and why it might be refused without touching disk, which is
what a stepper needs (``.insights/project_stepper_flows.md``). A user who
opens the flow, sees the path, and closes it has changed nothing.

The promote step does three things that are one operation, not three: it
writes the file, registers it so the key resolves immediately, and swaps the
Group's card for a placement. There is no honest place to stop in between — a
written-but-unregistered macro is invisible, and a registered one with the
Group still on the canvas is a duplicate of itself.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Protocol

from haywire.core.macro.promote import PromotableSubgraph
from haywire.ui.components.popup import Popup
from haywire.ui.components.stepper import StepFlow

from .copy import STEP_TITLES, STEPS

if TYPE_CHECKING:
    from haywire.core.macro.promote import PromotionPlan, PromotionTarget

logger = logging.getLogger(__name__)


class PromoteSource(Protocol):
    """The slice of the editor this flow drives.

    Narrowed to a protocol so the flow depends on two calls rather than on the
    canvas and everything it carries, which also lets the tests drive it
    without a browser or a session.
    """

    def register_macro_file(self, path: Path, library_id: str) -> str | None:
        """Register a newly written macro and return its registry key."""
        ...

    def swap_card_for_placement(self, node_id: str, registry_key: str) -> tuple[str | None, str | None]:
        """Replace the Group's card with a placement. Returns ``(id, refusal)``."""
        ...


class PromoteFlow(StepFlow):
    """Linear, resumable state machine for the Promote to Macro flow."""

    STEPS = STEPS
    STEP_TITLES = STEP_TITLES

    def __init__(
        self,
        *,
        source: PromoteSource,
        definition: PromotableSubgraph,
        node_id: str,
        targets: list["PromotionTarget"],
        name: str = "",
        popup: Optional[Popup] = None,
    ) -> None:
        super().__init__()
        self.source = source
        self.definition = definition
        self.node_id = node_id
        self.targets = targets
        self.popup = popup

        # The dialog must open with something valid in the field, whatever the
        # Group is called.
        from haywire.core.macro.promote import suggest_name

        self.name: str = name or suggest_name(definition.label or "")
        self.target: "PromotionTarget | None" = targets[0] if targets else None

        self.plan: "PromotionPlan | None" = None
        self.registry_key: str | None = None
        self.placement_node_id: str | None = None

    @property
    def name_refusal(self) -> str | None:
        """Why the current name cannot be used, or ``None``. For live validation."""
        from haywire.core.macro.promote import name_refusal

        return name_refusal(self.name)

    @property
    def can_plan(self) -> bool:
        """Whether the name and target are both usable."""
        return self.target is not None and self.name_refusal is None

    async def advance_from_name(self) -> None:
        """Describe the file that would be written. Read-only.

        A refusal is carried on the plan rather than raised: the planned step
        renders it beside the path, so the user sees what was going to happen
        and why it will not.
        """
        self.retry()
        if self.target is None:
            self.error = "No library in this project can receive a macro."
            return

        from haywire.core.macro.promote import plan_promotion

        try:
            self.plan = plan_promotion(
                self.definition,
                name=self.name,
                macros_folder=self.target.folder,
            )
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        self.step = "planned"

    async def advance_from_planned(self) -> None:
        """Write the file, register it, and swap the card. The mutating step."""
        self.retry()
        plan = self.plan
        target = self.target
        if plan is None or target is None:  # pragma: no cover — unreachable via the flow
            self.error = "Nothing planned to promote."
            return
        if plan.refusal is not None:
            self.error = plan.refusal
            return

        from haywire.core.macro.promote import write_macro_file

        try:
            # The write touches disk; the registration parses the document
            # back and validates it. Both off the event loop.
            path = await asyncio.to_thread(write_macro_file, plan)
            registry_key = await asyncio.to_thread(self.source.register_macro_file, path, target.library_id)
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return

        if not registry_key:
            # The file is on disk but the registry refused it — almost always
            # containment the plan could not see. Say so rather than swapping
            # the card for a placement of a macro that does not resolve.
            self.error = (
                f"'{plan.path.name}' was written, but {target.label} would not register it. "
                f"The file is on disk; the Group is unchanged."
            )
            return

        self.registry_key = registry_key
        placement_id, refusal = self.source.swap_card_for_placement(self.node_id, registry_key)
        if refusal is not None:
            self.error = refusal
            return

        self.placement_node_id = placement_id
        self.step = "promoted"
