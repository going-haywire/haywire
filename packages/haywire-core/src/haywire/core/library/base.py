# haywire.core.library.base.py
from abc import ABC, abstractmethod
import logging
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Tuple, Type, Optional

from haywire.core.namespaces import CATEGORY_LIBRARY_LOG

from haywire.core.errors.haywire_exception import ErrorSeverity, HaywireException
from haywire.core.library.compatibility import CompatibilityWarning
from haywire.core.library.file_watcher import FileWatcher
from haywire.core.library.haybale_toml import (
    HAYBALE_TOML,
    HaybaleTomlError,
    read_haybale_toml,
)
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry, FileChangeEvent, HotReloadRegistry
from haywire.core.debug.keys import library_log_key

logger = logging.getLogger(__name__)


# ============================================================================
#    BASE CLASS
# ============================================================================


class _HaybaleTomlWatcher(HotReloadRegistry):
    """Turns a ``haybale.toml`` write into a metadata refresh.

    An adapter, not a base class: a library is a plugin host, not a registry,
    and this interface is one method — cheap to delegate, misleading to inherit.
    It rides the ordinary root-fallback dispatch so metadata changes travel the
    same path as everything else the watcher sees, rather than a second
    mechanism beside it.
    """

    def __init__(self, library: "BaseLibrary") -> None:
        self._library = library

    def event_dispatcher(self, event: FileChangeEvent) -> None:
        path = Path(event.file_path)
        if path.name != HAYBALE_TOML:
            return
        if path.parent != Path(self._library.identity.folder_path):
            # A nested library's file, seen because the watch is recursive.
            # Its own library owns it.
            return
        self._library._reload_metadata()


