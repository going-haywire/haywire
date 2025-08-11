from typing import Dict, List

from haywire.core.node.node import BaseNode, NodeDiscoveryError, NodeErrorInfo, is_node
from ..base import BaseClassRegistry, FileChangeEvent, FileEventType, LibraryMetadata, RegistryFolder
from ..utils import camel_to_dot_case

class NodeRegistry(BaseClassRegistry):
    """Simplified registry for managing nodes using library_name:node_name keys"""
    directory_name: str = RegistryFolder.NODES.value
    class_filter = is_node  # Use the node filter

    def __init__(self):
        super().__init__()
        self._error_node: type | None = None

    def register_node(self, node_cls: type[BaseNode], library_metadata: LibraryMetadata):
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
        setattr(node_cls, 'library_name', library_metadata.name)
        setattr(node_cls, 'library_version', library_metadata.version)
        setattr(node_cls, 'library_url', library_metadata.url)
        setattr(node_cls, 'library_help_url', library_metadata.help_url)
        setattr(node_cls, 'library_author', library_metadata.author)
        setattr(node_cls, 'library_author_url', library_metadata.author_url)


        node_name = camel_to_dot_case(node_cls.__name__)

        # Create registry key
        key = f"{library_metadata.name}:{node_name}"

        # Check for duplicates
        if self.has(key):
            raise ValueError(f"Node already registered: {key}")

        self._register(key, node_cls, library_metadata)

    def unregister_node(self, name):
        return super()._unregister(name)

    def register_error_node(self, node_class: type[BaseNode]):
        """Register the error node class"""
        self._error_node = node_class

    def get_error_node(self) -> type[BaseNode] | None:
        """Get the error node class"""
        return self._error_node

    def get_node_class(self, key: str) -> tuple[NodeErrorInfo | None, BaseNode.__class__]:
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

    def handle_module_change(self, module: str, event: FileChangeEvent, metadata: LibraryMetadata):
        """
        Handle file change events for node modules.

        Args:
            event: FileChangeEvent containing file path and event type
        """
        if event.event_type == FileEventType.DELETED:
            affected_class_names = self._on_deleted(module)
            if affected_class_names:
                for cls_name in affected_class_names:
                    self.unregister_node(cls_name)
        elif event.event_type == FileEventType.CREATED:
            affected_class_names = self._on_created(module)
            if affected_class_names:
                for cls_name in affected_class_names:
                    self.register_node(cls_name, metadata)
        elif event.event_type == FileEventType.MODIFIED:
            affected_class_names = self._on_modified(module)
            if affected_class_names:
                for cls_name in affected_class_names:
                    self.unregister_node(cls_name)

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