# ============================================================================
# ROOT INTERFACE WITH SHARED IMPLEMENTATIONS
# ============================================================================


from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

from haywire.core.errors.haywire_exception import HaywireException

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.edge.edge_wrapper import EdgeWrapper

class IStructuralValidator(ABC):
    """
    Interface for structural validators.

    Defines methods for validating nodes, edges, and entire graphs
    against structural constraints.
    """

    def __init__(self, graph: 'BaseGraph'):
        """
        Initialize structural validator.

        Args:
            graph: The graph to validate
        """
        self.graph = graph

    @abstractmethod
    def validate_node(self, wrapper: 'NodeWrapper') -> tuple[bool, HaywireException | None]:
        """Validate structural constraints for a single node"""
        raise NotImplementedError()

    @abstractmethod
    def validate_edge(self, wrapper: 'EdgeWrapper') -> tuple[bool, HaywireException | None]:
        """Validate structural constraints for a single edge"""
        raise NotImplementedError()

    @abstractmethod
    def validate_graph(self) -> List[str]:
        """Validate all structural constraints across the graph"""
        raise NotImplementedError()