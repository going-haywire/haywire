# haywire/core/settings/registry.py
"""
SettingsRegistry - central registry for setting definitions and global values.
Extends BaseRegistry for hot-reload and folder scan support.

Three-tier value storage:
    global tier    (~/.haywire/settings.toml)      — hand-edited by user
    workspace tier (<workspace>/.haywire/settings.toml) — written by UI, saved via save_to_toml()
    local tier     (SettingsHolder per-node)        — serialised into graph JSON

Resolution priority:
    global OVERRIDE > workspace OVERRIDE > local SET > workspace SET > global SET > default
"""

from __future__ import annotations
import threading
import logging
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterator, Type

if TYPE_CHECKING:
    from .settings import Settings

try:
    import toml
except ImportError:
    toml = None

from .enums import FieldMode
from .value import FieldValue
from .descriptor import field
from ..registry.base import BaseRegistry
from ..library.identity import LibraryIdentity


logger = logging.getLogger(__name__)


# Framework identity used when registering built-in schema classes
FRAMEWORK_IDENTITY = LibraryIdentity(
    label="haywire-core",
    version="0.0.0",
    description="Haywire framework built-in settings",
    url="",
    help_url="",
    author="Haywire",
    author_url="",
    id="haywire-core",
    module_name="haywire",
    folder_path="",
)


