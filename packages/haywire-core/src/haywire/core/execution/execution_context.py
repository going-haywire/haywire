from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from haywire.barn.builtin.delivery import BacklogSettings
    from haywire.core.execution.event_source import Trigger
    from haywire.core.execution.vm import HaywireVM
    from haywire.core.node import BaseNode
    from haywire.core.state.data_namespace import AppDataNamespace

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExecutionContext:
    """
    Context passed to worker functions during execution.

    Contains all data needed by worker functions:
    - Global context (from external system)
    - Local context (graph variables)
    - Current trigger
    - Callback emission function
    """

    global_ctx: dict[str, Any]
    """Global context from external system"""
    local_ctx: dict[str, Any]
    """Local context (graph variables)"""
    trigger: Trigger | None = None
    """Current trigger that activated this flow (None when no specific trigger)"""
    control_pin: str | None = None
    """ID of control inlet that was triggered (for control nodes)"""
    node: BaseNode | None = None
    """Current node being executed"""
    vm: HaywireVM | None = None
    """Reference to VM for callback emission"""
    frame_number: int = 0
    """Current frame number"""
    exec_count: int = 0
    """Current node execution count for this flow and frame"""
    app_data: AppDataNamespace | None = None
    """Typed proxy to the app's LibraryStateContainer for AppState lookups.
    None if the VM was constructed without a container reference (test
    contexts only). ExecutionContext does not have a `data` (SessionState)
    namespace because graphs run app-globally — the VM has no notion of
    which UI session triggered execution."""
    cancel: threading.Event | None = None
    """Set when a stop that timed out kills the run: the frame ends at its next control node.
    ``None`` outside an execution group's frame."""
    failures: list[tuple[BaseNode, Exception]] = field(default_factory=list)
    """This frame's worker exceptions, in order, each with the node that raised it (ADR 0066)."""
    bail: str | None = None
    """Set by the VM when a worker raises: how far this frame bails (``run``, ``frame``, ``branch``)."""

    def emit_callback(
        self,
        event_name: str | Sequence[str],
        payload: dict[str, Any] | None = None,
        backlog: BacklogSettings | None = None,
    ) -> None:
        """
        Emit a callback to trigger other flows.

        Pass all of an emitter's subscriber names in one call: listeners whose
        Delivery is Pooled then share the callback (ADR 0097).

        Args:
            event_name: Name of callback event, or the names of all the emitter's subscribers
            payload: Optional data to pass
            backlog: The emitter's ``BacklogSettings``, where callbacks wait while every
                pooled listener is busy; ``None`` holds 16 and drops the oldest.

        Example::

            # One listener by name.
            context.emit_callback(event_name="my_callback", payload={"value": 1})
            # Every subscriber of the emitter in one emit, with its backlog.
            names = list(self.value("callbacks").values())
            context.emit_callback(event_name=names, payload={"value": 1}, backlog=self.backlog)
        """
        if self.vm:
            self.vm.emit_callback(event_name, payload, backlog)
        else:
            logger.warning("Cannot emit callback: No VM reference in context")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for worker function compatibility"""
        return {
            "global": self.global_ctx,
            "local": self.local_ctx,
            "trigger": self.trigger,
            "control_pin": self.control_pin,
            "node": self.node,
            "emit_callback": self.emit_callback,
        }
