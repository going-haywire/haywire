# haywire/core/settings/registry.py
"""
GlobalSettingsRegistry - central registry for setting definitions and global values.
"""

from __future__ import annotations
import threading
import logging
from pathlib import Path
from typing import Any, Callable, Iterator

try:
    import toml
except ImportError:
    toml = None

from .enums import SettingMode, SettingScope
from .value import SettingValue
from .definition import SettingDefinition


logger = logging.getLogger(__name__)


class GlobalSettingsRegistry:
    """
    Central registry for setting definitions and global values.
    
    Registered as singleton via DI:
        get_library_system().get_settings_registry()
    
    TOML Format:
        [ui.node]
        bg_color = "#f0f0f0"                           # SET (simple)
        font_size = { override = true, value = 14 }    # OVERRIDE
        
    Resolution:
        - Not in file → AUTO (use default from code definition)
        - Simple value → SET
        - { override = true, value = X } → OVERRIDE
        - Unknown setting in TOML → auto-defined with sensible defaults
    """
    
    TYPE_MAP = {
        'str': str,
        'string': str,
        'int': int,
        'integer': int,
        'float': float,
        'bool': bool,
        'boolean': bool,
        'list': list,
        'dict': dict,
    }
    
    TYPE_DEFAULTS = {
        str: '',
        int: 0,
        float: 0.0,
        bool: False,
        list: list,  # Factory
        dict: dict,  # Factory
    }
    
    def __init__(self):
        self._lock = threading.RLock()
        self._definitions: dict[str, SettingDefinition] = {}
        self._global_values: dict[str, SettingValue] = {}
        self._listeners: list[Callable[[str, SettingValue], None]] = []
        self._categories: dict[str, list[str]] = {}
        
        # Track which definitions came from TOML (vs code)
        self._toml_defined: set[str] = set()
        
        # File watching
        self._config_path: Path | None = None
        self._observer = None
        self._file_watch_enabled = False
    
    # =========================================================================
    # TOML Loading
    # =========================================================================
    
    def load_from_toml(self, path: Path | str, watch: bool = False) -> None:
        """
        Load setting values from TOML file.
        
        Settings defined in code take precedence for schema.
        Unknown settings in TOML are auto-registered with sensible defaults.
        
        Args:
            path: Path to TOML file
            watch: If True, hot-reload on file changes
        """
        if toml is None:
            logger.warning("toml package not installed, cannot load settings file")
            return
        
        path = Path(path).expanduser().resolve()
        self._config_path = path
        
        if path.exists():
            self._reload_from_file(path)
        else:
            logger.info(f"Settings file not found, will create on save: {path}")
        
        if watch and not self._file_watch_enabled:
            self._start_file_watcher(path)
            self._file_watch_enabled = True
    
    def _reload_from_file(self, path: Path) -> None:
        """Parse TOML and apply values."""
        try:
            with open(path, 'r') as f:
                data = toml.load(f)
        except Exception as e:
            logger.error(f"Failed to parse settings file: {e}")
            return
        
        with self._lock:
            # Track old values for change notification
            old_values = {
                name: (sv.mode, sv.value) 
                for name, sv in self._global_values.items()
            }
            
            # Reset all values to AUTO (file is source of truth for values)
            for name in self._definitions:
                self._global_values[name] = SettingValue(mode=SettingMode.AUTO)
            
            # Clear TOML-defined definitions (will be re-added if still in file)
            for name in list(self._toml_defined):
                if name in self._definitions:
                    del self._definitions[name]
                    # Also remove from categories
                    for cat_names in self._categories.values():
                        if name in cat_names:
                            cat_names.remove(name)
                self._toml_defined.discard(name)
            
            # Process TOML entries
            flat = self._flatten_toml(data)
            for name, entry in flat.items():
                self._process_entry(name, entry)
            
            # Notify listeners of changes
            self._notify_changes(old_values)
            
            logger.info(f"Loaded {len(flat)} settings from {path}")
    
    def _flatten_toml(self, data: dict, prefix: str = '') -> dict[str, Any]:
        """
        Flatten nested TOML to dot-notation keys.
        
        A dict is a "setting entry" (not namespace) if it contains
        any of: 'value', 'override', 'default', 'type', 'mode'
        """
        result = {}
        setting_keys = {'value', 'override', 'default', 'type', 'mode', 
                        'label', 'category', 'min_value', 'max_value', 'choices'}
        
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                if any(k in value for k in setting_keys):
                    result[full_key] = value
                else:
                    result.update(self._flatten_toml(value, full_key))
            else:
                result[full_key] = value
        
        return result
    
    def _process_entry(self, name: str, entry: Any) -> None:
        """Process a single TOML entry."""
        if isinstance(entry, dict):
            parsed = self._parse_config_dict(name, entry)
        else:
            parsed = {
                'value': entry,
                'mode': SettingMode.SET,
            }
        
        # Ensure definition exists
        if name not in self._definitions:
            self._auto_define(name, parsed)
        
        # Apply value
        if 'value' in parsed and parsed.get('mode') != SettingMode.AUTO:
            self._global_values[name] = SettingValue(
                mode=parsed.get('mode', SettingMode.SET),
                value=parsed['value']
            )
    
    def _parse_config_dict(self, name: str, config: dict) -> dict:
        """Parse a configuration dict from TOML."""
        result = {}
        
        if config.get('override', False):
            result['mode'] = SettingMode.OVERRIDE
        elif config.get('mode'):
            result['mode'] = SettingMode[config['mode'].upper()]
        else:
            result['mode'] = SettingMode.SET
        
        if 'value' in config:
            result['value'] = config['value']
        
        for key in ['default', 'type', 'label', 'category', 'description',
                    'min_value', 'max_value', 'choices', 'ui_widget', 'ui_order']:
            if key in config:
                result[key] = config[key]
        
        return result
    
    def _auto_define(self, name: str, parsed: dict) -> None:
        """Auto-define a setting from TOML that doesn't exist in code."""
        value = parsed.get('value', parsed.get('default'))
        
        # Type
        if 'type' in parsed:
            type_ = self.TYPE_MAP.get(parsed['type'].lower(), str)
        elif value is not None:
            type_ = type(value)
        else:
            type_ = str
        
        # Default
        if 'default' in parsed:
            default = parsed['default']
        elif value is not None:
            default = value
        else:
            default_factory = self.TYPE_DEFAULTS.get(type_, '')
            default = default_factory() if callable(default_factory) else default_factory
        
        # Label
        if 'label' in parsed:
            label = parsed['label']
        else:
            label = name.split('.')[-1].replace('_', ' ').title()
        
        # Category
        if 'category' in parsed:
            category = parsed['category']
        else:
            parts = name.split('.')
            category = '.'.join(parts[:-1]) if len(parts) > 1 else 'general'
        
        defn = SettingDefinition(
            name=name,
            default=default,
            type_=type_,
            scope=SettingScope.GLOBAL_AWARE,
            label=label,
            description=parsed.get('description', ''),
            category=category,
            min_value=parsed.get('min_value'),
            max_value=parsed.get('max_value'),
            choices=parsed.get('choices'),
            ui_widget=parsed.get('ui_widget'),
            ui_order=parsed.get('ui_order', 0),
        )
        
        self._definitions[name] = defn
        self._toml_defined.add(name)
        self._global_values[name] = SettingValue(mode=SettingMode.AUTO)
        
        # Add to category
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)
        
        logger.debug(f"Auto-defined setting from TOML: {name}")
    
    def _notify_changes(self, old_values: dict[str, tuple]) -> None:
        """Notify listeners of changed values."""
        all_names = set(old_values.keys()) | set(self._global_values.keys())
        
        for name in all_names:
            old = old_values.get(name, (SettingMode.AUTO, None))
            new = self._global_values.get(name, SettingValue())
            
            if (new.mode, new.value) != old:
                for listener in self._listeners:
                    try:
                        listener(name, new)
                    except Exception as e:
                        logger.error(f"Listener error for {name}: {e}")
    
    # =========================================================================
    # TOML Saving
    # =========================================================================
    
    def save_to_toml(self, path: Path | str | None = None) -> None:
        """
        Save current values to TOML.
        
        Only saves non-AUTO values. Uses minimal format where possible.
        """
        if toml is None:
            logger.warning("toml package not installed, cannot save settings file")
            return
        
        path = Path(path).expanduser().resolve() if path else self._config_path
        if not path:
            raise ValueError("No path specified and no config file loaded")
        
        data = {}
        
        with self._lock:
            for name, sv in sorted(self._global_values.items()):
                if sv.mode == SettingMode.AUTO:
                    continue
                
                if sv.mode == SettingMode.SET:
                    entry = sv.value
                else:
                    entry = {'override': True, 'value': sv.value}
                
                self._set_nested(data, name, entry)
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            toml.dump(data, f)
        
        logger.info(f"Settings saved to {path}")
    
    def _set_nested(self, data: dict, name: str, value: Any) -> None:
        """Set a value in nested dict using dot-notation key."""
        parts = name.split('.')
        current = data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    
    # =========================================================================
    # File Watching
    # =========================================================================
    
    def _start_file_watcher(self, path: Path) -> None:
        """Watch config file for changes."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            logger.warning(
                "watchdog not installed, file watching disabled. "
                "Install with: pip install watchdog"
            )
            return
        
        registry = self
        
        class ConfigHandler(FileSystemEventHandler):
            def __init__(self):
                self._debounce_time = 0
            
            def on_modified(self, event):
                import time
                now = time.time()
                if now - self._debounce_time < 0.5:
                    return
                self._debounce_time = now
                
                if Path(event.src_path).resolve() == path:
                    logger.info("Settings file changed, reloading...")
                    try:
                        registry._reload_from_file(path)
                    except Exception as e:
                        logger.error(f"Failed to reload settings: {e}")
        
        self._observer = Observer()
        self._observer.schedule(ConfigHandler(), str(path.parent), recursive=False)
        self._observer.start()
        logger.info(f"Watching settings file: {path}")
    
    def stop_watching(self) -> None:
        """Stop file watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            self._file_watch_enabled = False
    
    # =========================================================================
    # Programmatic Definition
    # =========================================================================
    
    def define(
        self,
        name: str,
        default: Any,
        type_: type | None = None,
        label: str | None = None,
        description: str = "",
        category: str = "general",
        min_value: Any = None,
        max_value: Any = None,
        choices: list | None = None,
        validator: Callable[[Any], bool] | None = None,
        ui_widget: str | None = None,
        ui_order: int = 0,
    ) -> SettingDefinition:
        """
        Define a setting from code (authoritative schema).
        
        Code definitions take precedence over TOML definitions.
        """
        with self._lock:
            self._toml_defined.discard(name)
            
            defn = SettingDefinition(
                name=name,
                default=default,
                type_=type_ or type(default),
                scope=SettingScope.GLOBAL_AWARE,
                label=label,
                description=description,
                category=category,
                min_value=min_value,
                max_value=max_value,
                choices=choices,
                validator=validator,
                ui_widget=ui_widget,
                ui_order=ui_order,
            )
            
            self._definitions[name] = defn
            
            if name not in self._global_values:
                self._global_values[name] = SettingValue(mode=SettingMode.AUTO)
            
            if category not in self._categories:
                self._categories[category] = []
            if name not in self._categories[category]:
                self._categories[category].append(name)
            
            return defn
    
    def has_definition(self, name: str) -> bool:
        return name in self._definitions
    
    def get_definition(self, name: str) -> SettingDefinition | None:
        return self._definitions.get(name)
    
    def all_definitions(self) -> dict[str, SettingDefinition]:
        return dict(self._definitions)
    
    def definitions_by_category(self) -> dict[str, list[SettingDefinition]]:
        result = {}
        for category, names in self._categories.items():
            defns = [self._definitions[n] for n in names if n in self._definitions]
            if defns:
                result[category] = sorted(defns, key=lambda d: (d.ui_order, d.name))
        return result
    
    # =========================================================================
    # Value Access
    # =========================================================================
    
    def get_global(self, name: str) -> SettingValue:
        """Get raw global value (mode + value)."""
        return self._global_values.get(name, SettingValue())
    
    def set_global(
        self, 
        name: str, 
        value: Any, 
        mode: SettingMode = SettingMode.SET
    ) -> None:
        """Set a global value programmatically."""
        with self._lock:
            if name not in self._definitions:
                raise KeyError(f"Unknown setting: {name}")
            
            defn = self._definitions[name]
            if mode != SettingMode.AUTO and not defn.validate(value):
                raise ValueError(f"Invalid value for '{name}': {value}")
            
            old = self._global_values.get(name, SettingValue())
            self._global_values[name] = SettingValue(mode=mode, value=value)
            
            if (old.mode, old.value) != (mode, value):
                for listener in self._listeners:
                    try:
                        listener(name, self._global_values[name])
                    except Exception as e:
                        logger.error(f"Listener error: {e}")
    
    def reset_global(self, name: str) -> None:
        """Reset to AUTO (use default)."""
        with self._lock:
            if name in self._global_values:
                old = self._global_values[name]
                self._global_values[name] = SettingValue(mode=SettingMode.AUTO)
                
                if old.mode != SettingMode.AUTO:
                    for listener in self._listeners:
                        try:
                            listener(name, self._global_values[name])
                        except Exception as e:
                            logger.error(f"Listener error: {e}")
    
    # =========================================================================
    # Resolution
    # =========================================================================
    
    def resolve(
        self, 
        name: str, 
        local: SettingValue | None = None
    ) -> tuple[Any, str]:
        """
        Resolve final value given optional local setting.
        
        Resolution order:
        1. Global OVERRIDE → forced
        2. Local SET → local wins
        3. Global SET → global default
        4. Definition default
        
        Returns:
            (resolved_value, source)
        """
        defn = self._definitions.get(name)
        if not defn:
            raise KeyError(f"Unknown setting: {name}")
        
        global_ = self._global_values.get(name, SettingValue())
        local = local or SettingValue()
        
        if global_.mode == SettingMode.OVERRIDE:
            return global_.value, 'global_override'
        
        if local.mode == SettingMode.SET:
            return local.value, 'local'
        
        if global_.mode == SettingMode.SET:
            return global_.value, 'global'
        
        return defn.default, 'default'
    
    # =========================================================================
    # Listeners
    # =========================================================================
    
    def add_listener(self, callback: Callable[[str, SettingValue], None]) -> None:
        self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[str, SettingValue], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    # =========================================================================
    # Iteration
    # =========================================================================
    
    def __iter__(self) -> Iterator[str]:
        return iter(self._definitions)
    
    def __len__(self) -> int:
        return len(self._definitions)
    
    def __contains__(self, name: str) -> bool:
        return name in self._definitions