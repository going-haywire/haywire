"""
AdapterRegistry - IType-to-IType conversion registry with chain support
"""

import inspect
from collections import deque
from typing import Optional

from ..library.identity import LibraryIdentity
from ..registry.base import BaseRegistry
from ..types.interface import IType
from .base import AdapterIdentity, BaseAdapter


class AdapterRegistry(BaseRegistry):
    """
    Registry for IType-to-IType conversion adapters.
    
    Design:
    - Stores adapters by (source_itype, target_itype) tuple
    - Supports adapter chains for multi-hop conversions
    - Handles priority when multiple adapters exist
    - IType-only (no mixing with Python types)
    
    Examples:
        # Register adapter
        registry.register_class(TempToFloatAdapter)
        
        # Check direct adapter
        registry.has_adapter(Temperature, FLOAT)  # True
        
        # Find adapter chain
        chain = registry.find_adapter_chain(Temperature, INT)
        # Returns: [TempToFloatAdapter, FloatToIntAdapter]
    """

    def __init__(self):
        super().__init__()
        # Key: (source_itype, target_itype)
        # Value: list of adapter classes (sorted by priority)
        self._adapters: dict[
            tuple[type[IType], type[IType]],
            list[type[BaseAdapter]]
        ] = {}

    def _class_filter(self, cls):
        """Check if a class is a valid Haywire adapter class."""
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, BaseAdapter)
                and cls != BaseAdapter
                and hasattr(cls, 'class_identity')
            )
        except TypeError:
            return False

    def _register_class(
        self,
        adapter_cls: type[BaseAdapter],
        library_identity: Optional[LibraryIdentity] = None
    ) -> str | None:
        """
        Register adapter class.
        
        Validates that converts_from/converts_to are ITypes,
        then stores by type pair with priority sorting.
        
        Args:
            adapter_cls: The adapter class to register
            library_identity: Optional library metadata
            
        Returns:
            str: The registry_key of the registered adapter
            
        Raises:
            TypeError: If converts_from/to are not IType subclasses
        """
        identity = adapter_cls.class_identity
        source_itype = identity.converts_from
        target_itype = identity.converts_to
        
        # Validate ITypes
        if source_itype and not issubclass(source_itype, IType):
            raise TypeError(
                f"Adapter {adapter_cls.__name__} converts_from must be "
                f"IType subclass, got {source_itype}"
            )
        
        if target_itype and not issubclass(target_itype, IType):
            raise TypeError(
                f"Adapter {adapter_cls.__name__} converts_to must be "
                f"IType subclass, got {target_itype}"
            )
        
        # Add to type-based lookup (with priority sorting)
        key = (source_itype, target_itype)
        if key not in self._adapters:
            self._adapters[key] = []
        
        # Insert sorted by priority (higher priority first)
        adapters = self._adapters[key]
        priority = identity.priority
        
        # Find insertion point
        insert_idx = 0
        for i, existing in enumerate(adapters):
            if priority > existing.class_identity.priority:
                insert_idx = i
                break
            insert_idx = i + 1
        
        adapters.insert(insert_idx, adapter_cls)
        
        # Register with base registry
        registry_key = identity.registry_key
        return super()._register(registry_key, adapter_cls, library_identity)

    def _unregister_class(
        self,
        registry_key: str
    ) -> type[BaseAdapter] | None:
        """
        Unregister an adapter by its registry_key.
        
        Args:
            registry_key: The registry_key of the adapter to unregister
            
        Returns:
            type[BaseAdapter] | None: Unregistered adapter or None
        """
        adapter_class = self._classes.get(registry_key)
        if not adapter_class:
            return None
        
        # Remove from type-based lookup
        identity = adapter_class.class_identity
        key = (identity.converts_from, identity.converts_to)
        
        if key in self._adapters:
            try:
                self._adapters[key].remove(adapter_class)
                # Clean up empty lists
                if not self._adapters[key]:
                    del self._adapters[key]
            except ValueError:
                pass
        
        return super()._unregister(registry_key)
   
    def has_adapter(
        self,
        source_itype: type[IType],
        target_itype: type[IType]
    ) -> bool:
        """
        Check if adapter exists for IType conversion.
        
        Args:
            source_itype: Source IType class (FLOAT, Temperature, etc.)
            target_itype: Target IType class (INT, MeshData, etc.)
            
        Returns:
            bool: True if at least one adapter exists
        """
        return (source_itype, target_itype) in self._adapters

    def get_adapter(
        self,
        source_itype: type[IType],
        target_itype: type[IType]
    ) -> type[BaseAdapter] | None:
        """
        Get highest priority adapter for IType conversion.
        
        Args:
            source_itype: Source IType class
            target_itype: Target IType class
            
        Returns:
            type[BaseAdapter] | None: Highest priority adapter or None
        """
        adapters = self._adapters.get((source_itype, target_itype))
        return adapters[0] if adapters else None
    
    def get_all_adapters(
        self,
        source_itype: type[IType],
        target_itype: type[IType]
    ) -> list[type[BaseAdapter]]:
        """
        Get all adapters for conversion (sorted by priority).
        
        Args:
            source_itype: Source IType class
            target_itype: Target IType class
            
        Returns:
            list[type[BaseAdapter]]: All adapters, highest priority first
        """
        return self._adapters.get((source_itype, target_itype), [])

    def find_adapter_chain(
        self,
        source_itype: type[IType],
        target_itype: type[IType],
        max_depth: int = 3
    ) -> list[type[BaseAdapter]] | None:
        """
        Find adapter chain for multi-hop conversion.
        
        Uses breadth-first search to find shortest conversion path.
        
        Args:
            source_itype: Source IType class
            target_itype: Target IType class
            max_depth: Maximum chain length (default 3)
            
        Returns:
            list[type[BaseAdapter]] | None: Chain of adapters or None
            
        Examples:
            # Direct adapter exists
            find_adapter_chain(Temperature, FLOAT)
            # → [TempToFloatAdapter]
            
            # Chain required
            find_adapter_chain(Temperature, INT)
            # → [TempToFloatAdapter, FloatToIntAdapter]
            
            # No path exists
            find_adapter_chain(MeshData, INT)
            # → None
        """
        # Direct adapter exists
        if self.has_adapter(source_itype, target_itype):
            return [self.get_adapter(source_itype, target_itype)]
        
        # BFS to find shortest chain
        # Queue: (current_type, chain_so_far)
        queue = deque([(source_itype, [])])
        visited = {source_itype}
        
        while queue:
            current_type, chain = queue.popleft()
            
            # Check depth limit
            if len(chain) >= max_depth:
                continue
            
            # Try all adapters from current_type
            for (src, tgt), adapters in self._adapters.items():
                if src != current_type:
                    continue
                
                # Found target!
                if tgt == target_itype:
                    return chain + [adapters[0]]
                
                # Add to queue if not visited
                if tgt not in visited:
                    visited.add(tgt)
                    queue.append((tgt, chain + [adapters[0]]))
        
        # No chain found
        return None

    def list_conversions(self) -> list[tuple[type[IType], type[IType]]]:
        """
        List all available IType conversions.
        
        Returns:
            list[tuple[type[IType], type[IType]]]: List of (source, target)
        """
        return list(self._adapters.keys())
    
    def list_conversions_from(
        self,
        source_itype: type[IType]
    ) -> list[type[IType]]:
        """
        List all target types that source can convert to.
        
        Args:
            source_itype: Source IType class
            
        Returns:
            list[type[IType]]: List of convertible target types
        """
        return [
            tgt for (src, tgt) in self._adapters.keys()
            if src == source_itype
        ]
    
    def list_conversions_to(
        self,
        target_itype: type[IType]
    ) -> list[type[IType]]:
        """
        List all source types that can convert to target.
        
        Args:
            target_itype: Target IType class
            
        Returns:
            list[type[IType]]: List of compatible source types
        """
        return [
            src for (src, tgt) in self._adapters.keys()
            if tgt == target_itype
        ]
