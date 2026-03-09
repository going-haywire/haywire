# haywire/core/settings/holder.py
"""
SettingsHolder — namespaced settings hub for nodes.

SettingsHolder is a thin hub that holds one SubHolder per schema.

    self.settings.node.threshold        # NodeSettings field
    self.settings.image.jpeg_quality    # LibrarySettings field (direct assignment)
    self.settings._node.muted           # NodeInstanceSettings (always injected, reserved)

SubHolder wraps a single _SettingsSchema and handles all field-level
resolution, caching, on_change callbacks, and weakref subscriptions.

The ResolutionChain is shared across all SubHolders on the same node instance.
The local store is keyed by _full_key, which is globally unique, so sharing
is safe and avoids duplicating tier-resolution logic.
"""

from __future__ import annotations
import weakref
import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional, TYPE_CHECKING

from .enums import SettingMode
from .value import SettingValue
from .descriptors import SettingDescriptor
from .chain import ResolutionChain

if TYPE_CHECKING:
    from .registry import GlobalSettingsRegistry


logger = logging.getLogger(__name__)


@dataclass
class SettingInfo:
    """Full information about a resolved setting, used for UI display."""
    name: str
    value: Any
    source: str
    is_overridden: bool
    is_inherited: bool
    local_mode: SettingMode
    local_value: Optional[Any]
    global_mode: SettingMode
    global_value: Optional[Any]
    definition: SettingDescriptor


def _collect_fields(schema_cls: type) -> dict[str, SettingDescriptor]:
    """
    Collect all SettingDescriptor instances from schema_cls and its MRO.

    Walking the MRO in reverse (most-base first) means a subclass field
    overrides a same-named parent field — consistent with normal Python
    attribute resolution. This correctly handles both direct assignments
    (image = ImageLibSettings) and empty inner class forms
    (class image(ImageLibSettings): ...).
    """
    fields: dict[str, SettingDescriptor] = {}
    for klass in reversed(schema_cls.__mro__):
        for name, val in klass.__dict__.items():
            if isinstance(val, SettingDescriptor):
                fields[name] = val
    return fields


