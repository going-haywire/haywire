"""
Registry implementations for widgets, adapters, and libraries
"""

from typing import Dict, Any, Optional, Type, Tuple
from .base import BaseRegistry, LibraryMetadata

# Import core data types for widget fallback
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.fields import DataField


class WidgetRegistry(BaseRegistry):
    """Registry for UI widgets that can render data fields"""
    
    def __init__(self):
        super().__init__()
        self._default_widgets: Dict[DataType, str] = {}
        self._error_widget: Optional[Type] = None
    
    def register_default_widget(self, data_type: DataType, widget_name: str):
        """Register a default widget for a data type"""
        self._default_widgets[data_type] = widget_name
    
    def register_error_widget(self, widget_class: Type):
        """Register the error widget class"""
        self._error_widget = widget_class
    
    def get_widget_class(self, widget_name: str, data_field: DataField) -> Type:
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
        self._adapters: Dict[Tuple[DataType, DataType], Type] = {}
    
    def register_adapter(self, source_type: DataType, target_type: DataType, adapter_class: Type):
        """Register an adapter for converting between two data types"""
        key = (source_type, target_type)
        self._adapters[key] = adapter_class
        
        # Also register in the base registry for metadata tracking
        adapter_name = f"{source_type.value}_to_{target_type.value}"
        self.register(adapter_name, adapter_class)
    
    def has_adapter(self, source_type: DataType, target_type: DataType) -> bool:
        """Check if an adapter exists for the given type conversion"""
        return (source_type, target_type) in self._adapters
    
    def get_adapter(self, source_type: DataType, target_type: DataType) -> Optional[Type]:
        """Get adapter class for converting between two data types"""
        return self._adapters.get((source_type, target_type))
    
    def list_conversions(self) -> list[Tuple[DataType, DataType]]:
        """List all available type conversions"""
        return list(self._adapters.keys())
    
    def can_connect(self, source_field: DataField, target_field: DataField) -> bool:
        """
        Check if two data fields can be connected.
        Returns True if types match or an adapter exists.
        """
        # Direct type match
        if source_field.type == target_field.type:
            return True
        
        # Check if adapter exists
        return self.has_adapter(source_field.type, target_field.type)


class LibraryRegistry(BaseRegistry):
    """Registry for managing loaded libraries"""
    
    def __init__(self):
        super().__init__()
        self._library_paths: Dict[str, str] = {}
        self._load_order: list[str] = []
    
    def register_library(self, library_name: str, library_instance, library_path: str):
        """Register a library instance with its path"""
        self.register(library_name, library_instance)
        self._library_paths[library_name] = library_path
        if library_name not in self._load_order:
            self._load_order.append(library_name)
    
    def get_library_path(self, library_name: str) -> Optional[str]:
        """Get the filesystem path for a library"""
        return self._library_paths.get(library_name)
    
    def get_load_order(self) -> list[str]:
        """Get the order in which libraries were loaded"""
        return self._load_order.copy()
    
    def get_library_metadata(self, library_name: str) -> Optional[LibraryMetadata]:
        """Get metadata for a library"""
        library = self.get(library_name)
        return library.metadata if library else None
