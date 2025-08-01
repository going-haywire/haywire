"""
Haywire Node Discovery and Version Management System
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from abc import abstractmethod


# ============================================================================
# Custom Exceptions
# ============================================================================

class NodeDiscoveryError(Exception):
    """Base exception for node discovery issues"""
    pass

class NodeNotFoundError(NodeDiscoveryError):
    """Node with specified criteria not found"""
    pass

class NodeAmbiguousError(NodeDiscoveryError):
    """Multiple nodes found, cannot determine which to use"""
    pass

class NodeVersionError(NodeDiscoveryError):
    """Node version compatibility issue"""
    pass

class NodeVersionIncompatibleError(NodeVersionError):
    """Node version is incompatible (major version mismatch)"""
    pass


# ============================================================================
# Version Utilities
# ============================================================================

def parse_version(version_str: str) -> Tuple[int, int, int]:
    """Parse version string into (major, minor, bugfix) tuple"""
    try:
        major, minor, bugfix = map(int, version_str.split('.'))
        return (major, minor, bugfix)
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid version format: {version_str}. Expected 'major.minor.bugfix'")

def compare_versions(saved_version: str, current_version: str) -> Dict[str, Any]:
    """
    Compare versions and return compatibility info
    Returns: {
        'compatible': bool,
        'action': 'ok' | 'warning' | 'error',
        'message': str,
        'saved_parsed': tuple,
        'current_parsed': tuple
    }
    """
    saved_major, saved_minor, saved_bugfix = parse_version(saved_version)
    current_major, current_minor, current_bugfix = parse_version(current_version)
    
    if saved_major == current_major:
        return {
            'compatible': True,
            'action': 'ok',
            'message': f"Version compatible: {saved_version} -> {current_version}",
            'saved_parsed': (saved_major, saved_minor, saved_bugfix),
            'current_parsed': (current_major, current_minor, current_bugfix)
        }
    elif current_major > saved_major:
        return {
            'compatible': True,
            'action': 'warning',
            'message': f"WARNING: Node upgraded from v{saved_version} to v{current_version}. "
                      f"Major version change may include breaking changes.",
            'saved_parsed': (saved_major, saved_minor, saved_bugfix),
            'current_parsed': (current_major, current_minor, current_bugfix)
        }
    else:  # current_major < saved_major
        return {
            'compatible': False,
            'action': 'error',
            'message': f"ERROR: Graph requires node v{saved_version} but only v{current_version} "
                      f"is available. Cannot load graph with older major version.",
            'saved_parsed': (saved_major, saved_minor, saved_bugfix),
            'current_parsed': (current_major, current_minor, current_bugfix)
        }


# ============================================================================
# Library/Package Declaration System
# ============================================================================
# The HAYWIRE_* constants are automatically detected by the metaclass
# using inspect.currentframe() to access module globals directly.
# This is more reliable than parsing source files.


# ============================================================================
# Enhanced Metaclass with Library/Package Support
# ============================================================================

import inspect
import sys

class NodeMetadataMeta(type):  # Assuming HaywireMeta inherits from type
    def __new__(cls, name, bases, attrs):
        # Automatically identify metadata attributes
        metadata_attrs = []
        for attr_name, attr_value in attrs.items():
            if attr_name.startswith('node_') and not callable(attr_value):
                metadata_attrs.append(attr_name)
        
        attrs['_node_metadata_attrs'] = metadata_attrs
        
        # Get the module where this class is being defined
        frame = inspect.currentframe()
        try:
            # Go up the call stack to find the module that's defining this class
            caller_frame = frame.f_back
            while caller_frame:
                if caller_frame.f_code.co_name == '<module>':
                    module_globals = caller_frame.f_globals
                    break
                caller_frame = caller_frame.f_back
            else:
                module_globals = {}
        finally:
            del frame
        
        # Extract file-level HAYWIRE declarations and auto-assign to node attributes
        file_declarations = {}
        
        # Check for HAYWIRE constants in the module globals
        if 'HAYWIRE_LIBRARY_NAME' in module_globals:
            file_declarations['library_name'] = module_globals['HAYWIRE_LIBRARY_NAME']
        if 'HAYWIRE_LIBRARY_URL' in module_globals:
            file_declarations['library_url'] = module_globals['HAYWIRE_LIBRARY_URL']
        if 'HAYWIRE_PACKAGE_NAME' in module_globals:
            file_declarations['package_name'] = module_globals['HAYWIRE_PACKAGE_NAME']
        
        # Auto-assign file-level declarations to node metadata if not explicitly set
        if 'node_library_name' not in attrs and 'library_name' in file_declarations:
            attrs['node_library_name'] = file_declarations['library_name']
            metadata_attrs.append('node_library_name')
        
        if 'node_library_url' not in attrs and 'library_url' in file_declarations:
            attrs['node_library_url'] = file_declarations['library_url']
            metadata_attrs.append('node_library_url')
        
        if 'node_package' not in attrs and 'package_name' in file_declarations:
            attrs['node_package'] = file_declarations['package_name']
            metadata_attrs.append('node_package')
        
        # Update metadata_attrs list
        attrs['_node_metadata_attrs'] = list(set(metadata_attrs))
        
        return super().__new__(cls, name, bases, attrs)


# ============================================================================
# Node Classes
# ============================================================================

@abstractmethod
class HaywireNode(object, metaclass=NodeMetadataMeta):
    def __init__(self, node_id, graph):
        self.graph = graph
        self.node_id = node_id
        
        # Copy class metadata to instance attributes for serialization
        for attr_name in self._node_metadata_attrs:
            if hasattr(self.__class__, attr_name):
                setattr(self, attr_name, getattr(self.__class__, attr_name))
        
        # Runtime attributes
        self.help_md = None
        self.help_url = 'https://haywire.io/docs/node-help'
        self.is_control_node = False
        self.is_data_node = True
        self.is_loopback_node = False
        self.can_be_muted = True
        self.is_muted = False
        self.mute_connection = ['control_in_ID', 'control_out_ID']
        self.ui_default_color = '#FFFFFF'
        self.ui_custom_color = '#000000'
        self.ui_posX = 0
        self.ui_posY = 0
        self.ui_width = 100
        self.ui_height = 100
        self.ui_width_min = -1
        self.ui_height_min = -1
        self.ui_is_collapsable = True
        self.ui_is_collapsed = False
        self.ui_is_condensable = True
        self.ui_is_condensed = False
        self.ui_is_pinned = False
        self.ui_icon = None
        self.ui_component = None
        self.allows_variables = False
    
    def get_metadata_dict(self):
        """Get current instance metadata for serialization"""
        return {attr: getattr(self, attr) for attr in self._node_metadata_attrs 
                if hasattr(self, attr)}
    
    def get_class_metadata_dict(self):
        """Get current class metadata for comparison"""
        return {attr: getattr(self.__class__, attr) for attr in self._node_metadata_attrs 
                if hasattr(self.__class__, attr)}


class ErrorNode(HaywireNode):
    """Special node to represent nodes that couldn't be loaded properly"""
    node_display_name = 'Error Node'
    node_description = 'Placeholder for node that could not be loaded'
    node_name = 'ERROR_NODE'
    node_package = 'org.github.maybites.haywire.error'
    node_version = '1.0.0'
    
    def __init__(self, node_id, graph, error_info: Dict[str, Any], 
                 original_inlets=None, original_outlets=None):
        super().__init__(node_id, graph)
        
        # Store error information
        self.error_info = error_info
        self.original_node_name = error_info.get('node_name', 'Unknown')
        self.original_package = error_info.get('node_package', 'Unknown')
        self.original_version = error_info.get('node_version', 'Unknown')
        self.error_message = error_info.get('error_message', 'Unknown error')
        
        # Preserve original inlet/outlet structure for connections
        self.original_inlets = original_inlets or []
        self.original_outlets = original_outlets or []
        
        # Override display properties
        self.node_display_name = f"ERROR: {self.original_node_name}"
        self.ui_default_color = '#FF0000'  # Red for error


