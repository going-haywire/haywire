# haywire/core/settings/settings.py
"""
Settings — observable setting container for Haywire.

Subclass and declare fields with ``setting()``:

    class FilterSettings(Settings):
        strength: float = setting(0.5, min=0.0, max=1.0, label='Strength')
        mode:     str   = setting('fast', choices=['fast', 'precise'])

Simple mode (no registry):
    Direct _local_store lookup.  Zero overhead.  Used by NodeProperties and
    any Settings subclass that doesn't need global defaults.

Extended mode (registry injected by @node decorator):
    Reads go through _resolve() — full resolution chain (TOML tiers).
    mirrors= on a setting links to a FrameworkSettings/LibrarySettings field.
    read_only=True on a setting prevents per-instance writes (watch behaviour).

Supports:
- Direct attribute access (``obj.field = value``)
- on_change callbacks (``setting(on_change='method_name')``)
- Change notification (``obj.subscribe(callback)``)
- Serialization (``to_dict()`` / ``from_dict()``)
- Reset (``reset(name)`` / ``reset_all()``)
- Cleanup of global subscriptions (``cleanup()``)
"""

from __future__ import annotations

import weakref
import logging
from typing import Any, Callable, TYPE_CHECKING

from .descriptor import setting

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry

logger = logging.getLogger(__name__)


class Settings:
    """
    Base Settings class for observable settings.

    Subclasses declare typed fields using ``setting()``.  When a
    ``SettingsRegistry`` is injected (extended mode), ``setting`` fields
    gain full TOML-tier resolution.
    """

    def __init__(self, registry: "SettingsRegistry | None" = None) -> None:
        self._callbacks: list[Callable] = []
        self._local_store: dict[str, Any] = {}  # key → value
        self._registry: "SettingsRegistry | None" = registry
        self._subscribed_refs: list = []  # weakrefs for mirrors invalidation
        self._cleaned_up: bool = False

    # -------------------------------------------------------------------------
    # Extended mode: resolution chain
    # -------------------------------------------------------------------------

    def _resolve(self, field_key: str, mirror_key: str, default: Any) -> Any:
        """
        Full resolution chain (extended mode):
            global OVERRIDE > workspace OVERRIDE > local SET > workspace SET > global SET > default
        """
        from haywire.core.settings.value import SettingValue
        from haywire.core.settings.enums import SettingMode

        registry = self._registry
        key = mirror_key if mirror_key else field_key
        local_sv = (
            SettingValue(mode=SettingMode.SET, value=self._local_store[field_key])
            if field_key in self._local_store
            else None
        )
        try:
            value, source = registry.resolve(key, local=local_sv)
            if source == "default" and not mirror_key:
                return default  # no mirror — use local descriptor's default
            return value
        except KeyError:
            return self._local_store.get(field_key, default)

    def _subscribe_mirrors(self) -> None:
        """Subscribe cache-invalidation weakrefs for mirrored settings (extended mode)."""
        if self._registry is None:
            return
        for descriptor in type(self)._prop_fields().values():
            if descriptor._mirror_key:
                cb_ref = weakref.WeakMethod(self._invalidate_mirror)
                self._registry.subscribe_namespace(descriptor._mirror_key, cb_ref)
                self._subscribed_refs.append(cb_ref)

    def _invalidate_mirror(self, full_key: str) -> None:
        """Called by registry when a mirrored global value changes."""
        if self._cleaned_up:
            return
        for name, descriptor in type(self)._prop_fields().items():
            if descriptor._mirror_key == full_key and descriptor._on_change:
                method = getattr(self, descriptor._on_change, None)
                if method:
                    new_val = getattr(self, name)
                    try:
                        method(new_val, name)
                    except TypeError:
                        try:
                            method(new_val)
                        except Exception as e:
                            logger.error(f"on_change error for mirrored '{name}': {e}")

    # -------------------------------------------------------------------------
    # Subscription
    # -------------------------------------------------------------------------

    def subscribe(self, callback: Callable) -> None:
        """Register ``callback(name, value, old)`` called on any setting change."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unsubscribe(self, callback: Callable) -> None:
        """Remove a previously registered callback."""
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    # -------------------------------------------------------------------------
    # Change hook (called by setting.__set__)
    # -------------------------------------------------------------------------

    def _on_prop_change(self, name: str, value: Any, old: Any) -> None:
        """Called when a setting value changes.  Default: fire all callbacks."""
        for cb in list(self._callbacks):
            try:
                cb(name, value, old)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """
        Return only fields whose value differs from the descriptor default.

        Extended mode: only locally-set fields (not inherited from global tiers).
        Simple mode: any field whose current value differs from its default.
        read_only (mirrored) fields are never serialized.
        """
        fields = type(self)._prop_fields()
        result: dict = {}
        for name, descriptor in fields.items():
            if descriptor._read_only:
                continue
            if not descriptor._stored:
                continue
            key = descriptor._field_key if descriptor._field_key else name
            if key in self._local_store:
                val = self._local_store[key]
                if val != descriptor._default:
                    result[name] = val
            elif self._registry is None:
                # Simple mode: check by attr name
                val = self._local_store.get(name, descriptor._default)
                if val != descriptor._default:
                    result[name] = val
        return result

    def from_dict(self, data: dict, *, silent: bool = True) -> None:
        """
        Restore values from *data*.

        silent=True (default): writes directly to _local_store — no callbacks fired.
            Used during deserialization (graph load).
        silent=False: uses normal setattr — callbacks fire.
            Used for live updates.

        Unknown keys are silently ignored (forward compatibility).
        read_only fields are silently skipped.
        """
        fields = type(self)._prop_fields()
        for attr_name, value in data.items():
            if attr_name not in fields:
                continue
            descriptor = fields[attr_name]
            if descriptor._read_only:
                continue
            if silent:
                key = descriptor._field_key if descriptor._field_key else attr_name
                self._local_store[key] = value
            else:
                setattr(self, attr_name, value)

    # -------------------------------------------------------------------------
    # Reset
    # -------------------------------------------------------------------------

    def reset(self, name: str) -> None:
        """Reset a single field to its descriptor default (removes local override)."""
        fields = type(self)._prop_fields()
        if name not in fields:
            raise KeyError(f"No setting '{name}' on {type(self).__name__}")
        descriptor = fields[name]
        key = descriptor._field_key if descriptor._field_key else name
        if key in self._local_store:
            old = self._local_store.pop(key)
            new = descriptor._default
            if old != new:
                self._on_prop_change(name, new, old)

    def reset_all(self) -> None:
        """Reset all fields to their defaults (clear all local overrides)."""
        for name in type(self)._prop_fields():
            self.reset(name)

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release global namespace subscriptions.  Call on node removal."""
        self._cleaned_up = True
        self._subscribed_refs.clear()
        self._callbacks.clear()

    # -------------------------------------------------------------------------
    # Introspection
    # -------------------------------------------------------------------------

    def is_locally_set(self, name: str) -> bool:
        """Return True if *name* has a local instance override."""
        fields = type(self)._prop_fields()
        if name not in fields:
            return False
        descriptor = fields[name]
        key = descriptor._field_key if descriptor._field_key else name
        return key in self._local_store

    @classmethod
    def _prop_fields(cls) -> dict[str, setting]:
        """Return all setting descriptors defined on this class (walks MRO, base-first)."""
        result: dict[str, setting] = {}
        for klass in reversed(cls.__mro__):
            for name, val in klass.__dict__.items():
                if isinstance(val, setting):
                    result[name] = val
        return result
