from abc import ABC, abstractmethod
from typing import Any
from haywire.core.library.identity import LibraryIdentity
from haywire.core.types.ports import DataPort
from haywire.core.data.fields import DataField
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

