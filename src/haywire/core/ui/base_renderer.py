import inspect
from typing import Callable, Type, TypeVar, Optional, Union
from haywire.core.node.node import BaseNode
from haywire.core.inventory.registry.widget_reg import WidgetRegistry
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

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar('T')

def renderer(cls: Type[T] = None, /, *,
             description: Optional[str] = None,
             renders: Optional[str] = None,
             is_default: bool = False,
             is_error: bool = False,
             registry_id: Optional[str] = None) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a node renderer.

    Args:
        registry_id: Unique identifier for the renderer
        description: Human-readable description
        renders: What types of nodes this renderer can handle
        is_default: Whether this renderer should be the default fallback
        is_error: Whether this renderer should handle error cases

    Usage:
        @renderer
        class MyRenderer(BaseNodeRenderer): ...

        @renderer(registry_id="custom_renderer", description="Custom node renderer")
        class MyRenderer(BaseNodeRenderer): ...

        @renderer(is_default=True, description="Default node renderer")
        class DefaultRenderer(BaseNodeRenderer): ...

        @renderer(is_error=True, description="Error node renderer")
        class ErrorRenderer(BaseNodeRenderer): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseNodeRenderer):
            raise TypeError(f"@renderer can only be applied to BaseNodeRenderer subclasses, got {inner_cls}")

        # Store renderer metadata
        inner_cls.class_identity = {
            'registry_id': registry_id or inner_cls.__name__,
            'description': description or '',
            'renders': renders,  # What types of nodes this renderer can handle
            'is_default': is_default,
            'is_error': is_error
        }
        return inner_cls

    if cls is None:
        return decorator
    return decorator(cls)
    
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


