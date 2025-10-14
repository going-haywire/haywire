from typing import Callable, Type, TypeVar, Optional, Union
from dataclasses import dataclass
from haywire.core.node.base_node import BaseNode
from haywire.core.inventory.registry.widget_reg import WidgetRegistry
from haywire.core.ui.base import UINodeCard

from abc import ABC, abstractmethod

@dataclass
class RendererIdentity:
    """Core identifying attributes of a renderer"""
    registry_id: str = ''  # Set by user for unique ID within library - fallback to class name
    registry_key: str = ''  # Full unique key including library ID - set by registry
    description: str = ''
    renders: str | None = None  # What types of nodes this renderer can handle
    is_default: bool = False
    is_error: bool = False

 
# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar('T')

def renderer(cls: Type[T] = None, /, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a node renderer.
    
    Accepts any RendererIdentity field as a keyword argument. Common arguments include:
    
    Args:
        registry_id (str, optional): Unique identifier for the renderer within its library.
            Defaults to class name if not provided.
        description (str, optional): Human-readable description of the renderer.
            Defaults to empty string.
        renders (str, optional): What types of nodes this renderer can handle.
            Defaults to None.
        is_default (bool, optional): Whether this renderer should be the default fallback.
            Defaults to False.
        is_error (bool, optional): Whether this renderer should handle error cases.
            Defaults to False.
    
    Any other keyword arguments will be passed through to the RendererIdentity constructor.
    See the RendererIdentity dataclass for the complete list of available fields.

    Usage:
        # Minimal usage - uses class name for registry_id
        @renderer
        class MyRenderer(BaseNodeRenderer): ...

        # Common customization
        @renderer(description="Custom node renderer")
        class MyRenderer(BaseNodeRenderer): ...

        # Full customization
        @renderer(
            registry_id="custom_renderer",
            description="Custom node renderer for special cases",
            renders="error_nodes",
            is_default=False
        )
        class CustomRenderer(BaseNodeRenderer): ...

        # Default renderer
        @renderer(is_default=True, description="Default node renderer")
        class DefaultRenderer(BaseNodeRenderer): ...

        # Error renderer
        @renderer(is_error=True, description="Error node renderer")
        class ErrorRenderer(BaseNodeRenderer): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseNodeRenderer):
            raise TypeError(f"@renderer can only be applied to BaseNodeRenderer subclasses, got {inner_cls}")

        # Set defaults from class name if not provided
        kwargs.setdefault('registry_id', inner_cls.__name__)
        
        inner_cls.class_identity = RendererIdentity(**kwargs)
        return inner_cls

    return decorator if cls is None else decorator(cls)
    
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


