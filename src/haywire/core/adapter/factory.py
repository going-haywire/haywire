"""
AdapterFactory - Creates adapter chains and manages hot reload.

This factory:
- Creates linked adapter chains from type compatibility queries
- Handles compound types (ARRAY, MAP) with structural adapters
- Tracks which EdgeWrappers depend on which adapters
- Notifies EdgeWrappers when adapters are hot-reloaded
- Provides adapter discovery services
"""

from typing import Dict, List, Optional, Set, TYPE_CHECKING
import logging

from .base import ReturnAdapter, IAdapter
from .registry import AdapterRegistry
from ..registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
    LiveCycleBatchCallback
)
from ..types.interface import IType
from ..types.base import CompoundType


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
    ) -> tuple[Optional[IAdapter], Optional[str]]:
        """
        Create adapter chain, handling scalar and compound types.
        
        Three cases:
        
        Case 1 - Scalar → Scalar:
            FLOAT → STRING
            Uses registry: FloatToStringAdapter
        
        Case 2 - Same compound structure:
            ARRAY[FLOAT] → ARRAY[STRING]
            Requires registered ArrayArrayAdapter
            Factory injects element chain
            Result: ArrayArrayAdapter(FloatToStringAdapter)
        
        Case 3 - Structural transformation:
            MAP[FLOAT] → ARRAY[STRING]
            Uses StructuralAdapter (core system)
            Wraps registered MapToArrayAdapter + element chain
            Result: StructuralAdapter(
                MapToArrayAdapter, FloatToStringAdapter
            )
        
        Args:
            source_type: Source IType (from outlet)
            target_type: Target IType (from inlet)
            connection_uuid: Connection identifier for dependency tracking
            max_depth: Maximum chain length (default 3)
            
        Returns:
            (first_adapter or None, error_message or None)
            
        Example:
            first_adapter, error = factory.create_chain(
                Temperature, 
                INT, 
                "conn_uuid_123"
            )
            if first_adapter:
                result = first_adapter.execute(temp_value)
        """        
        # Get base types for compound type detection
        # (ArrayType[FLOAT] → ArrayType)
        source_base = self._get_base_type(source_type)
        target_base = self._get_base_type(target_type)
        
        # Determine if types are compound
        source_is_compound = issubclass(source_base, CompoundType)
        target_is_compound = issubclass(target_base, CompoundType)
        
        # Create chain without registration (internal=True)
        first_adapter = None
        error = None
        
        # Case 1: Both scalar
        if not source_is_compound and not target_is_compound:
            # Direct type match - no adapters needed
            if source_type == target_type:
                return (ReturnAdapter(), None)
            else:
                first_adapter, error = self._create_scalar_chain(
                    source_type,
                    target_type,
                    max_depth
                )
        
        # Case 2: Both compound with same structure (ARRAY→ARRAY, MAP→MAP)
        elif (
            source_is_compound
            and target_is_compound
            and source_base == target_base
        ):
            first_adapter, error = self._create_element_chain(
                source_type,
                getattr(source_type, 'element_type_cls', None),
                target_type,
                getattr(target_type, 'element_type_cls', None),
                max_depth
            )
        
        # Case 3: Structural transformation (MAP→ARRAY, etc.)
        elif source_is_compound and target_is_compound:
            first_adapter, error = self._create_structural_chain(
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
        if first_adapter and error is None:
            # Unregister old dependencies
            self._unregister_edge_dependencies(connection_uuid)
            # Register new dependencies
            self._register_edge_dependencies(
                connection_uuid,
                first_adapter._get_registry_keys()
            )
        
        return (first_adapter, error)
    
    def _get_base_type(self, type_cls: type[IType]) -> type[IType]:
        """
        Get base type from potentially parameterized compound type.
        
        Parameterized compound types are created dynamically via
        __class_getitem__ (e.g., ArrayType[FLOAT]). This extracts
        the base class for registry lookups.
        
        Examples:
            ArrayType[FLOAT] → ArrayType
            PooledType[STRING] → PooledType
            ArrayType → ArrayType (already base)
            FLOAT → FLOAT (scalar type)
        
        Args:
            type_cls: Type class (possibly parameterized)
            
        Returns:
            Base type class for registry lookup
        """
        # Check if this is a dynamically created parameterized class
        # These have:
        # 1. __bases__ with single parent
        # 2. Parent is a CompoundType
        # 3. Has element_type_cls attribute
        if (
            hasattr(type_cls, '__bases__') 
            and len(type_cls.__bases__) == 1
            and issubclass(type_cls.__bases__[0], CompoundType)
            and hasattr(type_cls, 'element_type_cls')
        ):
            # This is ArrayType[X], return ArrayType (the base)
            return type_cls.__bases__[0]
        
        # Already a base type or scalar
        return type_cls
    
    def _create_scalar_chain(
        self,
        source_type: type[IType],
        target_type: type[IType],
        max_depth: int
    ) -> tuple[Optional[IAdapter], Optional[str]]:
        """
        Case 1: Create chain for scalar types.
        
        Example: FLOAT → STRING
        Result: FloatToStringAdapter (linked to ReturnAdapter)
        """
        # Direct match - no adapters needed
        if source_type == target_type:
            return (ReturnAdapter(), None)
        
        # Extract registry keys from types
        source_key = source_type.class_identity.registry_key
        target_key = target_type.class_identity.registry_key
        
        adapter_classes = self.adapter_registry.find_adapter_chain(
            source_key,
            target_key,
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
            # Build chain from right to left (terminal to first)
            chain = ReturnAdapter()  # Terminal
            
            for cls in reversed(adapter_classes):
                chain = cls(child=chain)
            
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
    ) -> tuple[Optional[IAdapter], Optional[str]]:
        """
        Case 2: Same structure compound types.
        
        Requires registered container adapter (e.g., ArrayArrayAdapter).
        Factory finds element chain and injects it.
        
        Example: ARRAY[FLOAT] → ARRAY[STRING]
        1. Registry must have ArrayArrayAdapter
        2. Find FLOAT → STRING chain
        3. Inject into ArrayArrayAdapter
        Result: ArrayArrayAdapter(FloatToStringAdapter)
        """
        
        if source_element is None or target_element is None:
            return (
                None,
                f"Compound types missing element_type_cls"
            )
 
        # Get base types for registry lookup
        # (ArrayType[FLOAT] → ArrayType)
        source_base = self._get_base_type(source_type)
        target_base = self._get_base_type(target_type)
        
        # Extract registry keys from base types
        source_base_key = source_base.class_identity.registry_key
        target_base_key = target_base.class_identity.registry_key
        
        # Find container adapter via registry
        # Note: Registry compares base types (ArrayType vs ArrayType)
        # not element types
        container_classes = self.adapter_registry.find_adapter_chain(
            source_base_key,
            target_base_key,
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

        # safety check - should only be one container adapter
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
                # Instantiate PassThrough adapter - no transformation needed
                return (ReturnAdapter(), None)
                
            except Exception as e:
                return (
                    None,
                    f"Failed to instantiate container adapter: {e}"
                )
        
        # Different element types - find element chain
        element_adapter, error = self._create_scalar_chain(
            source_element,
            target_element,
            max_depth
        )
        
        if element_adapter is None:
            return (None, f"Element chain failed: {error}")
        
        # Inject element adapter into container adapter
        try:
            # Instantiate container adapter with element adapter
            adapter = container_classes[0](child=element_adapter)
            
            return (adapter, None)
            
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
    ) -> tuple[Optional[IAdapter], Optional[str]]:
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
        # Get element types
        source_element = getattr(source_type, 'element_type_cls', None)
        target_element = getattr(target_type, 'element_type_cls', None)
        
        if source_element is None or target_element is None:
            return (
                None,
                f"Compound types missing element_type_cls"
            )
 
        # Get base types for registry lookup
        # (ArrayType[FLOAT] → ArrayType, PooledType[STRING] → PooledType)
        source_base = self._get_base_type(source_type)
        target_base = self._get_base_type(target_type)
        
        # Extract registry keys from base types
        source_base_key = source_base.class_identity.registry_key
        target_base_key = target_base.class_identity.registry_key
        
        # Find structural adapter via registry
        structural_classes = self.adapter_registry.find_adapter_chain(
            source_base_key,
            target_base_key,
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
               
        # Create element transformation chain using _create_element_chain
        # This handles the transformation AFTER structural change
        # e.g., ArrayList[FLOAT] → ArrayList[STRING] after Map[FLOAT] → ArrayList[FLOAT]
        element_adapter, error = self._create_element_chain(
            target_type,  # Use target structure (e.g., ArrayList)
            source_element,  # But source element type (e.g., FLOAT)
            target_type,  # Target structure (e.g., ArrayList)
            target_element,  # Target element type (e.g., STRING)
            max_depth
        )
        
        if element_adapter is None:
            return (None, f"Element chain failed: {error}")
        
        # Wrap in StructuralAdapter (core system component)
        try:
            structural_adapter = structural_classes[0](child=element_adapter)
            return (structural_adapter, None)
            
        except Exception as e:
            return (
                None,
                f"Failed to create structural chain: {e}"
            )
        
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
    
    # there is a good reason to separate the registration methods of the 
    # dependencies and the callback methods:
    # the dependecy registration is done internally when the chain is created,
    # and alse when the chain is rebuilt during hot-reload
    # the callback registration/unregistration is done externally by the
    # EdgeWrapper when it is created/destroyed

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
        Each EdgeWrapper receives only events for adapters it depends on.
        """
        # Group events by affected edges
        # edge_uuid -> list of relevant events
        edge_to_events: Dict[str, List[LifeCycleEvent]] = {}
        
        for event in batch:
            adapter_key = event.registry_key
            if adapter_key in self._adapter_to_edges:
                # This adapter affects some edges
                for connection_uuid in self._adapter_to_edges[adapter_key]:
                    if connection_uuid not in edge_to_events:
                        edge_to_events[connection_uuid] = []
                    edge_to_events[connection_uuid].append(event)
        
        # Notify affected EdgeWrappers with filtered events
        for connection_uuid, events in edge_to_events.items():
            if connection_uuid in self._edge_callbacks:
                callback = self._edge_callbacks[connection_uuid]
                callback(events)
    
    def cleanup(self):
        """Clean up factory resources"""
        self._adapter_to_edges.clear()
        self._edge_to_adapters.clear()
        self._edge_callbacks.clear()
