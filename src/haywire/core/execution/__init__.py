"""
Haywire Execution System

This module provides the runtime execution system for Haywire graphs.

Main Components:
- Interpreter: Main coordinator for graph execution
- HaywireVM: Virtual machine for executing flows
- Flow: Executable representation of graph flows
- Scheduler: Per-flow execution scheduler
- Event Sources: System, External, and Callback events
- Callback Manager: Inter-flow communication

Usage:
    from haywire.core.execution import Interpreter
    from haywire.core.execution.event_source import SystemEventType
    
    # Create interpreter
    interpreter = Interpreter()
    
    # Load graph
    interpreter.load_graph(my_graph)
    
    # Dispatch events
    interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
    
    # Wait and cleanup
    interpreter.wait_all()
    interpreter.shutdown()
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.execution.interpreter import Interpreter
from haywire.core.execution.vm import HaywireVM
from haywire.core.execution.flow import (
    Flow,
    ControlFlowGraph,
    ControlNodeInfo,
    LocalizedDataFlow
)
from haywire.core.execution.scheduler import FlowScheduler, QueueMode
from haywire.core.execution.event_source import (
    EventSource,
    SystemEvent,
    SystemEventType,
    ExternalEvent,
    CallbackEvent,
    Trigger
)
from haywire.core.execution.callback_manager import CallbackManager

__all__ = [
    # Main interface
    'Interpreter',
    
    # Core components
    'HaywireVM',
    'ExecutionContext',
    'Flow',
    'FlowScheduler',
    'QueueMode',
    'CallbackManager',
    
    # Flow structures
    'ControlFlowGraph',
    'ControlNodeInfo',
    'LocalizedDataFlow',
    
    # Event sources
    'EventSource',
    'SystemEvent',
    'SystemEventType',
    'ExternalEvent',
    'CallbackEvent',
    'Trigger',
]