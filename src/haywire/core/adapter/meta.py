"""
Meta-adapters for compound type transformations.

These are system components created dynamically by AdapterFactory.
They are NOT registered adapters - they wrap registered adapters.
"""

from typing import Any, List

from .base import BaseAdapter


class StructuralAdapter(BaseAdapter):
    """
    System meta-adapter: Combines structural + element transformation.
    
    Created dynamically by AdapterFactory. Not registered.
    Wraps both structural and element adapters.
    
    Example:
        # Factory creates this internally:
        structural = MapToArrayAdapter()  # Registered adapter
        element = FloatToStringAdapter()  # Registered adapter
        combined = StructuralAdapter(structural, element)  # System
        
        # MAP[FLOAT] → ARRAY[STRING]
        result = combined.convert({"a": 1.5, "b": 2.7})
        # → ["1.50", "2.70"]
    """
    
    def __init__(
        self,
        structural_adapter: BaseAdapter,
        elemental_adapter: BaseAdapter
    ):
        """
        Args:
            structural_adapter: Container transform (MAP → ARRAY)
            elemental_adapter: Element transform (ARRAY[FLOAT] → ARRAY[STRING])
        """
        self._structural = structural_adapter
        self._elemental = elemental_adapter
        
        # Create synthetic identity (not registered)
        label = structural_adapter.class_identity.label
        if elemental_adapter:
            label += f" + {elemental_adapter.class_identity.label}"
        
        self.class_identity = type('AdapterIdentity', (), {
            'registry_key': (
                f"structural_"
                f"{structural_adapter.class_identity.registry_key}"
            ),
            'label': label,
        })()
    
    def convert(self, value: Any) -> Any:
        """Apply structural then element transformation"""
        # First: structural transformation (e.g., MAP → ARRAY)
        result = self._structural.convert(value)
        
        # Second: element transformation (e.g. ARRAY[FLOAT] → ARRAY[STRING])
        result = self._elemental.convert(result)
        
        return result
    
    def get_registry_keys(self) -> List[str]:
        """
        Get registry keys including structural and element adapters.
        
        Returns:
            List with synthetic key plus all nested adapter keys
        """
        keys = [self.class_identity.registry_key]
        
        # Add structural adapter keys
        if self._structural:
            keys.extend(self._structural.get_registry_keys())
        
        # Add element adapter keys
        if self._elemental:
            keys.extend(self._elemental.get_registry_keys())
        
        return keys