# ============================================================================
# Node Discovery System
# ============================================================================

class NodeRegistry:
    """Registry for managing installed nodes"""
    
    def __init__(self):
        self.nodes: Dict[str, List[Dict[str, Any]]] = {}
    
    def register_node(self, node_class):
        """Register a node class in the registry"""
        node_name = getattr(node_class, 'node_name', node_class.__name__)
        library_name = getattr(node_class, 'node_library_name', 'Unknown')
        package_name = getattr(node_class, 'node_package', 'Unknown')
        
        if node_name not in self.nodes:
            self.nodes[node_name] = []
        
        self.nodes[node_name].append({
            'library': library_name,
            'package': package_name,
            'class': node_class,
            'version': getattr(node_class, 'node_version', '0.0.0')
        })
    
    def find_node_class(self, node_name: str, library_name: str, 
                       package_name: str) -> Dict[str, Any]:
        """
        Find the appropriate node class based on name, library, and package
        
        Returns dict with:
        - 'class': The node class to use
        - 'status': 'found' | 'warning' | 'error'
        - 'message': Status message
        """
        
        # Step 1: Check if there is a node with the same name
        if node_name not in self.nodes:
            raise NodeNotFoundError(f"No node named '{node_name}' found in registry")
        
        candidates = self.nodes[node_name]
        
        # Step 2: Filter by library
        library_matches = [n for n in candidates if n['library'] == library_name]
        
        if not library_matches:
            raise NodeNotFoundError(
                f"No node '{node_name}' found in library '{library_name}'. "
                f"Available libraries: {[n['library'] for n in candidates]}"
            )
        
        # Step 3: Filter by package
        exact_matches = [n for n in library_matches if n['package'] == package_name]
        
        if exact_matches:
            # Perfect match found
            if len(exact_matches) == 1:
                return {
                    'class': exact_matches[0]['class'],
                    'status': 'found',
                    'message': f"Exact match found for {node_name}"
                }
            else:
                # Multiple exact matches - shouldn't happen but handle gracefully
                return {
                    'class': exact_matches[0]['class'],
                    'status': 'warning',
                    'message': f"Multiple exact matches found for {node_name}, using first one"
                }
        
        # Step 4: No exact package match
        if len(library_matches) == 1:
            # Only one node in library, use it but warn about package mismatch
            return {
                'class': library_matches[0]['class'],
                'status': 'warning',
                'message': f"Package mismatch for '{node_name}' in library '{library_name}'. "
                          f"Expected: '{package_name}', Found: '{library_matches[0]['package']}'"
            }
        else:
            # Multiple nodes in library, cannot choose
            available_packages = [n['package'] for n in library_matches]
            raise NodeAmbiguousError(
                f"Multiple nodes named '{node_name}' found in library '{library_name}' "
                f"with different packages. Expected '{package_name}', "
                f"Available: {available_packages}"
            )


