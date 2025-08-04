"""
Node registry and discovery system for the Haywire library system.

This module contains the node registry and discovery functionality
for managing nodes across multiple libraries.
"""

import re
from typing import Dict, List, Optional, Tuple, Any

# Import core node classes from their proper location
from haywire.core.node.node import HaywireNode


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


class NodeValidationError(NodeDiscoveryError):
    """Node class is missing required attributes"""
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
        'saved_version': tuple,
        'current_version': tuple,
        'status': 'exact' | 'compatible' | 'warning' | 'incompatible',
        'message': str
    }
    """
    try:
        saved_tuple = parse_version(saved_version)
        current_tuple = parse_version(current_version)
    except ValueError as e:
        return {
            'compatible': False,
            'saved_version': None,
            'current_version': None,
            'status': 'incompatible',
            'message': str(e)
        }
    
    if saved_tuple == current_tuple:
        return {
            'compatible': True,
            'saved_version': saved_tuple,
            'current_version': current_tuple,
            'status': 'exact',
            'message': f"Exact version match: {saved_version}"
        }
    
    saved_major, saved_minor, saved_bugfix = saved_tuple
    current_major, current_minor, current_bugfix = current_tuple
    
    # Major version compatibility
    if saved_major != current_major:
        return {
            'compatible': False,
            'saved_version': saved_tuple,
            'current_version': current_tuple,
            'status': 'incompatible',
            'message': f"Major version mismatch: saved {saved_version}, current {current_version}"
        }
    
    # Minor version compatibility
    if saved_minor > current_minor:
        return {
            'compatible': False,
            'saved_version': saved_tuple,
            'current_version': current_tuple,
            'status': 'incompatible',
            'message': f"Saved version requires newer minor version: saved {saved_version}, current {current_version}"
        }
    
    if saved_minor < current_minor:
        return {
            'compatible': True,
            'saved_version': saved_tuple,
            'current_version': current_tuple,
            'status': 'compatible',
            'message': f"Compatible: current version is newer: saved {saved_version}, current {current_version}"
        }
    
    # Same major.minor, different bugfix
    return {
        'compatible': True,
        'saved_version': saved_tuple,
        'current_version': current_tuple,
        'status': 'compatible',
        'message': f"Compatible bugfix difference: saved {saved_version}, current {current_version}"
    }


# ============================================================================
# Error Node (specific to discovery system)
# ============================================================================


class ErrorNode(HaywireNode):
    """Special node to represent nodes that couldn't be loaded properly"""
    
    node_display_name = 'Error Node'
    node_description = 'Placeholder for node that could not be loaded'
    node_name = 'ERROR_NODE'
    node_package = 'org.github.maybites.haywire.error'
    node_library_name = 'Haywire System'
    node_library_url = 'https://haywire.io/docs/error-nodes'
    node_search_tags = ['error', 'system', 'placeholder']
    node_menu = 'system/error'
    node_version = '1.0.0'
    node_author = 'Haywire System'
    node_author_url = 'https://haywire.io'
    
    def __init__(self, node_id, graph, error_info: Dict[str, Any], 
                 original_inlets=None, original_outlets=None):
        super().__init__(node_id, graph)
        
        # Store error information
        self.error_info = error_info
        self.original_node_name = error_info.get('node_name', 'Unknown')
        self.original_package_name = error_info.get('node_package', 'Unknown')
        self.original_version = error_info.get('node_version', 'Unknown')
        self.error_message = error_info.get('error_message', 'Unknown error')
        
        # Preserve original inlet/outlet structure for connections
        self.original_inlets = original_inlets or []
        self.original_outlets = original_outlets or []
        
        # Override display properties
        self.node_display_name = f"ERROR: {self.original_node_name}"
        self.ui_default_color = '#FF0000'  # Red for error


# ============================================================================
# Node Registry
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
            'package_name': package_name,
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
        exact_matches = [n for n in library_matches if n['package_name'] == package_name]
        
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
                          f"Expected: '{package_name}', Found: '{library_matches[0]['package_name']}'"
            }
        else:
            # Multiple nodes in library, cannot choose
            available_packages = [n['package_name'] for n in library_matches]
            raise NodeAmbiguousError(
                f"Multiple nodes named '{node_name}' found in library '{library_name}' "
                f"with different packages. Expected '{package_name}', "
                f"Available: {available_packages}"
            )


# ============================================================================
# Node Discovery Functions
# ============================================================================

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
    saved_version = saved_metadata.get('node_version', '0.0.0')
    
    if not all([node_name, library_name, package_name]):
        error_info = {
            'node_name': node_name or 'Unknown',
            'node_package': package_name or 'Unknown',
            'node_version': saved_version,
            'error_message': 'Missing required metadata (node_name, node_library_name, or node_package)'
        }
        
        return {
            'class': ErrorNode,
            'status': 'error',
            'message': 'Missing required metadata',
            'version_info': None,
            'error_info': error_info
        }
    
    try:
        # Find the node class
        find_result = registry.find_node_class(node_name, library_name, package_name)
        node_class = find_result['class']
        
        # Check version compatibility
        current_version = getattr(node_class, 'node_version', '0.0.0')
        version_info = compare_versions(saved_version, current_version)
        
        if not version_info['compatible']:
            # Version incompatible - use ErrorNode
            error_info = {
                'node_name': node_name,
                'node_package': package_name,
                'node_version': saved_version,
                'error_message': f"Version incompatible: {version_info['message']}"
            }
            
            return {
                'class': ErrorNode,
                'status': 'error',
                'message': version_info['message'],
                'version_info': version_info,
                'error_info': error_info
            }
        
        # Success - return the found node class
        status = 'ok' if version_info['status'] == 'exact' else 'warning'
        message = find_result['message']
        if version_info['status'] != 'exact':
            message += f" (Version: {version_info['message']})"
        
        return {
            'class': node_class,
            'status': status,
            'message': message,
            'version_info': version_info
        }
        
    except (NodeNotFoundError, NodeAmbiguousError, NodeVersionError) as e:
        # Node discovery failed - use ErrorNode
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
        # Normal node creation
        node = node_class(node_id, graph)
    
    return node, validation_result


def serialize_node(node: HaywireNode) -> Dict[str, Any]:
    """
    Serialize a node instance to dictionary for saving
    Uses the get_metadata_dict() method
    """
    return {
        'node_id': node.node_id,
        'metadata': node.get_metadata_dict(),
        'ui_properties': {
            'posX': node.ui_posX,
            'posY': node.ui_posY,
            'width': node.ui_width,
            'height': node.ui_height,
            'is_collapsed': node.ui_is_collapsed,
            'is_condensed': node.ui_is_condensed,
            'is_pinned': node.ui_is_pinned,
            'custom_color': node.ui_custom_color
        }
    }
