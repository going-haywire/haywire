"""
Haywire Assembly System

This module provides the assembly system for converting graphs into
executable flows.

Main Components:
- FlowAssemblyManager: Main coordinator for assembly
- ControlFlowBuilder: Builds control flow navigation graphs
- DataFlowBuilder: Builds localized data flows for control nodes

Usage:
    from haywire.core.assembly import FlowAssemblyManager
    
    # Create assembly manager
    assembly_manager = FlowAssemblyManager()
    
    # Assemble graph
    flows = assembly_manager.assemble_graph(my_graph)
    
    # Access assembled flows
    for flow in flows:
        print(f"Flow: {flow.flow_id}, Event: {flow.event_subscription}")
"""

from haywire.core.assembly.flow_assembly_manager import (
    FlowAssemblyManager,
    AssemblyMetadata
)
from haywire.core.assembly.control_flow_builder import ControlFlowBuilder
from haywire.core.assembly.data_flow_builder import DataFlowBuilder

__all__ = [
    'FlowAssemblyManager',
    'AssemblyMetadata',
    'ControlFlowBuilder',
    'DataFlowBuilder',
]