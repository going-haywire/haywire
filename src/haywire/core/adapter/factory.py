"""
AdapterFactory - Creates adapter chains and manages hot reload.

This factory:
- Creates AdapterChain instances from type compatibility queries
- Handles compound types (ARRAY, MAP) with structural adapters
- Tracks which EdgeWrappers depend on which adapters
- Notifies EdgeWrappers when adapters are hot-reloaded
- Provides adapter discovery services
"""

from typing import Dict, List, Optional, Set, TYPE_CHECKING
import logging

from .base import PassThroughAdapter, ChainAdapter
from .chain import AdapterChain
from .meta import StructuralAdapter
from .registry import AdapterRegistry
from ..registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
    LiveCycleBatchCallback
)
from ..types.interface import IType
from ..types.base import CompoundType
from ..errors import HaywireException

if TYPE_CHECKING:
    from ..graph.edge_wrapper import EdgeWrapper

logger = logging.getLogger(__name__)


class AdapterFactory:
    """
    Factory for creating and managing adapter chains.
    
    Handles three cases:
    1. Scalar → Scalar: Uses registry to find adapters
    2. Same compound structure (ARRAY → ARRAY): Uses registered container
       adapter with element transformation
    3. Structural transformation (MAP → ARRAY): Uses StructuralAdapter
       (core system) wrapping registered structural adapter
    """
    
    def __init__(self, adapter_registry: AdapterRegistry):
        """
        Initialize adapter factory.
        
        Args:
            adapter_registry: Registry containing adapter class definitions
        """
        self.adapter_registry = adapter_registry
        
        # Dependency tracking for hot reload
        # Maps adapter registry_key → set of connection_uuids that use it
        self._adapter_to_edges: Dict[str, Set[str]] = {}
        
        # Maps connection_uuid → set of adapter registry_keys it uses
        self._edge_to_adapters: Dict[str, Set[str]] = {}
        
        # EdgeWrapper callbacks for lifecycle events
        # Maps connection_uuid → callback function
        self._edge_callbacks: Dict[str, LiveCycleBatchCallback] = {}
        
        # Subscribe to adapter registry hot reload events
        self.adapter_registry.add_batch_event_subscriber(
            self._on_adapter_lifecycle_event
        )
    
    def create_chain(
        self,
        source_type: type[IType],
        target_type: type[IType],
        connection_uuid: str,
        max_depth: int = 3
    ) -> tuple[Optional[AdapterChain], Optional[str]]:
        """
        Create adapter chain, handling scalar and compound types.
        
        Three cases:
        
        Case 1 - Scalar → Scalar:
            FLOAT → STRING
            Uses registry: [FloatToStringAdapter]
        
        Case 2 - Same compound structure:
            ARRAY[FLOAT] → ARRAY[STRING]
            Requires registered ArrayArrayAdapter
            Factory injects element chain
            Result: [ArrayArrayAdapter(FloatToStringAdapter)]
        
        Case 3 - Structural transformation:
            MAP[FLOAT] → ARRAY[STRING]
            Uses StructuralAdapter (core system)
            Wraps registered MapToArrayAdapter + element chain
            Result: [StructuralAdapter(
                MapToArrayAdapter, FloatToStringAdapter
            )]
        
        Args:
            source_type: Source IType (from outlet)
            target_type: Target IType (from inlet)
            connection_uuid: Connection identifier for dependency tracking
            max_depth: Maximum chain length (default 3)
            
        Returns:
            (AdapterChain or None, error_message or None)
            
        Example:
            chain, error = factory.create_chain(
                Temperature, 
                INT, 
                "conn_uuid_123"
            )
            if chain:
                result = chain.execute(temp_value)
        """
        # Direct type match - no adapters needed
        if source_type == target_type:
            return (AdapterChain([]), None)
        
        # Determine if types are compound
        source_is_compound = issubclass(source_type, CompoundType)
        target_is_compound = issubclass(target_type, CompoundType)
        
        # Create chain without registration (internal=True)
        chain = None
        error = None
        
        # Case 1: Both scalar
        if not source_is_compound and not target_is_compound:
            chain, error = self._create_scalar_chain(
                source_type,
                target_type,
                max_depth
            )
        
        # Case 2: Both compound with same structure (ARRAY→ARRAY, MAP→MAP)
        elif (
            source_is_compound
            and target_is_compound
            and source_type == target_type
        ):
            chain, error = self._create_element_chain(
                source_type,
                getattr(source_type, 'element_type_cls', None),
                target_type,
                getattr(target_type, 'element_type_cls', None),
                max_depth
            )
        
        # Case 3: Structural transformation (MAP→ARRAY, etc.)
        elif source_is_compound and target_is_compound:
            chain, error = self._create_structural_chain(
                source_type,
                target_type,
                max_depth
            )
        
        # Invalid: scalar ↔ compound mismatch
        else:
            return (
                None,
                (
                    f"Cannot convert between scalar and compound types: "
                    f"{source_type.__name__} → {target_type.__name__}"
                )
            )
        
        # Register dependencies ONLY at top level
        if chain and error is None:
            self._register_edge_dependencies(
                connection_uuid,
                chain.get_registry_keys()
            )
        
        return (chain, error)
    
    def _create_scalar_chain(
        self,
        source_type: type[IType],
        target_type: type[IType],
        max_depth: int
    ) -> tuple[Optional[AdapterChain], Optional[str]]:
        """
        Case 1: Create chain for scalar types.
        
        Example: FLOAT → STRING
        Result: [FloatToStringAdapter]
        """
        # Direct match - no adapters needed
        if source_type == target_type:
            return (AdapterChain([PassThroughAdapter()]), None)
        
        adapter_classes = self.adapter_registry.find_adapter_chain(
            source_type,
            target_type,
            max_depth=max_depth
        )
        
        if adapter_classes is None:
            return (
                None,
                (
                    f"No adapter chain found: "
                    f"{source_type.__name__} → {target_type.__name__}"
                )
            )
        
        try:
            adapters = [cls() for cls in adapter_classes]
            chain = AdapterChain(adapters)
            return (chain, None)
            
        except Exception as e:
            return (
                None,
                f"Failed to instantiate adapter chain: {e}"
            )
    
    def _create_element_chain(
        self,
        source_type: type[CompoundType],
        source_element: type[IType],
        target_type: type[CompoundType],
        target_element: type[IType],
        max_depth: int
    ) -> tuple[Optional[AdapterChain], Optional[str]]:
        """
        Case 2: Same structure compound types.
        
        Requires registered container adapter (e.g., ArrayArrayAdapter).
        Factory finds element chain and injects it.
        
        Example: ARRAY[FLOAT] → ARRAY[STRING]
        1. Registry must have ArrayArrayAdapter
        2. Find FLOAT → STRING chain
        3. Inject into ArrayArrayAdapter
        Result: [ArrayArrayAdapter(FloatToStringAdapter)]
        """
        
        if source_element is None or target_element is None:
            return (
                None,
                f"Compound types missing element_type_cls"
            )
 
        # Find container adapter via registry
        # Note: Registry compares base types (ArrayType vs ArrayType)
        # not element types
        container_classes = self.adapter_registry.find_adapter_chain(
            source_type,
            target_type,
            max_depth=1  # Direct transformation only
        )
        
        if container_classes is None:
            return (
                None,
                (
                    f"No container adapter found: "
                    f"{source_type.__name__} → {target_type.__name__}"
                )
            )

        # safty check - should only be one container adapter
        if len(container_classes) != 1:
            return (
                None,
                (
                    f"Container transformation must be direct: "
                    f"found {len(container_classes)} adapters"
                )
            )

       
        # Same element type - no transformation needed
        if source_element == target_element:
            try:
                # Instantiate Neutral adapter - no transformation needed
                chain = AdapterChain([PassThroughAdapter()])
                return (chain, None)
                
            except Exception as e:
                return (
                    None,
                    f"Failed to instantiate container adapter: {e}"
                )
        
        # Different element types - find element chain
        element_chain, error = self._create_scalar_chain(
            source_element,
            target_element,
            max_depth
        )
        
        if element_chain is None:
            return (None, f"Element chain failed: {error}")
        
        # Inject element adapter into container adapter
        try:            
            # Wrap element chain if needed
            if len(element_chain.adapters) == 1:
                # Single element adapter
                element_adapter = element_chain.adapters[0]
            else:
                # Multiple element adapters - wrap chain
                element_adapter = ChainAdapter(element_chain)
            
            # Instantiate container adapter with element adapter
            adapter = container_classes[0](element_adapter=element_adapter)
            
            chain = AdapterChain([adapter])
            return (chain, None)
            
        except Exception as e:
            return (
                None,
                f"Failed to inject element adapter: {e}"
            )
    
    def _create_structural_chain(
        self,
        source_type: type[CompoundType],
        target_type: type[CompoundType],
        max_depth: int
    ) -> tuple[Optional[AdapterChain], Optional[str]]:
        """
        Case 3: Structural transformation.
        
        Uses StructuralAdapter (core system component).
        Wraps structural adapter + element chain (which may include
        container adapter).
        
        Example: MAP[FLOAT] → ArrayList[STRING]
        1. Structural: MapToArrayListAdapter (MAP → ArrayList)
        2. Element: ArrayListArrayListAdapter(FloatToStringAdapter) 
           (ArrayList[FLOAT] → ArrayList[STRING])
        3. Wrap: StructuralAdapter(structural, element)
        
        Result: StructuralAdapter(
            MapToArrayAdapter,
            ArrayArrayAdapter(FloatToStringAdapter)
        )
        
        Execution flow:
        1. MAP[FLOAT] → ArrayList[FLOAT] (structural transform)
        2. ArrayList[FLOAT] → ArrayList[STRING] (element transform via container)
        """
        # Find structural adapter via registry
        structural_classes = self.adapter_registry.find_adapter_chain(
            source_type,
            target_type,
            max_depth=1  # Direct transformation only
        )
        
        if structural_classes is None:
            return (
                None,
                (
                    f"No structural adapter found: "
                    f"{source_type.__name__} → {target_type.__name__}"
                )
            )
        
        if len(structural_classes) != 1:
            return (
                None,
                (
                    f"Structural transformation must be direct: "
                    f"found {len(structural_classes)} adapters"
                )
            )
        
        # Instantiate structural adapter
        try:
            structural_adapter = structural_classes[0]()
        except Exception as e:
            return (
                None,
                f"Failed to instantiate structural adapter: {e}"
            )
        
        # Get element types
        source_element = getattr(source_type, 'element_type_cls', None)
        target_element = getattr(target_type, 'element_type_cls', None)
        
        if source_element is None or target_element is None:
            return (
                None,
                f"Compound types missing element_type_cls"
            )
        
        # Create element transformation chain using _create_element_chain
        # This handles the transformation AFTER structural change
        # e.g., ArrayList[FLOAT] → ArrayList[STRING] after Map[FLOAT] → ArrayList[FLOAT]
        element_chain, error = self._create_element_chain(
            target_type,  # Use target structure (e.g., ArrayList)
            source_element,  # But source element type (e.g., FLOAT)
            target_type,  # Target structure (e.g., ArrayList)
            target_element,  # Target element type (e.g., STRING)
            max_depth
        )
        
        if element_chain is None:
            return (None, f"Element chain failed: {error}")
        
        # Wrap element chain if needed
        elif len(element_chain.adapters) == 1:
            # Single adapter (could be container or scalar)
            element_adapter = element_chain.adapters[0]
        else:
            # Multiple adapters - wrap chain
            element_adapter = ChainAdapter(element_chain)
        
        # Wrap in StructuralAdapter (core system component)
        try:
            combined = StructuralAdapter(
                structural_adapter,
                element_adapter
            )
            chain = AdapterChain([combined])
            return (chain, None)
            
        except Exception as e:
            return (
                None,
                f"Failed to create structural chain: {e}"
            )
    
    def rebuild_chain(
        self,
        connection_uuid: str,
        source_type: type[IType],
        target_type: type[IType],
        max_depth: int = 3
    ) -> tuple[Optional[AdapterChain], Optional[str], bool]:
        """
        Rebuild adapter chain (used during hot reload).
        
        Returns:
            (chain, error, chain_changed)
            
        The chain_changed flag indicates if adapters are different,
        which should trigger a warning to the user.
        """
        # Get old adapter keys for comparison
        old_adapter_keys = self._edge_to_adapters.get(connection_uuid, set())
        
        # Unregister old dependencies
        self._unregister_edge_dependencies(connection_uuid)
        
        # Create new chain
        chain, error = self.create_chain(
            source_type,
            target_type,
            connection_uuid,
            max_depth
        )
        
        # Check if chain changed
        chain_changed = False
        if chain:
            new_adapter_keys = set(chain.get_registry_keys())
            chain_changed = (old_adapter_keys != new_adapter_keys)
        
        return (chain, error, chain_changed)
    
    def register_edge_callback(
        self,
        connection_uuid: str,
        callback: LiveCycleBatchCallback
    ):
        """Register EdgeWrapper callback for lifecycle notifications"""
        self._edge_callbacks[connection_uuid] = callback
    
    def unregister_edge_callback(self, connection_uuid: str):
        """Unregister EdgeWrapper callback"""
        if connection_uuid in self._edge_callbacks:
            del self._edge_callbacks[connection_uuid]
        
        # Clean up dependency tracking
        self._unregister_edge_dependencies(connection_uuid)
    
    def _register_edge_dependencies(
        self,
        connection_uuid: str,
        adapter_keys: List[str]
    ):
        """Track which adapters an edge depends on"""
        # Store edge → adapters mapping
        self._edge_to_adapters[connection_uuid] = set(adapter_keys)
        
        # Store adapter → edges mapping
        for adapter_key in adapter_keys:
            if adapter_key not in self._adapter_to_edges:
                self._adapter_to_edges[adapter_key] = set()
            self._adapter_to_edges[adapter_key].add(connection_uuid)
    
    def _unregister_edge_dependencies(self, connection_uuid: str):
        """Remove dependency tracking for an edge"""
        # Get adapters this edge uses
        adapter_keys = self._edge_to_adapters.get(connection_uuid, set())
        
        # Remove edge from adapter → edges mappings
        for adapter_key in adapter_keys:
            if adapter_key in self._adapter_to_edges:
                self._adapter_to_edges[adapter_key].discard(connection_uuid)
                
                # Clean up empty sets
                if not self._adapter_to_edges[adapter_key]:
                    del self._adapter_to_edges[adapter_key]
        
        # Remove edge → adapters mapping
        if connection_uuid in self._edge_to_adapters:
            del self._edge_to_adapters[connection_uuid]
    
    def _on_adapter_lifecycle_event(self, batch: List[LifeCycleEvent]):
        """
        Handle adapter hot reload events from registry.
        
        Notifies affected EdgeWrappers when their adapters change.
        """
        # Collect affected edges
        affected_edges: Set[str] = set()
        
        for event in batch:
            # Find edges that use this adapter
            adapter_key = event.registry_key
            if adapter_key in self._adapter_to_edges:
                affected_edges.update(self._adapter_to_edges[adapter_key])
        
        # Notify affected EdgeWrappers
        for connection_uuid in affected_edges:
            if connection_uuid in self._edge_callbacks:
                callback = self._edge_callbacks[connection_uuid]
                callback(batch)
    
    def get_available_adapters(
        self,
        source_type: Optional[type[IType]] = None,
        target_type: Optional[type[IType]] = None
    ) -> List[Dict[str, any]]:
        """
        Get available adapters, optionally filtered by type.
        
        Useful for UI/debugging to show available conversions.
        """
        adapters = []
        
        for (src, tgt), adapter_list in self.adapter_registry._adapters.items():
            # Filter by source type if specified
            if source_type is not None and src != source_type:
                continue
            
            # Filter by target type if specified
            if target_type is not None and tgt != target_type:
                continue
            
            for adapter_cls in adapter_list:
                identity = adapter_cls.class_identity
                adapters.append({
                    'registry_key': identity.registry_key,
                    'label': identity.label,
                    'description': identity.description,
                    'source_type': src.__name__ if src else None,
                    'target_type': tgt.__name__ if tgt else None,
                    'priority': identity.priority,
                })
        
        return adapters
    
    def cleanup(self):
        """Clean up factory resources"""
        self._adapter_to_edges.clear()
        self._edge_to_adapters.clear()
        self._edge_callbacks.clear()
