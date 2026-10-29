from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional
import logging
import threading

if TYPE_CHECKING:
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

    global_ctx: Dict[str, Any]
    """Global context from external system"""
    local_ctx: Dict[str, Any]
    """Local context (graph variables)"""
    trigger: Optional[Trigger] = None
    """Current trigger that activated this flow (None when no specific trigger)"""
    control_pin: Optional[str] = None
    """ID of control inlet that was triggered (for control nodes)"""
    node: Optional[BaseNode] = None
    """Current node being executed"""
    vm: Optional[HaywireVM] = None
    """Reference to VM for callback emission"""
    frame_number: int = 0
    """Current frame number"""
    exec_count: int = 0
    """Current node execution count for this flow and frame"""
    app_data: Optional[AppDataNamespace] = None
    """Typed proxy to the app's LibraryStateContainer for AppState lookups.
    None if the VM was constructed without a container reference (test
    contexts only). ExecutionContext does not have a `data` (SessionState)
    namespace because graphs run app-globally — the VM has no notion of
    which UI session triggered execution."""
    cancel: Optional[threading.Event] = None
    """Set when a stop that timed out kills the run: the frame ends at its next control node.
    ``None`` outside an execution group's frame."""

    def emit_callback(self, event_name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit a callback to trigger other flows.

        Args:
            event_name: Name of callback event
            payload: Optional data to pass
        """
        if self.vm:
            self.vm.emit_callback(event_name, payload)
        else:
            logger.warning("Cannot emit callback: No VM reference in context")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for worker function compatibility"""
        return {
            "global": self.global_ctx,
            "local": self.local_ctx,
            "trigger": self.trigger,
            "control_pin": self.control_pin,
            "node": self.node,
            "emit_callback": self.emit_callback,
        }
