# haywire.core.library.base.py
from abc import ABC, abstractmethod
import logging
from typing import Any, ClassVar, Dict, List, Tuple, Type, Optional

from haywire.core.namespaces import CATEGORY_LIBRARY_LOG

from haywire.core.library.file_watcher import FileWatcher
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry
from haywire.core.debug.keys import library_log_key

logger = logging.getLogger(__name__)


# ============================================================================
#    BASE CLASS
# ============================================================================


class BaseLibrary(ABC):
    """
    Abstract base class for all libraries

    Usage:

    Libraries that extend this class **must** be named 'Library'
    and be decorated with the @library decorator.
    """

    # Set by @library decorator at class definition time
    class_identity: ClassVar[LibraryIdentity]

    def __init__(self, file_path: str, enforce_file_watching: bool = False, debounce_delay: float = 0.5):
        self.file_path = file_path
        self.registries: Dict[Type[BaseRegistry], Any] = {}
        self.enforce_file_watching = enforce_file_watching
        self.debounce_delay = debounce_delay
        # registry_cls -> (folder_path, exclude_patterns)
        self._registry_folders: Dict[Type[BaseRegistry], Tuple[str, Optional[List[str]]]] = {}

        self._enabled = False  # Library starts disabled by default

        # Initialize FileWatcher with library folder path
        # Note: library_identity will be passed per-folder in add_watch
        if self.identity.folder_path is None:
            raise RuntimeError(
                f"Library '{self.identity.label}' has no folder_path set on its identity. "
                "Library registration must populate folder_path before instantiation."
            )
        self.file_watcher: FileWatcher = FileWatcher(watch_path=self.identity.folder_path)

    @property
    def enabled(self) -> bool:
        """Check if the library is currently enabled"""
        return self._enabled

    def enable(self):
        """Enable the library and register its components"""
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

    def add_registry(self, cls, instance):
        """Add a registry instance for a given registry class"""
        self.registries[cls] = instance

    def get_registry(self, cls):
        """Get a registry instance by its class type"""
        return self.registries.get(cls)

    def on_library_enable(self):
        """Hook called when the library is enabled"""
        self._register_log_level_setting()

    def on_library_disable(self):
        """Hook called when the library is disabled"""
        self._unregister_log_level_setting()

    def _register_log_level_setting(self) -> None:
        """Register a per-library log level setting in the SettingsRegistry."""
        from haywire.core.settings.registry import SettingsRegistry
        from haywire.core.debug.debug_settings import _GROUP_CHOICES
        from haywire.core.debug.keys import LIBRARY_LOG_LEVEL_FIELD_METATADATA_KEY

        registry: SettingsRegistry = self.get_registry(SettingsRegistry)
        if registry is None:
            return
        lib_id = self.identity.id
        module_name = self.identity.module_name
        if not lib_id or not module_name:
            return
        key = library_log_key(lib_id)
        registry.define(
            name=key,
            default="",
            type_=str,
            label=self.identity.label,
            description=f"Log level for {module_name} ('' = inherit from root)",
            category=CATEGORY_LIBRARY_LOG,
            choices=_GROUP_CHOICES,
            ui_order=0,
            metadata={LIBRARY_LOG_LEVEL_FIELD_METATADATA_KEY: module_name},
        )

    def _unregister_log_level_setting(self) -> None:
        """Remove the per-library log level setting from the SettingsRegistry."""
        from haywire.core.settings.registry import SettingsRegistry

        registry = self.get_registry(SettingsRegistry)
        if registry is None:
            return
        lib_id = self.identity.id
        if not lib_id:
            return
        registry.undefine(library_log_key(lib_id))

    @abstractmethod
    def register_components(self):
        """
        Register this library's components with the global registries
        This method is called by the library registry when loading the library
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate that this library is properly structured"""
        pass

    def add_folder_to_registry(
        self, folder_path: str, registry_cls: Type, exclude_patterns: Optional[List[str]] = None
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

        self._registry_folders[registry_cls] = (folder_path, exclude_patterns)

    # Canonical scan order: settings → state → (types/nodes/adapters/widgets/skins/themes)
    # → panels → editors. State must exist before editor CLASS_ADDED events fire.
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
    }

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
                list(self.registries.values()),
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
        self, folder_path: str, registry_cls: Type, exclude_patterns: Optional[List[str]] = None
    ):
        """Inform the registry to add classes from a folder and start watching it if needed"""
        registry: BaseRegistry = self.get_registry(registry_cls)
        if registry is None:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        registry.add_folder(folder_path, self.identity, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.add_watch(folder_path, self.identity, registry, self.debounce_delay)

    def _unregister_folder(
        self, folder_path: str, registry_cls: Type, exclude_patterns: Optional[List[str]] = None
    ):
        """Inform the registry to remove classes from a folder and stop watching it if needed"""
        registry: BaseRegistry = self.get_registry(registry_cls)
        if registry is None:
            raise ValueError(f"Registry {registry_cls} not found in library {self.identity.label}")

        registry.remove_folder(folder_path, self.identity, exclude_patterns)

        if self.enforce_file_watching or self.identity.file_watcher:
            self.file_watcher.remove_watch(folder_path, self.identity)
