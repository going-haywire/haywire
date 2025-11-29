from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from typing_extensions import Self

if TYPE_CHECKING:
    from ..adapter.base import BaseAdapter
    from ..adapter.registry import AdapterRegistry
    from ..library.identity import LibraryIdentity
    from ..types.identity import DataTypeIdentity

class IType(ABC):
    """
    Interface for all Haywire data types.
    """

    # Set by @type decorator:
    class_identity: 'DataTypeIdentity'
    class_library: 'LibraryIdentity'

    @abstractmethod
    def is_value_type(self, compare: type) -> bool:
        """
        Check if the value is an instance of the given type.

        Args:
            compare: Type to check against

        Returns:
            True if value is an instance of compare
        """
        pass

    @abstractmethod
    def has_adapter(self, type_cls: type[IType], adapter_registry: AdapterRegistry) -> bool:
        """
        Check if this type has an adapter to the specified type.

        Args:
            type_cls: Target TypeBase subclass to check for adapter 
        Returns:
            True if an adapter exists, False otherwise
        """
        pass

    @abstractmethod
    def get_adapter(self, type_cls: type[IType], adapter_registry: AdapterRegistry) -> BaseAdapter:
        """
        Get an adapter instance to convert this type to the specified type.

        Args:
            type_cls: Target TypeBase subclass to adapt to  
        Returns:
            Adapter instance for the conversion
        """
        pass

    @classmethod
    @abstractmethod
    def create_default(cls) -> Self:
        """Create a default instance of this type."""
        pass