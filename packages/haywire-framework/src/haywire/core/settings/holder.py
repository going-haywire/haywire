# haywire/core/settings/holder.py
"""
SettingsHolder — schema-driven settings access with caching and weakref subscriptions.
"""

from __future__ import annotations
import weakref
import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional, TYPE_CHECKING

from .enums import SettingMode, SettingScope
from .value import SettingValue
from .definition import SettingDefinition
from .chain import ResolutionChain

if TYPE_CHECKING:
    from .schema import _SettingsSchema
    from .registry import GlobalSettingsRegistry


logger = logging.getLogger(__name__)


@dataclass
class SettingInfo:
    """
    Full information about a resolved setting, used for UI display.
    """
    name: str
    value: Any
    source: str
    is_overridden: bool
    is_inherited: bool
    local_mode: SettingMode
    local_value: Optional[Any]
    global_mode: SettingMode
    global_value: Optional[Any]
    definition: SettingDefinition


class SettingsHolder:
    """
    Provides schema-driven settings access for nodes.

    Accepts one primary schema class (the node's inner ``Settings`` class) and
    zero or more *extra* schema classes that are merged in before the primary
    one.  ``NodeInstanceSettings`` is injected here by ``NodeData.__init__`` so
    that every node automatically exposes the framework-level instance fields
    (``skin``, ``muted``, ``collapsed``, …).

    Merged field lookup order: extra schemas (first wins) then primary schema
    (primary schema fields override any same-named field from extras).

    Caching: resolved values are cached; cache is invalidated via weakref
    namespace subscriptions when global settings change (Option B).

    Usage from node code::

        color    = self.settings.bg_color       # primary schema field
        is_muted = self.settings.muted          # NodeInstanceSettings field
        is_muted = self.settings['node.muted']  # via full_key — also works
    """

    def __init__(
        self,
        schema_cls: type['_SettingsSchema'],
        registry: 'GlobalSettingsRegistry',
        node_instance: Any,
        extra_schemas: tuple[type['_SettingsSchema'], ...] = (),
    ):
        object.__setattr__(self, '_schema', schema_cls)
        object.__setattr__(self, '_chain', ResolutionChain({}, registry))
        object.__setattr__(self, '_node', node_instance)

        # Merge fields: extras first, then primary; raise on collision
        _all_fields: dict[str, Any] = {}
        for extra in extra_schemas:
            for name, descriptor in extra._fields.items():
                if name in _all_fields:
                    raise ValueError(
                        f"Settings field '{name}' in {extra.__name__} collides with "
                        f"a field already registered by another extra schema."
                    )
                _all_fields[name] = descriptor
        for name, descriptor in schema_cls._fields.items():
            if name in _all_fields:
                raise ValueError(
                    f"Settings field '{name}' collides with "
                    f"a field from an extra schema. Rename to resolve the conflict."
                )
            _all_fields[name] = descriptor
        object.__setattr__(self, '_all_fields', _all_fields)

        # Resolved-value cache: attr_name -> value
        object.__setattr__(self, '_cache', {})

        # attr_name -> full_key and full_key -> attr_name (for all schemas)
        from .descriptors import shadow, watch as _watch_cls
        _key_to_attr: dict[str, str] = {}
        for name, d in _all_fields.items():
            if d._full_key:
                _key_to_attr[d._full_key] = name
            if isinstance(d, (shadow, _watch_cls)) and getattr(d, '_global_key', ''):
                _key_to_attr[d._global_key] = name
        object.__setattr__(self, '_key_to_attr', _key_to_attr)

        # on_change callbacks per attr name: attr_name -> bound method
        object.__setattr__(self, '_callbacks', {})
        for name, d in _all_fields.items():
            if d._on_change:
                method = getattr(node_instance, d._on_change, None) if node_instance else None
                if method:
                    self._callbacks[name] = method
                elif d._on_change:
                    logger.warning(
                        f"Settings on_change handler '{d._on_change}' not found "
                        f"on {type(node_instance).__name__ if node_instance else 'None'}"
                    )

        # General change callbacks (name, value, source) — for external subscribers
        object.__setattr__(self, '_change_callbacks', [])

        # WeakMethod refs we subscribed to the registry (kept so we can prune them)
        object.__setattr__(self, '_subscribed_refs', [])

        # Set to True by cleanup() — makes _invalidate a no-op after node removal
        object.__setattr__(self, '_cleaned_up', False)

        # Subscribe to global namespace changes for shadow/watch fields
        self._subscribe_to_global_namespaces()

    def _subscribe_to_global_namespaces(self) -> None:
        """
        For each shadow/watch field across all schemas, subscribe a weakref to
        the global registry so that when the referenced global key changes our
        cache is invalidated.
        """
        from .descriptors import shadow, watch
        registry: GlobalSettingsRegistry = self._chain._global
        _all_fields = object.__getattribute__(self, '_all_fields')

        for name, descriptor in _all_fields.items():
            if isinstance(descriptor, (shadow, watch)):
                ns = getattr(descriptor, '_global_key', '') or descriptor._full_key
                if ns:
                    cb_ref = weakref.WeakMethod(self._invalidate)
                    registry.subscribe_namespace(ns, cb_ref)
                    self._subscribed_refs.append(cb_ref)

    # =========================================================================
    # Cache invalidation (called by namespace subscriptions)
    # =========================================================================

    def _invalidate(self, full_key: str) -> None:
        """Evict full_key from cache and fire on_change callbacks."""
        if object.__getattribute__(self, '_cleaned_up'):
            return
        attr_name = self._key_to_attr.get(full_key)
        if attr_name:
            self._cache.pop(attr_name, None)
            cb = self._callbacks.get(attr_name)
            if cb:
                try:
                    new_val = getattr(self, attr_name)
                    try:
                        cb(new_val, attr_name)
                    except TypeError:
                        cb(new_val)
                except Exception as e:
                    logger.error(f"on_change callback error for {attr_name}: {e}")

    # =========================================================================
    # Schema field access (__getattr__)
    # =========================================================================

    def _resolve_descriptor(self, descriptor: Any) -> Any:
        """Resolve the effective value for a descriptor through the chain."""
        global_key = getattr(descriptor, '_global_key', '')
        if global_key:
            return self._chain.resolve_shadow(descriptor._full_key, global_key, descriptor._default)
        return self._chain.resolve(descriptor._full_key, descriptor._default)

    def __getattr__(self, name: str) -> Any:
        """Dot notation access: self.settings.threshold"""
        if name.startswith('_'):
            raise AttributeError(name)

        _all_fields = object.__getattribute__(self, '_all_fields')
        cache = object.__getattribute__(self, '_cache')

        if name in cache:
            return cache[name]

        if name in _all_fields:
            value = self._resolve_descriptor(_all_fields[name])
            cache[name] = value
            return value

        raise AttributeError(f"Setting '{name}' not found")

    def __setattr__(self, name: str, value: Any) -> None:
        """Dot notation setting: self.settings.threshold = 0.8"""
        if name.startswith('_'):
            object.__setattr__(self, name, value)
            return
        self.set(name, value)

    # =========================================================================
    # Dict-style access
    # =========================================================================

    def __getitem__(self, key: str) -> Any:
        """Dict-style access by attr name or full key: self.settings['node.muted']"""
        cache = object.__getattribute__(self, '_cache')
        if key in cache:
            return cache[key]

        _all_fields = object.__getattribute__(self, '_all_fields')
        _key_to_attr = object.__getattribute__(self, '_key_to_attr')

        # Resolve to attr_name: direct attr name lookup, then full-key lookup
        if key in _all_fields:
            attr_name = key
        elif key in _key_to_attr:
            attr_name = _key_to_attr[key]
        else:
            raise KeyError(f"Setting '{key}' not found")

        value = self._resolve_descriptor(_all_fields[attr_name])
        cache[attr_name] = value
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        _all_fields = object.__getattribute__(self, '_all_fields')
        if key in _all_fields:
            return True
        return any(d._full_key == key for d in _all_fields.values())

    def __iter__(self) -> Iterator[str]:
        _all_fields = object.__getattribute__(self, '_all_fields')
        yield from _all_fields

    def items(self) -> Iterator[tuple[str, Any]]:
        for name in self:
            try:
                yield name, self[name]
            except (KeyError, AttributeError):
                pass

    def get(self, name: str, default: Any = None) -> Any:
        try:
            return self[name]
        except (KeyError, AttributeError):
            return default

    # =========================================================================
    # set / reset
    # =========================================================================

    def set(
        self,
        name: str,
        value: Any,
        mode: SettingMode = SettingMode.SET
    ) -> None:
        """Set a local value for a schema field (attr name or full key)."""
        cache = object.__getattribute__(self, '_cache')
        _all_fields = object.__getattribute__(self, '_all_fields')

        # By attr name
        if name in _all_fields:
            descriptor = _all_fields[name]
            if descriptor._read_only:
                raise AttributeError(f"Setting '{name}' is read-only (watch descriptor)")
            if mode == SettingMode.SET:
                self._chain.set_local(descriptor._full_key, value)
            elif mode == SettingMode.AUTO:
                self._chain.clear_local(descriptor._full_key)
            cache.pop(name, None)
            resolved = self._resolve_descriptor(descriptor)
            self._fire_change_callbacks(name, resolved)
            return

        # By full key
        for attr_name, descriptor in _all_fields.items():
            if descriptor._full_key == name:
                self.set(attr_name, value, mode)
                return

        raise KeyError(f"Setting '{name}' not defined")

    def reset(self, name: str) -> None:
        """Reset setting to AUTO (inherit from global/default)."""
        cache = object.__getattribute__(self, '_cache')
        _all_fields = object.__getattribute__(self, '_all_fields')

        if name in _all_fields:
            descriptor = _all_fields[name]
            self._chain.clear_local(descriptor._full_key)
            cache.pop(name, None)
            return

        # By full key
        for attr_name, descriptor in _all_fields.items():
            if descriptor._full_key == name:
                self._chain.clear_local(descriptor._full_key)
                cache.pop(attr_name, None)
                return

    def reset_all(self) -> None:
        """Reset all local overrides."""
        _all_fields = object.__getattribute__(self, '_all_fields')
        for descriptor in _all_fields.values():
            if descriptor._full_key:
                self._chain.clear_local(descriptor._full_key)
        cache = object.__getattribute__(self, '_cache')
        cache.clear()

    # =========================================================================
    # Change callbacks
    # =========================================================================

    def _fire_change_callbacks(self, name: str, value: Any) -> None:
        """Notify general change callbacks."""
        change_callbacks = object.__getattribute__(self, '_change_callbacks')
        for cb in change_callbacks:
            try:
                cb(name, value, 'local')
            except Exception as e:
                logger.error(f"change callback error for '{name}': {e}")
        node = object.__getattribute__(self, '_node')
        if node and hasattr(node, 'redraw'):
            node.redraw()

    def on_change(self, callback: Callable[[str, Any, str], None]) -> None:
        """Subscribe to setting changes. Callback: (name, value, source)."""
        self._change_callbacks.append(callback)

    def remove_callback(self, callback: Callable) -> None:
        change_callbacks = object.__getattribute__(self, '_change_callbacks')
        if callback in change_callbacks:
            change_callbacks.remove(callback)

    # =========================================================================
    # Introspection
    # =========================================================================

    def get_info(self, name: str) -> SettingInfo:
        """Get full resolution info for UI display."""
        _all_fields = object.__getattribute__(self, '_all_fields')
        registry: GlobalSettingsRegistry = self._chain._global

        # Resolve by attr name or full key
        descriptor = _all_fields.get(name)
        if descriptor is None:
            for attr_name, d in _all_fields.items():
                if d._full_key == name:
                    descriptor = d
                    name = attr_name
                    break
        if descriptor is None:
            raise KeyError(f"Setting '{name}' not defined")

        full_key = descriptor._full_key
        global_key = getattr(descriptor, '_global_key', '') or full_key
        defn = registry.get_definition(global_key) or registry.get_definition(full_key)
        if defn is None:
            defn = SettingDefinition(
                name=full_key,
                default=descriptor._default,
                type_=type(descriptor._default) if descriptor._default is not None else str,
                scope=SettingScope.GLOBAL_AWARE,
            )

        has_local = self._chain.has_local(full_key)
        local_val = self._chain.get_local(full_key) if has_local else None
        local_mode = SettingMode.SET if has_local else SettingMode.AUTO

        # Delegate resolution (including source) to the registry so tier priority
        # is computed in one place.
        local_sv = SettingValue(mode=SettingMode.SET, value=local_val) if has_local else None
        try:
            value, source = registry.resolve(global_key, local=local_sv)
        except KeyError:
            value = descriptor._default
            source = 'default'

        # Effective global value for panel display (workspace beats global)
        effective_sv = registry.get_global(global_key)

        return SettingInfo(
            name=name,
            value=value,
            source=source,
            is_overridden=(source in ('global_override', 'workspace_override')),
            is_inherited=(source in ('global', 'workspace', 'default')),
            local_mode=local_mode,
            local_value=local_val,
            global_mode=effective_sv.mode,
            global_value=effective_sv.value,
            definition=defn,
        )

    def is_locally_set(self, name: str) -> bool:
        """Return True if name has a local instance override."""
        _all_fields = object.__getattribute__(self, '_all_fields')
        if name in _all_fields:
            return self._chain.has_local(_all_fields[name]._full_key)
        # Also accept full key
        for descriptor in _all_fields.values():
            if descriptor._full_key == name:
                return self._chain.has_local(descriptor._full_key)
        return False

    # =========================================================================
    # Serialization  (called by NodeData._to_dict / _initialize_from_dict)
    # =========================================================================

    def to_dict(self) -> dict:
        """
        Serialize settings state for graph persistence.

        Format::

            {
                'schema_values': {attr_name: value, ...},
            }

        Only locally-overridden fields are included.  Fields still at their
        global or descriptor default are omitted.
        """
        _all_fields = object.__getattribute__(self, '_all_fields')

        schema_values = {}
        for attr_name, descriptor in _all_fields.items():
            if descriptor._stored and descriptor._full_key:
                if self._chain.has_local(descriptor._full_key):
                    schema_values[attr_name] = self._chain.get_local(descriptor._full_key)

        return {'schema_values': schema_values}

    def from_dict(self, data: dict) -> None:
        """
        Restore serialized settings state.

        Handles the current format (``schema_values``) and migrates the previous
        legacy-bridge format (``legacy_values`` with ``node.X`` keys).
        """
        cache = object.__getattribute__(self, '_cache')
        _all_fields = object.__getattribute__(self, '_all_fields')

        cache.clear()

        # Callbacks are intentionally NOT fired during deserialization — the node
        # is being reconstructed from a saved state, not responding to a user change.
        # Current format: schema field overrides keyed by attr name
        for attr_name, value in data.get('schema_values', {}).items():
            if attr_name in _all_fields:
                descriptor = _all_fields[attr_name]
                if descriptor._stored and descriptor._full_key:
                    self._chain.set_local(descriptor._full_key, value)

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup(self) -> None:
        """
        Release namespace subscriptions and clear state.
        Called by NodeWrapper when node is removed.
        """
        object.__setattr__(self, '_cleaned_up', True)

        subscribed_refs = object.__getattribute__(self, '_subscribed_refs')
        subscribed_refs.clear()

        cache = object.__getattribute__(self, '_cache')
        cache.clear()

        change_callbacks = object.__getattribute__(self, '_change_callbacks')
        change_callbacks.clear()

    def __repr__(self) -> str:
        _all_fields = object.__getattribute__(self, '_all_fields')
        node = object.__getattribute__(self, '_node')
        return (
            f"SettingsHolder("
            f"node={type(node).__name__ if node else 'None'}, "
            f"fields={len(_all_fields)})"
        )
