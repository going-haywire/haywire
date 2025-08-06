"""
Registry implementations for widgets, adapters, and libraries
"""

from typing import Any
from .base import BaseRegistry, LibraryMetadata

# Import core data types for widget fallback
from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.fields import DataField
from haywire.core.adapter.base import BaseAdapter

class WidgetRegistry(BaseRegistry):
    """Registry for UI widgets that can render data fields"""
    
    def __init__(self):
        super().__init__()
        self._default_widgets: dict[DataType, str] = {}
        self._error_widget: type | None = None
    
    def register_default_widget(self, data_type: DataType, widget_name: str):
        """Register a default widget for a data type"""
        self._default_widgets[data_type] = widget_name
    
    def register_error_widget(self, widget_class: type):
        """Register the error widget class"""
        self._error_widget = widget_class
    
    def get_widget_class(self, widget_name: str | None, data_field: DataField) -> type:
        """
        Get widget class with fallback strategy:
        1. Try exact widget name lookup
        2. Fallback to default for scalar types
        3. Return error widget
        """
        # 1. Try exact widget name lookup
        if widget_name and self.has(widget_name):
            return self.get(widget_name)
        
        # 2. Fallback to default for scalar types
        if data_field.category == DataCategory.SCALAR:
            default_widget_name = self._default_widgets.get(data_field.type)
            if default_widget_name and self.has(default_widget_name):
                return self.get(default_widget_name)
        
        # 3. Return error widget
        if self._error_widget:
            return self._error_widget
        
        # Fallback if no error widget registered
        raise RuntimeError(f"No widget found for '{widget_name}' and no error widget registered")


class AdapterRegistry(BaseRegistry):
    """Registry for type conversion adapters"""
    
    def __init__(self):
        super().__init__()
        # Key: (source_type, target_type), Value: adapter_class
        self._adapters: dict[tuple[str, str], type[BaseAdapter]] = {}
    
    def register_adapter(self, adapter_class: type[BaseAdapter]):
        """
        Register a self-registering adapter class.
        
        The adapter class inherits from BaseAdapter which ensures source_type and target_type exist.
        """
        source_type = adapter_class.source_type
        target_type = adapter_class.target_type
        
        # Convert types to strings for consistent key format
        source_key = source_type if isinstance(source_type, str) else source_type.__name__ if hasattr(source_type, '__name__') else str(source_type)
        target_key = target_type if isinstance(target_type, str) else target_type.__name__ if hasattr(target_type, '__name__') else str(target_type)
        
        key = (source_key, target_key)
        self._adapters[key] = adapter_class
        
        # Register with base registry for metadata tracking
        adapter_name = f"{source_key}_to_{target_key}"
        super().register(adapter_name, adapter_class)
    
    def has_adapter(self, source_type: str, target_type: str) -> bool:
        """Check if an adapter exists for the given type conversion"""
        return (source_type, target_type) in self._adapters
    
    def get_adapter(self, source_type: str, target_type: str) -> type[BaseAdapter] | None:
        """Get adapter class for converting between two data types"""
        return self._adapters.get((source_type, target_type))
    
    def list_conversions(self) -> list[tuple[str, str]]:
        """List all available type conversions"""
        return list(self._adapters.keys())
    
    def can_connect(self, source_field: str, target_field: str) -> bool:
        """
        Check if two data fields can be connected.
        Returns True if types match or an adapter exists.
        """
        # Direct type match
        if source_field == target_field:
            return True
        
        # Check if adapter exists
        return self.has_adapter(source_field, target_field)


class LibraryRegistry(BaseRegistry):
    """Registry for managing loaded libraries"""
    
    def __init__(self):
        super().__init__()
        self._library_paths: dict[str, str] = {}
        self._load_order: list[str] = []
    
    def register_library(self, library_name: str, library_instance: Any, library_path: str):
        """Register a library instance with its path"""
        self.register(library_name, library_instance)
        self._library_paths[library_name] = library_path
        if library_name not in self._load_order:
            self._load_order.append(library_name)
    
    def get_library_path(self, library_name: str) -> str | None:
        """Get the filesystem path for a library"""
        return self._library_paths.get(library_name)
    
    def get_load_order(self) -> list[str]:
        """Get the order in which libraries were loaded"""
        return self._load_order.copy()
    
    def get_library_metadata(self, library_name: str) -> LibraryMetadata | None:
        """Get metadata for a library"""
        library = self.get(library_name)
        return library.metadata if library else None
