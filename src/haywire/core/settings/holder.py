# haywire/core/settings/holder.py
"""
SettingsHolder - provides dynaconf-style access to settings with caching.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Iterator, TYPE_CHECKING

from .enums import SettingMode, SettingScope
from .value import SettingValue
from .definition import SettingDefinition

if TYPE_CHECKING:
    from .registry import GlobalSettingsRegistry


@dataclass
class SettingInfo:
    """
    Full information about a resolved setting.
    
    Used for UI display to show resolution source, override status, etc.
    """
    name: str
    """Setting name"""
    
    value: Any
    """Resolved value"""
    
    source: str
    """Resolution source: 'global_override', 'local', 'global', 'default'"""
    
    is_overridden: bool
    """True if global override is active (cannot be changed locally)"""
    
    is_inherited: bool
    """True if using global or default value (not locally set)"""
    
    local_mode: SettingMode
    """Current local mode"""
    
    local_value: Any | None
    """Current local value (if SET)"""
    
    global_mode: SettingMode
    """Current global mode"""
    
    global_value: Any | None
    """Current global value (if SET or OVERRIDE)"""
    
    definition: SettingDefinition
    """The setting definition with type, label, etc."""


class _SettingsNamespace:
    """
    Proxy for nested namespace access.
    
    Allows: self.settings.ui.node.bg_color
    When settings are defined as 'ui.node.bg_color'
    """
    
    __slots__ = ('_holder', '_prefix')
    
    def __init__(self, holder: SettingsHolder, prefix: str):
        object.__setattr__(self, '_holder', holder)
        object.__setattr__(self, '_prefix', prefix)
    
    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        
        full_name = f"{self._prefix}.{name}".lower()
        
        # Try as direct setting
        if self._holder._get_definition(full_name):
            return self._holder[full_name]
        
        # Try as namespace
        all_names = self._holder._all_setting_names()
        prefix = full_name + '.'
        if any(n.startswith(prefix) for n in all_names):
            return _SettingsNamespace(self._holder, full_name)
        
        raise AttributeError(f"Setting '{full_name}' not found")
    
    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith('_'):
            object.__setattr__(self, name, value)
            return
        
        full_name = f"{self._prefix}.{name}".lower()
        self._holder.set(full_name, value)
    
    def __repr__(self) -> str:
        return f"SettingsNamespace('{self._prefix}')"


class SettingsHolder:
    """
    Provides dynaconf-style settings access for nodes and other objects.
    
    Features:
    - Dot notation: self.settings.bg_color
    - Dict access: self.settings['bg_color']
    - Nested keys: self.settings['ui.node.bg'] or self.settings.ui.node.bg
    - Case insensitive: self.settings.BG_COLOR == self.settings.bg_color
    - Automatic resolution: global override > local > global > default
    - Local-only settings: settings without global equivalent
    - Value caching: resolved values are cached for fast repeated access
    
    Usage:
        class MyNode(BaseNode):
            def initialize(self):
                # Local-only setting (no global equivalent)
                self.settings.define('cache_size', 100, scope=SettingScope.LOCAL_ONLY)
                
            def worker(self, context):
                # Access any global setting directly (no define needed)
                color = self.settings.ui.node.bg_color
                
                # Or dict style
                color = self.settings['ui.node.bg_color']
                
                # Check if overridden
                if self.settings.get_info('ui.node.bg_color').is_overridden:
                    # Handle override case
                    pass
                
                # Local-only setting
                cache = self.settings.cache_size
    """
    
    def __init__(
        self, 
        registry: GlobalSettingsRegistry,
        owner: Any = None,
        owner_name: str = ''
    ):
        """
        Initialize a SettingsHolder.
        
        Args:
            registry: The global settings registry
            owner: Optional owner object (e.g., NodeWrapper) for change notifications
            owner_name: Optional name for logging
        """
        object.__setattr__(self, '_registry', registry)
        object.__setattr__(self, '_owner', owner)
        object.__setattr__(self, '_owner_name', owner_name)
        object.__setattr__(self, '_local_values', {})
        object.__setattr__(self, '_local_definitions', {})
        object.__setattr__(self, '_local_only_names', set())  # Fast lookup for local-only
        object.__setattr__(self, '_change_callbacks', [])
        
        # Value cache for fast access
        object.__setattr__(self, '_value_cache', {})
        
        # Subscribe to global changes
        registry.add_listener(self._on_global_change)
    
    def _on_global_change(self, name: str, global_val: SettingValue) -> None:
        """Handle global setting changes."""
        name = name.lower()
        
        # Invalidate cache for this setting
        self._value_cache.pop(name, None)
        
        # Only care about settings we might use
        defn = self._get_definition(name)
        if not defn:
            return
        
        local = self._local_values.get(name, SettingValue())
        
        # Notify if we're affected
        if local.mode == SettingMode.AUTO or global_val.mode == SettingMode.OVERRIDE:
            resolved, source = self._resolve(name)
            for cb in self._change_callbacks:
                try:
                    cb(name, resolved, source)
                except Exception:
                    pass
    
    # =========================================================================
    # Cache Management
    # =========================================================================
    
    def _invalidate_cache(self, name: str | None = None) -> None:
        """
        Invalidate cached values.
        
        Args:
            name: Specific setting to invalidate, or None for all
        """
        if name is None:
            self._value_cache.clear()
        else:
            self._value_cache.pop(name.lower(), None)
    
    def _cache_value(self, name: str, value: Any) -> Any:
        """Cache and return a resolved value."""
        self._value_cache[name] = value
        return value
    
    # =========================================================================
    # Definition
    # =========================================================================
    
    def define(
        self,
        name: str,
        default: Any,
        type_: type | None = None,
        scope: SettingScope = SettingScope.GLOBAL_AWARE,
        label: str | None = None,
        description: str = "",
        category: str = "local",
        **kwargs
    ) -> 'SettingsHolder':
        """
        Define a setting for this holder.
        
        For GLOBAL_AWARE settings:
            - If already defined in registry, uses that definition
            - If not, creates a new global definition
        
        For LOCAL_ONLY settings:
            - Creates a local-only definition (not in global registry)
        
        Returns self for chaining.
        """
        name = name.lower()
        
        # Invalidate any cached value
        self._invalidate_cache(name)
        
        if scope == SettingScope.LOCAL_ONLY:
            self._local_definitions[name] = SettingDefinition(
                name=name,
                default=default,
                type_=type_ or type(default),
                scope=scope,
                label=label,
                description=description,
                category=category,
                **kwargs
            )
            self._local_values[name] = SettingValue(mode=SettingMode.AUTO)
            self._local_only_names.add(name)
        else:
            if not self._registry.has_definition(name):
                self._registry.define(
                    name, default, type_, label, description, category, **kwargs
                )
            self._local_values[name] = SettingValue(mode=SettingMode.AUTO)
        
        return self
    
    # =========================================================================
    # Resolution
    # =========================================================================
    
    def _all_setting_names(self) -> set[str]:
        """Get all available setting names."""
        names = set(self._local_definitions.keys())
        names.update(self._registry.all_definitions().keys())
        return names
    
    def _get_definition(self, name: str) -> SettingDefinition | None:
        """Get definition from local or global."""
        name = name.lower()
        return (
            self._local_definitions.get(name) or 
            self._registry.get_definition(name)
        )
    
    def _resolve_local_only(self, name: str) -> Any:
        """
        Optimized resolution for local-only settings.
        
        Skips global registry lookup entirely.
        """
        local = self._local_values.get(name)
        if local and local.mode == SettingMode.SET:
            return local.value
        return self._local_definitions[name].default
    
    def _resolve(self, name: str) -> tuple[Any, str]:
        """Resolve setting value with full hierarchy."""
        name = name.lower()
        
        local = self._local_values.get(name)
        
        # Local-only setting (fast path)
        if name in self._local_definitions:
            defn = self._local_definitions[name]
            if local and local.mode == SettingMode.SET:
                return local.value, 'local'
            return defn.default, 'default'
        
        # Global-aware setting
        if self._registry.has_definition(name):
            return self._registry.resolve(name, local)
        
        raise KeyError(f"Setting '{name}' not defined")
    
    # =========================================================================
    # Dynaconf-style API
    # =========================================================================
    
    def __getattr__(self, name: str) -> Any:
        """Dot notation access: self.settings.bg_color"""
        if name.startswith('_'):
            raise AttributeError(name)
        
        name_lower = name.lower()
        
        # Check cache first
        if name_lower in self._value_cache:
            return self._value_cache[name_lower]
        
        # Direct setting
        if self._get_definition(name_lower):
            # Fast path for local-only
            if name_lower in self._local_only_names:
                value = self._resolve_local_only(name_lower)
            else:
                value, _ = self._resolve(name_lower)
            return self._cache_value(name_lower, value)
        
        # Namespace prefix
        all_names = self._all_setting_names()
        prefix = name_lower + '.'
        if any(n.startswith(prefix) for n in all_names):
            return _SettingsNamespace(self, name_lower)
        
        raise AttributeError(f"Setting '{name}' not found")
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Dot notation setting: self.settings.bg_color = '#000'"""
        if name.startswith('_'):
            object.__setattr__(self, name, value)
            return
        
        self.set(name, value)
    
    def __getitem__(self, key: str) -> Any:
        """Dict-style access: self.settings['ui.node.bg_color']"""
        key = key.lower()
        
        # Check cache first
        if key in self._value_cache:
            return self._value_cache[key]
        
        # Fast path for local-only
        if key in self._local_only_names:
            value = self._resolve_local_only(key)
            return self._cache_value(key, value)
        
        # Standard resolution
        value, _ = self._resolve(key)
        return self._cache_value(key, value)
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Dict-style setting: self.settings['bg_color'] = '#000'"""
        self.set(key, value)
    
    def __contains__(self, key: str) -> bool:
        """Check if setting exists: 'bg_color' in self.settings"""
        return self._get_definition(key.lower()) is not None
    
    def __iter__(self) -> Iterator[str]:
        """Iterate over setting names."""
        yield from self._all_setting_names()
    
    def items(self) -> Iterator[tuple[str, Any]]:
        """Iterate over (name, resolved_value) pairs."""
        for name in self:
            yield name, self[name]
    
    def get(self, name: str, default: Any = None) -> Any:
        """Get with default: self.settings.get('missing', 'fallback')"""
        try:
            return self[name]
        except KeyError:
            return default
    
    # =========================================================================
    # Explicit Setting API
    # =========================================================================
    
    def set(
        self, 
        name: str, 
        value: Any, 
        mode: SettingMode = SettingMode.SET
    ) -> None:
        """
        Explicitly set a local value.
        
        Args:
            name: Setting name
            value: Value to set
            mode: SET (explicit) or AUTO (inherit)
        """
        name = name.lower()
        
        defn = self._get_definition(name)
        if not defn:
            raise KeyError(f"Setting '{name}' not defined")
        
        # Validate
        if mode == SettingMode.SET:
            try:
                value = defn.coerce(value)
            except ValueError:
                pass  # Use as-is if coercion fails
            
            if not defn.validate(value):
                raise ValueError(f"Invalid value for '{name}': {value}")
        
        # Get old value for change detection
        try:
            old_resolved = self[name]
        except KeyError:
            old_resolved = None
        
        # Update local value
        self._local_values[name] = SettingValue(mode=mode, value=value)
        
        # Invalidate cache
        self._invalidate_cache(name)
        
        # Get new resolved value
        new_resolved = self[name]
        source = 'local' if mode == SettingMode.SET else 'default'
        
        # Notify if changed
        if old_resolved != new_resolved:
            for cb in self._change_callbacks:
                try:
                    cb(name, new_resolved, source)
                except Exception:
                    pass
        
        # Notify owner (e.g., trigger redraw)
        if self._owner and hasattr(self._owner, 'redraw'):
            self._owner.redraw()
    
    def reset(self, name: str) -> None:
        """Reset setting to AUTO (inherit from global/default)."""
        name = name.lower()
        
        if name not in self._local_values:
            return
        
        try:
            old_resolved = self[name]
        except KeyError:
            old_resolved = None
        
        self._local_values[name] = SettingValue(mode=SettingMode.AUTO)
        
        # Invalidate cache
        self._invalidate_cache(name)
        
        new_resolved = self[name]
        source = self._resolve(name)[1]
        
        if old_resolved != new_resolved:
            for cb in self._change_callbacks:
                try:
                    cb(name, new_resolved, source)
                except Exception:
                    pass
        
        if self._owner and hasattr(self._owner, 'redraw'):
            self._owner.redraw()
    
    def reset_all(self) -> None:
        """Reset all local settings to AUTO."""
        for name in list(self._local_values.keys()):
            self.reset(name)
    
    # =========================================================================
    # Introspection
    # =========================================================================
    
    def get_info(self, name: str) -> SettingInfo:
        """
        Get full resolution info for UI display.
        
        Returns SettingInfo with value, source, override status, etc.
        
        Note: This bypasses the cache intentionally to get fresh source info.
        """
        name = name.lower()
        
        defn = self._get_definition(name)
        if not defn:
            raise KeyError(f"Setting '{name}' not defined")
        
        local = self._local_values.get(name, SettingValue())
        
        # Get global info
        if name in self._local_definitions:
            # Local-only setting
            global_mode = SettingMode.AUTO
            global_value = None
        else:
            global_sv = self._registry.get_global(name)
            global_mode = global_sv.mode
            global_value = global_sv.value
        
        value, source = self._resolve(name)
        
        return SettingInfo(
            name=name,
            value=value,
            source=source,
            is_overridden=source == 'global_override',
            is_inherited=source in ('global', 'default'),
            local_mode=local.mode,
            local_value=local.value,
            global_mode=global_mode,
            global_value=global_value,
            definition=defn,
        )
    
    def get_all_info(self) -> dict[str, SettingInfo]:
        """Get info for all available settings."""
        return {name: self.get_info(name) for name in self}
    
    def get_local_settings(self) -> dict[str, SettingInfo]:
        """Get info for settings that have local values (not AUTO)."""
        result = {}
        for name, sv in self._local_values.items():
            if sv.mode != SettingMode.AUTO:
                result[name] = self.get_info(name)
        return result
    
    # =========================================================================
    # Change Callbacks
    # =========================================================================
    
    def on_change(self, callback: Callable[[str, Any, str], None]) -> None:
        """
        Subscribe to setting changes.
        
        Callback receives: (name, resolved_value, source)
        """
        self._change_callbacks.append(callback)
    
    def remove_callback(self, callback: Callable) -> None:
        """Remove a change callback."""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def to_dict(self) -> dict:
        """
        Serialize local settings state.
        
        Only serializes:
        - Local-only definitions
        - Local values that are explicitly SET
        """
        return {
            'local_values': {
                name: sv.to_dict() 
                for name, sv in self._local_values.items()
                if sv.mode != SettingMode.AUTO
            },
            'local_definitions': {
                name: defn.to_dict()
                for name, defn in self._local_definitions.items()
            }
        }
    
    def from_dict(self, data: dict) -> None:
        """Restore local settings state."""
        type_map = {'int': int, 'float': float, 'str': str, 'bool': bool, 
                    'list': list, 'dict': dict}
        
        # Clear caches
        self._invalidate_cache()
        
        # Restore local-only definitions
        for name, defn_data in data.get('local_definitions', {}).items():
            name = name.lower()
            self._local_definitions[name] = SettingDefinition(
                name=name,
                default=defn_data['default'],
                type_=type_map.get(defn_data.get('type', 'str'), str),
                scope=SettingScope[defn_data.get('scope', 'LOCAL_ONLY')],
                label=defn_data.get('label'),
                description=defn_data.get('description', ''),
                category=defn_data.get('category', 'local'),
                min_value=defn_data.get('min_value'),
                max_value=defn_data.get('max_value'),
                choices=defn_data.get('choices'),
                ui_widget=defn_data.get('ui_widget'),
                ui_order=defn_data.get('ui_order', 0),
            )
            self._local_only_names.add(name)
        
        # Restore values
        for name, sv_data in data.get('local_values', {}).items():
            name = name.lower()
            self._local_values[name] = SettingValue.from_dict(sv_data)
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def cleanup(self) -> None:
        """Cleanup when holder is destroyed."""
        self._registry.remove_listener(self._on_global_change)
        self._change_callbacks.clear()
        self._local_values.clear()
        self._local_definitions.clear()
        self._local_only_names.clear()
        self._value_cache.clear()
    
    def __repr__(self) -> str:
        owner = self._owner_name or 'unknown'
        local_count = sum(1 for sv in self._local_values.values() if sv.mode != SettingMode.AUTO)
        cached_count = len(self._value_cache)
        return f"SettingsHolder(owner={owner}, local_overrides={local_count}, cached={cached_count})"