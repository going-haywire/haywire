import inspect
from haywire.core.node.node import BaseNode
from haywire.core.inventory.registry.widget import WidgetRegistry
from haywire.core.ui.base import UINodeCard

from abc import ABC, abstractmethod

# For renderers  
def is_renderer(cls):
    try:
        return (inspect.isclass(cls) and
                issubclass(cls, BaseNodeRenderer) and
                cls != BaseNodeRenderer)
    except TypeError:
        return False
    
class BaseNodeRenderer(ABC):
    """
    Abstract base class for all NodeRenderer classes.

    NodeRenderer classes are stateless and define the look and structure of nodes.
    They are cached and reused by the NodeRenderFactory.
    """

    def __init__(self, widget_registry: WidgetRegistry):
        """
        Initialize the renderer with a widget registry.

        Args:
            widget_registry: Registry for resolving widget classes
        """
        self.widget_registry = widget_registry

    @abstractmethod
    def render(self, node: BaseNode) -> UINodeCard:
        """
        Render a node into a UINodeCard.

        Args:
            node: The HaywireNode to render

        Returns:
            UINodeCard containing the rendered UI and widget instances
        """
        pass
