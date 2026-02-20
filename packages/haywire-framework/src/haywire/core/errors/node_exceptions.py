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