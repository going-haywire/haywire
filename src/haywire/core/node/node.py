from __future__ import annotations
from typing import Any, Dict, List
from abc import abstractmethod

from .elements import Config, Inlet, Outlet


class NodeData:
    """Main data structure for a Haywire node"""
    def __init__(self):
        self.configs: Dict[str, Config] = {}
        self.inlets: Dict[str, Inlet] = {}
        self.outlets: Dict[str, Outlet] = {}
        
        # Performance optimization: direct access caches
        self._inlet_data_cache: dict[str, Any] = {}
        self._cache_dirty = True
    
    def add_config(self, config: Config) -> Config:
        """Add a configuration element"""
        self.configs[config.id] = config
        return config
    
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
            'configs': {k: v.to_dict() for k, v in self.configs.items()},
            'inlets': {k: v.to_dict() for k, v in self.inlets.items()},
            'outlets': {k: v.to_dict() for k, v in self.outlets.items()}
        }


class HaywireNode(NodeData):
    """Base class combining HaywireNode requirements with NodeData"""
    def __init__(self, node_id: str, graph: Any):
        super().__init__()
        self.node_id = node_id
        self.graph = graph
        
        # Node metadata
        self.node_name: str | None = None
        self.node_display_name: str | None = None
        self.node_package: str | None = None
        self.node_library_name: str | None = None
        self.node_library_url: str | None = None
        self.node_search_tags: list[str] = []
        self.node_menu: str | None = None
        self.node_version: str | None = None
        
        # Runtime attributes
        self.help_md: str | None = None
        self.help_url: str = 'https://haywire.io/docs/node-help'
        self.is_control_node: bool = False
        self.is_data_node: bool = True
        self.is_loopback_node: bool = False
        self.can_be_muted: bool = True
        self.is_muted: bool = False
        self.ui_default_color: str = '#FFFFFF'
        self.ui_custom_color: str = '#000000'
        self.ui_posX: int = 0
        self.ui_posY: int = 0
        self.ui_width: int = 100
        self.ui_height: int = 100
        
    @abstractmethod
    def worker(self, context: dict) -> dict | None:
        """The main execution logic of the node. Override in subclasses."""
        pass