class SubHolder:
    """
    Wraps a single _SettingsSchema and provides field-level settings access.

    All field access, caching, on_change callbacks, and weakref namespace
    subscriptions are scoped to the schema this SubHolder wraps.
    The ResolutionChain is shared with the parent SettingsHolder.

    Usage::

        holder.node.threshold            # read
        holder.node.threshold = 0.8      # write
        holder.node.set('threshold', 0.8)
        holder.node.reset('threshold')
        holder.node.on_change(callback)  # callback(name, value, source)
        holder.node.get_info('threshold')
        holder.node.to_dict()
        holder.node.from_dict(data)
    """

    def __init__(
        self,
        accessor_name: str,
        schema_cls: type,
        chain: ResolutionChain,
        node_instance: Any,
    ) -> None:
        object.__setattr__(self, '_accessor_name', accessor_name)
        object.__setattr__(self, '_schema', schema_cls)
        object.__setattr__(self, '_chain', chain)
        object.__setattr__(self, '_node', node_instance)

        # Collect fields from MRO so that direct assignments and empty
        # inner class forms both work (inherited descriptors are included).
        fields: dict[str, SettingDescriptor] = _collect_fields(schema_cls)
        object.__setattr__(self, '_fields', fields)

        # Resolved-value cache: attr_name -> value
        object.__setattr__(self, '_cache', {})

        # full_key (and global_key for shadow/watch) -> attr_name
        from .descriptors import shadow, watch as _watch_cls
        _key_to_attr: dict[str, str] = {}
        for name, descriptor in fields.items():
            if descriptor._full_key:
                _key_to_attr[descriptor._full_key] = name
            if isinstance(descriptor, (shadow, _watch_cls)) and getattr(descriptor, '_global_key', ''):
                _key_to_attr[descriptor._global_key] = name
        object.__setattr__(self, '_key_to_attr', _key_to_attr)

        # on_change callbacks: attr_name -> bound method on node instance
        object.__setattr__(self, '_callbacks', {})
        for name, descriptor in fields.items():
            if descriptor._on_change:
                method = getattr(node_instance, descriptor._on_change, None) if node_instance else None
                if method:
                    self._callbacks[name] = method
                else:
                    logger.warning(
                        f"Settings on_change handler '{descriptor._on_change}' not found "
                        f"on {type(node_instance).__name__ if node_instance else 'None'}"
                    )

        # External change callbacks: (name, value, source)
        object.__setattr__(self, '_change_callbacks', [])

        # WeakMethod refs subscribed to the registry (retained to prune dead refs)
        object.__setattr__(self, '_subscribed_refs', [])

        # Set to True by cleanup() — makes _invalidate a no-op after node removal
        object.__setattr__(self, '_cleaned_up', False)

        # Subscribe to global namespace changes for shadow/watch fields
        self._subscribe_to_global_namespaces()

    # =========================================================================
    # Namespace subscriptions
    # =========================================================================

    def _subscribe_to_global_namespaces(self) -> None:
        """Subscribe cache-invalidation weakrefs for shadow/watch fields."""
        from .descriptors import shadow, watch
        registry: GlobalSettingsRegistry = self._chain._global
        fields = object.__getattribute__(self, '_fields')

        for descriptor in fields.values():
            if isinstance(descriptor, (shadow, watch)):
                ns = getattr(descriptor, '_global_key', '') or descriptor._full_key
                if ns:
                    cb_ref = weakref.WeakMethod(self._invalidate)
                    registry.subscribe_namespace(ns, cb_ref)
                    self._subscribed_refs.append(cb_ref)

    # =========================================================================
    # Cache invalidation
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
    # Field resolution
    # =========================================================================

    def _resolve_descriptor(self, descriptor: SettingDescriptor) -> Any:
        global_key = getattr(descriptor, '_global_key', '')
        if global_key:
            return self._chain.resolve_shadow(descriptor._full_key, global_key, descriptor._default)
        return self._chain.resolve(descriptor._full_key, descriptor._default)

    # =========================================================================
    # Attribute access
    # =========================================================================

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)

        fields = object.__getattribute__(self, '_fields')
        cache = object.__getattribute__(self, '_cache')

        if name in cache:
            return cache[name]

        if name in fields:
            value = self._resolve_descriptor(fields[name])
            cache[name] = value
            return value

        raise AttributeError(
            f"Setting '{name}' not found in schema '{self._schema.__name__}' "
            f"(accessor: '{self._accessor_name}')"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith('_'):
            object.__setattr__(self, name, value)
            return
        self.set(name, value)

    # =========================================================================
    # Dict-style access
    # =========================================================================

    def __getitem__(self, key: str) -> Any:
        cache = object.__getattribute__(self, '_cache')
        if key in cache:
            return cache[key]

        fields = object.__getattribute__(self, '_fields')
        _key_to_attr = object.__getattribute__(self, '_key_to_attr')

        if key in fields:
            attr_name = key
        elif key in _key_to_attr:
            attr_name = _key_to_attr[key]
        else:
            raise KeyError(f"Setting '{key}' not found in '{self._accessor_name}'")

        value = self._resolve_descriptor(fields[attr_name])
        cache[attr_name] = value
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        fields = object.__getattribute__(self, '_fields')
        if key in fields:
            return True
        return any(d._full_key == key for d in fields.values())

    def __iter__(self) -> Iterator[str]:
        fields = object.__getattribute__(self, '_fields')
        yield from fields

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

    def set(self, name: str, value: Any, mode: SettingMode = SettingMode.SET) -> None:
        """Set a local value for a field (attr name or full key)."""
        cache = object.__getattribute__(self, '_cache')
        fields = object.__getattribute__(self, '_fields')

        if name in fields:
            descriptor = fields[name]
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
        for attr_name, descriptor in fields.items():
            if descriptor._full_key == name:
                self.set(attr_name, value, mode)
                return

        raise KeyError(f"Setting '{name}' not defined in '{self._accessor_name}'")

    def reset(self, name: str) -> None:
        """Reset a field to AUTO (inherit from global/default)."""
        cache = object.__getattribute__(self, '_cache')
        fields = object.__getattribute__(self, '_fields')

        if name in fields:
            self._chain.clear_local(fields[name]._full_key)
            cache.pop(name, None)
            return

        for attr_name, descriptor in fields.items():
            if descriptor._full_key == name:
                self._chain.clear_local(descriptor._full_key)
                cache.pop(attr_name, None)
                return

    def reset_all(self) -> None:
        """Reset all local overrides for this schema."""
        fields = object.__getattribute__(self, '_fields')
        for descriptor in fields.values():
            if descriptor._full_key:
                self._chain.clear_local(descriptor._full_key)
        cache = object.__getattribute__(self, '_cache')
        cache.clear()

    # =========================================================================
    # Change callbacks
    # =========================================================================

    def _fire_change_callbacks(self, name: str, value: Any) -> None:
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
        """Subscribe to field changes. Callback signature: (name, value, source)."""
        self._change_callbacks.append(callback)

    def remove_callback(self, callback: Callable) -> None:
        change_callbacks = object.__getattribute__(self, '_change_callbacks')
        if callback in change_callbacks:
            change_callbacks.remove(callback)

    # =========================================================================
    # Introspection
    # =========================================================================

    def get_info(self, name: str) -> SettingInfo:
        """Get full resolution info for UI display (by attr name or full key)."""
        fields = object.__getattribute__(self, '_fields')
        registry: GlobalSettingsRegistry = self._chain._global

        descriptor = fields.get(name)
        if descriptor is None:
            for attr_name, d in fields.items():
                if d._full_key == name:
                    descriptor = d
                    name = attr_name
                    break
        if descriptor is None:
            raise KeyError(f"Setting '{name}' not defined in '{self._accessor_name}'")

        full_key = descriptor._full_key
        global_key = getattr(descriptor, '_global_key', '') or full_key
        defn = registry.get_definition(global_key) or registry.get_definition(full_key)
        if defn is None:
            defn = descriptor

        has_local = self._chain.has_local(full_key)
        local_val = self._chain.get_local(full_key) if has_local else None
        local_mode = SettingMode.SET if has_local else SettingMode.AUTO

        local_sv = SettingValue(mode=SettingMode.SET, value=local_val) if has_local else None
        try:
            value, source = registry.resolve(global_key, local=local_sv)
        except KeyError:
            value = descriptor._default
            source = 'default'

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
        fields = object.__getattribute__(self, '_fields')
        if name in fields:
            return self._chain.has_local(fields[name]._full_key)
        for descriptor in fields.values():
            if descriptor._full_key == name:
                return self._chain.has_local(descriptor._full_key)
        return False

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict:
        """
        Serialize locally-overridden field values for graph persistence.

        Only locally-set fields are included. Global defaults and watch()
        values are never stored.
        """
        fields = object.__getattribute__(self, '_fields')
        schema_values = {}
        for attr_name, descriptor in fields.items():
            if descriptor._stored and descriptor._full_key:
                if self._chain.has_local(descriptor._full_key):
                    schema_values[attr_name] = self._chain.get_local(descriptor._full_key)
        return {'schema_values': schema_values}

    def from_dict(self, data: dict) -> None:
        """Restore serialized field values. Callbacks are NOT fired."""
        cache = object.__getattribute__(self, '_cache')
        fields = object.__getattribute__(self, '_fields')
        cache.clear()
        for attr_name, value in data.get('schema_values', {}).items():
            if attr_name in fields:
                descriptor = fields[attr_name]
                if descriptor._stored and descriptor._full_key:
                    self._chain.set_local(descriptor._full_key, value)

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup(self) -> None:
        """Release namespace subscriptions and clear state."""
        object.__setattr__(self, '_cleaned_up', True)
        object.__getattribute__(self, '_subscribed_refs').clear()
        object.__getattribute__(self, '_cache').clear()
        object.__getattribute__(self, '_change_callbacks').clear()

    def __repr__(self) -> str:
        fields = object.__getattribute__(self, '_fields')
        schema = object.__getattribute__(self, '_schema')
        accessor = object.__getattribute__(self, '_accessor_name')
        return f"SubHolder(accessor='{accessor}', schema={schema.__name__}, fields={len(fields)})"


class SettingsHolder:
    """
    Namespaced settings hub for a node instance.

    Holds one SubHolder per schema, keyed by the accessor name declared
    in the node class body (inner class name or direct assignment name).

    Reserved accessor ``'_node'`` is always injected with NodeInstanceSettings.
    Node developers cannot use ``'_node'`` as an accessor name.

    Usage::

        self.settings.node.threshold        # NodeSettings field
        self.settings.image.jpeg_quality    # LibrarySettings field
        self.settings._node.muted           # NodeInstanceSettings (framework)

    The ResolutionChain is shared across all SubHolders — the local store is
    keyed by _full_key which is globally unique.

    ``schemas`` is built by the ``@node`` decorator from all ``_SettingsSchema``
    subclasses found in the node class body, with ``'_node': NodeInstanceSettings``
    always appended.
    """

    def __init__(
        self,
        schemas: dict[str, type],
        registry: 'GlobalSettingsRegistry',
        node_instance: Any,
    ) -> None:
        # One shared local store + chain for the whole node instance
        local_store: dict[str, Any] = {}
        chain = ResolutionChain(local_store, registry)
        object.__setattr__(self, '_chain', chain)

        sub_holders: dict[str, SubHolder] = {}
        for accessor_name, schema_cls in schemas.items():
            sub_holders[accessor_name] = SubHolder(accessor_name, schema_cls, chain, node_instance)
        object.__setattr__(self, '_sub_holders', sub_holders)

    # =========================================================================
    # Sub-holder access
    # =========================================================================

    def __getattr__(self, name: str) -> SubHolder:
        sub_holders = object.__getattribute__(self, '_sub_holders')
        if name in sub_holders:
            return sub_holders[name]
        raise AttributeError(
            f"No settings schema with accessor '{name}'. "
            f"Available: {list(sub_holders.keys())}"
        )

    def __contains__(self, name: str) -> bool:
        """True if name is a registered accessor name."""
        sub_holders = object.__getattribute__(self, '_sub_holders')
        return name in sub_holders

    def __iter__(self) -> Iterator[str]:
        """Iterate accessor names."""
        sub_holders = object.__getattribute__(self, '_sub_holders')
        yield from sub_holders

    @property
    def sub_holders(self) -> dict[str, 'SubHolder']:
        """All sub-holders keyed by accessor name — for panels and introspection."""
        return object.__getattribute__(self, '_sub_holders')

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict:
        """
        Serialize all sub-holders.

        Format::

            {
                'node':  {'schema_values': {'threshold': 0.8}},
                '_node': {'schema_values': {'skin': 'rounded'}},
                'image': {'schema_values': {}},
            }
        """
        sub_holders = object.__getattribute__(self, '_sub_holders')
        return {name: sh.to_dict() for name, sh in sub_holders.items()}

    def from_dict(self, data: dict) -> None:
        """Restore all sub-holders from serialized data."""
        sub_holders = object.__getattribute__(self, '_sub_holders')
        for name, sh in sub_holders.items():
            if name in data:
                sh.from_dict(data[name])

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup(self) -> None:
        """Release all sub-holder subscriptions. Call on node removal."""
        sub_holders = object.__getattribute__(self, '_sub_holders')
        for sh in sub_holders.values():
            sh.cleanup()

    def __repr__(self) -> str:
        sub_holders = object.__getattribute__(self, '_sub_holders')
        return f"SettingsHolder(schemas={list(sub_holders.keys())})"
