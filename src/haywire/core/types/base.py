"""
Type Base - Base class for all Haywire data types.

This module provides the TypeBase class which serves as the foundation for all
data types in the Haywire system, both primitive type variants and custom compound types.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..library.library_identity import LibraryIdentity
    from ..data.identity import DataPortIdentity
    from ..node.ports import PortInlet, PortOutlet


class TypeBase:
    """
    Base class for all Haywire data types.
    
    All types (primitive variants and custom compound types) inherit from this.
    Provides the interface for creating ports from types.
    
    Usage:
        # In a node:
        _ = self.add_inlet(FLOAT.as_inlet('value', default=1.0))
        _ = self.add_inlet(Temperature.as_inlet('temp', default=25.0))
        _ = self.add_inlet(MeshData.as_inlet('mesh'))
    
    Attributes (set by @type_ decorator):
        class_identity: DataPortIdentity with all type metadata
        class_library: LibraryIdentity of the library this type belongs to
    """
    
    # Set by @type_ decorator:
    class_identity: 'DataPortIdentity'
    # Set by type registration:
    class_library: 'LibraryIdentity'
    
    @classmethod
    def as_inlet(cls, id: str, **kwargs) -> 'PortInlet':
        """
        Create an inlet from this type.
        
        Args:
            id: Port identifier within the node (e.g., 'input_value')
            **kwargs: Override identity attributes or add port-specific fields
                     (default, flow_type, callback, is_pooled, etc.)
        
        Returns:
            PortInlet configured with this type's identity
        
        Example:
            FLOAT.as_inlet('value', default=1.0)
            Temperature.as_inlet('temp', default=25.0, ui={'unit': '°C'})
        """
        inlet = cls.class_identity.as_inlet(id, **kwargs)
        inlet.class_library = cls.class_library
        return inlet
    
    @classmethod
    def as_outlet(cls, id: str, **kwargs) -> 'PortOutlet':
        """
        Create an outlet from this type.
        
        Args:
            id: Port identifier within the node (e.g., 'output_result')
            **kwargs: Override identity attributes or add port-specific fields
        
        Returns:
            PortOutlet configured with this type's identity
        
        Example:
            FLOAT.as_outlet('result')
            MeshData.as_outlet('mesh')
        """
        outlet = cls.class_identity.as_outlet(id, **kwargs)
        outlet.class_library = cls.class_library
        return outlet
    
    @classmethod
    def as_config(cls, id: str, **kwargs) -> 'PortInlet':
        """
        Create a config inlet (no visible pin) from this type.
        
        Args:
            id: Config identifier within the node
            **kwargs: Override identity attributes
        
        Returns:
            PortInlet with flow_type=NONE (no visible pin)
        
        Example:
            FLOAT.as_config('threshold', default=0.5)
        """
        from ..data.enums import FlowType
        return cls.as_inlet(id, flow_type=FlowType.NONE, **kwargs)