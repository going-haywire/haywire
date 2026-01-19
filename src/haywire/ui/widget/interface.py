from abc import ABC, abstractmethod
from typing import Any, Dict
from haywire.core.library.identity import LibraryIdentity
from haywire.core.types.ports import DataPort
from haywire.ui.widget.identity import WidgetIdentity

# ============================================================================
# Core Interface - Minimal Contract
# ============================================================================

class IWidget(ABC):
    """
    Minimal widget interface.
    
    Developers are FREE to implement data binding however they want:
    - Use SimpleWidget for performance-critical simple cases
    - Use BaseWidget for sophisticated features
    - Roll their own for custom requirements
    """
    
    # Set by @widget decorator
    class_identity: WidgetIdentity
    class_library: LibraryIdentity
    
    @abstractmethod
    def __init__(self, element: DataPort):
        """
        Initialize widget with a DataPort.
        
        Args:
            element: DataPort containing the data to bind to
        """
        pass
    
    @abstractmethod
    def render(self) -> Any:
        """
        Render the widget and return the UI element.
        
        Returns:
            NiceGUI element or other UI representation
        """
        pass
    
    def cleanup(self) -> None:
        """
        Optional cleanup method.
        Override if your widget needs to release resources.
        """
        pass

    @classmethod
    def config(cls, **kwargs) -> Dict[str, Any]:
        """
        Generate widget configuration dictionary for use in port creation.
        
        This method simplifies widget configuration by combining the widget key
        and configuration into a single dictionary.
        
        Args:
            **kwargs: Widget configuration options (e.g., properties, etc.)
        
        Returns:
            Dictionary with 'key' and 'config' for port creation
            
        Example:
            SelectWidget.config(
                properties={'options': ['A', 'B', 'C']}
            )
            # Returns:
            # {
            #     'key': 'core:widget:SelectWidget',
            #     'config': {'properties': {'options': ['A', 'B', 'C']}}
            # }
        """
        if not hasattr(cls, 'class_identity'):
            raise AttributeError(
                f"{cls.__name__} has no class_identity. "
                f"Did you forget to apply @widget decorator?"
            )
        
        return {
            'key': cls.class_identity.registry_key,
            'config': kwargs
        }
