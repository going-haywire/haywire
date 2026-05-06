import copy
import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

from ...ui.utils import generate_edge_uuid
from ..graph.types import ChangeReason
from ..validation.interface import IStructuralValidator
from ..types import FlowType
from ..adapter.base import IAdapter, ReturnAdapter
from ..errors import HaywireException
from ..registry.lifecycle_event import LifeCycleEvent
from ..types.interface import IType
from .edge import Edge

if TYPE_CHECKING:
    from ..graph.base import BaseGraph
    from ..adapter.factory import AdapterFactory
    from ..node.node_wrapper import NodeWrapper
    from ..types import DataPort

logger = logging.getLogger(__name__)


@dataclass
class EdgeWrapperState:
    """Lifecycle state of wrapper and its edge instance"""

    is_registered: bool = False
    """The edge has been registered with the graph"""
    is_formally_validated: bool = False
    """The edge is formally validated (node/port existence and type compatibility)"""
    is_built: bool = False
    """The edge adapter chain has been built (inlets/outlets are compatible)"""
    is_structural: bool = False
    """The edge has passed structural validation"""
    has_test_passed: bool = False
    """The edge adapter chain has been successfully tested"""
    is_inlet_linked: bool = False
    """The inlet port has been validated"""
    is_outlet_linked: bool = False
    """The outlet port has been validated"""
    is_linked: bool = False
    """The edge is linked to both ports"""
    is_executing: bool = False
    """Edge is currently transforming data"""
    warnings: List[str] = field(default_factory=list)
    """main warning message"""
    error_link: Optional[HaywireException] = None
    """port validation error message"""
    error_formal: Optional[HaywireException] = None
    """port type error"""
    error_build: Optional[HaywireException] = None
    """build error"""
    error_structural: Optional[HaywireException] = None
    """structural validation error"""
    error_test: Optional[HaywireException] = None
    """test error message"""
    creation_time: float = 0.0
    """When edge was created"""
    execution_count: int = 0
    """Number of times transform() was called"""
    last_execution_time_us: float = 0.0
    """Last transform() execution time"""
    average_execution_time_us: float = 0.0
    """Average transform() execution time"""
    example_test_value: str | None = None
    """Example test value used during test"""
    example_test_result: str | None = None
    """Example test result value used during test"""

    def has_warning(self) -> bool:
        """Check if connection has warnings"""
        return bool(len(self.warnings) > 0)

    def is_functional(self) -> bool:
        """Check if connection is functional (registered, port-type-validated and built)"""
        return self.is_registered and self.is_formally_validated and self.is_built and self.has_test_passed

    def is_valid(self) -> bool:
        """Check if connection is in valid state (functional and linked)"""
        return self.is_functional() and self.is_structural and self.is_linked

    def get_error(self) -> Optional[HaywireException]:
        """Get main error"""
        if self.error_formal:
            return self.error_formal
        elif self.error_build:
            return self.error_build
        elif self.error_structural:
            return self.error_structural
        elif self.error_link:
            return self.error_link
        elif self.error_test:
            return self.error_test
        else:
            return None


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
        graph: "BaseGraph",
        source_node_id: str,
        outlet_port_id: str,
        sink_node_id: str,
        inlet_port_id: str,
        edge_type: FlowType,
        lazy: bool = False,
    ):
        """
        Initialize EdgeWrapper (similar to NodeWrapper.__init__).

        Args:
            source_node_id: Source node ID
            outlet_port_id: Source outlet ID
            sink_node_id: Sink node ID
            inlet_port_id: Sink inlet ID
            edge_type: edge type
            lazy: If True, edge uses lazy (pull-on-demand) propagation
        """
        self.source_node_id = source_node_id
        self.outlet_port_id = outlet_port_id
        self.sink_node_id = sink_node_id
        self.inlet_port_id = inlet_port_id

        # Edge type (may be overridden during registration)
        self._edge_type = edge_type

        # Generate connection UUID
        self._edge_id = generate_edge_uuid(source_node_id, outlet_port_id, sink_node_id, inlet_port_id)

        # the fallback port hierarchies for edge reconnection in case
        # the ports are hidden inside groups or the skin failed to render them
        self.outletPinFallback: str = f"{self.outlet_port_id}>>root_out"
        self.inletPinFallback: str = f"{self.inlet_port_id}>>root_in"

        # Reference to parent graph
        self._graph: "BaseGraph" = graph

        from haywire.core.di.context import get_adapter_factory

        self._adapter_factory: Optional["AdapterFactory"] = get_adapter_factory()

        # Node wrapper references (set during registration)
        self._source_wrapper: Optional["NodeWrapper"] = None
        self._sink_wrapper: Optional["NodeWrapper"] = None

        # DataPort references (set during registration)
        self._outlet_port: Optional["DataPort"] = None
        self._inlet_port: Optional["DataPort"] = None

        # First adapter in chain (created during registration)
        self._first_adapter: Optional[IAdapter] = ReturnAdapter()

        # State management
        self._state = EdgeWrapperState(creation_time=time.time())

        # Create Edge instance in any case
        self._edge = Edge(
            source_node_id=self.source_node_id,
            outlet_port_id=self.outlet_port_id,
            sink_node_id=self.sink_node_id,
            inlet_port_id=self.inlet_port_id,
            edge_type=self._edge_type,
            chain_adapter_keys=([]),
            is_lazy=lazy,
        )

        self._source_type: Optional[type[IType]] = None

        # Subscribe to adapter factory for hot reload
        self._adapter_factory.register_edge_callback(self._edge_id, self._on_adapter_lifecycle_event)

        self._structural_validator: "IStructuralValidator" = self._graph._structural

    def is_valid(self) -> bool:
        """Check if edge is valid"""
        return self._state.is_valid()

    def is_functional(self) -> bool:
        """Check if connection is functional (registered, formal-validated and built)"""
        return self._state.is_functional()

    def is_callback_edge(self) -> bool:
        """Check if this is a callback edge"""
        return self.edge_type == FlowType.CALLBACK

    def is_control_edge(self) -> bool:
        """Check if this is a control edge"""
        return self.edge_type == FlowType.CONTROL

    def is_data_edge(self) -> bool:
        """Check if this is a data edge"""
        return self.edge_type == FlowType.DATA

    @property
    def edge(self) -> Edge:
        """Get the Edge instance.

        Raises:
            RuntimeError: If the wrapper has been cleaned up.
        """
        if self._edge is None:
            raise RuntimeError(f"EdgeWrapper '{self._edge_id}' has been cleaned up.")
        return self._edge

    @property
    def edge_id(self) -> str:
        """Get the Edge id"""
        return self._edge_id

    @property
    def first_adapter(self) -> Optional[IAdapter]:
        """Get the first adapter in the chain"""
        return self._first_adapter

    @property
    def state(self) -> EdgeWrapperState:
        """Get the Edge state"""
        return self._state

    @property
    def edge_type(self) -> FlowType:
        """Get the edge flow type"""
        return self._edge_type

    @property
    def is_lazy(self) -> bool:
        """True if this edge uses lazy (pull-on-demand) propagation."""
        return self._edge.is_lazy

    @is_lazy.setter
    def is_lazy(self, value: bool) -> None:
        self._edge.is_lazy = value

    # =========================================================================
    # GRAPH NOTIFICATION (mirrors NodeWrapper pattern)
    # =========================================================================

    def redraw(self) -> None:
        """
        Request a visual redraw of this edge in the UI.
        Mirrors NodeWrapper.redraw().
        """
        if self._graph:
            self._graph._validation.mark_edge_dirty(self._edge_id, ChangeReason.EDGE_REDRAW_REQUESTED)

    def request_revalidation(self) -> None:
        """
        Request revalidation of this edge (rebuild + re-link).
        Mirrors NodeWrapper.mark_as_structuraly_dirty().
        """
        if self._graph:
            self._graph._validation.mark_edge_dirty(self._edge_id, ChangeReason.EDGE_VALIDATION_REQUESTED)

    # =========================================================================
    # LINK LIFECYCLE
    # =========================================================================

    def link(self) -> None:
        """
        Attempt to link this edge at both ports.

        Precondition: edge must be functional (is_functional() == True).
        If not functional, this is a no-op.

        Flow:
        1. Register at inlet via _add_link (may displace an old edge)
        2. Register at outlet via _add_link (may displace an old edge)
        3. Update own link state flags
        4. Handle displaced edges with asymmetric invalidation rules
        5. Housekeeping on both ports (rebuild pipes)
        """
        if not self.is_functional():
            return

        if not self._inlet_port or not self._outlet_port:
            return

        # Link at both ports — each returns the displaced edge (if any)
        displaced_at_inlet = self._inlet_port._add_link(self)
        displaced_at_outlet = self._outlet_port._add_link(self)

        # Update own link flags
        self._update_link_state()

        # Handle displaced edges with asymmetric invalidation:
        # Inlet displaced old edge → old edge DOES inform its source outlet
        if displaced_at_inlet:
            displaced_at_inlet._on_displaced_from_inlet()

        # Outlet displaced old edge → old edge does NOT inform its sink inlet
        if displaced_at_outlet:
            displaced_at_outlet._on_displaced_from_outlet()

        # Housekeeping (rebuild pipes)
        self._inlet_port._housekeeping()
        self._outlet_port._housekeeping()

    def unlink(self) -> None:
        """
        Remove this edge from the linked set of both ports.
        The edge remains tracked in _all_edges for potential re-enablement.

        Used when the edge loses functionality (e.g. hot reload broke
        the adapter chain).

        After unlinking, attempts re-enablement on both ports.
        """
        if self._inlet_port:
            self._inlet_port._clear_link(self._edge_id)

        if self._outlet_port:
            self._outlet_port._clear_link(self._edge_id)

        self._update_link_state()
        self._try_reenable_on_ports()

        if self._inlet_port:
            self._inlet_port._housekeeping()
        if self._outlet_port:
            self._outlet_port._housekeeping()

    def detach(self) -> None:
        """
        Fully remove this edge from both ports (both tiers).
        Used when the edge is explicitly deleted or its port is destroyed.

        After detaching, attempts re-enablement on both ports.
        """
        if self._inlet_port:
            self._inlet_port._remove_edge(self._edge_id)

        if self._outlet_port:
            self._outlet_port._remove_edge(self._edge_id)

        self._update_link_state()
        self._try_reenable_on_ports()

        if self._inlet_port:
            self._inlet_port._housekeeping()
        if self._outlet_port:
            self._outlet_port._housekeeping()

    # =========================================================================
    # ASYMMETRIC DISPLACEMENT HANDLERS
    # =========================================================================

    def _on_displaced_from_inlet(self) -> None:
        """
        Called when this edge was displaced from its INLET port by a newer edge.

        Asymmetric rule: DOES inform the source outlet, because the outlet
        needs to remove this edge from its pipes.
        """
        self._state.is_inlet_linked = False
        self._state.is_linked = False
        self._state.error_link = HaywireException.create(
            message="Edge was displaced from inlet port by a newer connection.",
            category="Port Linking Error",
        ).enrich(operation="Port Linking Validation", suggestions=["Remove this edge or reconnect it"])

        # Inform source outlet: remove from its linked set too
        if self._outlet_port:
            self._outlet_port._clear_link(self._edge_id)
            self._state.is_outlet_linked = False
            self._outlet_port._housekeeping()

        self.redraw()

    def _on_displaced_from_outlet(self) -> None:
        """
        Called when this edge was displaced from its OUTLET port by a newer edge.

        Asymmetric rule: does NOT inform the sink inlet. The inlet may
        have stale link state, but the edge will be drawn as invalid,
        and the user can clean up.
        """
        self._state.is_outlet_linked = False
        self._state.is_linked = False
        self._state.error_link = HaywireException.create(
            message="Edge was displaced from outlet port by a newer connection.",
            category="Port Linking Error",
        ).enrich(operation="Port Linking Validation", suggestions=["Remove this edge or reconnect it"])

        # Do NOT inform sink inlet (asymmetric rule)
        self.redraw()

    # =========================================================================
    # LINK STATE HELPERS
    # =========================================================================

    def _update_link_state(self) -> None:
        """
        Update own link state flags based on whether each port considers
        this edge as linked.
        """
        if self._inlet_port:
            self._state.is_inlet_linked = self._inlet_port._is_linked_to(self._edge_id)
        else:
            self._state.is_inlet_linked = False

        if self._outlet_port:
            self._state.is_outlet_linked = self._outlet_port._is_linked_to(self._edge_id)
        else:
            self._state.is_outlet_linked = False

        self._state.is_linked = self._state.is_inlet_linked and self._state.is_outlet_linked

        # Update error state
        if self._state.is_linked:
            self._state.error_link = None
        elif not self._state.is_inlet_linked:
            self._state.error_link = HaywireException.create(
                message="Port link refused due to link limit on inlet port.", category="Port Linking Error"
            ).enrich(
                operation="Port Linking Validation",
                suggestions=["Check port linking limits", "Ensure port is not already linked"],
            )
        elif not self._state.is_outlet_linked:
            self._state.error_link = HaywireException.create(
                message="Port link refused due to link limit on outlet port.", category="Port Linking Error"
            ).enrich(
                operation="Port Linking Validation",
                suggestions=["Check port linking limits", "Ensure port is not already linked"],
            )

    def _try_reenable_on_ports(self) -> None:
        """
        After this edge is unlinked or detached, check both ports for
        re-enablement candidates.
        """
        if self._inlet_port:
            candidate = self._inlet_port._try_reenable()
            if candidate:
                candidate.link()
                candidate.redraw()

        if self._outlet_port:
            candidate = self._outlet_port._try_reenable()
            if candidate:
                candidate.link()
                candidate.redraw()

    # =========================================================================
    # BUILD PIPELINE
    # =========================================================================

    def build(self):
        """
        Build edge wrapper (including rebuild adapter chain).
        """
        logger.debug(f"Start edge rebuilding: {self._edge_id} ... ")

        self._state.error_formal = None
        self._state.error_build = None
        self._state.error_link = None
        self._state.error_test = None
        self._state.warnings = []

        if self._formal_validation():
            if self._structural_validation():
                if self._build_adapter_chain():
                    if self._test():
                        logger.debug(".. rebuilding edge done.")
                        return

        logger.debug(".. rebuilding failed with errors.")

    def _check_chain_for_changes(self, chain: List[str]):
        """
        Check if adapter chain has changed compared to given chain.
        Issues a warning to the state if so.

        Args:
            chain: List of adapter registry keys to compare against
        """
        if self._edge.chain_adapter_keys != chain:
            self._state.warnings.append(
                f"Adapter chain composition changed during hot reload. "
                f"From '{' -> '.join(chain)}' "
                f"to '{' -> '.join(self._edge.chain_adapter_keys)}'. "
                f"Graph behavior may differ!"
            )

    def _build_adapter_chain(self) -> bool:
        """
        Build adapter chain for this edge.

        Precondition: ``_formal_validation`` has run successfully, which sets
        ``_inlet_port`` / ``_outlet_port`` and validates the graph reference.
        ``_adapter_factory`` is set in ``__init__``.
        """
        assert self._inlet_port is not None
        assert self._outlet_port is not None
        assert self._adapter_factory is not None
        inlet_port = self._inlet_port
        outlet_port = self._outlet_port
        adapter_factory = self._adapter_factory
        try:
            # create adapter chain (only for DATA edges)
            if self._edge_type == FlowType.DATA:
                # Inlet determines what type it needs from outlet
                sink_type = inlet_port._data.get_stored_type()

                outlet_field = outlet_port._data
                source_type = outlet_field.type_cls

                # Create new chain
                first_adapter, error = adapter_factory.create_chain(source_type, sink_type, self._edge_id)

                if first_adapter:
                    # Check for chain changes on rebuild
                    if self._edge.chain_adapter_keys:
                        old_adapter_keys = list(self._edge.chain_adapter_keys)[::-1]
                        new_adapter_keys = list(first_adapter._get_registry_keys())[::-1]
                        if self._source_type == source_type and old_adapter_keys != new_adapter_keys:
                            # we only want to warn about adapter chain changes if
                            # the source type is the same, otherwise it's expected that the chain changes
                            self._state.warnings.append(
                                f"Adapter chain composition changed during hot reload. "
                                f"From '{' -> '.join(old_adapter_keys)}' "
                                f"to '{' -> '.join(new_adapter_keys)}'. "
                                f"Graph behavior may differ!"
                            )
                    # Set first adapter
                    self._first_adapter = first_adapter
                    self._edge.chain_adapter_keys = first_adapter._get_registry_keys()

                    self._source_type = source_type

                else:
                    # creating the haywire exception in here to avoid missleading stack traces
                    self._state.error_build = HaywireException.create(
                        message=f"{error}: Edge adapter creation failed for {self._edge_id}",
                    ).enrich(
                        operation="Adapter Chain Creation",
                        category="Adapter Creation Error",
                        suggestions=[
                            "Check if libraries with required adapters are registered",
                            "Create custom adapters if needed for your data types",
                        ],
                    )
                    self._state.error_build.log()
                    self._state.is_built = False
                    self._state.warnings = []

                    return False

            self._state.is_built = True
            self._state.error_build = None

            return True

        except Exception as e:
            self._state.error_build = HaywireException.from_exception(
                exception=e,
                message=f"{e}: Edge adapter creation failed for {self._edge_id}",
            ).enrich(
                operation="Adapter Chain Creation",
                category="Adapter Creation Error",
                suggestions=[
                    "Check if libraries with required adapters are registered",
                    "Create custom adapters if needed for your data types",
                ],
            )
            self._state.error_build.log()
            self._state.is_built = False
            self._state.warnings = []

            return False

    def _formal_validation(self) -> bool:
        """
        Validate connection between ports.

        This formally validates that the connection between
        the two ports is possible based on their existence and types.

        set flag is_formally_validated to True if successful.

        Args:
            graph: The graph containing this edge
        Returns:
            True if validation successful, False otherwise
        """

        try:
            # Get node wrapper references
            self._source_wrapper = self._graph.get_node_wrapper(self.source_node_id)
            self._sink_wrapper = self._graph.get_node_wrapper(self.sink_node_id)

            if not self._source_wrapper or not self._sink_wrapper:
                raise Exception(
                    f"Nodes not found for edge: "
                    f"{self._edge_id} | "
                    f" (source_node_id={self.source_node_id}, sink_node_id={self.sink_node_id})"
                )

            # Get DataPort references
            outlet_node = self._source_wrapper.node
            inlet_node = self._sink_wrapper.node

            self._outlet_port = outlet_node.ports.get(self.outlet_port_id)
            self._inlet_port = inlet_node.ports.get(self.inlet_port_id)

            # Determine edge type if not set
            if self._edge_type is None:
                self._edge_type = self._outlet_port.flow_type

            if self.source_node_id == self.sink_node_id:
                raise Exception(f"Source and sink node are the same: {self.source_node_id}")

            if not self._outlet_port or not self._inlet_port:
                raise Exception(
                    f"Ports not found for edge: "
                    f"{self._edge_id} | "
                    f"(outlet_port_id={self.outlet_port_id}, inlet_port_id={self.inlet_port_id})"
                )

            # Check if this is an inlet (sanity check)
            if self._outlet_port.is_inlet():
                raise Exception(
                    f"Invalid port types for edge: Outlet port {self._outlet_port.id} is an inlet"
                )

            if self._inlet_port.is_outlet():
                raise Exception(
                    f"Invalid port types for edge: Inlet port {self._inlet_port.id} is an outlet"
                )

            if self._outlet_port.flow_type != self._inlet_port.flow_type:
                raise Exception(
                    f"Flow type mismatch between outlet "
                    f"({self._outlet_port.flow_type}) and inlet "
                    f"({self._inlet_port.flow_type}) on edge "
                    f"{self._edge_id}"
                )

            self._state.is_formally_validated = True
            self._state.error_formal = None
            return True

        except Exception as e:
            logger.error(f"Failed to validate port types on edge {self._edge_id}: {e}")
            self._state.error_formal = HaywireException.create(
                message=f"Port type validation failed: {e}", category="Port type Validation Error"
            ).enrich(
                operation="Port Type Validation",
                suggestions=["Ensure both ports exist", "Check port flow types for compatibility"],
            )
            self._state.error_formal.log()
            self._state.is_formally_validated = False

            return False

    def _structural_validation(self) -> bool:
        """
        Validate structural constraints for this edge.

        Uses the graph's structural validator to check domain-specific rules
        such as callback edge constraints, control flow topology, etc.

        Returns:
            True if validation passed, False otherwise
        """
        try:
            # Call structural validator
            (is_valid, error_message, suggestions) = self._structural_validator.validate_edge(self)

            # Update state
            self._state.is_structural = is_valid

            # Create exception from error message if validation failed
            if not is_valid and error_message:
                self._state.error_structural = HaywireException.create(message=error_message).enrich(
                    edge_id=self._edge_id,
                    operation="Structural Validation",
                    category="Structural Validation Error",
                    suggestions=suggestions,
                )
                self._state.error_structural.log()
            else:
                self._state.error_structural = None

            return is_valid

        except Exception as e:
            self._state.error_structural = HaywireException.from_exception(
                exception=e, message=f"Structural validation failed: {e}"
            ).enrich(
                operation="Structural Validation",
                category="Structural Validation Error",
                suggestions=[
                    "Check edge type and node constraints",
                    "Verify callback edge rules if applicable",
                ],
            )
            self._state.error_structural.log()
            self._state.is_structural = False
            return False

    def _test(self) -> bool:
        """
        test adapter chain with test value.

        Returns:
            True if test passes, False otherwise

        """

        try:
            # Execute adapter chain with performance tracking

            if self._first_adapter:
                self._state.execution_count = self._first_adapter.get_test_repetitions()
                self._state.example_test_value = self._first_adapter.get_test_value()
                if self._state.execution_count > 0:
                    start_time = time.perf_counter()
                    for i in range(self._state.execution_count):
                        self._state.example_test_result = self._first_adapter.test(
                            self._state.example_test_value
                        )

                    # Update metrics
                    execution_time = (time.perf_counter() - start_time) * 1000000.0
                    self._state.last_execution_time_us = execution_time
                    self._state.average_execution_time_us = (
                        self._state.last_execution_time_us / self._state.execution_count
                    )

            self._state.has_test_passed = True
            self._state.error_test = None

            return True

        except Exception as e:
            self._state.error_test = HaywireException.from_exception(
                exception=e, message=f"Edge test execution failed: {e}"
            ).enrich(
                operation="Edge Test Execution",
                category="Edge Execution Error",
                suggestions=["Check adapter chain code for errors", "Ensure data types are compatible"],
            )
            self._state.error_test.log()
            self._state.has_test_passed = False
            return False

    def _on_adapter_lifecycle_event(self, batch: List[LifeCycleEvent]):
        """
        Handle adapter hot reload events.

        Called by AdapterFactory when adapters in our chain are reloaded.
        """
        logger.debug(f"Edge {self._edge_id} received adapter lifecycle events: {len(batch)} events")

        # before attempting rebuild, check for warnings/errors
        for event in batch:
            if event.is_warning_event():
                if event.error:
                    self._state.error_build = event.error
                else:
                    self._state.error_build = HaywireException.create(
                        message=f"Adapter hot reload error on edge {self._edge_id}",
                        operation=f"Adapter Hot Reload: {event.event_type}",
                        category="Adapter Hot Reload Error",
                    ).enrich(
                        library_identity=event.library_identity,
                        module_name=event.module_name,
                        registry_key=event.registry_key,
                    )

                self._state.error_build.log()
                self._state.is_built = False
                self._state.warnings = []

                # Tell graph about error
                if self._graph:
                    self._graph._validation.mark_edge_dirty(
                        self._edge_id, ChangeReason.EDGE_HOT_RELOAD_ERROR
                    )
                return  # abort on first warning/error

        # Tell graph about successful reload
        if self._graph:
            self._graph._validation.mark_edge_dirty(self._edge_id, ChangeReason.EDGE_ADAPTERS_RELOADED)

    def set_as_registered(self, is_registered: bool):
        """
        Set edge as registered or unregistered with graph.

        Args:
            is_registered: True to mark as registered, False otherwise
        """
        self._state.is_registered = is_registered

    def get_state(self) -> EdgeWrapperState:
        """
        Get metrics.

        Returns:
            shallow copy of internal EdgeWrapperState with execution statistics
        """
        return copy.copy(self._state)

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize edge wrapper state.

        Returns the edge data which includes adapter chain metadata.
        This can be used directly by BaseGraph serialization.

        Returns:
            Dictionary containing edge state
        """
        return self._edge.to_dict()

    def restore_after_load(self) -> bool:
        """
        Restore edge state after graph load.

        Called after both nodes have been loaded and the edge has been
        instantiated. Rebuilds the adapter chain based on current port
        types.

        Returns:
            True if restoration succeeded, False otherwise
        """
        logger.debug(f"Restoring edge {self._edge_id} after load")

        # Build adapter chain (will auto-detect types from ports)
        self.build()

        return self._state.is_valid()

    def cleanup(self):
        """Clean up edge resources"""
        # Remove from ports before nulling references
        self.detach()

        # Unsubscribe from adapter factory
        self._adapter_factory.unregister_edge_callback(self._edge_id)

        # Clear references
        self._first_adapter = None
        self._source_wrapper = None
        self._sink_wrapper = None
        self._outlet_port = None
        self._inlet_port = None
        self._edge = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        status = "valid" if self._state.is_valid() else "invalid"

        # Build chain description from linked adapters
        if self._first_adapter:
            adapter_names = []
            current = self._first_adapter
            while hasattr(current, "_chain"):
                adapter_names.append(current.__class__.__name__)
                current = current._chain
                if current.__class__.__name__ == "ReturnAdapter":
                    break
            chain_desc = " → ".join(adapter_names) if adapter_names else "direct"
        else:
            chain_desc = "none"

        return (
            f"EdgeWrapper({self._edge_id}, "
            f"type={self._edge_type.value if self._edge_type else 'unknown'}, "
            f"status={status}, chain={chain_desc})"
        )
