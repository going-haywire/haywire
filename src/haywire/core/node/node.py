from __future__ import annotations
from typing import Any, Dict, List
from abc import abstractmethod
import inspect

from .elements import Inlet, Outlet


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


class NodeMetadataMeta(type):  # Assuming HaywireMeta inherits from type
    def __new__(cls, name, bases, attrs):
        # Automatically identify metadata attributes
        metadata_attrs = []
        for attr_name, attr_value in attrs.items():
            if attr_name.startswith('node_') and not callable(attr_value):
                metadata_attrs.append(attr_name)
        
        attrs['_node_metadata_attrs'] = metadata_attrs
               
        # Skip validation for abstract base classes
        # Check if this is an abstract class or the base HaywireNode class
        is_abstract = (
            name == 'HaywireNode' or  # Skip the base class itself
            attrs.get('__abstractmethods__') or  # Has abstract methods
            any(hasattr(base, '__abstractmethods__') and base.__abstractmethods__ for base in bases)  # Inherits abstract methods
        )
        
        if not is_abstract:
            # Validate that required node attributes are set
            required_attrs = [
                'node_name', 
                'node_label',
                'node_package',
                'node_library_name',
                'node_library_url',
                'node_search_tags',
                'node_menu',
                'node_version'
            ]
            
            missing_attrs = []
            for required_attr in required_attrs:
                if required_attr not in attrs:
                    missing_attrs.append(required_attr)
            
            if missing_attrs:
                # Create helpful error message
                missing_haywire = []
                for attr in missing_attrs:
                    haywire_equivalent = 'HAYWIRE_' + attr[5:].upper()  # node_library_name -> HAYWIRE_LIBRARY_NAME
                    missing_haywire.append(haywire_equivalent)
                
                raise NodeValidationError(
                    f"Node class '{name}' is missing required attributes: {missing_attrs}\n"
                    f"Either set them explicitly in the class or define these HAYWIRE constants: {missing_haywire}"
                )
        
        return super().__new__(cls, name, bases, attrs)

@abstractmethod
class NodeData():
    """Main data structure for a Haywire node"""
    def __init__(self):
        self.inlets: Dict[str, Inlet] = {}
        self.outlets: Dict[str, Outlet] = {}
        
        # Performance optimization: direct access caches
        self._inlet_data_cache: dict[str, Any] = {}
        self._cache_dirty = True
       
    def add_inlet(self, inlet: Inlet) -> Inlet:
        """Add an inlet element"""
        self.inlets[inlet.id] = inlet
        self._cache_dirty = True        
        return inlet
    
    def add_outlet(self, outlet: Outlet) -> Outlet:
        """Add an outlet element"""
        self.outlets[outlet.id] = outlet
        return outlet
    
    def get_inlet_value(self, inlet_id: str) -> Any:
        """Fast access to inlet value (cached)"""
        if self._cache_dirty:
            self._rebuild_cache()
        
        if inlet_id in self._inlet_data_cache:
            data = self._inlet_data_cache[inlet_id]
            return data.get_value()
        return None
    
    def get_inlet_values_list(self, inlet_id: str) -> List[Any]:
        """Get inlet values as list (useful for many-coupling inlets)"""
        if self._cache_dirty:
            self._rebuild_cache()
        
        if inlet_id in self._inlet_data_cache:
            data = self._inlet_data_cache[inlet_id]
            return data.get_values_list()
        return []
    
    def set_outlet_value(self, outlet_id: str, value: Any):
        """Set outlet value and propagate through pipes"""
        if outlet_id in self.outlets:
            outlet = self.outlets[outlet_id]
            if outlet.data:
                outlet.data.set_value(value)
            
            # Propagate to connected inlets through pipes
            for pipe in outlet.pipes:
                pipe.propagate(value)
    
    def _rebuild_cache(self):
        """Rebuild inlet data cache for performance"""
        self._inlet_data_cache = {
            inlet_id: inlet.data 
            for inlet_id, inlet in self.inlets.items() 
            if inlet.data
        }
        self._cache_dirty = False
    
    def get_dirty_inlets(self) -> List[str]:
        """Get list of dirty inlet IDs"""
        return [
            inlet_id for inlet_id, inlet in self.inlets.items()
            if inlet.data and inlet.data.is_dirty
        ]
    
    def mark_inlets_clean(self):
        """Mark all inlets as clean after processing"""
        for inlet in self.inlets.values():
            if inlet.data:
                inlet.data.mark_clean()
    
    def to_dict(self) -> Dict:
        """Serialize to dict structure"""
        return {
            'inlets': {k: v.to_dict() for k, v in self.inlets.items()},
            'outlets': {k: v.to_dict() for k, v in self.outlets.items()}
        }

@abstractmethod
class HaywireNode(NodeData, metaclass=NodeMetadataMeta):
    """Base class combining HaywireNode requirements with NodeData"""
    
    # Type annotation for dynamically created attribute by NodeMetadataMeta
    # This is set by the NodeMetadataMeta metaclass in __new__
    _node_metadata_attrs: list[str] = []
    def __init__(self, node_id: str, graph: Any):
        super().__init__()
        self.node_id = node_id
        self.graph = graph

        ## identifying attributes
        self.Node_label = 'Node Name'
        self.node_description = 'Node Description'
        self.node_name = 'Node_NAME'
        self.node_package = 'org.github.maybites.haywire.nodes'
        self.node_library_name = 'MathLibrary'
        self.node_library_url = 'https://haywire.io/docs/node-help'
        self.node_search_tags = ['add', 'sub', 'math', 'vector']
        self.node_menu = 'misc/custom'
        self.node_version = '0.0.0'
        self.node_author = 'Customer'
        self.node_author_url = 'https://customer.org'
        self.node_help_md = None
        self.node_help_url = 'https://haywire.io/docs/node-help'
        self.help_md = None
        self.help_url = 'https://haywire.io/docs/node-help'


        # Runtime attributes
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


    @abstractmethod
    def worker(self, context: dict) -> dict | None:
        """The main execution logic of the node. Override in subclasses."""
        pass    
           
    def get_metadata_dict(self):
        """Get current instance metadata for serialization"""
        return {attr: getattr(self, attr) for attr in self._node_metadata_attrs 
                if hasattr(self, attr)}
    
    def get_class_metadata_dict(self):
        """Get current class metadata for comparison"""
        return {attr: getattr(self.__class__, attr) for attr in self._node_metadata_attrs 
                if hasattr(self.__class__, attr)}

