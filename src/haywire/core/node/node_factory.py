"""
Pure Node Factory utility.

This factory is a utility class that creates node instances from registry keys.
It handles hot reloading support and node tracking but does not manage graph
lifecycle or undo operations - those are handled by Graph and Actions respectively.
"""

import time
import uuid
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass
from collections import defaultdict

from .node import BaseNode
from ..graph.graph import HaywireGraph
from ..inventory.registry.node import NodeRegistry


@dataclass
class NodeSnapshot:
    """
    Serializable snapshot of a node's state for cloning and hot reload recovery.
    
    This captures all the essential state needed to recreate a node
    in the same configuration.
    """
    node_id: str
    registry_key: str
    name: str
    
    # Position and UI state
    posX: float = 0.0
    posY: float = 0.0
    is_collapsed: bool = False
    is_condensed: bool = False
    custom_color: Optional[str] = None
    
    # Node configuration (would be expanded based on actual node structure)
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def from_node(cls, node: BaseNode) -> 'NodeSnapshot':
        """Create a snapshot from an existing node."""
        return cls(
            node_id=node.node_id,
            registry_key=node.identity.registry_key,
            name=node.identity.label,
            posX=node.ui_state.posX,
            posY=node.ui_state.posY,
            is_collapsed=node.ui_state.is_collapsed,
            is_condensed=node.ui_state.is_condensed,
            custom_color=node.ui_state.custom_color,
            metadata={}  # Would include more node-specific data
        )


