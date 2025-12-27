from __future__ import annotations
from abc import ABC
from typing import Generic, TypeVar, final
from typing_extensions import Self

from .interface import IType

T = TypeVar('T')

# ============================================================================
# PRIMITIVETYPE - Wraps single primitive value
# ============================================================================

class PrimitiveType(IType, ABC, Generic[T]):
    """
    Base class for primitive type wrappers.
    
    Primitive types wrap Python built-in types (int, float, str, bool, bytes).
    The actual storage in PrimitiveField is unwrapped for performance.
    
    The wrapper serves as:
    - Type descriptor (metadata via @type decorator)
    - Interface contract (adapters work with types)
    - Default value creation
    
    Storage strategy: PrimitiveField stores unwrapped primitive (42.0 not FLOAT(42.0))
    
    AUTOMATIC element_type_cls:
    
    element_type_cls is extracted from Generic[T] parameter automatically:
        class FLOAT(PrimitiveType[float]):
            pass
        # → FLOAT.element_type_cls = float
    
    Examples:
        @type(default={'value': 12.0})
        class FLOAT(PrimitiveType[float]):
            pass
        
        # PrimitiveField will be used automatically
        FLOAT.field_class  # Returns PrimitiveField
        FLOAT.element_type_cls  # Returns float
    """
    
    # Field class set after PrimitiveField is defined
    field_class = None  # Will be set to PrimitiveField
    
    def __init_subclass__(cls, **kwargs):
        """
        Extract element_type_cls from Generic[T] parameter.
        
        Called automatically when PrimitiveType is subclassed.
        """
        super().__init_subclass__(**kwargs)
        
        # Extract T from PrimitiveType[T]
        if hasattr(cls, '__orig_bases__'):
            for base in cls.__orig_bases__:
                if hasattr(base, '__origin__'):
                    origin_name = getattr(base.__origin__, '__name__', None)
                    if origin_name == 'PrimitiveType':
                        if hasattr(base, '__args__') and base.__args__:
                            cls.element_type_cls = base.__args__[0]
                            break
    
    def __init__(self, value: T = None, **kwargs):
        """
        Initialize primitive with a value.
        
        Args:
            value: The primitive value to wrap
            **kwargs: For compatibility with create_default dict unpacking
        """
        # Handle keyword arg style from create_default
        if value is None and 'value' in kwargs:
            value = kwargs['value']
        
        # Fall back to class default
        if value is None:
            if hasattr(self.__class__, 'class_identity'):
                default_dict = getattr(self.__class__.class_identity, 'default', None)
                if isinstance(default_dict, dict):
                    value = default_dict.get('value')
        
        if value is None:
            raise TypeError(
                f"{self.__class__.__name__}() missing required argument: 'value'"
            )
        
        self._value: T = value
    
    @property
    @final
    def value(self) -> T:
        """Returns the wrapped primitive value."""
        return self._value
    
    @value.setter
    @final
    def value(self, val: T):
        """Sets the wrapped primitive value."""
        self._value = val


# ============================================================================
# BASETYPE - Custom complex types
# ============================================================================

class BaseType(IType, ABC):
    """
    Base class for custom complex data types.
    
    Complex types are user-defined dataclasses or classes that represent
    structured data (e.g., MeshData, Vector3, Transform).
    
    Storage strategy: BaseField stores the instance directly (instance IS the value)
    
    Key insight: For BaseType, value property returns self because
    the instance itself is the data container.
    
    AUTOMATIC element_type_cls:
    
    element_type_cls is set to the class itself automatically:
        class MeshData(BaseType):
            pass
        # → MeshData.element_type_cls = MeshData
    
    Examples:
        @type(default={'vertices': [], 'faces': []})
        @dataclass
        class MeshData(BaseType):
            vertices: list
            faces: list
        
        # BaseField will be used automatically
        MeshData.field_class  # Returns BaseField
        MeshData.element_type_cls  # Returns MeshData
    """
    
    # Field class set after BaseField is defined
    field_class = None  # Will be set to BaseField
    
    def __init_subclass__(cls, **kwargs):
        """
        Set element_type_cls to self for complex types.
        
        Called automatically when BaseType is subclassed.
        """
        super().__init_subclass__(**kwargs)
        # The class IS the element type
        cls.element_type_cls = cls
    
    @property
    def value(self):
        """
        Returns self - the instance IS the value.
        
        Unlike PrimitiveType which wraps a primitive,
        BaseType instances are themselves the data.
        """
        return self


# ============================================================================
# COMPOUNDTYPE - Collections with element types
# ============================================================================

