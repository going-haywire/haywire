from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional
from typing_extensions import Self

if TYPE_CHECKING:
    from ..adapter.base import BaseAdapter
    from ..adapter.registry import AdapterRegistry
    from ..library.identity import LibraryIdentity
    from ..types.identity import DataTypeIdentity
    from ..data.fields import DataField
    from ..types.ports import DataPort



# ============================================================================
# ROOT INTERFACE WITH SHARED IMPLEMENTATIONS
# ============================================================================

class IType(ABC):
    """
    Abstract base for Haywire type system.
    
    ARCHITECTURE:
    
    Type System (IType):
        - Describes data types (metadata, ports, adapters)
        - Can be instantiated for adapters and defaults
        - Instances are TEMPLATES, not runtime storage
    
    Storage System (DataField):
        - Stores actual runtime data efficiently
        - Uses unwrapped values for primitives
        - Uses instances for complex types
    
    TWO PATTERNS:
    
    1. PRIMITIVES (FLOAT, INT, STRING)
       - Type: FLOAT class (descriptor)
       - Instance: FLOAT(value=42.0) (template for adapters/defaults)
       - Storage: 42.0 (unwrapped in PrimitiveField)
    
    2. COMPLEX (MeshData, Vector3)
       - Type: MeshData class (descriptor AND data container)
       - Instance: MeshData(...) (descriptor instance IS the data)
       - Storage: MeshData(...) instance (in BaseField)
    
    The .value property provides uniform interface:
    - PrimitiveType.value → unwrapped primitive
    - BaseType.value → self (instance is the value)
    
    HIERARCHICAL TYPE SYSTEM:
    
    element_type_cls creates a hierarchical structure:
    - PrimitiveType: Points to Python primitive (float, str, int, bool)
    - BaseType: Points to itself (the class IS the element type)
    - CompoundType: Points to IType of elements (FLOAT, MeshData)
    
    This enables drilling down through type layers:
        ArrayType[FLOAT].element_type_cls → FLOAT
        FLOAT.element_type_cls → float
    
    **Abstract Requirements** (subclasses must implement):
    - value property: Returns the type's data in natural form
    
    **Concrete Defaults** (subclasses inherit, can override):
    - as_inlet/as_outlet/as_config: Port creation methods
    - create_field: DataField creation
    - _validate_port_type: Port type validation hook (default: allow all)
    - _configure_port: Port configuration hook (default: no config)
    
    **Class Attributes** (subclasses must set):
    - field_class: DataField class that handles storage
    - element_type_cls: What this type wraps/contains (set automatically)
    
    This follows Python's ABC pattern where base classes provide both
    abstract requirements and concrete default implementations.
    
    Attributes (set by @type decorator):
        class_identity: DataTypeIdentity with all type metadata
        class_library: LibraryIdentity of the library this type belongs to
    """
    
    # STRUCTURAL ATTRIBUTES (type system mechanics)
    field_class: type['DataField'] = None
    element_type_cls: type = None  # What this type wraps/contains
    
    # IDENTITY ATTRIBUTES (set by @type decorator)
    class_identity: 'DataTypeIdentity'
    class_library: 'LibraryIdentity'
    
    @property
    @abstractmethod
    def value(self):
        """
        Returns the value of this type in its natural form.
        
        For PrimitiveType: returns the unwrapped primitive (42.0, "hello")
        For BaseType: returns self (the instance IS the value)
        For CompoundType: returns the container (list, dict, etc.)
        """
        pass
    
    # ========================================================================
    # FIELD CREATION - Type creates its own field
    # ========================================================================
    
    @classmethod
    def create_field(
        cls,
        element_type_cls: Optional[type['IType']] = None,
        default_override: Optional[Dict[str, Any]] = None
    ) -> 'DataField':
        """
        Create the DataField for this type.
        
        Each type is responsible for creating its own field instance.
        This replaces the DataFieldFactory pattern - types know what they need!
        
        Args:
            element_type_cls: For compound types, the element type
            default_override: Override default kwargs from @type decorator
        
        Returns:
            Configured DataField instance
        
        Raises:
            ValueError: If field_class not declared or invalid parameters
        
        Examples:
            # Simple type
            field = FLOAT.create_field()
            
            # Compound type
            field = ArrayType.create_field(element_type_cls=FLOAT)
        """
        if not cls.field_class:
            raise ValueError(
                f"{cls.__name__} doesn't declare field_class. "
                f"Add 'field_class = SomeField' to the type definition."
            )
        
        # Get default kwargs
        default_kwargs = default_override or {}
        if not default_kwargs and hasattr(cls, 'class_identity'):
            default_kwargs = getattr(cls.class_identity, 'default', {})
        
        # Import here to avoid circular imports
        from haywire.core.types.base import CompoundType, PrimitiveType, BaseType
        
        # Create field based on type category
        if issubclass(cls, CompoundType):
            # Compound types require element_type_cls
            if not element_type_cls:
                raise ValueError(
                    f"CompoundType {cls.__name__} requires element_type_cls. "
                    f"Use: {cls.__name__}[ElementType].as_inlet(...)"
                )
            
            return cls.field_class(
                element_type_cls=element_type_cls,
                default_kwargs=default_kwargs
            )
        
        elif issubclass(cls, (PrimitiveType, BaseType)):
            # Simple types
            return cls.field_class(
                type_cls=cls,
                default_kwargs=default_kwargs
            )
        
        else:
            raise TypeError(f"Unknown type category for {cls.__name__}")
    
    # ========================================================================
    # HOOKS - Subclasses override to customize behavior
    # ========================================================================
    
    @classmethod
    def _validate_port_type(cls, port_type: str) -> None:
        """
        Validate if this type supports the given port type.
        
        Hook for subclasses to restrict which port types they support.
        Default implementation allows all port types.
        
        Args:
            port_type: 'inlet', 'outlet', or 'config'
        
        Raises:
            ValueError: If this type doesn't support the port type
        
        Examples:
            # Override to restrict
            class PooledType(CompoundType):
                @classmethod
                def _validate_port_type(cls, port_type: str):
                    if port_type == 'outlet':
                        raise ValueError("PooledType only supports inlets")
        """
        pass  # Default: all port types allowed
    
    @classmethod
    def _configure_port(cls, port: 'DataPort', **context) -> None:
        """
        Configure port-specific attributes after creation.
        
        Hook for subclasses to add custom port configuration.
        Default implementation does nothing.
        
        Args:
            port: Port to configure
            **context: Additional context (element_type_cls, etc.)
        
        Examples:
            # Override to configure
            class PooledType(CompoundType):
                @classmethod
                def _configure_port(cls, port, **context):
                    port.allow_multiple_connections = True
        """
        pass  # Default: no extra configuration
    
    # ========================================================================
    # PORT CREATION - Universal implementation for all types
    # ========================================================================
    
    @classmethod
    def as_inlet(cls, id: str, element_type_cls: Optional[type['IType']] = None, **kwargs):
        """
        Create an inlet from this type.
        
        Universal implementation that works for all type categories:
        - PrimitiveType: FLOAT.as_inlet('value', default=0.0)
        - BaseType: MeshData.as_inlet('mesh', default={...})
        - CompoundType: Uses parameterized syntax (see below)
        
        For CompoundType, use parameterized syntax:
            ArrayType[FLOAT].as_inlet('numbers')
            PooledType[MeshData].as_inlet('meshes')
        
        Or pass element_type_cls explicitly:
            ArrayType.as_inlet('numbers', element_type_cls=FLOAT)
        
        Args:
            id: Port identifier
            element_type_cls: For compound types, the element type
            **kwargs: Override identity attributes or add port-specific fields
        
        Returns:
            PortInlet configured with this type's identity and data field
        
        Examples:
            FLOAT.as_inlet('value', default=1.0)
            ArrayType[FLOAT].as_inlet('numbers', default=[1.0, 2.0])
            PooledType[FLOAT].as_inlet('values')
        """
        from haywire.core.types.ports import PortInlet
        from haywire.core.types.utils import create_port_from_type
        
        # Validate port type
        cls._validate_port_type('inlet')
        
        # Create port (field created in __post_init__ via type.create_field())
        port = create_port_from_type(
            type_cls=cls,
            port_cls=PortInlet,
            id=id,
            element_type_cls=element_type_cls,
            **kwargs
        )
        
        # Let subclass configure
        cls._configure_port(port, element_type_cls=element_type_cls)
        
        return port
    
    @classmethod
    def as_outlet(cls, id: str, element_type_cls: Optional[type['IType']] = None, **kwargs):
        """
        Create an outlet from this type.
        
        Universal implementation that works for all type categories.
        See as_inlet() for usage examples.
        
        Args:
            id: Port identifier
            element_type_cls: For compound types, the element type
            **kwargs: Override identity attributes
        
        Returns:
            PortOutlet configured with this type's identity and data field
        
        Examples:
            FLOAT.as_outlet('result')
            ArrayType[FLOAT].as_outlet('sorted')
        """
        from haywire.core.types.ports import PortOutlet
        from haywire.core.types.utils import create_port_from_type
        
        # Validate port type
        cls._validate_port_type('outlet')
        
        # Create port
        port = create_port_from_type(
            type_cls=cls,
            port_cls=PortOutlet,
            id=id,
            element_type_cls=element_type_cls,
            **kwargs
        )
        
        # Let subclass configure
        cls._configure_port(port, element_type_cls=element_type_cls)
        
        return port
    
    @classmethod
    def as_config(cls, id: str, element_type_cls: Optional[type['IType']] = None, **kwargs):
        """
        Create a config inlet (no visible pin) from this type.
        
        Config inlets are internal parameters that don't show as connection pins.
        
        Args:
            id: Config identifier
            element_type_cls: For compound types, the element type
            **kwargs: Override identity attributes
        
        Returns:
            PortInlet with flow_type=NONE (no visible pin)
        
        Examples:
            FLOAT.as_config('threshold', default=0.5)
            ArrayType[STRING].as_config('tags', default=['a', 'b'])
        """
        from haywire.core.data.enums import FlowType
        kwargs['flow_type'] = FlowType.NONE
        return cls.as_inlet(id, element_type_cls=element_type_cls, **kwargs)
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def has_adapter(self, type_cls: type['IType'], adapter_registry: AdapterRegistry) -> bool:
        """Check if adapter exists to convert to target type"""
        return adapter_registry.has_adapter(type(self), type_cls)
    
    def get_adapter(self, type_cls: type['IType'], adapter_registry: AdapterRegistry) -> BaseAdapter:
        """Get adapter to convert to target type"""
        return adapter_registry.get_adapter(type(self), type_cls)
    
    def is_value_type(self, compare: type) -> bool:
        """Check if the value is of a specific type"""
        return isinstance(self.value, compare)
    
    @classmethod
    def create_default(cls):
        """
        Create a default instance.
        
        Default implementation uses the 'default' dict from @type decorator
        as constructor kwargs. Override this method for complex default logic.
        
        Returns:
            New instance with default values
        """
        default_kwargs = getattr(cls.class_identity, 'default', None) if hasattr(cls, 'class_identity') else None
        if default_kwargs is None:
            default_kwargs = {}
        
        try:
            return cls(**default_kwargs)
        except Exception as e:
            raise TypeError(
                f"Cannot create default instance of {cls.__name__} using default={default_kwargs}. "
                f"Consider overriding create_default() classmethod. "
                f"Original error: {e}"
            ) from e