class NodeFactory:
    """
    Pure node factory utility.
    
    This factory is a utility class that creates node instances from registry keys.
    It handles hot reload tracking but does not manage graph lifecycle or undo 
    operations - those are handled by Graph and Actions respectively.
    """
    
    def __init__(self, node_registry: NodeRegistry):
        """
        Initialize the node factory.
        
        Args:
            node_registry: Registry containing node class definitions
        """
        self.node_registry = node_registry
        
        # Track created nodes for hot reload support only
        self._active_nodes: Dict[str, BaseNode] = {}
        self._nodes_by_registry_key: Dict[str, set[str]] = defaultdict(set)
        self._node_registry_keys: Dict[str, str] = {}  # node_id -> registry_key
        
        # Hot reload notification callbacks
        self._hot_reload_listeners: List[Callable[[str, List[str]], None]] = []
        
        # Performance tracking
        self._creation_count = 0
        self._last_creation_time = time.time()
    
    def create_instance(self, registry_key: str, graph: HaywireGraph, 
                       node_id: Optional[str] = None, position: Optional[Tuple[float, float]] = None) -> BaseNode:
        """
        Pure utility method to create a node instance.
        
        This method only creates the node instance and tracks it for hot reload.
        It does not add the node to any graph or interact with undo systems.
        
        Args:
            registry_key: Key in the node registry
            graph: Parent graph for the node
            node_id: Optional custom node ID (generated if not provided)
            position: Optional (x, y) position for the node
            
        Returns:
            The created node instance
            
        Raises:
            ValueError: If registry key is not found or node creation fails
        """
        # Generate node ID if not provided
        if node_id is None:
            node_id = self._generate_node_id()
        
        # Get node class from registry
        error_info, node_class = self.node_registry.get_node_class(registry_key)
        if error_info is not None:
            raise ValueError(f"Failed to get node class '{registry_key}': {error_info}")
        
        # Create the node instance (registry_key now set by metaclass from class_identity)
        node = node_class(node_id, graph)
        
        # Set the library metadata from the class default
        if hasattr(node_class, '_default_library_metadata'):
            node.library = node_class._default_library_metadata
        
        if error_info:
            node.error_info = error_info
        
        # Set position if provided
        if position:
            node.ui_state.posX, node.ui_state.posY = position
        
        # Track the node for hot reload support
        self._track_node(node, registry_key)
        
        self._creation_count += 1
        self._last_creation_time = time.time()
        
        return node
    
    def untrack_node(self, node_id: str) -> bool:
        """
        Stop tracking a node (called when node is removed from graph).
        
        This method only handles the factory's internal tracking and does not
        remove the node from any graph - that should be done by the graph itself.
        
        Args:
            node_id: ID of the node to stop tracking
            
        Returns:
            True if node was being tracked, False if not found
        """
        if node_id not in self._active_nodes:
            return False
        
        # Untrack the node
        self._untrack_node(node_id)
        return True
    
    def clone_node(self, source_node: BaseNode, graph: HaywireGraph,
                   new_node_id: Optional[str] = None, offset: Optional[Tuple[float, float]] = None) -> BaseNode:
        """
        Clone an existing node instance.
        
        This creates a new node instance based on an existing one but does not
        add it to any graph - that should be done by the caller.
        
        Args:
            source_node: The node to clone
            graph: Target graph for the cloned node
            new_node_id: Optional ID for the cloned node
            offset: Optional (x, y) offset from source position
            
        Returns:
            The cloned node instance (not added to graph)
        """
        # Create snapshot and modify for clone
        snapshot = NodeSnapshot.from_node(source_node)
        
        if new_node_id:
            snapshot.node_id = new_node_id
        else:
            snapshot.node_id = self._generate_node_id()
        
        if offset:
            snapshot.posX += offset[0]
            snapshot.posY += offset[1]
        
        # Create the cloned node
        return self.create_node_from_snapshot(snapshot, graph)
    
    def create_node_from_snapshot(self, snapshot: NodeSnapshot, graph: HaywireGraph) -> BaseNode:
        """
        Create a node instance from a snapshot.
        
        This creates the node instance but does not add it to any graph -
        that should be done by the caller.
        
        Args:
            snapshot: The node snapshot to restore
            graph: Target graph for the node
            
        Returns:
            The restored node instance (not added to graph)
        """
        # Create the base node
        node = self.create_instance(
            snapshot.registry_key, 
            graph, 
            snapshot.node_id,
            (snapshot.posX, snapshot.posY)
        )
        
        # Restore additional state
        node.identity.name = snapshot.name
        node.ui_state.is_collapsed = snapshot.is_collapsed
        node.ui_state.is_condensed = snapshot.is_condensed
        node.ui_state.custom_color = snapshot.custom_color
        
        # Restore metadata
        for key, value in snapshot.metadata.items():
            if hasattr(node, key):
                setattr(node, key, value)
        
        return node
    
    def create_snapshot(self, node_id: str) -> Optional[NodeSnapshot]:
        """
        Create a snapshot of a node's current state.
        
        Args:
            node_id: ID of the node to snapshot
            
        Returns:
            Node snapshot or None if node not found
        """
        if node_id not in self._active_nodes:
            return None
        
        node = self._active_nodes[node_id]
        
        return NodeSnapshot.from_node(node)
    
    def get_nodes_by_registry_key(self, registry_key: str) -> List[BaseNode]:
        """
        Get all active nodes of a specific type.
        
        Args:
            registry_key: The registry key to filter by
            
        Returns:
            List of nodes matching the registry key
        """
        node_ids = self._nodes_by_registry_key.get(registry_key, set())
        return [self._active_nodes[node_id] for node_id in node_ids 
                if node_id in self._active_nodes]
    
    def handle_hot_reload(self, registry_key: str) -> List[str]:
        """
        Handle hot reload of a node class.
        
        This method is called when the node registry detects that a node class
        has been reloaded. It notifies listeners but does not modify existing
        node instances (as per the requirement to keep hot reload separate
        from undo history).
        
        Args:
            registry_key: The registry key that was reloaded
            
        Returns:
            List of node IDs that are affected by this reload
        """
        affected_node_ids = list(self._nodes_by_registry_key.get(registry_key, set()))
        
        # Notify listeners about the hot reload
        for listener in self._hot_reload_listeners:
            listener(registry_key, affected_node_ids)
        
        return affected_node_ids
    
    def add_hot_reload_listener(self, callback: Callable[[str, List[str]], None]) -> None:
        """
        Add a callback for hot reload notifications.
        
        Args:
            callback: Function called with (registry_key, affected_node_ids)
        """
        self._hot_reload_listeners.append(callback)
    
    def remove_hot_reload_listener(self, callback: Callable[[str, List[str]], None]) -> None:
        """
        Remove a hot reload notification callback.
        
        Args:
            callback: The callback to remove
        """
        if callback in self._hot_reload_listeners:
            self._hot_reload_listeners.remove(callback)
    
    # Private helper methods
    
    def _generate_node_id(self) -> str:
        """Generate a unique node ID."""
        return f"node_{uuid.uuid4().hex[:8]}"
    
    def _track_node(self, node: BaseNode, registry_key: str) -> None:
        """Track a node for management and hot reload."""
        self._active_nodes[node.node_id] = node
        self._nodes_by_registry_key[registry_key].add(node.node_id)
        self._node_registry_keys[node.node_id] = registry_key
    
    def _untrack_node(self, node_id: str) -> None:
        """Stop tracking a node."""
        if node_id in self._active_nodes:
            del self._active_nodes[node_id]
        
        if node_id in self._node_registry_keys:
            registry_key = self._node_registry_keys[node_id]
            self._nodes_by_registry_key[registry_key].discard(node_id)
            del self._node_registry_keys[node_id]
    
    # ============================================================================
    # Node Discovery and UI Services (moved from NodeRegistry)
    # ============================================================================
    
    def get_menu_structure(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get nodes organized by menu path for UI building.

        Returns:
            Dictionary mapping menu paths to lists of node info dicts
        """
        menu = {}

        for key in self.node_registry.list_names():
            node_class = self.node_registry.get(key)
            
            # Use class_identity if available, fallback to old attributes
            if hasattr(node_class, 'class_identity'):
                identity = node_class.class_identity
                menu_path = identity.menu
                label = identity.label
                description = identity.description
                tags = identity.search_tags
            else:
                menu_path = getattr(node_class, 'node_menu', 'misc')
                label = node_class._default_library_metadata.label
                description = node_class._default_library_metadata.description
                tags = getattr(node_class, 'node_search_tags', [])

            if menu_path not in menu:
                menu[menu_path] = []

            menu[menu_path].append({
                'label': label,           # Display name
                'key': key,               # Registry key
                'description': description,
                'tags': tags
            })

        return menu

    def search_nodes(self, query: str) -> List[Dict[str, str]]:
        """
        Search for nodes matching a query string.

        Args:
            query: Search query string

        Returns:
            List of matching node info dicts
        """
        results = []
        query_lower = query.lower()

        for key in self.node_registry.list_names():
            node_class = self.node_registry.get(key)

            # Use class_identity if available, fallback to old attributes
            if hasattr(node_class, 'class_identity'):
                identity = node_class.class_identity
                label = identity.label
                description = identity.description
                tags = identity.search_tags
            else:
                label = node_class._default_library_metadata.label
                description = node_class._default_library_metadata.description
                tags = getattr(node_class, 'node_search_tags', [])

            # Search in label, description, and tags
            searchable = [
                label.lower(),
                description.lower(),
                *[tag.lower() for tag in tags]
            ]

            if any(query_lower in text for text in searchable):
                metadata = self.node_registry.get_metadata(key)
                library_name = metadata.name if metadata else 'Unknown'
                
                results.append({
                    'label': label,
                    'key': key,
                    'description': description,
                    'library': library_name
                })

        return results

    def get_nodes_by_library(self, library_name: str) -> List[Dict[str, str]]:
        """
        Get all nodes from a specific library.

        Args:
            library_name: Name of the library

        Returns:
            List of node info dicts from the specified library
        """
        results = []

        for registry_key in self.node_registry.list_names():
            metadata = self.node_registry.get_metadata(registry_key)
            if metadata and metadata.name == library_name:
                node_class = self.node_registry.get(registry_key)
                
                # Use class_identity if available, fallback to old attributes
                if hasattr(node_class, 'class_identity'):
                    identity = node_class.class_identity
                    label = identity.label
                    description = identity.description
                else:
                    label = node_class._default_library_metadata.label
                    description = node_class._default_library_metadata.description
                
                results.append({
                    'label': label,
                    'key': registry_key,
                    'description': description
                })

        return results

    def list_all_nodes(self) -> List[str]:
        """
        Get list of all registered node registry keys.

        Returns:
            List of all registry keys
        """
        return self.node_registry.list_names()

    def get_node_info(self, registry_key: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific node.

        Args:
            registry_key: Registry key of the node

        Returns:
            Dictionary with node information or None if not found
        """
        if not self.node_registry.has(registry_key):
            return None
        
        node_class = self.node_registry.get(registry_key)
        metadata = self.node_registry.get_metadata(registry_key)
        
        # Use class_identity if available, fallback to old attributes
        if hasattr(node_class, 'class_identity'):
            identity = node_class.class_identity
            label = identity.label
            description = identity.description
            tags = identity.search_tags
            menu = identity.menu
        else:
            label = node_class._default_library_metadata.label
            description = node_class._default_library_metadata.description
            tags = getattr(node_class, 'node_search_tags', [])
            menu = getattr(node_class, 'node_menu', 'misc')
        
        return {
            'registry_key': registry_key,
            'label': label,
            'description': description,
            'search_tags': tags,
            'menu': menu,
            'library_name': metadata.name if metadata else None,
            'library_version': metadata.version if metadata else None,
            'class_name': node_class.__name__,
            'module': node_class.__module__
        }

    def get_factory_stats(self) -> Dict[str, Any]:
        """Get statistics about the factory state."""
        return {
            'active_nodes': len(self._active_nodes),
            'registry_keys': len(self._nodes_by_registry_key),
            'creation_count': self._creation_count,
            'last_creation_time': self._last_creation_time,
            'hot_reload_listeners': len(self._hot_reload_listeners)
        }
