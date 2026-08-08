# haywire/core/settings/registry.py
"""
SettingsRegistry - central registry for setting definitions and global values.
Extends BaseRegistry for hot-reload and folder scan support.

Three-tier value storage:
    global tier    (~/.haywire/settings.json)      — hand-edited by user
    workspace tier (<workspace>/.haywire/settings.json) — written by UI, saved via save_to_json()
    local tier     (Settings per-node)        — serialised into graph JSON

Each tier value is simply set or unset (SettingValue.is_set); there is no
forcing/OVERRIDE strength (dropped in the P2 tier collapse).

Resolution priority (highest-priority *set* tier wins):
    local SET > workspace SET > global SET > default
"""

from __future__ import annotations
from typing import Any, Callable, Iterator, Optional, Type
import threading
import logging
import weakref
from pathlib import Path

from .value import SettingValue
from .descriptor import setting
from .persistence import SettingsFileStore
from ..registry.base import BaseRegistry
from ..library.identity import LibraryIdentity
from ..types.fields import DataField
from ..types.interface import IType
from .settings import Settings

logger = logging.getLogger(__name__)


# Framework identity used when registering built-in schema classes
FRAMEWORK_IDENTITY = LibraryIdentity(
    label="haywire-core",
    version="0.0.0",
    description="Haywire framework built-in settings",
    authors=["Haywire"],
    id="haywire-core",
    module_name="haywire",
    folder_path="",
)


