# haywire/core/node/user_data.py
"""
User data containers for node state.
"""

import logging
from types import SimpleNamespace
from typing import Any, Iterator

logger = logging.getLogger(__name__)


class NodeCache(SimpleNamespace):
    """
    Transient runtime cache for nodes.

    NOT serialized - data is lost when node is reloaded or graph is closed.
    Use for temporary computations, caches, buffers, and any data that
    can be safely recomputed.

    Example:
        def initialize(self):
            self.cache.lookup_table = {}
            self.cache.last_result = None

        def worker(self, context, value: float):
            # Cache expensive computation
            if value not in self.cache.lookup_table:
                self.cache.lookup_table[value] = expensive_compute(value)
            return self.cache.lookup_table[value]
    """

    def clear(self) -> None:
        """Clear all cached data."""
        self.__dict__.clear()

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"NodeCache({items})" if items else "NodeCache()"


class NodeStore:
    """
    Persistent user state storage for nodes.

    Serialized with the node - data persists across saves/loads.
    NOT exposed to GUI - use settings for user-configurable values.

    Use for:
    - Accumulated results (counters, statistics)
    - Internal state that must persist
    - Data that users don't need to see/edit

    Example:
        def initialize(self):
            self.store.execution_count = 0
            self.store.accumulated_sum = 0.0
            self.store.history = []

        def worker(self, context, value: float):
            self.store.execution_count += 1
            self.store.accumulated_sum += value
            self.store.history.append(value)

            # History is preserved when graph is saved/loaded
    """

    __slots__ = ("_data",)

    def __init__(self):
        object.__setattr__(self, "_data", {})

    # =========================================================================
    # Attribute Access
    # =========================================================================

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(
                f"NodeStore has no attribute '{name}'. Initialize it first: self.store.{name} = value"
            )

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value

    def __delattr__(self, name: str) -> None:
        if name.startswith("_"):
            object.__delattr__(self, name)
        else:
            try:
                del self._data[name]
            except KeyError:
                raise AttributeError(name)

    # =========================================================================
    # Dict-Style Access
    # =========================================================================

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    # =========================================================================
    # Iteration & Inspection
    # =========================================================================

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def keys(self):
        """Return all attribute names."""
        return self._data.keys()

    def values(self):
        """Return all values."""
        return self._data.values()

    def items(self):
        """Return all (name, value) pairs."""
        return self._data.items()

    def get(self, key: str, default: Any = None) -> Any:
        """Get value with optional default."""
        return self._data.get(key, default)

    def setdefault(self, key: str, default: Any = None) -> Any:
        """Get value, setting default if not present."""
        return self._data.setdefault(key, default)

    def has(self, key: str) -> bool:
        """Check if attribute exists."""
        return key in self._data

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    def update(self, **kwargs) -> None:
        """Update multiple values at once."""
        self._data.update(kwargs)

    def clear(self) -> None:
        """Clear all stored data."""
        self._data.clear()

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict:
        """
        Serialize store data to dictionary.

        Handles common Python types. Complex objects should either:
        - Implement to_dict() method
        - Be JSON-serializable
        - Be skipped (with warning in logs)
        """
        result = {}
        for key, value in self._data.items():
            try:
                serialized = self._serialize_value(value)
                if serialized is not None:
                    result[key] = serialized
            except (TypeError, ValueError) as e:
                logger.warning(f"NodeStore: Cannot serialize '{key}': {e}")

        return result

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a single value."""
        # Primitives
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        # Lists and tuples
        if isinstance(value, (list, tuple)):
            serialized = [self._serialize_value(v) for v in value]
            if isinstance(value, tuple):
                return {"__type__": "tuple", "values": serialized}
            return serialized

        # Dicts
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}

        # Sets
        if isinstance(value, set):
            return {"__type__": "set", "values": [self._serialize_value(v) for v in value]}

        # Frozensets
        if isinstance(value, frozenset):
            return {"__type__": "frozenset", "values": [self._serialize_value(v) for v in value]}

        # Objects with to_dict
        if hasattr(value, "to_dict"):
            return {
                "__type__": f"{type(value).__module__}.{type(value).__name__}",
                "__data__": value.to_dict(),
            }

        # Objects with __dict__ (simple objects)
        if hasattr(value, "__dict__"):
            return {
                "__type__": f"{type(value).__module__}.{type(value).__name__}",
                "__dict__": self._serialize_value(value.__dict__),
            }

        # Cannot serialize
        raise TypeError(f"Cannot serialize type: {type(value).__name__}")

    def from_dict(self, data: dict) -> None:
        """
        Restore store data from dictionary.

        Note: Complex custom types are restored as dicts.
        Override or extend for custom type reconstruction.
        """
        self._data.clear()
        for key, value in data.items():
            self._data[key] = self._deserialize_value(value)

    def _deserialize_value(self, value: Any) -> Any:
        """Deserialize a single value."""
        # Primitives
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        # Lists
        if isinstance(value, list):
            return [self._deserialize_value(v) for v in value]

        # Dicts (may contain type info)
        if isinstance(value, dict):
            if "__type__" in value:
                type_name = value["__type__"]

                # Built-in types
                if type_name == "tuple":
                    return tuple(self._deserialize_value(v) for v in value["values"])
                elif type_name == "set":
                    return set(self._deserialize_value(v) for v in value["values"])
                elif type_name == "frozenset":
                    return frozenset(self._deserialize_value(v) for v in value["values"])

                # Custom objects - return as dict (node can reconstruct if needed)
                if "__data__" in value:
                    return value["__data__"]
                if "__dict__" in value:
                    return self._deserialize_value(value["__dict__"])

                return value

            # Regular dict
            return {k: self._deserialize_value(v) for k, v in value.items()}

        return value

    # =========================================================================
    # Representation
    # =========================================================================

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in self._data.items())
        return f"NodeStore({items})" if items else "NodeStore()"

    def __str__(self) -> str:
        if not self._data:
            return "NodeStore(empty)"
        keys = ", ".join(self._data.keys())
        return f"NodeStore({keys})"
