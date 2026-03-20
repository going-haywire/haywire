# haywire/core/property/bag.py
"""
Bag — lightweight observable property container for Haywire.

Subclass and declare fields with ``prop()``:

    class ExecutionSettings(Bag):
        auto_execute: bool = prop(True, label='Auto Execute')
        debounce_ms:  int  = prop(100,  label='Debounce (ms)', min=0, max=2000)

Supports:
- Direct attribute access (``obj.field = value``)
- Change notification (``obj.subscribe(callback)``)
- Serialization (``to_dict()`` / ``from_dict()``)
- Reset (``reset(name)`` / ``reset_all()``)
"""

from __future__ import annotations

from typing import Any, Callable

from .descriptor import prop


class Bag:
    """
    Base class for observable property bags.

    """

    def __init__(self) -> None:
        self._callbacks: list[Callable] = []

    # -------------------------------------------------------------------------
    # Subscription
    # -------------------------------------------------------------------------

    def subscribe(self, callback: Callable) -> None:
        """Register ``callback(name, value, old)`` called on any prop change."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unsubscribe(self, callback: Callable) -> None:
        """Remove a previously registered callback."""
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    # -------------------------------------------------------------------------
    # Change hook (called by prop.__set__)
    # -------------------------------------------------------------------------

    def _on_prop_change(self, name: str, value: Any, old: Any) -> None:
        """Called when a prop value changes.  Default: fire all callbacks."""
        for cb in list(self._callbacks):
            try:
                cb(name, value, old)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return only fields whose current value differs from the descriptor default."""
        result: dict = {}
        for name, descriptor in type(self)._prop_fields().items():
            value = getattr(self, name)
            if value != descriptor._default:
                result[name] = value
        return result

    def from_dict(self, data: dict, *, silent: bool = True) -> None:
        """
        Restore values from *data*.

        silent=True (default): writes directly to __dict__ — no callbacks fired.
            Used during deserialization (graph load, TOML hydration).
        silent=False: uses normal setattr — callbacks fire.
            Used for live updates.

        Unknown keys are silently ignored (forward compatibility).
        """
        fields = type(self)._prop_fields()
        for key, value in data.items():
            if key not in fields:
                continue
            if silent:
                self.__dict__[f'_prop_{key}'] = value
            else:
                setattr(self, key, value)

    # -------------------------------------------------------------------------
    # Reset
    # -------------------------------------------------------------------------

    def reset(self, name: str) -> None:
        """Reset a single field to its descriptor default."""
        fields = type(self)._prop_fields()
        if name not in fields:
            raise KeyError(f"No prop '{name}' on {type(self).__name__}")
        setattr(self, name, fields[name]._default)

    def reset_all(self) -> None:
        """Reset all fields to their defaults."""
        for name in type(self)._prop_fields():
            self.reset(name)

    # -------------------------------------------------------------------------
    # Introspection
    # -------------------------------------------------------------------------

    @classmethod
    def _prop_fields(cls) -> dict[str, prop]:
        """Return all prop descriptors defined on this class (walks MRO, base-first)."""
        result: dict[str, prop] = {}
        for klass in reversed(cls.__mro__):
            for name, val in klass.__dict__.items():
                if isinstance(val, prop):
                    result[name] = val
        return result