class SettingsRegistry(BaseRegistry[Settings]):
    """
    Central registry for setting definitions and global values.

    Extends BaseRegistry for hot-reload and library folder scan support.
    Schema classes (FrameworkSettings / LibrarySettings) can be registered
    via register_schema() or discovered automatically from library folders.

    Two global tiers:
        'global'    — loaded from ~/.haywire/settings.json, hand-edited, never saved by UI
        'workspace' — loaded from <workspace>/.haywire/settings.json, written by UI via save_to_json()

    JSON Format (each value serialized via its IType's to_dict):
        { "ui": { "node": { "bg_color": { "value": "#f0f0f0" } } } }   # SET

    Resolution:
        - Not in file → unset (use default from code definition)
        - {"value": X} (or a bare value) → SET (eligible to win)
        - Legacy { "override": true, "value": X } → read as a plain SET of X
        - Unknown setting in file → auto-defined with sensible defaults
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

    # Zero-arg factories per type (str() == "", int() == 0, ...). Uniform
    # callables so the lookup result is always called, not type-tested.
    TYPE_DEFAULTS: dict[type, Callable[[], Any]] = {
        str: str,
        int: int,
        float: float,
        bool: bool,
        list: list,
        dict: dict,
    }

    def __init__(self):
        super().__init__()  # sets up BaseRegistry state: _classes, _dependency_graph, etc.

        self._lock = threading.RLock()
        self._definitions: dict[str, setting] = {}

        # Two-tier global value storage
        self._global_tier_values: dict[str, SettingValue] = {}
        self._workspace_tier_values: dict[str, SettingValue] = {}

        self._subscribers: dict[str | None, list[weakref.ref]] = {}
        self._categories: dict[str, list[str]] = {}

        # One live DataField per definition — THE cell every consumer of a
        # persistent setting binds ("one cell, N views"). Lazily created by
        # cell_for(), kept current by the _notify_subscribers write-through, and
        # dropped with its definition on unregister (hot-reload).
        self._cells: dict[str, "DataField"] = {}

        # Track which definitions came from a settings file (vs code)
        self._file_defined: set[str] = set()

        # File paths per tier
        self._global_path: Path | None = None
        self._workspace_path: Path | None = None

        # File I/O + watching collaborator (persistence.py) — one store, one
        # set of watchdog observers, shared across both tiers. Registry keeps
        # only the per-tier enabled flags (read externally, e.g. di/config.py's
        # status printer).
        self._files = SettingsFileStore()
        self._global_watch_enabled = False
        self._workspace_watch_enabled = False

        # Drain FrameworkSettings classes that were defined before the registry existed
        self._drain_pending_global()

    def _drain_pending_global(self) -> None:
        """Register FrameworkSettings subclasses queued before this registry was created."""
        from .settings_framework import FrameworkSettings, _pending_global

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
        from .settings_library import LibrarySettings
        from .settings_framework import FrameworkSettings

        return (
            isinstance(cls, type)
            and issubclass(cls, (LibrarySettings, FrameworkSettings))
            and cls not in (LibrarySettings, FrameworkSettings)
            and hasattr(cls, "class_identity")
        )

    def _register_class(
        self, cls: type[Settings], library_identity: Optional[LibraryIdentity] = None
    ) -> str | None:
        """Register schema class fields then store class in BaseRegistry.

        After registering the fields, re-reads both settings files (global +
        workspace) for the keys this schema declared. This restores any
        on-disk values for these fields — necessary on re-registration
        (library disable→enable, hot-reload) because
        ``_unregister_schema_fields`` clears the in-memory tier entries
        while the files keep their values.
        """
        registry_key = cls.class_identity.registry_key
        self._register_schema_fields(cls)
        cls._registry = self
        # Collect this schema's setting keys and re-read both settings files
        # so on-disk values survive disable→re-enable / hot-reload cycles.
        schema_keys: set[str] = {d._setting_key for d in cls._property_settings().values() if d._setting_key}
        if schema_keys:
            if self._global_path is not None and self._global_path.exists():
                self._repopulate_from_file_for_keys(schema_keys, self._global_path, tier="global")
            if self._workspace_path is not None and self._workspace_path.exists():
                self._repopulate_from_file_for_keys(schema_keys, self._workspace_path, tier="workspace")
        return super()._register(registry_key, cls, library_identity or FRAMEWORK_IDENTITY)

    def _unregister_class(self, registry_key: str) -> type[Settings] | None:
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
        for _name, descriptor in schema_cls._property_settings().items():
            if not descriptor._setting_key:
                continue
            self._store_definition(
                descriptor._setting_key, descriptor, category=descriptor._category or "root"
            )

    def _notify_subscribers(self, changed: dict[str, "SettingValue"]) -> None:
        """
        Notify all subscribers for a batch of changed keys.

        Exact-key subscribers fire for their key; subscribers registered under
        key=None receive every change. Dead weakrefs are cleaned up.

        Also the single write-through point for registry-owned cells (ADR
        0016): every tier mutation funnels here, so this is where the changed
        key's live cell is brought current — set → the new effective value,
        unset → whatever resolve() now yields (lower tier or default). A key
        whose definition is gone (hot-reload unregister / undefine) drops its
        cell; anything still bound to it holds a frozen, orphaned field.

        Subscriptions are exact-key, plus ``None`` for listen-all (debug
        configurator).
        """
        self._write_through_cells(changed)
        for key, value in changed.items():
            for ns in (key, None):
                dead: list[weakref.ref] = []
                for cb_ref in self._subscribers.get(ns, []):
                    cb = cb_ref()
                    if cb is None:
                        dead.append(cb_ref)
                    else:
                        try:
                            cb(key, value)
                        except Exception as e:
                            logger.error(f"Subscriber error for {key!r} (namespace={ns!r}): {e}")
                for ref in dead:
                    self._subscribers[ns].remove(ref)

    def _write_through_cells(self, changed: dict[str, "SettingValue"]) -> None:
        """Bring registry-owned cells current for a batch of changed keys."""
        for key, value in changed.items():
            cell = self._cells.get(key)
            if cell is None:
                continue
            if key not in self._definitions:
                # Definition gone (unregister/undefine) — the cell dies with it.
                del self._cells[key]
                continue
            new_val = value.value if value.is_set else self.resolve(key)[0]
            if new_val != cell.get_value():
                cell.set_value(new_val)

    def cell_for(self, key: str) -> DataField:
        """THE live cell for a registered setting — one per definition.

        Lazily created, seeded via ``resolve(key)`` (so a tier already loaded
        from JSON seeds correctly), stamped with ``field_id = key``, and kept
        current by the ``_notify_subscribers`` write-through. Settings
        instances and panels borrow this cell by reference — "one cell,
        N views". Raises ``KeyError`` for an unregistered key.
        """
        cell = self._cells.get(key)
        if cell is None:
            defn = self._definitions.get(key)
            if defn is None:
                raise KeyError(f"Unknown setting: {key}")
            value, _source = self.resolve(key)
            itype = defn._type
            if not (isinstance(itype, type) and issubclass(itype, IType)):
                raise TypeError(f"setting {key!r} has no IType (got {itype!r})")
            cell = itype.create_field(default_override={"value": value})
            cell.field_id = key
            self._cells[key] = cell
        return cell

    def _store_definition(self, name: str, descriptor: setting, category: str = "root") -> None:
        """Store a descriptor in the definitions dict and initialize tier entries."""
        is_new = name not in self._definitions
        self._definitions[name] = descriptor
        if name not in self._global_tier_values:
            self._global_tier_values[name] = SettingValue.unset()
        if name not in self._workspace_tier_values:
            self._workspace_tier_values[name] = SettingValue.unset()
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)
        if is_new:
            self._notify_subscribers({name: SettingValue.unset()})

    def _unregister_schema_fields(self, schema_cls: type["Settings"]) -> None:
        """Remove all descriptor fields of a schema class from definitions."""
        changed_keys: set[str] = set()
        with self._lock:
            for descriptor in schema_cls._property_settings().values():
                if not descriptor._setting_key:
                    continue
                key = descriptor._setting_key
                self._definitions.pop(key, None)
                self._global_tier_values.pop(key, None)
                self._workspace_tier_values.pop(key, None)
                self._file_defined.discard(key)
                for cat_names in self._categories.values():
                    if key in cat_names:
                        cat_names.remove(key)
                changed_keys.add(key)
        if changed_keys:
            self._notify_subscribers({k: SettingValue.unset() for k in changed_keys})

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
            from haywire.core.library.utils import SETTING, derive_library_identity, reg_key

            ns = schema_cls._namespace
            lib = library_identity or derive_library_identity(schema_cls)
            reg_key_val = reg_key(lib.id, SETTING, ns)
            schema_cls.class_identity = SettingsClassIdentity(
                namespace=ns,
                registry_id=ns,
                registry_key=reg_key_val,
                label=ns,
                class_name=schema_cls.__name__,
                module=schema_cls.__module__,
            )
        registry_key = schema_cls.class_identity.registry_key
        if self.has(registry_key):
            return registry_key
        return self._register_class(schema_cls, library_identity or FRAMEWORK_IDENTITY)

    # =========================================================================
    # Subscriptions
    # =========================================================================

    def subscribe(self, key: str | None, callback: Callable[[str, "SettingValue"], None]) -> None:
        """
        Subscribe *callback* to setting changes for *key*.

        *key* controls the scope (exact-key only):
            None            — fires on every key change (global listener)
            'ui.node.color' — fires only when that exact key changes

        The callback signature is ``callback(key: str, value: SettingValue)``.

        All subscriptions are stored as weakrefs.  Bound methods must be kept
        alive by the caller (hold a reference to ``self``); plain functions must
        be kept alive by the caller as well.  Raises ``TypeError`` for objects
        that cannot be weakly referenced.
        """
        try:
            ref: weakref.ref = weakref.WeakMethod(callback)  # type: ignore[arg-type]
        except TypeError:
            ref = weakref.ref(callback)
        bucket = self._subscribers.setdefault(key, [])
        if any(r() == callback for r in bucket):
            return  # already subscribed — deduplicate
        bucket.append(ref)

    def unsubscribe(self, key: str | None, callback: Callable[[str, "SettingValue"], None]) -> None:
        """Remove a subscription registered with ``subscribe``."""
        bucket = self._subscribers.get(key, [])
        self._subscribers[key] = [r for r in bucket if r() is not callback]

    # =========================================================================
    # File loading
    # =========================================================================

    def load_from_json(self, path: Path | str, tier: str = "workspace", watch: bool = False) -> None:
        """
        Load setting values from a JSON file into the specified tier.

        Args:
            path:  Path to the JSON file.
            tier:  'global'    — hand-edited user defaults (~/.haywire/settings.json)
                   'workspace' — set via UI, saved by save_to_json() (<workspace>/.haywire/settings.json)
            watch: If True, hot-reload on file changes.
        """
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
                self._files.watch(path, lambda: self._reload_from_file(path, tier=tier))
                setattr(self, watch_flag, True)

    def _reload_from_file(self, path: Path, tier: str = "workspace") -> None:
        """Read *path* via the store and apply its entries into *tier*.

        Used by `load_from_json`, the file watcher callback, and external
        callers (e.g. di/config.py's `reload_settings()`).
        """
        flat = self._files.read(path)
        if flat is None:
            return
        self._apply_file_entries(flat, tier, source=path)

    def _apply_file_entries(self, flat: dict[str, Any], tier: str, source: Path | None = None) -> None:
        """Apply a flat {dot.key: entry} dict into *tier*, replacing its contents.

        The file is the source of truth for this tier: existing values are
        reset to unset, file-defined definitions that originated from this
        tier's file are cleared, then each entry is processed (auto-defining
        unknown keys) before subscribers are notified of the net effective
        change.
        """
        tier_dict = self._workspace_tier_values if tier == "workspace" else self._global_tier_values

        with self._lock:
            # Snapshot effective values before change for change notification
            old_effective = {
                name: (self._effective_value(name).is_set, self._effective_value(name).value)
                for name in self._definitions
            }

            # Reset this tier's values to unset (file is the source of truth for this tier)
            for name in self._definitions:
                tier_dict[name] = SettingValue.unset()

            # Clear file-defined definitions that originated from this tier's file
            for name in list(self._file_defined):
                if name in self._definitions:
                    del self._definitions[name]
                    for cat_names in self._categories.values():
                        if name in cat_names:
                            cat_names.remove(name)
                self._file_defined.discard(name)

            # Process file entries into the tier dict
            for name, entry in flat.items():
                self._process_entry(name, self._rehydrate_entry(name, entry), tier_dict)

            self._notify_changes(old_effective)
            logger.info(f"Loaded {len(flat)} settings from {source} into {tier} tier")

    def _repopulate_from_file_for_keys(self, keys: set[str], path: Path, tier: str = "workspace") -> None:
        """Restore file values for *keys* in *tier* without touching other keys.

        Used by ``_register_class`` to re-hydrate the in-memory tier dict
        for a schema's fields after it's re-registered (library
        disable→re-enable, hot-reload). ``_unregister_schema_fields``
        clears the tier entries when a schema leaves the registry; this
        method puts them back from the on-disk file when the schema
        comes back.

        Unlike ``_reload_from_file``, this does NOT reset other keys'
        tier values or clear ``_file_defined``. Only the entries whose
        flattened key is in *keys* are applied.

        Silently skips if the file can't be parsed — best-effort restore.
        """
        flat = self._files.read(path)
        if flat is None:
            logger.error(f"Failed to parse settings file for key repopulate: {path}")
            return

        tier_dict = self._workspace_tier_values if tier == "workspace" else self._global_tier_values

        with self._lock:
            old_effective = {
                name: (self._effective_value(name).is_set, self._effective_value(name).value)
                for name in keys
                if name in self._definitions
            }

            applied = 0
            for name, entry in flat.items():
                if name not in keys:
                    continue
                self._process_entry(name, self._rehydrate_entry(name, entry), tier_dict)
                applied += 1

            self._notify_changes(old_effective)
            if applied:
                logger.debug(f"Repopulated {applied} setting(s) from {path} into {tier} tier")

    def _process_entry(self, name: str, entry: Any, tier_dict: dict[str, SettingValue]) -> None:
        """Process a single settings-file entry into the given tier dict."""
        if isinstance(entry, dict):
            parsed = self._parse_config_dict(name, entry)
        else:
            parsed = {"value": entry}

        if name not in self._definitions:
            self._auto_define(name, parsed)

        if "value" in parsed:
            tier_dict[name] = SettingValue.of(parsed["value"])

    def _parse_config_dict(self, name: str, config: dict) -> dict:
        """Parse a configuration dict from a settings file (legacy {override,value} → bare value)."""
        result: dict = {}

        # Legacy compatibility: a {override=true, value=X} table from a pre-P2
        # file is read as a plain set value X. The 'override' flag is ignored.
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
            "ui_order",
        ]:
            if key in config:
                result[key] = config[key]

        return result

    def _auto_define(self, name: str, parsed: dict) -> None:
        """Auto-define a setting from a settings file that doesn't exist in code."""
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
            default_factory = self.TYPE_DEFAULTS.get(type_, str)
            default = default_factory()

        if "label" in parsed:
            label = parsed["label"]
        else:
            label = name.split(".")[-1].replace("_", " ").title()

        if "category" in parsed:
            category = parsed["category"]
        else:
            parts = name.split(".")
            category = ".".join(parts[:-1]) if len(parts) > 1 else "root"

        # IType cutover: the descriptor stores an IType, never a Python type.
        # Resolve the inferred Python type to its registered IType via each
        # IType's declared element_type_cls (no hand-maintained mapping). An
        # undeclared settings-file key whose Python type has no registered
        # IType is skipped rather than crashing settings load.
        itype = self._resolve_itype_for_python_type(type_)
        if itype is None:
            logger.warning(
                "Skipping auto-define of '%s': no registered IType for Python type %r", name, type_
            )
            return

        widget_config: dict | None = None
        if parsed.get("choices") is not None:
            # A settings-file "choices" entry auto-defines as CHOICES:
            # the file dialect never speaks widget_key/ui_widget directly, only
            # "choices" -> setting[CHOICES](..., widget_config={"options": ...}).
            from haywire.barn.builtin.types import CHOICES

            itype = CHOICES
            widget_config = {"options": parsed["choices"]}

        d: setting[Any] = setting(
            default=default,
            type_=itype,
            label=label,
            description=parsed.get("description", ""),
            category=category,
            min=parsed.get("min_value"),
            max=parsed.get("max_value"),
            widget_config=widget_config,
            order=parsed.get("ui_order", 0),
        )
        d._attr_name = name.split(".")[-1]
        d._setting_key = name

        self._file_defined.add(name)
        self._store_definition(name, d, category=category)
        logger.debug(f"Auto-defined setting from file: {name}")

    def _resolve_itype_for_python_type(self, py_type: type) -> "type[IType] | None":
        """Resolve an inferred Python type to its registered IType.

        Used only by the runtime/settings-file auto-define path. Prefers the global
        TypeRegistry (source of truth via each IType's ``element_type_cls``); when
        it is unavailable (e.g. an isolated registry in a unit test, or early init
        before libraries load) falls back to the builtin scalar ITypes so a plain
        settings-file scalar still auto-defines. Returns ``None`` only for a Python type
        with no scalar builtin and no registry match.
        """
        try:
            from haywire.core.di.config import get_type_registry

            resolved = get_type_registry().get_type_for_python_type(py_type)
            if resolved is not None:
                return resolved
        except Exception:
            pass

        from haywire.barn.builtin.types import BOOL, FLOAT, INT, STRING

        mapping: dict[type, type[IType]] = {bool: BOOL, int: INT, float: FLOAT, str: STRING}
        return mapping.get(py_type)

    def _notify_changes(self, old_effective: dict[str, tuple]) -> None:
        """Notify subscribers of changed effective values after a settings file reload."""
        all_names = set(old_effective.keys()) | set(self._definitions.keys())
        changed: dict[str, SettingValue] = {}

        for name in all_names:
            old = old_effective.get(name, (False, None))
            new = self._effective_value(name)
            if (new.is_set, new.value) != old:
                changed[name] = new

        if changed:
            self._notify_subscribers(changed)

    # =========================================================================
    # File saving  (workspace tier only — global tier is hand-edited)
    # =========================================================================

    def save_to_json_debounced(self, path: Path | str | None = None) -> None:
        """Schedule a debounced ``save_to_json()`` call.

        Each call resets the timer so that the file write only happens
        once the caller stops requesting saves for the store's debounce
        window. Useful during continuous interactions like drag-to-change
        widgets.

        No-op when there is no workspace path configured AND no path is
        passed in — there is nowhere to persist to (unsaved workspace, or
        test fixture). In-memory tier values still update via set_global;
        only the disk write is skipped.
        """
        if path is None and self._workspace_path is None:
            return

        resolved = Path(path).expanduser().resolve() if path else self._workspace_path
        assert resolved is not None
        self._files.write_debounced(resolved, lambda: self._collect_workspace_entries())

    @property
    def _save_timer(self) -> threading.Timer | None:
        """Exposes the store's debounce timer for introspection (tests)."""
        return self._files._save_timer

    def _collect_workspace_entries(self) -> dict[str, Any]:
        """Snapshot *set* workspace-tier values as their JSON-able form, keyed by dot-key."""
        with self._lock:
            return {
                name: self._value_to_jsonable(name, sv.value)
                for name, sv in sorted(self._workspace_tier_values.items())
                if sv.is_set
            }

    def save_to_json(self, path: Path | str | None = None) -> None:
        """
        Save current workspace-tier values to JSON.

        Only the workspace tier is saved — the global tier is hand-edited by the
        user and is never overwritten by the application. Only *set* values are
        written, each as its IType's to_dict-form (see _value_to_jsonable).
        """
        resolved = Path(path).expanduser().resolve() if path else self._workspace_path
        if not resolved:
            raise ValueError("No workspace path configured and no path argument provided")

        entries = self._collect_workspace_entries()
        self._files.write(resolved, entries)

    # =========================================================================
    # File Watching
    # =========================================================================

    def stop_watching(self) -> None:
        """Stop all file watchers.

        Delegates to the store, which bounds its ``join`` so a watchdog
        observer thread that fails to terminate (seen with the macOS
        FSEvents backend) degrades to a warning instead of wedging the
        caller.
        """
        self._files.stop()
        self._global_watch_enabled = False
        self._workspace_watch_enabled = False

    # =========================================================================
    # Programmatic Definition
    # =========================================================================

    def define(
        self,
        name: str,
        default: Any,
        type_: type[IType],
        label: str | None = None,
        description: str = "",
        category: str = "root",
        min_value: Any = None,
        max_value: Any = None,
        validator: Callable[[Any], bool] | None = None,
        widget_config: dict | None = None,
        ui_order: int = 0,
        metadata: dict | None = None,
    ) -> setting:
        """
        Define a custom setting from code (authoritative schema).

        This creates a new setting definition not associated to any Settings bag
        and adds it to the registry, making it available
        for resolution and UI immediately.

        Code definitions take precedence over file-defined definitions. ``type_``
        must be an IType (e.g. ``FLOAT``). For a dropdown, pass
        ``type_=CHOICES, widget_config={"options": [...]}``.
        """
        with self._lock:
            self._file_defined.discard(name)

            d: setting[Any] = setting(
                default=default,
                type_=type_,
                validator=validator,
                label=label or name.split(".")[-1].replace("_", " ").title(),
                description=description,
                category=category,
                min=min_value,
                max=max_value,
                widget_config=widget_config,
                order=ui_order,
                metadata=metadata,
            )
            d._attr_name = name.split(".")[-1]
            d._setting_key = name

            self._store_definition(name, d, category=category)
            return d

    def undefine(self, name: str) -> None:
        """Remove a programmatically-defined setting key.

        Notifies listeners with an unset SettingValue sentinel so subscribers
        (e.g. LoggingConfigurator) can react to the removal.
        No-op if the key is not defined.
        """
        with self._lock:
            if name not in self._definitions:
                return
            del self._definitions[name]
            self._global_tier_values.pop(name, None)
            self._workspace_tier_values.pop(name, None)
            self._file_defined.discard(name)
            for cat_names in self._categories.values():
                if name in cat_names:
                    cat_names.remove(name)
        self._notify_subscribers({name: SettingValue.unset()})

    def has_definition(self, name: str) -> bool:
        return name in self._definitions

    def get_definition(self, name: str) -> setting | None:
        return self._definitions.get(name)

    def all_definitions(self) -> dict[str, setting]:
        return dict(self._definitions)

    def definitions_by_category(self) -> dict[str, list[setting]]:
        result = {}
        for category, names in self._categories.items():
            defns = [self._definitions[n] for n in names if n in self._definitions]
            if defns:
                result[category] = sorted(defns, key=lambda d: (d._order, d._setting_key))
        return result

    # =========================================================================
    # Value Access
    # =========================================================================

    def _value_to_jsonable(self, name: str, value: Any) -> Any:
        """Convert a live tier value to its JSON-able form via the IType's to_dict.

        Keyed by the setting's declared ``_type``. Unknown keys (auto-defined
        from a file, no code definition) and ITypes without a ``class_identity``
        pass the value through unchanged — a plain JSON scalar.
        """
        defn = self._definitions.get(name)
        itype = getattr(defn, "_type", None) if defn else None
        if itype is None or not hasattr(itype, "class_identity"):
            return value
        try:
            return itype(value).to_dict()
        except Exception:
            return value

    def _value_from_jsonable(self, name: str, raw: Any) -> Any:
        """Inverse of _value_to_jsonable: rehydrate the live value via from_dict.

        A ``{"value": ...}`` dict from a typed key is run through the IType's
        ``from_dict``; anything else (plain scalar, unknown key) passes through.
        """
        defn = self._definitions.get(name)
        itype = getattr(defn, "_type", None) if defn else None
        if itype is None or not hasattr(itype, "from_dict") or not isinstance(raw, dict):
            return raw
        try:
            return itype.from_dict(raw)
        except Exception:
            return raw

    def _rehydrate_entry(self, name: str, entry: Any) -> Any:
        """Rehydrate a flattened JSON entry into the live value for _process_entry.

        ``_process_entry`` expects either a bare scalar or a {"value": …, ...} dict.
        For an ALREADY-DEFINED typed key whose entry is a {"value": …} dict, run
        from_dict so the tier stores the live Python value (Vec2i, etc.); otherwise
        (unknown key — the auto-define path, or a plain scalar) pass through
        unchanged. Only defined keys are rehydrated: ``_value_from_jsonable``
        returns its input as-is when there is no definition yet, so re-wrapping
        that passthrough here would double-wrap the whole entry (including
        auto-define metadata like ``type``/``choices``) inside another
        ``{"value": ...}``.
        """
        if name in self._definitions and isinstance(entry, dict) and "value" in entry:
            return {"value": self._value_from_jsonable(name, entry)}
        return entry

    def _effective_value(self, name: str) -> SettingValue:
        """Return the merged effective global value: workspace-set beats global-set, else unset.

        Used internally for change detection and by get_global().
        """
        workspace_sv = self._workspace_tier_values.get(name, SettingValue.unset())
        if workspace_sv.is_set:
            return workspace_sv
        global_sv = self._global_tier_values.get(name, SettingValue.unset())
        if global_sv.is_set:
            return global_sv
        return SettingValue.unset()

    def get_global(self, name: str) -> SettingValue:
        """
        Get the merged effective global value (workspace tier beats global tier).

        Used by ResolutionChain and Settings for value resolution.
        """
        return self._effective_value(name)

    def get_global_tier(self, name: str, tier: str = "workspace") -> SettingValue:
        """
        Get the raw SettingValue for a specific tier ('global' or 'workspace').

        Use this for introspection (e.g. get_info() UI display) when you need
        to distinguish which tier a value came from.
        """
        if tier == "global":
            return self._global_tier_values.get(name, SettingValue())
        return self._workspace_tier_values.get(name, SettingValue())

    def set_global(
        self,
        name: str,
        value: Any,
        tier: str = "workspace",
    ) -> None:
        """Set a tier value programmatically (marks the tier *set*).

        Args:
            name:  Full setting key (e.g. 'ui.node.bg_color').
            value: New value.
            tier:  'workspace' (default, saved by UI) or 'global' (hand-edited).
        """
        tier_dict = self._workspace_tier_values if tier == "workspace" else self._global_tier_values

        with self._lock:
            if name not in self._definitions:
                raise KeyError(f"Unknown setting: {name}")

            defn = self._definitions[name]
            if not defn.validate(value):
                raise ValueError(f"Invalid value for '{name}': {value}")

            old_effective = (self._effective_value(name).is_set, self._effective_value(name).value)
            tier_dict[name] = SettingValue.of(value)
            new_effective = self._effective_value(name)

            if (new_effective.is_set, new_effective.value) != old_effective:
                self._notify_subscribers({name: new_effective})

    def reset_global(self, name: str, tier: str = "workspace") -> None:
        """Reset a value to *unset* in the specified tier.

        Args:
            name: Full setting key.
            tier: 'workspace' (default) or 'global'.
        """
        tier_dict = self._workspace_tier_values if tier == "workspace" else self._global_tier_values

        with self._lock:
            if name in tier_dict:
                old_effective = (self._effective_value(name).is_set, self._effective_value(name).value)
                tier_dict[name] = SettingValue.unset()
                new_effective = self._effective_value(name)

                if (new_effective.is_set, new_effective.value) != old_effective:
                    self._notify_subscribers({name: new_effective})

    # =========================================================================
    # Resolution
    # =========================================================================

    def resolve(self, name: str, local: SettingValue | None = None) -> tuple[Any, str]:
        """Resolve the final value for a setting given an optional local override.

        Resolution order (highest-priority set tier wins):
            1. local SET            → per-node/per-instance override
            2. workspace tier SET   → workspace default (set via UI)
            3. global tier SET      → user global default (hand-edited)
            4. definition default

        Returns (resolved_value, source) where source is one of:
        'local', 'workspace', 'global', 'default'.
        """
        defn = self._definitions.get(name)
        if not defn:
            raise KeyError(f"Unknown setting: {name}")

        local = local or SettingValue.unset()
        if local.is_set:
            return local.value, "local"

        workspace_sv = self._workspace_tier_values.get(name, SettingValue.unset())
        if workspace_sv.is_set:
            return workspace_sv.value, "workspace"

        global_sv = self._global_tier_values.get(name, SettingValue.unset())
        if global_sv.is_set:
            return global_sv.value, "global"

        # A callable default is late-binding (e.g. "current default skin" —
        # the source registry doesn't exist at class-definition time). It is
        # evaluated here, at resolve/seed time — never on the read path, which
        # is a pure cell read.
        default = defn._default() if callable(defn._default) else defn._default
        return default, "default"

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

    def definitions_for_schema(self, schema_cls: type) -> dict[str, setting]:
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
