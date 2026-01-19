"""
Base adapter classes for type conversion
"""

from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    Optional,
    Type,
    TypeVar,
    Union
)
from dataclasses import dataclass

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.identity import BaseIdentity
from haywire.core.library.utils import derive_library_identity, reg_key

if TYPE_CHECKING:
    from haywire.core.types.interface import IType


@dataclass
class AdapterIdentity(BaseIdentity):
    """
    Core identifying attributes of an adapter.
    
    IType-based: converts_from and converts_to are IType classes.
    """
    converts_from: type['IType'] | None = None  # Source IType (FLOAT, Temperature, etc.)
    converts_to: type['IType'] | None = None    # Target IType (INT, MeshData, etc.)
    priority: int = 0                            # Priority (higher = preferred)


# ============================================================================
#    Adapter Interface
# ============================================================================

class IAdapter(ABC):
    """
    Interface for all adapters.
    
    All adapters must implement:
    - convert(): Transform a value
    - execute(): Execute this adapter, then chain to next
    - get_registry_keys(): Get all registry keys in chain
    """

    # IDENTITY ATTRIBUTES (set by @type decorator)
    class_identity: AdapterIdentity
    class_library: LibraryIdentity
        
    @abstractmethod
    def convert(self, value: Any) -> Any:
        """Transform value"""
        pass
    
    @abstractmethod
    def execute(self, value: Any) -> Any:
        """Execute this adapter, then execute the inside chain"""
        pass

    @abstractmethod
    def _get_registry_keys(self) -> List[str]:
        """Get all registry keys in chain"""
        pass

    @abstractmethod
    def get_test_value(self) -> Any:
        """
        method returns a sample value of the type this adapter 
        is converting from for testing this adapter
        
        Returns: sample value of the expected input type
        """
        return True

    def get_test_repetitions(self) -> int:
        """method returns the number of repetitions the test needs to run"""
        return 1

    @abstractmethod
    def test(self, value: any) -> any:
        """
        Tests this adapter with sample data
        
        Args:
            value: Sample input value of the type this adapter expects
        """
        return True


# ============================================================================
#    Base Adapter Class
# ============================================================================

class ReturnAdapter(IAdapter):
    """
    Terminal adapter that returns values unchanged.
    
    Used as the default terminal adapter in chains.
    Does not have a registry key (not registered).
    """
       
    def convert(self, value: Any) -> Any:
        """Pass through unchanged"""
        return value
    
    def execute(self, value: Any) -> Any:
        """Terminal - just return value"""
        return value

    def get_test_value(self) -> any:
        """Terminal - always succeeds"""
        return True

    def test(self, value: int) -> any:
        return self.execute(value)

    def _get_registry_keys(self) -> List[str]:
        """Terminal - no registry keys"""
        return []


class BaseAdapter(IAdapter):
    """
    Base class for type adapters.
    
    Key design:
    - Type-level operations use IType classes (for registration, matching)
    - Value-level operations use unwrapped primitives/instances (for conversion)
    - Chaining via _chain attribute for recursive execution
    
    This creates clean separation between type system and runtime values.
    
    Example:
        # Register with type classes
        registry.register_adapter(
            source=Temperature,  # IType class
            target=FLOAT,        # IType class
            adapter=TemperatureToFloatAdapter
        )
        
        # Convert with unwrapped values
        adapter = TemperatureToFloatAdapter()
        result = adapter.convert(25.0)  # float -> float (not FLOAT -> FLOAT)
    """

    def __init__(self, child: Optional[IAdapter] = None):
        """Initialize adapter with child in chain"""
        self._chain: IAdapter = child if child is not None else ReturnAdapter()

    @abstractmethod
    def convert(self, value: Any) -> Any:
        """
        Value-level conversion: Convert UNWRAPPED value.
        
        This is where actual data transformation happens.
        Operates on unwrapped primitives or instances, not IType wrappers.
        
        Args:
            value: Unwrapped value from source field
                   - For primitives: 25.0 (not FLOAT(25.0))
                   - For complex: MeshData(...) instance
        
        Returns:
            Unwrapped value for target field
            - For primitives: 77.0 (not FLOAT(77.0))
            - For complex: PointCloud(...) instance
        
        Examples:
            # Primitive to primitive
            def convert(self, celsius: float) -> float:
                return (celsius * 9/5) + 32
            
            # Complex to complex
            def convert(self, mesh: MeshData) -> PointCloud:
                return PointCloud(points=mesh.vertices)
            
            # Primitive to string
            def convert(self, value: float) -> str:
                return f\"{value:.2f}\"
        """
        pass
    
    def execute(self, value: Any) -> Any:
        """
        Execute this adapter, then delegate to chain.
        
        Args:
            value: Input value (unwrapped)
            
        Returns:
            Transformed value after executing entire chain
        """
        converted = self.convert(value)
        return self._chain.execute(converted)

    def test(self, value: int) -> any:
        return self.execute(value)
        
    def _get_registry_keys(self) -> List[str]:
        """
        Get all registry keys for this adapter and any nested adapters.
        
        Base implementation returns this adapter's key plus chained keys.
        Compound adapters (ArrayArrayAdapter, StructuralAdapter) should
        override to include nested adapter keys.
        
        Returns:
            List of registry keys for hot-reload dependency tracking
        """
        keys = [self.class_identity.registry_key]
        keys.extend(self._chain._get_registry_keys())
        return keys


class ConversionError(Exception):
    """Raised when a type conversion fails"""
    pass
