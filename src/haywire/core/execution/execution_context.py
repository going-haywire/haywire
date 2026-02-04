from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from haywire.core.execution.event_source import Trigger
    from haywire.core.execution.vm import HaywireVM, logger
    from haywire.core.node.node_wrapper import NodeWrapper

@dataclass
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
    trigger: 'Trigger'
    """Current trigger that activated this flow"""
    control_pin: Optional[str] = None
    """ID of control inlet that was triggered (for control nodes)"""
    node_wrapper: Optional['NodeWrapper'] = None
    """Current node being executed"""
    vm: Optional['HaywireVM'] = None
    """Reference to VM for callback emission"""
    frame_number: Optional[int] = 0
    """Current frame number"""
    exec_count: Optional[int] = 0
    """Current node execution count for this flow and frame"""

    def emit_callback(self, event_name: str, payload: Optional[Dict] = None):
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
            'global': self.global_ctx,
            'local': self.local_ctx,
            'trigger': self.trigger,
            'control_pin': self.control_pin,
            'node': self.node_wrapper,
            'emit_callback': self.emit_callback
        }