def find_and_validate_node(registry: NodeRegistry, saved_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find and validate node class before instantiation
    
    Returns dict with:
    - 'class': Node class to instantiate (or ErrorNode)
    - 'status': 'ok' | 'warning' | 'error'
    - 'message': Status message
    - 'version_info': Version comparison results
    """
    
    node_name = saved_metadata.get('node_name')
    library_name = saved_metadata.get('node_library_name')
    package_name = saved_metadata.get('node_package')
    saved_version = saved_metadata.get('node_version')
    
    try:
        # Step 1: Find the node class
        discovery_result = registry.find_node_class(node_name, library_name, package_name)
        node_class = discovery_result['class']
        
        # Step 2: Check version compatibility
        current_version = getattr(node_class, 'node_version', '0.0.0')
        version_info = compare_versions(saved_version, current_version)
        
        # Step 3: Determine final status
        if not version_info['compatible']:
            # Version incompatible - return ErrorNode
            error_info = {
                'node_name': node_name,
                'node_package': package_name,
                'node_version': saved_version,
                'error_message': version_info['message']
            }
            
            return {
                'class': ErrorNode,
                'status': 'error',
                'message': version_info['message'],
                'version_info': version_info,
                'error_info': error_info
            }
        
        elif version_info['action'] == 'warning' or discovery_result['status'] == 'warning':
            # Warnings but functional
            messages = []
            if version_info['action'] == 'warning':
                messages.append(version_info['message'])
            if discovery_result['status'] == 'warning':
                messages.append(discovery_result['message'])
            
            return {
                'class': node_class,
                'status': 'warning',
                'message': '; '.join(messages),
                'version_info': version_info
            }
        
        else:
            # All good
            return {
                'class': node_class,
                'status': 'ok',
                'message': 'Node loaded successfully',
                'version_info': version_info
            }
    
    except (NodeNotFoundError, NodeAmbiguousError) as e:
        # Node discovery failed - return ErrorNode
        error_info = {
            'node_name': node_name,
            'node_package': package_name,
            'node_version': saved_version,
            'error_message': str(e)
        }
        
        return {
            'class': ErrorNode,
            'status': 'error',
            'message': str(e),
            'version_info': None,
            'error_info': error_info
        }


def create_node_from_saved_data(registry: NodeRegistry, saved_data: Dict[str, Any], 
                               graph) -> Tuple[HaywireNode, Dict[str, Any]]:
    """
    Create a node instance from saved data, handling all discovery and version checking
    
    Returns: (node_instance, status_info)
    """
    
    saved_metadata = saved_data.get('metadata', {})
    
    # Find and validate the node
    validation_result = find_and_validate_node(registry, saved_metadata)
    
    node_class = validation_result['class']
    node_id = saved_data['node_id']
    
    # Create the node instance
    if node_class == ErrorNode:
        # Special handling for ErrorNode
        error_info = validation_result.get('error_info', {})
        original_inlets = saved_data.get('inlets', [])
        original_outlets = saved_data.get('outlets', [])
        
        node = ErrorNode(node_id, graph, error_info, original_inlets, original_outlets)
    else:
        # Normal node
        node = node_class(node_id, graph)
        
        # Restore UI state and other non-metadata attributes
        if 'ui_state' in saved_data:
            for ui_attr, value in saved_data['ui_state'].items():
                if hasattr(node, ui_attr):
                    setattr(node, ui_attr, value)
    
    return node, validation_result


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how the system would be used
    
    # Simulate file-level constants (normally these would be at top of the file)
    HAYWIRE_LIBRARY_NAME = "MathLibrary"
    HAYWIRE_LIBRARY_URL = "https://github.com/mathteam/mathlibrary"
    HAYWIRE_PACKAGE_NAME = "com.math.basic"
    
    # Create registry and register some example nodes
    registry = NodeRegistry()
    
    class MathAddNode(HaywireNode):
        node_display_name = 'Add Numbers'
        node_name = 'Add'
        # Note: node_library_name, node_library_url, node_package will be 
        # automatically set from HAYWIRE_* constants by the metaclass
        node_version = '2.1.0'
    
    # Different file/module would have different constants
    class StringAddNode(HaywireNode):
        node_display_name = 'Concatenate Strings'
        node_name = 'Add' 
        node_library_name = 'StringLibrary'  # Explicitly set, overrides file constant
        node_package = 'com.string.ops'      # Explicitly set, overrides file constant
        node_version = '2.5.0'
    
    registry.register_node(MathAddNode)
    registry.register_node(StringAddNode)
    
    # Test that the file constants were automatically applied
    print("MathAddNode metadata:")
    print(f"  Library: {MathAddNode.node_library_name}")  # Should be "MathLibrary"
    print(f"  Package: {MathAddNode.node_package}")       # Should be "com.math.basic"
    print(f"  URL: {MathAddNode.node_library_url}")       # Should be the GitHub URL
    
    print("\nStringAddNode metadata:")
    print(f"  Library: {StringAddNode.node_library_name}")  # Should be "StringLibrary" (explicit)
    print(f"  Package: {StringAddNode.node_package}")       # Should be "com.string.ops" (explicit)
    
    # Simulate loading a saved graph
    saved_node_data = {
        'node_id': 'node_001',
        'metadata': {
            'node_name': 'Add',
            'node_library_name': 'MathLibrary',
            'node_package': 'com.math.basic',
            'node_version': '1.0.0'  # Older version
        },
        'ui_state': {
            'ui_posX': 100,
            'ui_posY': 200
        }
    }
    
    # Load the node
    graph = None  # Mock graph object
    node, status = create_node_from_saved_data(registry, saved_node_data, graph)
    
    print(f"\nNode loaded: {node.__class__.__name__}")
    print(f"Status: {status['status']}")
    print(f"Message: {status['message']}")
    
    # Show the actual instance values
    print(f"\nLoaded node metadata:")
    print(f"  Library: {node.node_library_name}")
    print(f"  Package: {node.node_package}")
    print(f"  Version: {node.node_version}")
