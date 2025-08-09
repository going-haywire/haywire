"""
Registry implementations for widgets, adapters, and libraries
"""

from typing import Any, Dict, List, Optional
from .base import BaseRegistry, BaseClassRegistry, LibraryMetadata

# Import core data types for widget fallback
from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.fields import DataField
from haywire.core.adapter.base import BaseAdapter
from haywire.core.node.node import HaywireNode, NodeDiscoveryError, NodeErrorInfo

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

class WidgetRegistry(BaseClassRegistry):
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


class AdapterRegistry(BaseClassRegistry):
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


class RendererRegistry(BaseClassRegistry):
    """Registry for NodeRenderer classes with fallback support"""
    
    def __init__(self):
        super().__init__()
        self._default_renderer_name: str | None = None
        self._error_renderer: type | None = None
    
    def register_default_renderer(self, renderer_name: str):
        """Register the default renderer by name"""
        if not self.has(renderer_name):
            raise ValueError(f"Renderer '{renderer_name}' must be registered before setting as default")
        self._default_renderer_name = renderer_name
    
    def register_error_renderer(self, renderer_class: type):
        """Register the error renderer class"""
        self._error_renderer = renderer_class
    
    def get_renderer_class(self, renderer_name: str | None):
        """
        Get renderer class with fallback strategy:
        1. Try exact renderer name lookup
        2. Use default if no renderer name is specified
        3. Return error renderer if exact renderer doesn't exist
        """
        # 1. Try exact renderer name lookup
        if renderer_name and self.has(renderer_name):
            return self.get(renderer_name)
        
        # 2. Use default if no renderer name is specified
        if renderer_name is None and self._default_renderer_name:
            return self.get(self._default_renderer_name)
        
        # 3. Return error renderer if exact renderer doesn't exist
        if self._error_renderer:
            return self._error_renderer
        
        # Fallback if no error renderer registered
        raise RuntimeError(f"No renderer found for '{renderer_name}' and no error renderer registered")
    
    def register_renderer(self, name: str, renderer_class, metadata: Optional[Dict[str, Any]] = None):
        """
        Register a renderer class.
        
        Args:
            name: Unique name for the renderer
            renderer_class: The NodeRenderer class
            metadata: Optional metadata for the renderer
        """
        self.register(name, renderer_class, metadata)
        
        # Automatically set as default if no default is set yet
        if self._default_renderer_name is None:
            self._default_renderer_name = name
    
    def get_default_renderer(self) -> type | None:
        """Get the default renderer class"""
        if self._default_renderer_name:
            return self.get(self._default_renderer_name)
        return None
    
    def get_error_renderer(self) -> type | None:
        """Get the error renderer class"""
        return self._error_renderer

