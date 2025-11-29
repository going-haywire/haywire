"""
Port Creation Helpers - Pooled and ArrayList

This module provides helper classes for creating pooled and array ports
with a clean API similar to Type.as_inlet()/as_outlet().
"""

from dataclasses import asdict
from typing import Any, Dict, Optional

from haywire.core.types.interface import IType
from haywire.core.types.ports import PortInlet, PortOutlet


class Pooled:
    """
    Helper for creating pooled inlets.
    
    Pooled inlets aggregate data from multiple upstream nodes,
    storing each source separately by node ID.
    
    Usage:
        self.add(Pooled.as_inlet(
            element_type_cls=FLOAT,
            id='float_pool',
            label='Aggregated Values'
        ))
    
    Note: Pooled outlets are not supported - pooled fields are inlet-only.
    """
    
    @staticmethod
    def as_inlet(element_type_cls: type[IType], id: str, **kwargs) -> PortInlet:
        """
        Create a pooled inlet for a specific element type.
        
        Args:
            element_type_cls: Type of elements in the pool (FLOAT, MeshData, etc.)
            id: Port identifier within the node
            **kwargs: Additional port configuration (label, ui, etc.)
        
        Returns:
            PortInlet configured as pooled field
        
        Examples:
            # Pooled primitive inlet
            Pooled.as_inlet(
                element_type_cls=FLOAT,
                id='temperatures',
                label='Temperature Readings'
            )
            
            # Pooled complex type inlet
            Pooled.as_inlet(
                element_type_cls=MeshData,
                id='mesh_collection',
                label='Mesh Pool'
            )
        """
        # Inherit identity from element type (color, icon, etc.)
        element_identity = asdict(element_type_cls.class_identity)
        
        # Create port kwargs
        port_kwargs = {
            **element_identity,  # Inherit visual properties
            'id': id,
            'is_pooled': True,
            **kwargs  # User overrides
        }
        
        # Remove fields that don't apply to pooled
        port_kwargs.pop('default', None)  # Pooled has no default value
        
        # Create the inlet
        port = PortInlet(**port_kwargs)
        port.element_type_cls = element_type_cls
        
        # Store creation recipe for serialization
        if element_type_cls.class_identity.registry_key:
            port._creation_recipe = {
                'registry_key': 'core:special:pooled',  # Special marker
                'method': 'as_inlet',
                'kwargs': {
                    'id': id,
                    'element_type_registry_key': element_type_cls.class_identity.registry_key,
                    **kwargs
                }
            }
        
        return port


class ArrayList:
    """
    Helper for creating array inlets and outlets.
    
    Array ports handle homogeneous lists of a specific type,
    with type checking and efficient unwrapped storage.
    
    Usage:
        # Array inlet
        self.add(ArrayList.as_inlet(
            element_type_cls=FLOAT,
            id='numbers',
            default=[1.0, 2.0, 3.0]
        ))
        
        # Array outlet
        self.add(ArrayList.as_outlet(
            element_type_cls=FLOAT,
            id='sorted_numbers'
        ))
    """
    
    @staticmethod
    def as_inlet(
        element_type_cls: type[IType], 
        id: str, 
        default: Optional[Any] = None,
        **kwargs
    ) -> PortInlet:
        """
        Create an array inlet for a specific element type.
        
        Args:
            element_type_cls: Type of array elements (FLOAT, MeshData, etc.)
            id: Port identifier within the node
            default: Default array value (list or dict with 'value' key)
            **kwargs: Additional port configuration
        
        Returns:
            PortInlet configured as array field
        
        Examples:
            # Array of primitives with default
            ArrayList.as_inlet(
                element_type_cls=FLOAT,
                id='numbers',
                default=[1.0, 2.0, 3.0]
            )
            
            # Array of complex types (empty default)
            ArrayList.as_inlet(
                element_type_cls=MeshData,
                id='mesh_array',
                default=[]
            )
        """
        # Auto-wrap default if it's a plain list
        if default is not None:
            if isinstance(default, list):
                default = {'value': default}
            elif not isinstance(default, dict):
                raise ValueError(
                    f"ArrayList default must be a list or dict with 'value' key, "
                    f"got {type(default).__name__}"
                )
        
        # Inherit identity from element type
        element_identity = asdict(element_type_cls.class_identity)
        
        # Create port kwargs
        port_kwargs = {
            **element_identity,  # Inherit visual properties
            'id': id,
            'is_array': True,
            **kwargs  # User overrides
        }
        
        # Add default if provided
        if default is not None:
            port_kwargs['default'] = default
        
        # Create the inlet
        port = PortInlet(**port_kwargs)
        port.element_type_cls = element_type_cls
        
        # Mark as array
        port.is_array = True
        
        # Store creation recipe for serialization
        if element_type_cls.class_identity.registry_key:
            recipe_kwargs = {'id': id, **kwargs}
            if default is not None:
                recipe_kwargs['default'] = default
            
            port._creation_recipe = {
                'registry_key': 'core:special:array',  # Special marker
                'method': 'as_inlet',
                'kwargs': {
                    **recipe_kwargs,
                    'element_type_registry_key': element_type_cls.class_identity.registry_key
                }
            }
        
        return port
    
    @staticmethod
    def as_outlet(element_type_cls: type[IType], id: str, **kwargs) -> PortOutlet:
        """
        Create an array outlet for a specific element type.
        
        Args:
            element_type_cls: Type of array elements (FLOAT, MeshData, etc.)
            id: Port identifier within the node
            **kwargs: Additional port configuration
        
        Returns:
            PortOutlet configured as array field
        
        Examples:
            ArrayList.as_outlet(
                element_type_cls=FLOAT,
                id='sorted_numbers'
            )
        """
        # Inherit identity from element type
        element_identity = asdict(element_type_cls.class_identity)
        
        # Create port kwargs
        port_kwargs = {
            **element_identity,  # Inherit visual properties
            'id': id,
            'is_array': True,
            **kwargs  # User overrides
        }
        
        # Create the outlet
        port = PortOutlet(**port_kwargs)
        port.element_type_cls = element_type_cls
        
        # Mark as array
        port.is_array = True
        
        # Store creation recipe for serialization
        if element_type_cls.class_identity.registry_key:
            port._creation_recipe = {
                'registry_key': 'core:special:array',  # Special marker
                'method': 'as_outlet',
                'kwargs': {
                    'id': id,
                    'element_type_registry_key': element_type_cls.class_identity.registry_key,
                    **kwargs
                }
            }
        
        return port