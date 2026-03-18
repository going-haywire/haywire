"""
Editor - High-level graph manipulation interface with simple callback notifications

This class provides a clean, semantic API for graph operations while using
simple callbacks for change notifications. It wraps the graph, history manager,
and node factory to provide convenient methods for graph manipulation.

Design Philosophy:
- Simple callback-based notifications for graph changes (upstream: graph → UI)
- Complex event system remains for UI interactions (downstream: UI → graph)
- Clean separation between business logic and presentation layer
"""

from typing import Dict, List, Optional, Tuple, Set, Any, Callable
from haywire.core.graph.base import BaseGraph
from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.node.factory import NodeFactory
from haywire.core.undo.interfaces import IHistoryManager
from haywire.core.undo.history_manager import HistoryManager
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.actions.graph_actions import (
    AddNodeAction,
    MoveNodesAction,
    RemoveElementsAction,
    AddEdgeAction,
)

class Editor:
    """
    High-level editor interface with simple callback-based change notifications.
    
    This class provides semantic methods for graph operations and abstracts away
    the complexity of managing the graph, history, and node factory together.
    Uses simple callbacks for change notifications rather than complex events.
    """
    
    def __init__(
        self,
        graph: BaseGraph,
        node_factory: NodeFactory,
        undo_config: Optional[UndoConfig] = None,
    ):
        """
        Initialize the editor with core components.

        Args:
            graph:        The graph instance to manipulate.
            node_factory: Factory for looking up and subscribing to node classes.
            undo_config:  Optional undo configuration. Defaults to UndoConfig().
        """
        self.graph: BaseGraph = graph
        self.history_manager: IHistoryManager = HistoryManager(undo_config or UndoConfig())
        self._node_factory = node_factory
    
    # =============================================================================
    # NODE OPERATIONS
    # =============================================================================
    
    def create_wrapper(
        self, 
        registry_key: str, 
        position: Tuple[float, float] = (100, 100)
    ) -> Optional[NodeWrapper]:
        """
        Create a new node wrapper of the specified type at the given position.
        
        Args:
            registry_key: Registry key for the node type to create
            position: (x, y) position for the node
            
        Returns:
            The created node wrapper or None if creation failed
        """
        try:
            # Create and execute undo action
            action = AddNodeAction(
                graph=self.graph, 
                registry_key=registry_key, 
                position=position
            )
            self.history_manager.add_action(action)

            print(f"✅ Editor: Created node of type {registry_key} at {position}")
                       
            return action.wrapper
            
        except Exception as e:
            print(f"❌ Editor: Error creating node of type {registry_key}: {e}")
            return None

    
    def move_nodes(self, nodes: List[str], deltaX: float, deltaY: float) -> bool:
        """
        Move multiple nodes by delta amounts.
        
        Args:
            nodes: List of node IDs to move
            deltaX: Delta X amount to move all nodes
            deltaY: Delta Y amount to move all nodes
            
        Returns:
            True if nodes were moved, False otherwise
        """
        if not nodes:
            return False
                
        try:
            # Create and execute delta move action
            action = MoveNodesAction(self.graph, nodes, deltaX, deltaY)
            self.history_manager.add_action(action)
                        
            print(f"✅ Editor: Moved {len(nodes)} nodes by delta ({deltaX}, {deltaY})")
            return True
            
        except Exception as e:
            print(f"❌ Editor: Error moving nodes by delta: {e}")
            return False
    
    def remove_elements(self, nodes: List[str] = None, edges: List[str] = None) -> bool:
        """
        Remove multiple nodes and connections in a single operation.
        
        Args:
            nodes: List of node IDs to remove
            connections: List of connection UUIDs to remove
            
        Returns:
            True if elements were removed, False otherwise
        """
        nodes = nodes or []
        edges = edges or []
        
        if not nodes and not edges:
            return False
        
        # Validate nodes exist
        missing_nodes = [node_id for node_id in nodes if node_id not in self.graph.node_wrappers]
        if missing_nodes:
            print(f"⚠️ Editor: Nodes not found for removal: {missing_nodes}")
            return False
        
        # Validate connections exist
        missing_edges = [
            conn_id for conn_id in edges 
            if not self.graph.get_edge_wrapper(conn_id)
        ]
        if missing_edges:
            print(f"⚠️ Editor: Connections not found for removal: {missing_edges}")
            return False
        
        try:
            # Create and execute remove elements action
            action = RemoveElementsAction(self.graph, nodes, edges)
            self.history_manager.add_action(action)
                        
            total_count = len(nodes) + len(edges)
            print(
                f"✅ Editor: Removed {total_count} elements "
                f"({len(nodes)} nodes, {len(edges)} connections)"
            )
            return True
            
        except Exception as e:
            print(f"❌ Editor: Error removing elements: {e}")
            return False
    
    def get_node_wrapper(self, node_id: str) -> Optional[NodeWrapper]:
        """Get a node wrapper by ID."""
        return self.graph.get_node_wrapper(node_id)
        
    def list_node_wrappers(self) -> List[NodeWrapper]:
        """Get a list of all node wrappers in the graph."""
        return list(self.graph.node_wrappers.values())
    
    def get_available_node_regkeys(self) -> List[str]:
        """Get a list of all available node types from the factory."""
        return self._node_factory.node_registry.list_names()

    # =============================================================================
    # CONNECTION OPERATIONS
    # =============================================================================
    
    def create_edge(
        self, 
        source_node_id: str, 
        outlet_pin: str, 
        sink_node_id: str, 
        inlet_pin: str
    ) -> bool:
        """
        Create a connection between two nodes.
        
        Args:
            source_node_id: ID of the source node
            outlet_pin: Name of the output pin
            sink_node_id: ID of the sink node  
            inlet_pin: Name of the input pin
            
        Returns:
            True if connection was created, False otherwise
        """
        try:
            # Create and execute action using graph-managed pattern
            action = AddEdgeAction(
                graph=self.graph,
                source_node_id=source_node_id,
                outlet_pin_id=outlet_pin,
                sink_node_id=sink_node_id,
                inlet_pin_id=inlet_pin
            )
            self.history_manager.add_action(action)
                       
            print(
                f"✅ Editor: Created connection {source_node_id}:{outlet_pin} -> "
                f"{sink_node_id}:{inlet_pin}"
            )
            return True
            
        except Exception as e:
            print(f"❌ Editor: Error creating connection: {e}")
            return False
    
    def list_edges(self) -> List[EdgeWrapper]:
        """Get a list of all connections in the graph."""
        return list(self.graph.edge_wrappers.values())
    
    # =============================================================================
    # HISTORY OPERATIONS
    # =============================================================================
    
    def undo(self) -> bool:
        """Perform an undo operation. Returns True if undo was performed."""
        if self.history_manager.can_undo():
            try:
                result = self.history_manager.undo()
                if result:
                    print("✅ Editor: Undo performed")
                return result
            except Exception as e:
                print(f"❌ Editor: Error during undo: {e}")
                return False
        print("⚠️ Editor: Nothing to undo")
        return False

    def redo(self) -> bool:
        """Perform a redo operation. Returns True if redo was performed."""
        if self.history_manager.can_redo():
            try:
                result = self.history_manager.redo()
                if result:
                    print("✅ Editor: Redo performed")
                return result
            except Exception as e:
                print(f"❌ Editor: Error during redo: {e}")
                return False
        print("⚠️ Editor: Nothing to redo")
        return False

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self.history_manager.can_undo()

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self.history_manager.can_redo()

    def add_fence(self) -> None:
        """Add a fence to group operations."""
        self.history_manager.add_fence()
    
    # =============================================================================
    # GRAPH STATE
    # =============================================================================
    
    def get_graph_info(self) -> Dict[str, Any]:
        """Get information about the current graph state."""
        return {
            'graph_id': self.graph.graph_id,
            'node_count': len(self.graph.node_wrappers),
            'edge_count': len(self.graph.edge_wrappers),
            'can_undo': self.can_undo(),
            'can_redo': self.can_redo(),
            'history_size': len(self.history_manager.history),
            'current_history_index': self.history_manager.current_index,
        }

    def is_valid(self) -> bool:
        """Check if the editor is in a valid state."""
        return self.graph is not None