class NodeRegistry(BaseClassRegistry):
    """Simplified registry for managing nodes using library_name:node_name keys"""
    
    def __init__(self):
        super().__init__()
        self._error_node: type | None = None
    
    def register_node(self, node_class: type, library_metadata: LibraryMetadata):
        """
        Register a node class with library metadata.
        
        Sets node class attributes from library metadata and registers under
        the key format: library_name:node_name
        
        Args:
            node_class: The node class to register
            library_metadata: Library metadata to use for setting node attributes
            
        Raises:
            ValueError: If a node with the same key is already registered
        """
        # Set library-derived attributes on the node class
        setattr(node_class, 'library_name', library_metadata.name)
        setattr(node_class, 'library_version', library_metadata.version)
        setattr(node_class, 'library_url', library_metadata.url)
        setattr(node_class, 'library_help_url', library_metadata.help_url)
        setattr(node_class, 'library_author', library_metadata.author)
        setattr(node_class, 'library_author_url', library_metadata.author_url)


        # Create registry key
        key = f"{library_metadata.name}:{node_class.node_name}"
        
        # Check for duplicates
        if self.has(key):
            raise ValueError(f"Node already registered: {key}")
        
        # Register with metadata
        metadata = {
            'library_name': library_metadata.name,
            'library_metadata': library_metadata,
            'node_name': node_class.node_name,
            'node_version': library_metadata.version,
            'node_author': library_metadata.author,
            'node_url': library_metadata.url,
            'node_help_url': library_metadata.help_url
        }
        
        self.register(key, node_class, metadata)
    
    def register_error_node(self, node_class: type):
        """Register the error node class"""
        self._error_node = node_class
    
    def get_error_node(self) -> type | None:
        """Get the error node class"""
        return self._error_node

    def get_node_class(self, key: str) -> tuple[NodeErrorInfo | None, HaywireNode.__class__]:
        """
        Get node class by registry key for graph operations.
        
        Args:
            key: Registry key in format "library_name:node_name"
            
        Returns:
            Tuple of (success: bool, node_class: type)
            - success: True if the requested node was found, False if error node was returned
            - node_class: Either the requested node class or the error node class
            
        Raises:
            NodeDiscoveryError: If node is not found and no error node is registered
        """
        node_class = self.get(key)
        if node_class is None:
            # Return error node if registered
            if self._error_node:
                creationerror = NodeErrorInfo(
                    error='Node Not Found',
                    error_message='The requested node could not be found in the registry.'
                )
                creationerror.add_note(f"Library: {key.split(':')[0]}")
                creationerror.add_note(f"Node: {key.split(':')[-1]}")
                return creationerror, self._error_node
            # Otherwise raise error
            raise NodeDiscoveryError(f"Node not found: {key}. No error node registered.")
        return None, node_class
    
    def get_menu_structure(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get nodes organized by menu path for UI building.
        
        Returns:
            Dictionary mapping menu paths to lists of node info dicts
        """
        menu = {}
        
        for key in self.list_names():
            node_class = self.get(key)
            menu_path = getattr(node_class, 'node_menu', 'misc')
            
            if menu_path not in menu:
                menu[menu_path] = []
            
            menu[menu_path].append({
                'label': node_class.node_label,           # Display name
                'key': key,                               # Registry key
                'description': node_class.node_description,
                'tags': getattr(node_class, 'node_search_tags', [])
            })
        
        return menu
    
    def search_nodes(self, query: str) -> List[Dict[str, str]]:
        """
        Search nodes by name, description, or tags.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching node info dicts
        """
        results = []
        query_lower = query.lower()
        
        for key in self.list_names():
            node_class = self.get(key)
            
            # Search in label, description, and tags
            searchable = [
                node_class.node_label.lower(),
                node_class.node_description.lower(),
                *[tag.lower() for tag in getattr(node_class, 'node_search_tags', [])]
            ]
            
            if any(query_lower in text for text in searchable):
                results.append({
                    'label': node_class.node_label,
                    'key': key,
                    'description': node_class.node_description,
                    'library': self.get_metadata(key)['library_name']
                })
        
        return results
    
    def get_nodes_by_library(self, library_name: str) -> List[Dict[str, str]]:
        """
        Get all nodes from a specific library.
        
        Args:
            library_name: Name of the library
            
        Returns:
            List of node info dicts from the specified library
        """
        results = []
        
        for key in self.list_names():
            metadata = self.get_metadata(key)
            if metadata and metadata.get('library_name') == library_name:
                node_class = self.get(key)
                results.append({
                    'label': node_class.node_label,
                    'key': key,
                    'description': node_class.node_description,
                    'node_name': node_class.node_name
                })
        
        return results
    
    def list_libraries(self) -> List[str]:
        """
        Get list of all libraries that have registered nodes.
        
        Returns:
            List of unique library names
        """
        libraries = set()
        
        for key in self.list_names():
            metadata = self.get_metadata(key)
            if metadata:
                libraries.add(metadata['library_name'])
        
        return sorted(list(libraries))
