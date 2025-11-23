from abc import ABC, abstractmethod
from dataclasses import dataclass

from ...node.node_wrapper import NodeWrapper
from ...library.base_identity import BaseIdentity

class UINodeCard(ABC):
    """
    Container for a rendered node's UI elements and widget instances.
    detailed implementations are up to the implementation of the chosen
    UI renderer framework.
    """
    pass

class INodeRenderFactory(ABC):
    """
    Abstract base class for NodeRenderFactory implementations.
    Responsible for creating UINodeCard instances using registered
    NodeRenderer classes.
    """
    pass


@dataclass
class RendererIdentity(BaseIdentity):
    """Core identifying attributes of a renderer"""
    is_default: bool = False
    is_error: bool = False

 
class IBaseNodeRenderer(ABC):
    """
    Abstract base class for all NodeRenderer classes.

    NodeRenderer classes are stateless and define the look and structure of nodes.
    They are cached and reused by the NodeRenderFactory.
    """

    @abstractmethod
    def __init__(self, render_factory: INodeRenderFactory):
        """
        Initialize the renderer with a widget registry.

        Args:
            widget_registry: Registry for resolving widget classes
        """
        pass


    @abstractmethod
    def render(self, wrapper: NodeWrapper) -> UINodeCard:
        """
        Render a node into a UINodeCard.

        Args:
            wrapper: The NodeWrapper containing the HaywireNode to render

        Returns:
            UINodeCard containing the rendered UI and widget registry keys
        """
        pass