class CompoundType(BaseType, ABC, Generic[T]):
    """
    Abstract base for compound/collection types.
    
    Compound types hold multiple elements of a specific type.
    They track element_type_cls for type safety and adapter support.
    
    Storage strategy: CompoundField subclasses store unwrapped elements
    
    HIERARCHICAL element_type_cls:
    
    element_type_cls is set during parameterization to the IType:
        ArrayType[FLOAT].element_type_cls → FLOAT
        ArrayType[FLOAT].element_type_cls.element_type_cls → float
    
    This creates a two-level hierarchy for drilling down to Python types.
    
    Type parameterization via __class_getitem__:
        ArrayType[FLOAT].as_inlet(id='numbers')
        PooledType[MeshData].as_inlet(id='meshes')
    
    Subclasses must:
    - Define field_class (ArrayField, PooledField, etc.)
    - Can override _validate_port_type() to restrict inlet/outlet
    - Can override _configure_port() to add port attributes
    
    Examples:
        @type(default={'value': []})
        class ArrayType(CompoundType[T]):
            field_class = ArrayField
        
        # Usage with type parameterization:
        ArrayType[FLOAT].as_inlet(id='numbers')
        # → element_type_cls = FLOAT
        
        # Or explicit element_type_cls:
        ArrayType.as_inlet(id='numbers', element_type_cls=FLOAT)
    """
    
    # Subclasses MUST override field_class
    field_class = None
    
    @classmethod
    def __class_getitem__(cls, element_type_cls: type[IType]):
        """
        Enable type parameterization syntax: CompoundType[ElementType]
        
        This is the standard Python way to create generic-like syntax
        (same as typing.List[int], typing.Dict[str, int], etc.)
        
        Python calls when you use square brackets on a class.
        
        Args:
            element_type_cls: The type of elements (FLOAT, MeshData, etc.)
        
        Returns:
            A class-like object that remembers element_type_cls and
            provides as_inlet/as_outlet/as_config methods
        
        Examples:
            ArrayType[FLOAT]  # Calls ArrayType.__class_getitem__(FLOAT)
            # Returns _ParameterizedCompound with FLOAT remembered
            
            ArrayType[FLOAT].as_inlet('numbers')
            # Calls _ParameterizedCompound.as_inlet('numbers')
            # Which calls ArrayType.as_inlet('numbers', element_type_cls=FLOAT)
        """

        # Store parent class and element type for use in methods
        _parent_cls = cls
        _element_type_cls = element_type_cls
        
        class _ParameterizedCompound(cls):  # Inherit from parent CompoundType!
            """
            Parameterized version that remembers element_type_cls.
            
            CRITICAL: Must inherit from cls (the CompoundType subclass) so that
            ArrayType(CompoundType[T]) properly inherits the full type hierarchy
            including IType for decorator validation.
            
            Created by __class_getitem__ to enable clean syntax:
                ArrayType[FLOAT].as_inlet(id='numbers')
            
            The element_type_cls is stored as a class attribute and passed
            to port creation methods automatically.
            
            Note: class_identity, class_library, and field_class are inherited
            from the parent cls automatically through Python's attribute lookup.
            """
            
            @classmethod
            def as_inlet(cls_inner, id: str, **kwargs):
                """
                Create inlet with remembered element_type_cls.
                
                Called by: ArrayType[FLOAT].as_inlet('numbers')
                Injects: element_type_cls=FLOAT
                
                Note: We must use __func__ to bypass MRO because _parent_cls itself
                may inherit from _ParameterizedCompound, which would cause recursion.
                """
                # Remove element_type_cls from kwargs if present to avoid conflict
                kwargs.pop('element_type_cls', None)
                # Call IType.as_inlet directly, passing parent class explicitly
                return IType.as_inlet.__func__(_parent_cls, id, element_type_cls=_element_type_cls, **kwargs)
            
            @classmethod
            def as_outlet(cls_inner, id: str, **kwargs):
                """
                Create outlet with remembered element_type_cls.
                
                Called by: ArrayType[FLOAT].as_outlet('result')
                Injects: element_type_cls=FLOAT
                """
                # Remove element_type_cls from kwargs if present to avoid conflict
                kwargs.pop('element_type_cls', None)
                # Call IType.as_outlet directly, passing parent class explicitly
                return IType.as_outlet.__func__(_parent_cls, id, element_type_cls=_element_type_cls, **kwargs)
            
            @classmethod
            def as_config(cls_inner, id: str, **kwargs):
                """
                Create config with remembered element_type_cls.
                
                Called by: ArrayType[FLOAT].as_config('params')
                Injects: element_type_cls=FLOAT
                """
                # Remove element_type_cls from kwargs if present to avoid conflict
                kwargs.pop('element_type_cls', None)
                # Call IType.as_config directly, passing parent class explicitly
                return IType.as_config.__func__(_parent_cls, id, element_type_cls=_element_type_cls, **kwargs)
        
        return _ParameterizedCompound