class BaseLibrary(ABC):
    """
    Abstract base class for all libraries.

    A subclass must be named ``Library`` and decorated with ``@library``::

        @library(label="my.library")
        class Library(BaseLibrary):
            ...
    """

    # Set by @library decorator at class definition time
    class_identity: ClassVar[LibraryIdentity]

    def __init__(self, file_path: str, enforce_file_watching: bool = False, debounce_delay: float = 0.5):
        self.file_path = file_path
        self.registries: Dict[Type[BaseRegistry[Any]], Any] = {}
        self.enforce_file_watching = enforce_file_watching
        self.debounce_delay = debounce_delay
        # registry_cls -> (folder_path, exclude_patterns)
        self._registry_folders: Dict[Type[BaseRegistry[Any]], Tuple[str, Optional[List[str]]]] = {}

        self._enabled = False  # Library starts disabled by default

        # Initialize FileWatcher with library folder path
        # Note: library_identity will be passed per-folder in add_watch
        if self.identity.folder_path is None:
            raise RuntimeError(
                f"Library '{self.identity.label}' has no folder_path set on its identity. "
                "Library registration must populate folder_path before instantiation."
            )
        self.file_watcher: FileWatcher = FileWatcher(watch_path=self.identity.folder_path)
        # Rides the root fallback like any other registry — see
        # _HaybaleTomlWatcher and _attach_to_registries.
        self._toml_watcher = _HaybaleTomlWatcher(self)

    @property
    def enabled(self) -> bool:
        """Check if the library is currently enabled"""
        return self._enabled

    def enable(self):
        """Enable the library and register its components.

        MAY RUN OFF THE EVENT LOOP — the marketplace calls this from a worker
        thread after an install. So no hook reached from here may call NiceGUI.
        """
        if not self._enabled:
            self._enabled = True
            self.register_components()
            self._attach_to_registries()
            self.on_library_enable()
            if self.enforce_file_watching or self.identity.file_watcher:
                self.file_watcher.start()
            logger.info(f"Library '{self.identity.label}': Enabled and components registered")

    def disable(self):
        """Disable the library and remove its components from registries"""
        if self._enabled:
            self._enabled = False
            self.on_library_disable()
            self._detach_from_registries()
            self.file_watcher.stop()
            logger.info(f"Library '{self.identity.label}': Disabled and components unregistered")

    @property
    def identity(self) -> LibraryIdentity:
        return self.__class__.class_identity

    def compatibility_warnings(self) -> list[CompatibilityWarning]:
        """Author-declared, APPEND-ONLY history of compatibility notices.

        Override in a library subclass to advise users when a graph saved by an
        older version of this library may not reflect a later behavioural change.
        Entries are NEVER removed or re-dated — a graph saved at any past version
        must still trigger the right historical entries.

        Example::

            def compatibility_warnings(self) -> list[CompatibilityWarning]:
                return [
                    CompatibilityWarning(
                        version="0.0.14",                       # where the change landed
                        component=FrameDisplayNode,   # or None for library-wide
                        message="The 'frame' inlet widget strategy became "
                                "author-declared; graphs saved before 0.0.14 may "
                                "hide the preview widget. Reset the node to "
                                "re-derive it from current code.",
                    ),
                ]

        Returns an empty list by default (no warnings declared).
        """
        return []

    def add_registry(self, cls, instance):
        """Add a registry instance for a given registry class"""
        self.registries[cls] = instance

    def get_registry(self, cls):
        """Get a registry instance by its class type"""
        return self.registries.get(cls)

    def on_library_enable(self):
        """Hook called when the library is enabled.

        Override to acquire resources at enable time. Do NOT call NiceGUI from
        here — see :meth:`enable` for why.
        """
        self._register_log_level_setting()

    def on_library_disable(self):
        """Hook called when the library is disabled"""
        self._unregister_log_level_setting()

    def _register_log_level_setting(self) -> None:
        """Register a per-library log level setting in the SettingsRegistry."""
        from haywire.barn.builtin.types import CHOICES
        from haywire.core.settings.registry import SettingsRegistry
        from haywire.core.debug.debug_settings import _GROUP_CHOICES
        from haywire.core.debug.keys import LIBRARY_LOG_LEVEL_FIELD_METATADATA_KEY

        registry: SettingsRegistry = self.get_registry(SettingsRegistry)
        if registry is None:
            return
        lib_id = self.identity.name
        module_name = self.identity.module_name
        if not lib_id or not module_name:
            return
        key = library_log_key(lib_id)
        registry.define(
            name=key,
            default="",
            type_=CHOICES,
            label=self.identity.label,
            description=f"Log level for {module_name} ('' = inherit from root)",
            category=CATEGORY_LIBRARY_LOG,
            widget_config={"options": _GROUP_CHOICES},
            ui_order=0,
            metadata={LIBRARY_LOG_LEVEL_FIELD_METATADATA_KEY: module_name},
        )

    def _unregister_log_level_setting(self) -> None:
        """Remove the per-library log level setting from the SettingsRegistry."""
        from haywire.core.settings.registry import SettingsRegistry

        registry = self.get_registry(SettingsRegistry)
        if registry is None:
            return
        lib_id = self.identity.name
        if not lib_id:
            return
        registry.undefine(library_log_key(lib_id))

    @abstractmethod
    def register_components(self):
        """
        Register this library's components with the global registries
        This method is called by the library registry when loading the library

        Do NOT call NiceGUI from here — see :meth:`enable` for why.
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate that this library is properly structured"""
        pass

    def add_folder_to_registry(
        self,
        folder_path: str,
        registry_cls: Type[BaseRegistry[Any]],
        exclude_patterns: Optional[List[str]] = None,
    ):
        """
        Scan a folder for classes matching the registry's class filter
        and add them to the specified registry.

        This method should only be called by the _init__ method within each library subfolder

        Args:
            folder: Relative folder path within the library
            registry_cls: The registry class to add discovered classes to
        """
        registry: Type[BaseRegistry] = self.get_registry(registry_cls)
        if registry is None:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        if Path(folder_path).resolve() == Path(self.identity.folder_path).resolve():
            # Folder mappings have priority AND exclusivity over root fallbacks
            # in the watcher: if any folder mapping matches a path, the fallbacks
            # are never consulted. Claiming the root as a component folder would
            # therefore starve everything registered on the fallback — including
            # this library's own haybale.toml refresh, which would simply stop
            # firing with nothing to show for it. Register a subfolder.
            raise ValueError(
                f"Library '{self.identity.label}': cannot register the library root "
                f"('{folder_path}') as a component folder for {registry_cls.__name__}. "
                "Register a subfolder (e.g. 'nodes', 'types') instead."
            )

        self._registry_folders[registry_cls] = (folder_path, exclude_patterns)

    # Canonical scan order: settings → state → (types/nodes/adapters/
    # widgets/skins/themes) → panels → editors → farmhands. State must exist before editor
    # CLASS_ADDED events fire;
    # Registry classes not listed here sort to the middle tier (priority 50).
    _REGISTRY_SCAN_PRIORITY: ClassVar[Dict[str, int]] = {
        "ThemeRegistry": 10,
        "SettingsRegistry": 20,
        "LibraryStateRegistry": 30,
        "TypeRegistry": 40,
        "AdapterRegistry": 50,
        "WidgetRegistry": 60,
        "NodeRegistry": 70,
        "SkinRegistry": 80,
        "PanelRegistry": 90,
        "EditorTypeRegistry": 100,
        "FarmhandRegistry": 110,
    }

    def _reload_metadata(self) -> None:
        """Re-read ``haybale.toml`` into :attr:`identity`.

        A metadata edit is not a code change: nothing needs re-importing and no
        class reference goes stale, so this deliberately skips the reload
        pipeline entirely.

        Only the fields that *cannot* be read at the point of use are refreshed.
        ``label`` is logged and rendered from inside the registry, which cannot
        do a file read per line; ``linked_libraries`` is consumed during module
        registration, inside the import machinery; ``on_reload`` is read after a
        library is evicted, when its files may already be gone. Everything else
        — description, tags, urls — is read straight from the file by whoever
        displays it.

        Mutates the identity in place rather than replacing it: the same object
        is held by the watcher's routing tables and by the registry, so a fresh
        instance would update nothing.

        Never raises. The author is mid-keystroke and a half-written file is
        expected; the previous values stay in force until the next save. That is
        the opposite of the import-time rule, where a library that cannot name
        itself must not load at all.
        """
        try:
            fields = read_haybale_toml(Path(self.identity.folder_path))
        except HaybaleTomlError as exc:
            HaywireException.from_exception(
                exception=exc,
                message=f"Library '{self.identity.label}': keeping previous metadata — {exc}",
                severity=ErrorSeverity.WARNING,
                operation="Reload Library Metadata",
            ).enrich(
                library_identity=self.identity,
                module_name=self.identity.module_name,
            ).log(logger)
            return

        for key in ("label", "linked_libraries", "on_reload"):
            if key in fields:
                setattr(self.identity, key, fields[key])
        logger.info(f"Library '{self.identity.label}': reloaded {HAYBALE_TOML}")

    def _attach_to_registries(self):
        """Add ALL library classes to their registries, in canonical scan order."""

        def _priority(item: Tuple[Type[BaseRegistry], Any]) -> int:
            return self._REGISTRY_SCAN_PRIORITY.get(item[0].__name__, 50)

        for registry_cls, (folder_path, exclude_patterns) in sorted(
            self._registry_folders.items(), key=_priority
        ):
            self._register_folder(folder_path, registry_cls, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.add_root_fallback(
                self.identity.folder_path,
                self.identity,
                [*self.registries.values(), self._toml_watcher],
                self.debounce_delay,
            )

    def _detach_from_registries(self):
        """Remove ALL library classes from their registries"""
        for registry_cls, (folder_path, exclude_patterns) in self._registry_folders.items():
            self._unregister_folder(folder_path, registry_cls, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.remove_root_fallback(self.identity.folder_path, self.identity)

        self.file_watcher.stop()

    def _register_folder(
        self,
        folder_path: str,
        registry_cls: Type[BaseRegistry[Any]],
        exclude_patterns: Optional[List[str]] = None,
    ):
        """Inform the registry to add classes from a folder and start watching it if needed"""
        registry: BaseRegistry = self.get_registry(registry_cls)
        if registry is None:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        registry.add_folder(folder_path, self.identity, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.add_watch(folder_path, self.identity, registry, self.debounce_delay)

    def _unregister_folder(
        self,
        folder_path: str,
        registry_cls: Type[BaseRegistry[Any]],
        exclude_patterns: Optional[List[str]] = None,
    ):
        """Inform the registry to remove classes from a folder and stop watching it if needed"""
        registry: BaseRegistry = self.get_registry(registry_cls)
        if registry is None:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        registry.remove_folder(folder_path, self.identity, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.remove_watch(folder_path, self.identity)