class SettingsRegistry(BaseRegistry):
    """
    Central registry for setting definitions and global values.

    Extends BaseRegistry for hot-reload and library folder scan support.
    Schema classes (FrameworkSettings / LibrarySettings) can be registered
    via register_schema() or discovered automatically from library folders.

    Two global tiers:
        'global'    — loaded from ~/.haywire/settings.toml, hand-edited, never saved by UI
        'workspace' — loaded from <workspace>/.haywire/settings.toml, written by UI via save_to_toml()

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
        "str": str,
        "string": str,
        "int": int,
        "integer": int,
        "float": float,
        "bool": bool,
        "boolean": bool,
        "list": list,
        "dict": dict,
    }

    TYPE_DEFAULTS = {
        str: "",
        int: 0,
        float: 0.0,
        bool: False,
        list: list,  # factory
        dict: dict,  # factory
    }

    def __init__(self):
        super().__init__()  # sets up BaseRegistry state: _classes, _dependency_graph, etc.

        self._lock = threading.RLock()
        self._definitions: dict[str, field] = {}

        # Two-tier global value storage
        self._global_tier_values: dict[str, FieldValue] = {}
        self._workspace_tier_values: dict[str, FieldValue] = {}

        self._listeners: list[Callable[[str, FieldValue], None]] = []
        self._categories: dict[str, list[str]] = {}

        # Track which definitions came from TOML (vs code)
        self._toml_defined: set[str] = set()

        # File paths per tier
        self._global_path: Path | None = None
        self._workspace_path: Path | None = None

        # File watching per tier
        self._global_observer = None
        self._workspace_observer = None
        self._global_watch_enabled = False
        self._workspace_watch_enabled = False

        # Namespace-scoped weak-ref subscriptions for holder cache invalidation (Option B)
        self._namespace_subscribers: dict[str, list[weakref.ref]] = {}

        # Drain FrameworkSettings classes that were defined before the registry existed
        self._drain_pending_global()

    def _drain_pending_global(self) -> None:
        """Register FrameworkSettings subclasses queued before this registry was created."""
        from .schema import FrameworkSettings, _pending_global

        FrameworkSettings._registry = self
        while _pending_global:
            schema_cls = _pending_global.pop(0)
            self.register_schema(schema_cls)
            schema_cls._registry = self

    # =========================================================================
    # BaseRegistry abstract methods
    # =========================================================================

    def _class_filter(self, cls: Type) -> bool:
        """Accept LibrarySettings and FrameworkSettings subclasses with class_identity."""
        from .schema import LibrarySettings, FrameworkSettings

        return (
            isinstance(cls, type)
            and issubclass(cls, (LibrarySettings, FrameworkSettings))
            and cls not in (LibrarySettings, FrameworkSettings)
            and hasattr(cls, "class_identity")
        )

    def _register_class(self, cls: Type, library_identity: LibraryIdentity) -> str | None:
        """Register schema class fields then store class in BaseRegistry."""
        registry_key = cls.class_identity.registry_key
        self._register_schema_fields(cls)
        cls._registry = self
        return super()._register(registry_key, cls, library_identity or FRAMEWORK_IDENTITY)

    def _unregister_class(self, registry_key: str) -> type | None:
        """Unregister a schema class and remove its field definitions."""
        removed_cls = super()._unregister(registry_key)
        if removed_cls is not None:
            self._unregister_schema_fields(removed_cls)
        return removed_cls

    # =========================================================================
    # Schema field registration helpers
    # =========================================================================

    def _register_schema_fields(self, schema_cls: type["Settings"]) -> None:
        """Register all descriptor fields from a schema class into the definitions."""
        for _name, descriptor in schema_cls._property_fields().items():
            if not descriptor._field_key:
                continue
            self._store_definition(
                descriptor._field_key, descriptor, category=descriptor._category or "general"
            )

    def _notify_listeners(self, name: str, sv: "FieldValue") -> None:
        for listener in self._listeners:
            try:
                listener(name, sv)
            except Exception as e:
                logger.error(f"Listener error for {name}: {e}")

    def _store_definition(self, name: str, descriptor: field, category: str = "general") -> None:
        """Store a descriptor in the definitions dict and initialize tier entries."""
        is_new = name not in self._definitions
        self._definitions[name] = descriptor
        if name not in self._global_tier_values:
            self._global_tier_values[name] = FieldValue(mode=FieldMode.INHERIT)
        if name not in self._workspace_tier_values:
            self._workspace_tier_values[name] = FieldValue(mode=FieldMode.INHERIT)
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)
        if is_new:
            self._notify_listeners(name, FieldValue(mode=FieldMode.INHERIT))

    def _unregister_schema_fields(self, schema_cls: type["Settings"]) -> None:
        """Remove all descriptor fields of a schema class from definitions."""
        changed_keys: set[str] = set()
        with self._lock:
            for descriptor in schema_cls._property_fields().values():
                if not descriptor._field_key:
                    continue
                key = descriptor._field_key
                self._definitions.pop(key, None)
                self._global_tier_values.pop(key, None)
                self._workspace_tier_values.pop(key, None)
                self._toml_defined.discard(key)
                for cat_names in self._categories.values():
                    if key in cat_names:
                        cat_names.remove(key)
                changed_keys.add(key)
        if changed_keys:
            self._notify_namespace_subscribers(changed_keys)

    def register_schema(self, schema_cls, library_identity: LibraryIdentity | None = None) -> str | None:
        """
        Explicitly register a FrameworkSettings or LibrarySettings schema class.

        Creates a class_identity from _namespace if not already present
        (needed for FrameworkSettings built-ins that don't use @settings).

        Idempotent: if the class is already registered in this registry instance,
        returns the existing registry_key without raising.
        """
        if not hasattr(schema_cls, "class_identity"):
            from .decorator import SettingsClassIdentity
            from haywire.core.library.utils import derive_library_identity, reg_key

            ns = schema_cls._namespace
            lib = library_identity or derive_library_identity(schema_cls)
            library_id = lib.id if lib else None
            schema_cls.class_identity = SettingsClassIdentity(
                namespace=ns,
                registry_key=reg_key(library_id, "settings", ns),
                label=ns,
            )
        registry_key = schema_cls.class_identity.registry_key
        if self.has(registry_key):
            return registry_key
        return self._register_class(schema_cls, library_identity or FRAMEWORK_IDENTITY)

    # =========================================================================
    # Namespace subscriptions (Option B — weakref holder cache invalidation)
    # =========================================================================

    def subscribe_namespace(self, namespace: str, callback: weakref.ref) -> None:
        """
        Subscribe a weakref callback to any change under a namespace prefix.

        Called by SettingsHolder to set up targeted cache invalidation.
        """
        self._namespace_subscribers.setdefault(namespace, []).append(callback)

    def _notify_namespace_subscribers(self, changed_keys: set[str]) -> None:
        """
        Notify namespace subscribers for all changed keys.

        Walks all prefixes of each key so that a subscriber on 'ui' gets notified
        when 'ui.node.bg_color' changes.
        """
        for key in changed_keys:
            parts = key.split(".")
            for i in range(1, len(parts) + 1):
                ns = ".".join(parts[:i])
                dead: list[weakref.ref] = []
                for cb_ref in self._namespace_subscribers.get(ns, []):
                    cb = cb_ref()
                    if cb is None:
                        dead.append(cb_ref)
                    else:
                        try:
                            cb(key)
                        except Exception as e:
                            logger.error(f"Namespace subscriber error for {key}: {e}")
                for ref in dead:
                    self._namespace_subscribers[ns].remove(ref)

    # =========================================================================
    # TOML Loading
    # =========================================================================

    def load_from_toml(self, path: Path | str, tier: str = "workspace", watch: bool = False) -> None:
        """
        Load setting values from a TOML file into the specified tier.

        Args:
            path:  Path to the TOML file.
            tier:  'global'    — hand-edited user defaults (~/.haywire/settings.toml)
                   'workspace' — set via UI, saved by save_to_toml() (<workspace>/.haywire/settings.toml)
            watch: If True, hot-reload on file changes.
        """
        if toml is None:
            logger.warning("toml package not installed, cannot load settings file")
            return

        path = Path(path).expanduser().resolve()

        if tier == "global":
            self._global_path = path
        else:
            self._workspace_path = path

        if path.exists():
            self._reload_from_file(path, tier=tier)
        else:
            logger.info(f"Settings file not found, will create on save: {path}")

        if watch:
            watch_flag = f"_{tier}_watch_enabled"
            if not getattr(self, watch_flag, False):
                self._start_file_watcher(path, tier=tier)
                setattr(self, watch_flag, True)

    def _reload_from_file(self, path: Path, tier: str = "workspace") -> None:
        """Parse TOML and apply values into the specified tier dict."""
        try:
            with open(path, "r") as f:
                data = toml.load(f)
        except Exception as e:
            logger.error(f"Failed to parse settings file: {e}")
            return

        tier_dict = self._workspace_tier_values if tier == "workspace" else self._global_tier_values

        with self._lock:
            # Snapshot effective values before change for change notification
            old_effective = {
                name: (self._effective_value(name).mode, self._effective_value(name).value)
                for name in self._definitions
            }

            # Reset this tier's values to AUTO (file is the source of truth for this tier)
            for name in self._definitions:
                tier_dict[name] = FieldValue(mode=FieldMode.INHERIT)

            # Clear TOML-defined definitions that originated from this tier's file
            for name in list(self._toml_defined):
                if name in self._definitions:
                    del self._definitions[name]
                    for cat_names in self._categories.values():
                        if name in cat_names:
                            cat_names.remove(name)
                self._toml_defined.discard(name)

            # Process TOML entries into the tier dict
            flat = self._flatten_toml(data)
            for name, entry in flat.items():
                self._process_entry(name, entry, tier_dict)

            self._notify_changes(old_effective)
            logger.info(f"Loaded {len(flat)} settings from {path} into {tier} tier")

    def _flatten_toml(self, data: dict, prefix: str = "") -> dict[str, Any]:
        """
        Flatten nested TOML to dot-notation keys.

        A dict is a "setting entry" (not namespace) if it contains
        any of: 'value', 'override', 'default', 'type', 'mode'
        """
        result = {}
        setting_keys = {
            "value",
            "override",
            "default",
            "type",
            "mode",
            "label",
            "category",
            "min_value",
            "max_value",
            "choices",
        }

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

    def _process_entry(self, name: str, entry: Any, tier_dict: dict[str, FieldValue]) -> None:
        """Process a single TOML entry into the given tier dict."""
        if isinstance(entry, dict):
            parsed = self._parse_config_dict(name, entry)
        else:
            parsed = {
                "value": entry,
                "mode": FieldMode.EXPLICIT,
            }

        if name not in self._definitions:
            self._auto_define(name, parsed)

        if "value" in parsed and parsed.get("mode") != FieldMode.INHERIT:
            tier_dict[name] = FieldValue(mode=parsed.get("mode", FieldMode.EXPLICIT), value=parsed["value"])

    def _parse_config_dict(self, name: str, config: dict) -> dict:
        """Parse a configuration dict from TOML."""
        result = {}

        if config.get("override", False):
            result["mode"] = FieldMode.OVERRIDE
        elif config.get("mode"):
            result["mode"] = FieldMode[config["mode"].upper()]
        else:
            result["mode"] = FieldMode.EXPLICIT

        if "value" in config:
            result["value"] = config["value"]

        for key in [
            "default",
            "type",
            "label",
            "category",
            "description",
            "min_value",
            "max_value",
            "choices",
            "ui_widget",
            "ui_order",
        ]:
            if key in config:
                result[key] = config[key]

        return result

    def _auto_define(self, name: str, parsed: dict) -> None:
        """Auto-define a setting from TOML that doesn't exist in code."""
        value = parsed.get("value", parsed.get("default"))

        if "type" in parsed:
            type_ = self.TYPE_MAP.get(parsed["type"].lower(), str)
        elif value is not None:
            type_ = type(value)
        else:
            type_ = str

        if "default" in parsed:
            default = parsed["default"]
        elif value is not None:
            default = value
        else:
            default_factory = self.TYPE_DEFAULTS.get(type_, "")
            default = default_factory() if callable(default_factory) else default_factory

        if "label" in parsed:
            label = parsed["label"]
        else:
            label = name.split(".")[-1].replace("_", " ").title()

        if "category" in parsed:
            category = parsed["category"]
        else:
            parts = name.split(".")
            category = ".".join(parts[:-1]) if len(parts) > 1 else "general"

        d = field(
            default=default,
            type_=type_,
            label=label,
            description=parsed.get("description", ""),
            category=category,
            min=parsed.get("min_value"),
            max=parsed.get("max_value"),
            choices=parsed.get("choices"),
            widget=parsed.get("ui_widget"),
            order=parsed.get("ui_order", 0),
        )
        d._attr_name = name.split(".")[-1]
        d._field_key = name

        self._toml_defined.add(name)
        self._store_definition(name, d, category=category)
        logger.debug(f"Auto-defined setting from TOML: {name}")

    def _notify_changes(self, old_effective: dict[str, tuple]) -> None:
        """Notify listeners and namespace subscribers of changed effective values."""
        all_names = set(old_effective.keys()) | set(self._definitions.keys())
        changed_keys: set[str] = set()

        for name in all_names:
            old = old_effective.get(name, (FieldMode.INHERIT, None))
            new = self._effective_value(name)

            if (new.mode, new.value) != old:
                changed_keys.add(name)
                self._notify_listeners(name, new)

        if changed_keys:
            self._notify_namespace_subscribers(changed_keys)

    # =========================================================================
    # TOML Saving  (workspace tier only — global tier is hand-edited)
    # =========================================================================

    _SAVE_DEBOUNCE: float = 0.5  # seconds

    def save_to_toml_debounced(self, path: Path | str | None = None) -> None:
        """Schedule a debounced ``save_to_toml()`` call.

        Each call resets the timer so that the file write only happens
        once the caller stops requesting saves for ``_SAVE_DEBOUNCE`` seconds.
        Useful during continuous interactions like drag-to-change widgets.
        """
        timer = getattr(self, "_save_timer", None)
        if timer is not None:
            timer.cancel()
        self._save_timer = threading.Timer(self._SAVE_DEBOUNCE, self.save_to_toml, args=(path,))
        self._save_timer.daemon = True
        self._save_timer.start()

    def save_to_toml(self, path: Path | str | None = None) -> None:
        """
        Save current workspace-tier values to TOML.

        Only the workspace tier is saved — the global tier is hand-edited by the user
        and is never overwritten by the application.  Only non-AUTO values are written.
        """
        if toml is None:
            logger.warning("toml package not installed, cannot save settings file")
            return

        path = Path(path).expanduser().resolve() if path else self._workspace_path
        if not path:
            raise ValueError("No workspace path configured and no path argument provided")

        data = {}

        with self._lock:
            for name, sv in sorted(self._workspace_tier_values.items()):
                if sv.mode == FieldMode.INHERIT:
                    continue

                if sv.mode == FieldMode.EXPLICIT:
                    entry = sv.value
                else:
                    entry = {"override": True, "value": sv.value}

                self._set_nested(data, name, entry)

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            toml.dump(data, f)

        logger.info(f"Settings saved to {path}")

    def _set_nested(self, data: dict, name: str, value: Any) -> None:
        """Set a value in nested dict using dot-notation key."""
        parts = name.split(".")
        current = data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    # =========================================================================
    # File Watching
    # =========================================================================

    def _start_file_watcher(self, path: Path, tier: str = "workspace") -> None:
        """Watch a config file for changes and reload into the specified tier."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            logger.warning(
                "watchdog not installed, file watching disabled. Install with: pip install watchdog"
            )
            return

        registry = self
        tier_ref = tier

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
                    logger.info(f"Settings file changed ({tier_ref} tier), reloading...")
                    try:
                        registry._reload_from_file(path, tier=tier_ref)
                    except Exception as e:
                        logger.error(f"Failed to reload settings: {e}")

        observer = Observer()
        observer.schedule(ConfigHandler(), str(path.parent), recursive=False)
        observer.start()

        if tier == "global":
            self._global_observer = observer
        else:
            self._workspace_observer = observer

        logger.info(f"Watching settings file ({tier} tier): {path}")

    def stop_watching(self) -> None:
        """Stop all file watchers."""
        for attr in ("_global_observer", "_workspace_observer"):
            observer = getattr(self, attr, None)
            if observer:
                observer.stop()
                observer.join()
                setattr(self, attr, None)
        self._global_watch_enabled = False
        self._workspace_watch_enabled = False

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
        metadata: dict | None = None,
    ) -> field:
        """
        Define a setting from code (authoritative schema).

        Code definitions take precedence over TOML definitions.
        """
        with self._lock:
            self._toml_defined.discard(name)

            d = field(
                default=default,
                type_=type_ or (type(default) if default is not None else str),
                validator=validator,
                label=label or name.split(".")[-1].replace("_", " ").title(),
                description=description,
                category=category,
                min=min_value,
                max=max_value,
                choices=choices,
                widget=ui_widget,
                order=ui_order,
                metadata=metadata,
            )
            d._attr_name = name.split(".")[-1]
            d._field_key = name

            self._store_definition(name, d, category=category)
            return d

    def undefine(self, name: str) -> None:
        """Remove a programmatically-defined setting key.

        Notifies listeners with a FieldValue(mode=AUTO, value=None) sentinel
        so subscribers (e.g. LoggingConfigurator) can react to the removal.
        No-op if the key is not defined.
        """
        with self._lock:
            if name not in self._definitions:
                return
            del self._definitions[name]
            self._global_tier_values.pop(name, None)
            self._workspace_tier_values.pop(name, None)
            self._toml_defined.discard(name)
            for cat_names in self._categories.values():
                if name in cat_names:
                    cat_names.remove(name)
        self._notify_listeners(name, FieldValue(mode=FieldMode.INHERIT))
        self._notify_namespace_subscribers({name})

    def has_definition(self, name: str) -> bool:
        return name in self._definitions

    def get_definition(self, name: str) -> field | None:
        return self._definitions.get(name)

    def all_definitions(self) -> dict[str, field]:
        return dict(self._definitions)

    def definitions_by_category(self) -> dict[str, list[field]]:
        result = {}
        for category, names in self._categories.items():
            defns = [self._definitions[n] for n in names if n in self._definitions]
            if defns:
                result[category] = sorted(defns, key=lambda d: (d._order, d._field_key))
        return result

    # =========================================================================
    # Value Access
    # =========================================================================

    def _effective_value(self, name: str) -> FieldValue:
        """
        Return the merged effective global value for a name.

        Priority: global OVERRIDE > workspace OVERRIDE > workspace SET > global SET > AUTO
        Used internally for change detection and by get_global().
        """
        global_sv = self._global_tier_values.get(name, FieldValue())
        workspace_sv = self._workspace_tier_values.get(name, FieldValue())

        if global_sv.mode == FieldMode.OVERRIDE:
            return global_sv
        if workspace_sv.mode == FieldMode.OVERRIDE:
            return workspace_sv
        if workspace_sv.mode == FieldMode.EXPLICIT:
            return workspace_sv
        if global_sv.mode == FieldMode.EXPLICIT:
            return global_sv
        return FieldValue()  # AUTO

    def get_global(self, name: str) -> FieldValue:
        """
        Get the merged effective global value (workspace tier beats global tier).

        Used by ResolutionChain and SettingsHolder for value resolution.
        """
        return self._effective_value(name)

    def get_global_tier(self, name: str, tier: str = "workspace") -> FieldValue:
        """
        Get the raw FieldValue for a specific tier ('global' or 'workspace').

        Use this for introspection (e.g. get_info() UI display) when you need
        to distinguish which tier a value came from.
        """
        if tier == "global":
            return self._global_tier_values.get(name, FieldValue())
        return self._workspace_tier_values.get(name, FieldValue())

    def set_global(
        self,
        name: str,
        value: Any,
        mode: FieldMode = FieldMode.EXPLICIT,
        tier: str = "workspace",
    ) -> None:
        """
        Set a global value programmatically.

        Args:
            name:  Full setting key (e.g. 'ui.node.bg_color').
            value: New value.
            mode:  FieldMode.EXPLICIT (default) or FieldMode.OVERRIDE.
            tier:  'workspace' (default, saved by UI) or 'global' (hand-edited).
        """
        tier_dict = self._workspace_tier_values if tier == "workspace" else self._global_tier_values

        with self._lock:
            if name not in self._definitions:
                raise KeyError(f"Unknown setting: {name}")

            defn = self._definitions[name]
            if mode != FieldMode.INHERIT and not defn.validate(value):
                raise ValueError(f"Invalid value for '{name}': {value}")

            old_effective = (self._effective_value(name).mode, self._effective_value(name).value)
            tier_dict[name] = FieldValue(mode=mode, value=value)
            new_effective = self._effective_value(name)

            if (new_effective.mode, new_effective.value) != old_effective:
                self._notify_listeners(name, new_effective)
                self._notify_namespace_subscribers({name})

    def reset_global(self, name: str, tier: str = "workspace") -> None:
        """
        Reset a value to AUTO in the specified tier.

        Args:
            name: Full setting key.
            tier: 'workspace' (default) or 'global'.
        """
        tier_dict = self._workspace_tier_values if tier == "workspace" else self._global_tier_values

        with self._lock:
            if name in tier_dict:
                old_effective = (self._effective_value(name).mode, self._effective_value(name).value)
                tier_dict[name] = FieldValue(mode=FieldMode.INHERIT)
                new_effective = self._effective_value(name)

                if (new_effective.mode, new_effective.value) != old_effective:
                    self._notify_listeners(name, new_effective)
                    self._notify_namespace_subscribers({name})

    # =========================================================================
    # Resolution
    # =========================================================================

    def resolve(self, name: str, local: FieldValue | None = None) -> tuple[Any, str]:
        """
        Resolve the final value for a setting given an optional local override.

        Resolution order:
            1. global tier OVERRIDE   → forced (admin policy)
            2. workspace tier OVERRIDE → forced (workspace-wide policy)
            3. local SET              → per-node/per-instance override
            4. workspace tier SET     → workspace default (set via UI)
            5. global tier SET        → user global default (hand-edited)
            6. definition default

        Returns:
            (resolved_value, source) where source is one of:
            'global_override', 'workspace_override', 'local', 'workspace', 'global', 'default'
        """
        defn = self._definitions.get(name)
        if not defn:
            raise KeyError(f"Unknown setting: {name}")

        global_sv = self._global_tier_values.get(name, FieldValue())
        workspace_sv = self._workspace_tier_values.get(name, FieldValue())
        local = local or FieldValue()

        if global_sv.mode == FieldMode.OVERRIDE:
            return global_sv.value, "global_override"

        if workspace_sv.mode == FieldMode.OVERRIDE:
            return workspace_sv.value, "workspace_override"

        if local.mode == FieldMode.EXPLICIT:
            return local.value, "local"

        if workspace_sv.mode == FieldMode.EXPLICIT:
            return workspace_sv.value, "workspace"

        if global_sv.mode == FieldMode.EXPLICIT:
            return global_sv.value, "global"

        default = defn._default() if callable(defn._default) else defn._default
        return default, "default"

    # =========================================================================
    # Listeners
    # =========================================================================

    def add_listener(self, callback: Callable[[str, FieldValue], None]) -> None:
        """
        Add a listener callback that gets called with
        (name, new_effective_value) on any change of any setting.
        """
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, FieldValue], None]) -> None:
        """Remove a listener callback."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    # =========================================================================
    # Iteration
    # =========================================================================

    def registered_schemas(self) -> list[type]:
        """
        All registered FrameworkSettings / LibrarySettings schema classes, in
        registration order.  Useful for building workspace settings panels that
        enumerate settings grouped by schema.
        """
        return list(self._classes.values())

    def definitions_for_schema(self, schema_cls: type) -> dict[str, field]:
        """
        Return all definitions that belong to *schema_cls*, keyed by full_key.

        Matching is done by namespace prefix — every definition whose full_key
        starts with ``schema_cls._namespace + '.'`` is included.  Returns an
        empty dict when the schema has no namespace (i.e. has not been
        registered yet).
        """
        ns = getattr(schema_cls, "_namespace", "")
        if not ns:
            return {}
        prefix = ns + "."
        return {key: defn for key, defn in self._definitions.items() if key.startswith(prefix)}

    def __iter__(self) -> Iterator[str]:
        return iter(self._definitions)

    def __len__(self) -> int:
        return len(self._definitions)

    def __contains__(self, name: str) -> bool:
        return name in self._definitions
