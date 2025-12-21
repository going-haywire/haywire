# Edge/EdgeWrapper Implementation Specification

**Version:** 1.0  
**Date:** December 20, 2025  
**Status:** Draft Specification

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Lifecycle Management](#lifecycle-management)
5. [Adapter Chain System](#adapter-chain-system)
6. [Hot Reload Support](#hot-reload-support)
7. [API Specification](#api-specification)
8. [Migration Strategy](#migration-strategy)
9. [Implementation Phases](#implementation-phases)

---

## Overview

This specification defines the implementation of EdgeWrapper and related components, following the same architectural patterns as NodeWrapper. The EdgeWrapper manages the complete lifecycle of an Edge, including adapter chain management, hot reload support, validation, and data transformation.

### Design Principles

- **Parallel to NodeWrapper**: EdgeWrapper follows the same lifecycle patterns as NodeWrapper
- **Separation of Concerns**: Edge (data), EdgeWrapper (lifecycle), AdapterFactory (adapter chain creation)
- **Type Safety**: Full type checking through adapter chains
- **Hot Reload**: Automatic adapter chain updates when adapters are reloaded
- **Validation**: Edge validity determined by inlet DataField with adapter chain support

---

## Architecture

### Component Hierarchy

```
BaseGraph
    ├── NodeWrapper (manages nodes)
    │   └── BaseNode
    │
    └── EdgeWrapper (manages edges) ← NEW
        ├── Edge (data structure)
        └── AdapterChain (transformation pipeline) ← NEW

AdapterFactory ← NEW
    ├── AdapterRegistry (existing)
    └── Manages EdgeWrapper dependencies
```

### Data Flow

```
1. Edge Creation:
   User Action → AddEdgeAction → Graph.create_edge_wrapper() 
   → EdgeWrapper.__init__() → EdgeWrapper.initialize(graph)
   → EdgeWrapper returns self → Graph.add_edge_wrapper()

2. Hot Reload:
   AdapterRegistry → AdapterFactory → EdgeWrapper 
   → EdgeWrapper.rebuild_chain() → Notify UIEdge

3. Data Execution:
   Source Outlet → EdgeWrapper.transform(value) 
   → AdapterChain.execute(value) → Target Inlet
```

---

## Core Components

### 1. Edge (Data Structure)

**Location:** `src/haywire/core/graph/edge.py` (NEW FILE)

**Purpose:** Simple data container for edge information (parallel to BaseNode as data container)

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

class EdgeType(Enum):
    """Types of edges in a Haywire graph"""
    CONTROL = "control"
    DATA = "data"
    CALLBACK = "callback"


@dataclass
class Edge:
    """
    Data structure representing a connection between two nodes.
    
    This is a pure data container - lifecycle is managed by EdgeWrapper.
    Stores connection endpoints and adapter chain metadata for serialization.
    """
    
    # Connection endpoints
    output_node_id: str
    outlet_pin_id: str
    input_node_id: str
    inlet_pin_id: str
    
    # Edge classification
    edge_type: EdgeType
    
    # Adapter chain metadata (for serialization/deserialization)
    adapter_registry_keys: List[str] = field(default_factory=list)
    """List of adapter registry keys in execution order (e.g., ['temp_to_float', 'float_to_int'])"""
    
    # Connection ID (generated from components)
    connection_uuid: str = ""
    """UUID generated from connection components"""
    
    def to_dict(self) -> dict:
        """Serialize edge for graph save"""
        return {
            'output_node_id': self.output_node_id,
            'outlet_pin_id': self.outlet_pin_id,
            'input_node_id': self.input_node_id,
            'inlet_pin_id': self.inlet_pin_id,
            'edge_type': self.edge_type.value,
            'adapter_registry_keys': self.adapter_registry_keys,
            'connection_uuid': self.connection_uuid
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Edge':
        """Deserialize edge from graph load"""
        return cls(
            output_node_id=data['output_node_id'],
            outlet_pin_id=data['outlet_pin_id'],
            input_node_id=data['input_node_id'],
            inlet_pin_id=data['inlet_pin_id'],
            edge_type=EdgeType(data['edge_type']),
            adapter_registry_keys=data.get('adapter_registry_keys', []),
            connection_uuid=data.get('connection_uuid', '')
        )
```

---

### 2. AdapterChain (Transformation Pipeline)

**Location:** `src/haywire/core/adapter/chain.py` (NEW FILE)

**Purpose:** Executable adapter chain that transforms values

```python
from typing import Any, List, Optional
from dataclasses import dataclass

from .base import BaseAdapter
from ..errors import HaywireException


@dataclass
class AdapterChainMetrics:
    """Performance and execution metrics for adapter chains"""
    execution_count: int = 0
    total_execution_time_ms: float = 0.0
    last_execution_time_ms: float = 0.0
    average_execution_time_ms: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None


class AdapterChain:
    """
    Executable adapter chain for type transformations.
    
    This class:
    - Stores instantiated adapter objects (not classes)
    - Executes adapters in sequence
    - Tracks execution metrics
    - Handles errors gracefully
    
    Example:
        # Create chain: Temperature → FLOAT → INT
        chain = AdapterChain([
            TempToFloatAdapter(),
            FloatToIntAdapter()
        ])
        
        result = chain.execute(temp_value)  # Returns int
    """
    
    def __init__(self, adapters: List[BaseAdapter]):
        """
        Initialize adapter chain with instantiated adapters.
        
        Args:
            adapters: List of adapter instances in execution order
        """
        self.adapters = adapters
        self.metrics = AdapterChainMetrics()
        self._is_valid = True
        self._error: Optional[HaywireException] = None
    
    def execute(self, value: Any) -> Any:
        """
        Execute adapter chain on value.
        
        Args:
            value: Input value (unwrapped primitive or type instance)
            
        Returns:
            Transformed value ready for target inlet
            
        Raises:
            HaywireException: If transformation fails
        """
        import time
        
        if not self._is_valid:
            raise HaywireException(
                message="Cannot execute invalid adapter chain",
                error=self._error
            )
        
        start_time = time.perf_counter()
        
        try:
            result = value
            for adapter in self.adapters:
                result = adapter.convert(result)
            
            # Update metrics
            execution_time = (time.perf_counter() - start_time) * 1000
            self.metrics.execution_count += 1
            self.metrics.last_execution_time_ms = execution_time
            self.metrics.total_execution_time_ms += execution_time
            self.metrics.average_execution_time_ms = (
                self.metrics.total_execution_time_ms / 
                self.metrics.execution_count
            )
            
            return result
            
        except Exception as e:
            self.metrics.error_count += 1
            self.metrics.last_error = str(e)
            
            raise HaywireException(
                message=f"Adapter chain execution failed: {e}",
                error=e
            )
    
    def get_registry_keys(self) -> List[str]:
        """Get registry keys of all adapters in chain for serialization"""
        return [
            adapter.class_identity.registry_key 
            for adapter in self.adapters
        ]
    
    def get_chain_description(self) -> str:
        """Get human-readable chain description"""
        if not self.adapters:
            return "direct"
        
        names = [a.__class__.__name__ for a in self.adapters]
        return " → ".join(names)
    
    @property
    def is_valid(self) -> bool:
        """Check if chain is valid and executable"""
        return self._is_valid
    
    @property
    def chain_length(self) -> int:
        """Get number of adapters in chain"""
        return len(self.adapters)
    
    def invalidate(self, error: Optional[HaywireException] = None):
        """Mark chain as invalid"""
        self._is_valid = False
        self._error = error
```

---

### 3. AdapterFactory

**Location:** `src/haywire/core/adapter/factory.py` (NEW FILE)

**Purpose:** Creates and manages adapter chains, tracks EdgeWrapper dependencies

```python
"""
AdapterFactory - Creates adapter chains and manages hot reload

This factory:
- Creates AdapterChain instances from type compatibility queries
- Tracks which EdgeWrappers depend on which adapters
- Notifies EdgeWrappers when adapters are hot-reloaded
- Provides adapter discovery services
"""

from typing import Dict, List, Optional, Set, TYPE_CHECKING
import logging

from .base import BaseAdapter
from .chain import AdapterChain
from .registry import AdapterRegistry
from ..registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
    LiveCycleBatchCallback
)
from ..types.interface import IType
from ..errors import HaywireException

if TYPE_CHECKING:
    from ..graph.edge_wrapper import EdgeWrapper

logger = logging.getLogger(__name__)


class AdapterFactory:
    """
    Factory for creating and managing adapter chains.
    
    Similar to NodeFactory, this factory:
    - Creates AdapterChain instances from AdapterRegistry
    - Tracks EdgeWrapper dependencies for hot reload
    - Notifies EdgeWrappers when adapters change
    - Provides adapter discovery services
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
        Create adapter chain for type conversion.
        
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
        
        # Find adapter chain
        adapter_classes = self.adapter_registry.find_adapter_chain(
            source_type,
            target_type,
            max_depth=max_depth
        )
        
        if adapter_classes is None:
            error_msg = (
                f"No adapter chain found from {source_type.__name__} "
                f"to {target_type.__name__} (max depth: {max_depth})"
            )
            return (None, error_msg)
        
        # Instantiate adapters
        try:
            adapter_instances = [
                adapter_cls() for adapter_cls in adapter_classes
            ]
            chain = AdapterChain(adapter_instances)
            
            # Track dependencies for hot reload
            adapter_keys = chain.get_registry_keys()
            self._register_edge_dependencies(connection_uuid, adapter_keys)
            
            return (chain, None)
            
        except Exception as e:
            error_msg = f"Failed to instantiate adapter chain: {e}"
            logger.error(error_msg)
            return (None, error_msg)
    
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
        # Implementation similar to NodeFactory.search_nodes
        # Returns list of adapter info dicts
        pass
    
    def cleanup(self):
        """Clean up factory resources"""
        self._adapter_to_edges.clear()
        self._edge_to_adapters.clear()
        self._edge_callbacks.clear()
```

---

### 4. EdgeWrapper

**Location:** `src/haywire/core/graph/edge_wrapper.py` (NEW FILE)

**Purpose:** Complete lifecycle management for Edge instances

```python
"""
EdgeWrapper - Complete lifecycle management for Haywire edges.

This wrapper manages the complete lifecycle of an Edge instance,
including creation, adapter chain management, hot reload, validation,
serialization, and cleanup.

Parallel to NodeWrapper design.
"""

import logging
import time
from typing import Any, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field

from .edge import Edge, EdgeType
from ..adapter.chain import AdapterChain
from ..errors import HaywireException
from ..registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
    LiveCycleBatchCallback
)
from ..types.interface import IType
from ..types.ports import DataPort

if TYPE_CHECKING:
    from .base import BaseGraph
    from ..adapter.factory import AdapterFactory
    from ..node.node_wrapper import NodeWrapper

logger = logging.getLogger(__name__)


@dataclass
class EdgeWrapperState:
    """Lifecycle state of wrapper and its edge instance"""
    is_registered: bool = False
    """The edge has been registered with the graph"""
    is_valid: bool = True
    """The edge connection is valid (adapter chain exists)"""
    is_executing: bool = False
    """Edge is currently transforming data"""
    last_hot_reload: float = 0.0
    """Timestamp of last adapter hot reload"""
    history: List[LifeCycleEvent] = field(default_factory=list)
    """Lifecycle event history"""
    error: Optional[HaywireException] = None
    """Current error state"""
    creation_time: float = 0.0
    """When edge was created"""
    execution_count: int = 0
    """Number of times transform() was called"""
    hot_reload_count: int = 0
    """Number of adapter chain rebuilds"""
    chain_changed_warning: bool = False
    """True if adapter chain changed during hot reload"""


class EdgeWrapper:
    """
    Manages the complete lifecycle of an Edge instance.
    
    Responsibilities:
    - Edge instance management and lifecycle
    - Adapter chain creation and hot reload
    - Data transformation execution
    - State validation and error handling
    - Change notifications (for UIEdge)
    - Serialization/deserialization
    - Resource management
    
    Similar to NodeWrapper but for edges.
    """
    
    def __init__(
        self,
        output_node_id: str,
        outlet_pin_id: str,
        input_node_id: str,
        inlet_pin_id: str,
        edge_type: Optional[EdgeType] = None
    ):
        """
        Initialize EdgeWrapper (lightweight construction, parallel to NodeWrapper).
        
        Args:
            output_node_id: Source node ID
            outlet_pin_id: Source outlet ID
            input_node_id: Target node ID
            inlet_pin_id: Target inlet ID
            edge_type: Optional edge type (determined during initialize)
        """
        self.output_node_id = output_node_id
        self.outlet_pin_id = outlet_pin_id
        self.input_node_id = input_node_id
        self.inlet_pin_id = inlet_pin_id
        
        # AdapterFactory injected during initialize()
        self._adapter_factory: Optional[AdapterFactory] = None
        
        # Generate connection UUID
        from ...ui.utils import generate_connection_uuid
        self.connection_uuid = generate_connection_uuid(
            output_node_id, outlet_pin_id, input_node_id, inlet_pin_id
        )
        
        # Edge instance (created during initialize)
        self._edge: Optional[Edge] = None
        
        # Adapter chain (created during registration)
        self._adapter_chain: Optional[AdapterChain] = None
        
        # Node wrapper references (set during registration)
        self._output_wrapper: Optional['NodeWrapper'] = None
        self._input_wrapper: Optional['NodeWrapper'] = None
        
        # DataPort references (set during registration)
        self._outlet_port: Optional[DataPort] = None
        self._inlet_port: Optional[DataPort] = None
        
        # State management
        self.state = EdgeWrapperState(creation_time=time.time())
        
        # Lifecycle event subscribers (for UIEdge)
        self._lifecycle_subscribers: List[LiveCycleBatchCallback] = []
        
        # Edge type (may be overridden during registration)
        self._edge_type = edge_type
    
    def initialize(self, graph: 'BaseGraph') -> Optional['EdgeWrapper']:
        """
        Initialize edge wrapper (similar to NodeWrapper.initialize).
        
        This is the second initialization step where we:
        1. Get node wrapper references
        2. Get DataPort references
        3. Determine edge type
        4. Validate compatibility
        5. Create adapter chain
        6. Create Edge instance
        7. Subscribe to adapter factory
        
        Does NOT add wrapper to graph - that's the caller's responsibility.
        
        Args:
            graph: The graph containing this edge
            
        Returns:
            Self if initialization successful, None otherwise
        """
        try:
            # Inject adapter factory from graph
            self._adapter_factory = graph._adapter_factory
            
            # Get node wrapper references
            self._output_wrapper = graph.get_node_wrapper(self.output_node_id)
            self._input_wrapper = graph.get_node_wrapper(self.input_node_id)
            
            if not self._output_wrapper or not self._input_wrapper:
                raise HaywireException(
                    message=f"Node wrappers not found for edge {self.connection_uuid}"
                )
            
            # Get DataPort references
            outlet_node = self._output_wrapper.node
            inlet_node = self._input_wrapper.node
            
            self._outlet_port = outlet_node.outlets.get(self.outlet_pin_id)
            self._inlet_port = inlet_node.inlets.get(self.inlet_pin_id)
            
            if not self._outlet_port or not self._inlet_port:
                raise HaywireException(
                    message=f"Ports not found for edge {self.connection_uuid}"
                )
            
            # Determine edge type if not set
            if self._edge_type is None:
                self._edge_type = self._determine_edge_type()
            
            # Validate and create adapter chain (only for DATA edges)
            if self._edge_type == EdgeType.DATA:
                success, error = self._create_adapter_chain()
                if not success:
                    self.state.is_valid = False
                    self.state.error = error
                    # Still create edge but mark invalid
            
            # Create Edge instance
            self._edge = Edge(
                output_node_id=self.output_node_id,
                outlet_pin_id=self.outlet_pin_id,
                input_node_id=self.input_node_id,
                inlet_pin_id=self.inlet_pin_id,
                edge_type=self._edge_type,
                adapter_registry_keys=(
                    self._adapter_chain.get_registry_keys() 
                    if self._adapter_chain else []
                ),
                connection_uuid=self.connection_uuid
            )
            
            # Subscribe to adapter factory for hot reload
            self._adapter_factory.register_edge_callback(
                self.connection_uuid,
                self._on_adapter_lifecycle_event
            )
            
            self.state.is_registered = True
            
            # Notify subscribers
            self._notify_lifecycle_event(LifeCycleEvent(
                registry_key=self.connection_uuid,
                event_type=LifeCycleEventType.CLASS_INSTANTIATED,
                affected_class=Edge,
                library_identity=None
            ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to register edge {self.connection_uuid}: {e}")
            self.state.error = HaywireException(
                message=f"Edge registration failed: {e}",
                error=e
            )
            self.state.is_valid = False
            return False
    
    def _determine_edge_type(self) -> EdgeType:
        """Determine edge type from outlet's flow type"""
        from ..data.enums import FlowType
        
        flow_type = self._outlet_port.flow_type
        
        if flow_type == FlowType.CONTROL:
            return EdgeType.CONTROL
        elif flow_type == FlowType.DATA:
            return EdgeType.DATA
        elif flow_type == FlowType.CALLBACK:
            return EdgeType.CALLBACK
        else:
            # Default to DATA
            return EdgeType.DATA
    
    def _create_adapter_chain(self) -> Tuple[bool, Optional[HaywireException]]:
        """
        Validate connection and create adapter chain.
        
        Three-step validation process:
        1. Port-level rules (connection count, state, direction)
        2. Optional custom field validation
        3. Type compatibility via adapter chain creation (authoritative)
        
        Returns:
            (success, error)
        """
        # Step 1: Validate port-level rules (no type checking)
        is_valid, error_msg = self._inlet_port.validate_connection_rules(
            self._outlet_port
        )
        if not is_valid:
            error = HaywireException(message=f"Port validation failed: {error_msg}")
            return (False, error)
        
        # Step 2: Optional custom field validation (subclass hook)
        # Allows fields to reject based on custom logic (not type compatibility)
        is_acceptable, error_msg = self._inlet_port.data.accept_source_field(
            self._outlet_port.data
        )
        if not is_acceptable:
            error = HaywireException(message=f"Field validation failed: {error_msg}")
            return (False, error)
        
        # Step 3: Create adapter chain (SINGLE SOURCE OF TRUTH for type compatibility)
        # This is the ONLY place where type compatibility is evaluated
        source_type = self._outlet_port.type_cls
        target_type = self._inlet_port.type_cls
        
        chain, error_msg = self._adapter_factory.create_chain(
            source_type,
            target_type,
            self.connection_uuid
        )
        
        if chain:
            self._adapter_chain = chain
            return (True, None)
        else:
            # Type incompatible - no adapter chain exists
            error = HaywireException(
                message=f"Type incompatible: {error_msg or 'Unknown error'}"
            )
            return (False, error)
    
    def transform(self, value: Any) -> Any:
        """
        Transform value through adapter chain.
        
        This method will be referenced by the outlet DataPort for
        data transformation during graph execution.
        
        Args:
            value: Source value from outlet
            
        Returns:
            Transformed value ready for inlet
            
        Raises:
            HaywireException: If edge is invalid or transformation fails
            
        Example:
            # Store reference in outlet port
            outlet_port.edge_transform = edge_wrapper.transform
            
            # During execution
            transformed = outlet_port.edge_transform(raw_value)
            inlet_port.set_value(transformed)
        """
        if not self.state.is_valid:
            raise HaywireException(
                message=f"Cannot transform - edge {self.connection_uuid} is invalid",
                error=self.state.error
            )
        
        # For CONTROL edges, pass through unchanged
        if self._edge_type != EdgeType.DATA:
            return value
        
        # No adapter chain needed (direct type match)
        if not self._adapter_chain or self._adapter_chain.chain_length == 0:
            return value
        
        # Execute adapter chain
        self.state.is_executing = True
        try:
            result = self._adapter_chain.execute(value)
            self.state.execution_count += 1
            return result
        finally:
            self.state.is_executing = False
    
    def _on_adapter_lifecycle_event(self, batch: List[LifeCycleEvent]):
        """
        Handle adapter hot reload events.
        
        Called by AdapterFactory when adapters in our chain are reloaded.
        """
        logger.info(
            f"Edge {self.connection_uuid} received adapter lifecycle events: "
            f"{len(batch)} events"
        )
        
        # Attempt to rebuild chain
        source_type = self._outlet_port.type_cls
        target_type = self._inlet_port.type_cls
        
        chain, error, chain_changed = self._adapter_factory.rebuild_chain(
            self.connection_uuid,
            source_type,
            target_type
        )
        
        self.state.last_hot_reload = time.time()
        self.state.hot_reload_count += 1
        
        if chain:
            # Successfully rebuilt
            old_chain = self._adapter_chain
            self._adapter_chain = chain
            self.state.is_valid = True
            self.state.error = None
            
            # Warn if chain changed
            if chain_changed:
                self.state.chain_changed_warning = True
                logger.warning(
                    f"Edge {self.connection_uuid} adapter chain changed "
                    f"during hot reload - graph behavior may differ!"
                )
                
                # Update Edge instance with new adapter keys
                if self._edge:
                    self._edge.adapter_registry_keys = chain.get_registry_keys()
            
            # Notify subscribers
            self._notify_lifecycle_event(LifeCycleEvent(
                registry_key=self.connection_uuid,
                event_type=LifeCycleEventType.CLASS_RELOADED,
                affected_class=Edge,
                library_identity=None
            ))
        else:
            # Failed to rebuild
            self.state.is_valid = False
            self.state.error = HaywireException(
                message=f"Failed to rebuild adapter chain: {error}",
                error=None
            )
            
            logger.error(
                f"Edge {self.connection_uuid} became invalid - "
                f"no adapter chain available"
            )
            
            # Notify subscribers
            self._notify_lifecycle_event(LifeCycleEvent(
                registry_key=self.connection_uuid,
                event_type=LifeCycleEventType.CLASS_RELOAD_FAILED,
                affected_class=Edge,
                library_identity=None,
                error=self.state.error
            ))
    
    def add_lifecycle_subscriber(self, callback: LiveCycleBatchCallback):
        """Add subscriber for lifecycle events (for UIEdge)"""
        if callback not in self._lifecycle_subscribers:
            self._lifecycle_subscribers.append(callback)
    
    def remove_lifecycle_subscriber(self, callback: LiveCycleBatchCallback):
        """Remove lifecycle subscriber"""
        if callback in self._lifecycle_subscribers:
            self._lifecycle_subscribers.remove(callback)
    
    def _notify_lifecycle_event(self, event: LifeCycleEvent):
        """Notify all subscribers of lifecycle event"""
        self.state.history.append(event)
        
        # Batch notification (similar to NodeWrapper)
        batch = [event]
        for callback in self._lifecycle_subscribers:
            try:
                callback(batch)
            except Exception as e:
                logger.error(f"Lifecycle subscriber error: {e}")
    
    def validate(self) -> List[str]:
        """
        Validate edge state.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not self.state.is_registered:
            errors.append("Edge not registered with graph")
        
        if not self.state.is_valid:
            errors.append(f"Edge invalid: {self.state.error}")
        
        if self._edge_type == EdgeType.DATA and not self._adapter_chain:
            errors.append("DATA edge missing adapter chain")
        
        if self.state.chain_changed_warning:
            errors.append(
                "WARNING: Adapter chain changed during hot reload - "
                "graph behavior may differ"
            )
        
        return errors
    
    def get_metrics(self) -> dict:
        """
        Get edge execution metrics (for UIEdge display).
        
        Returns:
            Dict with execution statistics
        """
        metrics = {
            'connection_uuid': self.connection_uuid,
            'edge_type': self._edge_type.value if self._edge_type else None,
            'is_valid': self.state.is_valid,
            'execution_count': self.state.execution_count,
            'hot_reload_count': self.state.hot_reload_count,
            'chain_changed_warning': self.state.chain_changed_warning,
        }
        
        if self._adapter_chain:
            metrics.update({
                'adapter_chain': self._adapter_chain.get_chain_description(),
                'chain_length': self._adapter_chain.chain_length,
                'chain_metrics': {
                    'execution_count': self._adapter_chain.metrics.execution_count,
                    'avg_time_ms': self._adapter_chain.metrics.average_execution_time_ms,
                    'last_time_ms': self._adapter_chain.metrics.last_execution_time_ms,
                    'error_count': self._adapter_chain.metrics.error_count,
                }
            })
        
        return metrics
    
    def cleanup(self):
        """Clean up edge resources"""
        # Unsubscribe from adapter factory
        self._adapter_factory.unregister_edge_callback(self.connection_uuid)
        
        # Clear references
        self._adapter_chain = None
        self._output_wrapper = None
        self._input_wrapper = None
        self._outlet_port = None
        self._inlet_port = None
        self._edge = None
        
        # Clear subscribers
        self._lifecycle_subscribers.clear()
    
    @property
    def edge(self) -> Optional[Edge]:
        """Get the Edge instance"""
        return self._edge
    
    @property
    def is_valid(self) -> bool:
        """Check if edge is valid"""
        return self.state.is_valid
    
    @property
    def adapter_chain(self) -> Optional[AdapterChain]:
        """Get the adapter chain"""
        return self._adapter_chain
    
    def __repr__(self) -> str:
        status = "valid" if self.state.is_valid else "invalid"
        chain_desc = (
            self._adapter_chain.get_chain_description() 
            if self._adapter_chain 
            else "none"
        )
        return (
            f"EdgeWrapper({self.connection_uuid}, "
            f"type={self._edge_type.value if self._edge_type else 'unknown'}, "
            f"status={status}, chain={chain_desc})"
        )
```

---

## Lifecycle Management

### Edge Creation Flow

```
1. User creates connection in UI
   ↓
2. AddEdgeAction created with node/pin IDs
   ↓
3. Action._execute_impl() - first execution
   ↓
4. Graph.create_edge_wrapper() called
   ↓
5. EdgeWrapper.__init__()
   - Stores node/pin IDs
   - Generates connection_uuid
   - State = not initialized
   ↓
6. EdgeWrapper.initialize(graph)
   - Gets node wrapper references
   - Gets DataPort references
   - Determines edge type
   - Validates with inlet DataField
   - Creates adapter chain via factory
   - Creates Edge instance
   - Subscribes to adapter factory
   - Returns self if successful, None if failed
   ↓
7. Graph.add_edge_wrapper(wrapper)
   - Adds to edge_wrappers dict
   - Adds to legacy edges dict (for compatibility)
   ↓
8. Action stores wrapper reference for undo
   ↓
9. UIEdge subscribes to EdgeWrapper
   - Receives lifecycle events
   - Displays metrics/warnings

Redo Flow:
   AddEdgeAction._execute_impl() checks if self.wrapper is None:
   - If None (first execution): create_edge_wrapper()
   - Else (redo): add_edge_wrapper(self.wrapper)
```

### Hot Reload Flow

```
1. Adapter class file modified
   ↓
2. AdapterRegistry detects change
   - Reloads adapter class
   - Creates LifeCycleEvent
   ↓
3. AdapterFactory receives event
   - Looks up dependent edges
   - Calls EdgeWrapper callbacks
   ↓
4. EdgeWrapper rebuilds chain
   - Calls factory.rebuild_chain()
   - Compares old/new adapter keys
   - Updates state
   ↓
5. EdgeWrapper notifies UIEdge
   - Lifecycle event with status
   - Warnings if chain changed
   ↓
6. UIEdge updates display
   - Shows new chain description
   - Displays warning if needed
```

---

## Adapter Chain System

### Chain Creation Strategy

1. **Direct Match** (chain length = 0)
   - Source type == Target type
   - No adapters needed
   - Example: FLOAT → FLOAT

2. **Single Adapter** (chain length = 1)
   - Direct adapter exists
   - Example: Temperature → FLOAT (via TempToFloatAdapter)

3. **Multi-hop Chain** (chain length = 2-3)
   - Registry finds adapter path
   - Example: Temperature → FLOAT → INT
   - Maximum depth configurable (default 3)

4. **No Chain** (invalid edge)
   - No adapter path found
   - Edge marked invalid
   - Error stored in state

### Inlet Validation Strategy

**Simplified Validation - Single Method for Compatibility**

Validation uses `DataField.get_compatible_type()` which combines structural validation with type compatibility declaration. This approach correctly handles compound types where element-level compatibility matters (e.g., `Array[FLOAT] → Array[FLOAT]` checks FLOAT compatibility, not ArrayType compatibility).

**Flow:**
1. EdgeWrapper validates port-level rules (via DataPort)
2. EdgeWrapper calls `inlet_field.get_compatible_type(outlet_field)`
3. Fields declare what type they need and perform structural validation:
   - **Scalar fields** (PrimitiveField/BaseField): Return `type_cls`
   - **Compound fields** (ArrayField): Raise ValueError if outlet not compound, return `element_type_cls`
   - **Pooled fields** (PooledField): Accept both scalar and compound, return `element_type_cls`
4. EdgeWrapper creates adapter chain with resolved types (single source of truth)

**DataField.get_compatible_type() Method:**

```python
# In DataField base class (fields.py)
def get_compatible_type(self, outlet_field: 'DataField') -> type:
    """
    Return the type needed for adapter compatibility checking.
    
    For structural validation, raise ValueError with clear message.
    Default: return own type_cls (scalar behavior).
    
    Examples:
        # Scalar fields check type_cls
        FLOAT inlet returns FLOAT type_cls
        
        # Compound fields check element_type_cls
        Array[FLOAT] inlet checks outlet is also compound,
        returns FLOAT element_type_cls
        
        # Pooled accepts both, checks element_type_cls
        Pooled[FLOAT] returns FLOAT element_type_cls
        (works with FLOAT outlet or Array[FLOAT] outlet)
    """
    return self.type_cls  # Default for scalars
```

**Field Implementations:**

```python
# PrimitiveField/BaseField - use default (returns type_cls)

# CompoundField base - element-level checking for arrays
def get_compatible_type(self, outlet_field):
    if not isinstance(outlet_field, CompoundField):
        raise ValueError(
            f"Cannot connect scalar to compound. "
            f"{outlet_field.type_cls.__name__} → {self.type_cls.__name__}"
        )
    return self.element_type_cls  # Check FLOAT, not Array

# PooledField - flexible, accepts both scalar and compound
def get_compatible_type(self, outlet_field):
    # No structural restrictions
    # Pooled[FLOAT] accepts FLOAT or Array[FLOAT]
    return self.element_type_cls
```

**EdgeWrapper Validation Flow:**

```python
# In EdgeWrapper._create_adapter_chain()

# Step 1: Port-level rules
is_valid, error_msg = self._inlet_port.validate_connection_rules(
    self._outlet_port
)
if not is_valid:
    return (False, HaywireException(message=error_msg))

# Step 2: Get compatible types (includes structural validation)
try:
    # Inlet determines what type it needs
    target_type = self._inlet_port.data.get_compatible_type(
        self._outlet_port.data
    )
    
    # Outlet provides its type
    outlet_field = self._outlet_port.data
    if hasattr(outlet_field, 'element_type_cls'):
        source_type = outlet_field.element_type_cls
    else:
        source_type = outlet_field.type_cls
        
except ValueError as e:
    return (False, HaywireException(message=str(e)))

# Step 3: Create adapter chain (SINGLE registry access)
chain, error_msg = self._adapter_factory.create_chain(
    source_type, target_type, self.connection_uuid
)
```

**Example Connections:**

```python
# Scalar → Scalar
FLOAT → FLOAT:
    inlet.get_compatible_type(outlet) → FLOAT
    outlet provides → FLOAT
    adapter_factory.create_chain(FLOAT, FLOAT) → no adapter needed ✓

Temperature → FLOAT:
    inlet.get_compatible_type(outlet) → FLOAT
    outlet provides → Temperature
    adapter_factory.create_chain(Temperature, FLOAT) → TempToFloat adapter ✓

# Compound → Compound  
Array[FLOAT] → Array[FLOAT]:
    inlet.get_compatible_type(outlet) → FLOAT (element check)
    outlet provides → FLOAT (element)
    adapter_factory.create_chain(FLOAT, FLOAT) → no adapter needed ✓

Array[Temperature] → Array[FLOAT]:
    inlet.get_compatible_type(outlet) → FLOAT
    outlet provides → Temperature
    adapter_factory.create_chain(Temperature, FLOAT) → TempToFloat adapter ✓

# Scalar → Compound (INVALID)
FLOAT → Array[FLOAT]:
    inlet.get_compatible_type(outlet) raises ValueError ✗
    "Cannot connect scalar FLOAT to compound ArrayType"

# Pooled (flexible)
FLOAT → Pooled[FLOAT]:
    inlet.get_compatible_type(outlet) → FLOAT
    outlet provides → FLOAT
    adapter_factory.create_chain(FLOAT, FLOAT) ✓

Array[FLOAT] → Pooled[Array[FLOAT]]:
    inlet.get_compatible_type(outlet) → FLOAT (element)
    outlet provides → FLOAT (element)
    adapter_factory.create_chain(FLOAT, FLOAT) ✓
```

**Key Benefits:**

1. **Single Method** - `get_compatible_type()` handles structural and type declaration
2. **Element-Level Checking** - Correctly handles compound types (Array[X] checks X compatibility)
3. **No Registry Bypass** - DataField never calls AdapterRegistry
4. **Clear Separation**: DataPort (connection rules) → DataField (type declaration) → AdapterFactory (compatibility)
5. **Flexible Pooling** - Supports both scalar and compound aggregation
6. **Single Responsibility** - Type checking once in AdapterFactory

---

## Hot Reload Support

### Adapter Change Scenarios

1. **Adapter Modified** (code changed)
   - Registry reloads adapter class
   - Factory rebuilds chains
   - EdgeWrapper validates new chain
   - If same adapters: silent update
   - If different adapters: warning

2. **Adapter Removed**
   - Registry removes adapter
   - Factory attempts rebuild
   - If alternative found: warning
   - If no alternative: edge invalid

3. **Adapter Added**
   - Registry adds new adapter
   - Existing edges unaffected
   - New edges can use it

4. **Adapter Failed to Load**
   - Registry reports error
   - EdgeWrappers keep old chain
   - Warning issued

### Warning System

EdgeWrapper tracks chain changes:
```python
state.chain_changed_warning = True  # Flag set during hot reload
```

UIEdge displays warnings:
- Visual indicator on edge
- Tooltip with chain comparison
- Option to view details/dismiss

User should be informed:
- Which edges affected
- Old vs new adapter chain
- Potential behavior changes

---

## API Specification

### BaseGraph Changes

**Replace current edge methods with EdgeWrapper API:**

```python
class BaseGraph:
    """Main Graph class with EdgeWrapper support"""
    
    def __init__(self, graph_id: str):
        # Existing init...
        
        # NEW: EdgeWrapper storage (parallel to node_wrappers)
        self.edge_wrappers: Dict[str, EdgeWrapper] = {}
        """Maps connection_uuid → EdgeWrapper"""
        
        # NEW: AdapterFactory reference (from DI)
        from ..di.config import get_adapter_factory
        self._adapter_factory = get_adapter_factory()
        
        # NEW: NodeFactory reference (from DI)
        from ..di.config import get_node_factory
        self._node_factory = get_node_factory()
    
    # NEW: EdgeWrapper-based methods (mirror NodeWrapper API)
    
    def create_edge_wrapper(
        self,
        output_node_id: str,
        outlet_pin_id: str,
        input_node_id: str,
        inlet_pin_id: str
    ) -> Optional[EdgeWrapper]:
        """
        Create and register EdgeWrapper (graph-managed factory pattern).
        
        Returns:
            EdgeWrapper if successful, None if failed
        """
        from .edge_wrapper import EdgeWrapper
        
        # Create wrapper (factories injected from graph)
        wrapper = EdgeWrapper(
            output_node_id=output_node_id,
            outlet_pin_id=outlet_pin_id,
            input_node_id=input_node_id,
            inlet_pin_id=inlet_pin_id
        )
        
        # Initialize wrapper (returns self if successful)
        if wrapper.initialize(self):
            # Add to graph's collection
            return self.add_edge_wrapper(wrapper)
        else:
            return None
    
    def add_edge_wrapper(self, wrapper: EdgeWrapper) -> EdgeWrapper:
        """
        Add an initialized wrapper to the graph's collection.
        
        Used by create_edge_wrapper() for new wrappers and by undo/redo
        operations to re-add existing wrappers.
        
        Args:
            wrapper: EdgeWrapper instance to add (must be initialized)
            
        Returns:
            The added wrapper
        """
        if wrapper.connection_uuid in self.edge_wrappers:
            raise ValueError(
                f"Edge wrapper with UUID '{wrapper.connection_uuid}' "
                f"already exists in graph"
            )
        
        self.edge_wrappers[wrapper.connection_uuid] = wrapper
        
        # Also add to legacy edges dict for backward compatibility
        if wrapper.edge:
            self.edges[wrapper.connection_uuid] = wrapper.edge
        
        return wrapper
        Returns:
            The added wrapper
        """
        if wrapper.connection_uuid in self.edge_wrappers:
            raise ValueError(
                f"Edge wrapper with UUID '{wrapper.connection_uuid}' "
                f"already exists in graph"
            )
        
        self.edge_wrappers[wrapper.connection_uuid] = wrapper
        
        # Also add to legacy edges dict for backward compatibility
        if wrapper.edge:
            self.edges[wrapper.connection_uuid] = wrapper.edge
        
        return wrapper
    
    def remove_edge_wrapper(
        self,
        connection_uuid: str
    ) -> Optional[EdgeWrapper]:
        """
        Remove EdgeWrapper from graph.
        
        Returns:
            Removed wrapper or None
        """
        if connection_uuid not in self.edge_wrappers:
            return None
        
        wrapper = self.edge_wrappers[connection_uuid]
        wrapper.cleanup()
        del self.edge_wrappers[connection_uuid]
        
        return wrapper
    
    def get_edge_wrapper(
        self,
        connection_uuid: str
    ) -> Optional[EdgeWrapper]:
        """Get EdgeWrapper by connection UUID"""
        return self.edge_wrappers.get(connection_uuid)
    
    def list_edge_wrappers(self) -> List[EdgeWrapper]:
        """Get all EdgeWrappers"""
        return list(self.edge_wrappers.values())
    
    # DEPRECATED: Mark old methods as deprecated
    
    @deprecated("Use create_edge_wrapper() instead")
    def add_edge(self, ...):
        """DEPRECATED - Use create_edge_wrapper()"""
        pass
    
    @deprecated("Use remove_edge_wrapper() instead")
    def remove_edge(self, ...):
        """DEPRECATED - Use remove_edge_wrapper()"""
        pass
```

### Editor Changes

**Update Editor to use EdgeWrapper API:**

```python
class Editor:
    """High-level editor with graph-managed wrapper pattern"""
    
    def __init__(
        self, 
        graph: BaseGraph, 
        history_manager: IHistoryManager
    ):
        """Initialize editor (graph manages all factories)."""
        self.graph = graph
        self.history_manager = history_manager
    
    def create_connection(
        self,
        output_node_id: str,
        outlet_pin: str,
        input_node_id: str,
        inlet_pin: str
    ) -> bool:
        """
        Create connection using graph-managed EdgeWrapper.
        
        Returns:
            True if successful, False otherwise
        """
        action = AddEdgeAction(
            graph=self.graph,
            output_node_id=output_node_id,
            outlet_pin_id=outlet_pin,
            input_node_id=input_node_id,
            inlet_pin_id=inlet_pin
        )
        
        self.history_manager.add_action(action)
        
        if action.wrapper:
            self._notify_change("connection_created")
            return True
        
        return False
    
    def get_edge_wrapper(
        self,
        connection_uuid: str
    ) -> Optional[EdgeWrapper]:
        """Get EdgeWrapper for connection"""
        return self.graph.get_edge_wrapper(connection_uuid)
    
    def list_edge_wrappers(self) -> List[EdgeWrapper]:
        """List all EdgeWrappers"""
        return self.graph.list_edge_wrappers()
```

---

## Migration Strategy

### Phase 1: Core Implementation

**Goal:** Implement EdgeWrapper without breaking existing code

1. Create new files:
   - `src/haywire/core/graph/edge.py` (move Edge from base.py)
   - `src/haywire/core/adapter/chain.py`
   - `src/haywire/core/adapter/factory.py`
   - `src/haywire/core/graph/edge_wrapper.py`

2. Update DI configuration:
   - Add AdapterFactory as service
   - Wire AdapterRegistry → AdapterFactory

3. Add EdgeWrapper methods to BaseGraph:
   - `create_edge_wrapper()`
   - `remove_edge_wrapper()`
   - `get_edge_wrapper()`
   - Keep old methods for compatibility

4. Test in isolation:
   - Unit tests for AdapterChain
   - Unit tests for AdapterFactory
   - Unit tests for EdgeWrapper
   - Integration tests

### Phase 2: Action Updates

**Goal:** Update undo/redo system to use EdgeWrapper with graph-managed pattern

1. Update `AddEdgeAction`:
   ```python
   class AddEdgeAction(ActionBase):
       \"\"\"Action for adding an edge using graph-managed EdgeWrapper.\"\"\"
       
       def __init__(
           self,
           graph: BaseGraph,
           output_node_id: str,
           outlet_pin_id: str,
           input_node_id: str,
           inlet_pin_id: str,
           description: Optional[str] = None
       ):
           super().__init__(
               description or 
               f"Connect {output_node_id} to {input_node_id}"
           )
           self.graph = graph
           self.output_node_id = output_node_id
           self.outlet_pin_id = outlet_pin_id
           self.input_node_id = input_node_id
           self.inlet_pin_id = inlet_pin_id
           
           # Wrapper created during execute
           self.wrapper: Optional[EdgeWrapper] = None
       
       def _execute_impl(self):
           \"\"\"Add the edge to the graph.\"\"\"
           if self.wrapper is None:
               # First execution: Create new wrapper via graph
               self.wrapper = self.graph.create_edge_wrapper(
                   self.output_node_id,
                   self.outlet_pin_id,
                   self.input_node_id,
                   self.inlet_pin_id
               )
           else:
               # Redo: Re-add existing wrapper
               self.wrapper = self.graph.add_edge_wrapper(self.wrapper)
           
           if not self.wrapper:
               raise RuntimeError(
                   f"Failed to create edge wrapper for connection "
                   f"{self.output_node_id}:{self.outlet_pin_id} -> "
                   f"{self.input_node_id}:{self.inlet_pin_id}"
               )
       
       def _undo_impl(self):
           \"\"\"Remove the edge from the graph.\"\"\"
           if self.wrapper:
               self.graph.remove_edge_wrapper(
                   self.wrapper.connection_uuid
               )
   ```

2. Update `RemoveElementsAction`:
   - Use `get_edge_wrapper()` to retrieve
   - Use `remove_edge_wrapper()` to remove
   - Use `add_edge_wrapper()` to restore in undo
   - Store EdgeWrapper references for restoration

3. Update Editor.create_connection():
   ```python
   def create_connection(
       self,
       output_node_id: str,
       outlet_pin: str,
       input_node_id: str,
       inlet_pin: str
   ) -> bool:
       \"\"\"Create connection using graph-managed EdgeWrapper.\"\"\"
       action = AddEdgeAction(
           graph=self.graph,
           output_node_id=output_node_id,
           outlet_pin_id=outlet_pin,
           input_node_id=input_node_id,
           inlet_pin_id=inlet_pin
       )
       
       self.history_manager.add_action(action)
       self._notify_change(\"create_connection\")
       
       return action.wrapper is not None
   ```

### Phase 3: DataField Integration

**Goal:** Update DataField validation methods

1. Add `validate_connection()` to DataField:
   ```python
   def validate_connection(
       self,
       outlet_field: 'DataField',
       adapter_registry: 'AdapterRegistry'
   ) -> bool:
       # Implementation...
   ```

2. Implement in subclasses:
   - PrimitiveField: basic type check
   - BaseField: type + custom logic
   - CompoundField: element type check

3. Mark `is_compatible_with()` as deprecated:
   ```python
   @deprecated("Use validate_connection() instead")
   def is_compatible_with(self, other_field, adapter_registry):
       # Redirect to new method
       return self.validate_connection(other_field, adapter_registry)
   ```

### Phase 4: UI Integration

**Goal:** Create UIEdge component (future work)

1. Create `UIEdge` class (similar to UINode):
   - Subscribes to EdgeWrapper lifecycle
   - Displays edge line + metrics
   - Shows warnings for chain changes

2. Update GraphCanvasManager:
   - Track UIEdge instances
   - Sync with EdgeWrappers

3. Add edge inspection UI:
   - Show adapter chain
   - Display execution metrics
   - Warning indicators

### Phase 5: Deprecation Cleanup

**Goal:** Remove old edge methods

1. Mark as deprecated:
   - `BaseGraph.add_edge()`
   - `BaseGraph.remove_edge()`
   - `DataField.is_compatible_with()`

2. Update documentation

3. After migration period:
   - Remove deprecated methods
   - Clean up old Edge storage

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

- [ ] Create `edge.py` with updated Edge dataclass
- [ ] Create `chain.py` with AdapterChain class
- [ ] Create `factory.py` with AdapterFactory class
- [ ] Add AdapterFactory to DI system
- [ ] Write unit tests for AdapterChain
- [ ] Write unit tests for AdapterFactory

### Phase 2: EdgeWrapper (Week 2)

- [ ] Create `edge_wrapper.py` with EdgeWrapper class
- [ ] Add EdgeWrapper methods to BaseGraph
- [ ] Write unit tests for EdgeWrapper
### Phase 4: Validation Methods (Week 4)

- [ ] Add `validate_connection_rules()` to DataPort
- [ ] Add `accept_source_field()` to DataField (optional hook)
- [ ] Implement custom validation in subclasses (if needed)
- [ ] Deprecate `is_compatible_with()`
- [ ] Update tests
- [ ] Verify no duplicate chain buildingdo with EdgeWrapper
- [ ] Update serialization/deserialization

### Phase 4: Validation Methods (Week 4)

- [ ] Add `validate_connection()` to DataPort
- [ ] Add `validate_type_compatibility()` to DataField
- [ ] Implement in PrimitiveField
- [ ] Implement in BaseField
- [ ] Implement in CompoundField
- [ ] Deprecate `is_compatible_with()`
- [ ] Update tests

### Phase 5: Documentation & Testing (Week 5)

- [ ] Update architecture documentation
- [ ] Write developer guide for EdgeWrapper
- [ ] Create adapter chain examples
- [ ] Performance testing
- [ ] Hot reload stress testing
- [ ] User acceptance testing

---

## Testing Strategy

### Unit Tests

**AdapterChain:**
- Direct type match (empty chain)
- Single adapter execution
- Multi-adapter chain execution
- Error handling
- Metrics tracking

**AdapterFactory:**
- Chain creation (various types)
- Dependency tracking
- Hot reload notifications
- Chain rebuilding
- Error scenarios

**EdgeWrapper:**
- Registration flow
- Validation logic
- Transform execution
- Hot reload handling
- Lifecycle events
- Cleanup

### Integration Tests

**EdgeWrapper + AdapterFactory:**
- Create edge with adapter chain
- Hot reload adapter
- Rebuild chain
- Invalid chain handling

**Graph + EdgeWrapper:**
- Add/remove edges
- Undo/redo
- Serialization
- Multiple edges

### Performance Tests

**Adapter Chain Execution:**
- Benchmark transform() speed
- Compare direct vs chain overhead
- Test with large graphs

**Hot Reload:**
- Many edges affected
- Chain rebuild time
- Memory usage

---

## Appendix

### Example Usage

**Creating an Edge:**

```python
# Via Editor
editor.create_connection(
    output_node_id="node_1",
    outlet_pin="temperature_out",
    input_node_id="node_2",
    inlet_pin="value_in"
)

# Via Action (undo/redo)
action = AddEdgeAction(
    graph=graph,
    output_node_id="node_1",
    outlet_pin_id="temperature_out",
    input_node_id="node_2",
    inlet_pin_id="value_in"
)
history_manager.add_action(action)
```

**Using Transform:**

```python
# Get edge wrapper
wrapper = graph.get_edge_wrapper(connection_uuid)

# Transform value
temp_value = Temperature(25.0)  # Celsius
int_value = wrapper.transform(temp_value)  # Returns: 25 (int)

# Or reference in outlet port
outlet_port.edge_transform = wrapper.transform
```

**Checking Edge Status:**

```python
wrapper = graph.get_edge_wrapper(connection_uuid)

# Validation
errors = wrapper.validate()
if errors:
    print(f"Edge issues: {errors}")

# Metrics
metrics = wrapper.get_metrics()
print(f"Chain: {metrics['adapter_chain']}")
print(f"Executions: {metrics['execution_count']}")
print(f"Avg time: {metrics['chain_metrics']['avg_time_ms']}ms")

# Warnings
if wrapper.state.chain_changed_warning:
    print("WARNING: Adapter chain changed!")
```

---

## Breaking Changes

1. **BaseGraph.add_edge()** → `BaseGraph.create_edge_wrapper()`
   - Returns EdgeWrapper instead of connection_uuid
   - Requires AdapterFactory reference

2. **Edge storage** → Now wrapped in EdgeWrapper
   - Access via `graph.edge_wrappers` dict
   - Edge instance via `wrapper.edge`

3. **DataField.is_compatible_with()** → Simplified validation:
   - `DataPort.validate_connection_rules()` - Port-level rules only
   - `DataField.accept_source_field()` - Optional custom validation hook
   - Type compatibility via `AdapterFactory.create_chain()` (single source of truth)
   - No duplicate chain building

4. **AddEdgeAction** → Requires AdapterFactory parameter
   - Stores EdgeWrapper instead of Edge

5. **Edge dataclass** → New fields
   - `adapter_registry_keys` added
   - `connection_uuid` added

---

## Future Enhancements

1. **UIEdge Component**
   - Visual edge representation
   - Real-time metrics display
   - Interactive debugging

2. **Edge Execution Integration**
   - Integrate with pipeline execution
   - Lazy evaluation support
   - Parallel execution

3. **Advanced Validation**
   - Edge dependency cycles
   - Type constraint checking
   - Performance optimization

4. **Adapter Chain Optimization**
   - Cache compiled chains
   - JIT compilation
   - Vectorized operations

5. **User Warnings UI**
   - Edge health dashboard
   - Chain change notifications
   - Automatic issue detection

---

**End of Specification**
