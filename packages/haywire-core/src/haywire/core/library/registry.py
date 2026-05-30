import os
import sys
import importlib
import traceback
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Type
from pathlib import Path
import logging

from .base import BaseLibrary
from .utils import format_external_exception
from .discovery import LibraryDiscovery, DiscoveredLibrary
from .install_type import InstallType
from .identity import LibraryIdentity
from ..host import HostStore
from ..registry.base import BaseRegistry


_HOST_STORE_SECTION = "libraries"
_HOST_STORE_KEY_DISABLED = "disabled"

logger = logging.getLogger(__name__)


class LibraryDiscoveryError(Exception):
    """Base exception for library discovery issues"""

    pass


class LibraryLoadError(LibraryDiscoveryError):
    """Library failed to load properly"""

    pass


class LibraryRegistry:
    """Registry for managing loaded libraries.

    The registry owns the persisted-disabled-state contract: writes go through
    ``HostStore`` (under section ``libraries``, key ``disabled``) whenever
    ``enable_library`` / ``disable_library`` is called. The bootstrap-apply
    path is ``apply_persisted_disabled_state()`` — called once between
    ``scan_for_libraries()`` and ``enable_all_libraries()`` and explicitly
    suppresses the write-through (the values being applied came *from* the
    store; re-writing them would be a no-op churn). See ADR-0001.

    If the host supplied no ``HostStore``, the in-memory default returned by
    ``HostStore.in_memory()`` is used: reads return defaults, writes are
    kept in memory only.
    """

    def __init__(self, host_store: Optional[HostStore] = None):
        # Registry functionality moved from BaseRegistry
        self._libraries: Dict[str, BaseLibrary] = {}  # registry_id -> library_instance
        """key is library_registry_id (e.g. 'visiongraph'), value is the instantiated library object"""
        # registry_cls -> registry instance
        self._class_registries: Dict[Type[BaseRegistry], BaseRegistry] = {}

        # LibraryRegistry specific attributes
        self.discovered_libraries: Dict[str, Dict[str, Any]] = {}
        self._library_root_paths: list[str] = []  # Paths to search for libraries
        self._load_order: list[str] = []
        self.enforce_file_watching = False
        self.debounce_delay = 0.5

        # Track library sources to avoid duplicates
        self._library_sources: Dict[str, str] = {}  # library_id -> source path
        self._library_install_types: Dict[str, InstallType] = {}  # library_id -> install type
        self._library_distribution_names: Dict[str, str] = {}  # library_id -> pip package name

        # Host-provided persistence (engine bootstrap state). When the host
        # supplies no store, a detached in-memory one is used so the registry
        # still has a uniform write interface.
        self._host_store: HostStore = host_store if host_store is not None else HostStore.in_memory()
        # Set of library_registry_ids the user has explicitly disabled. Honored
        # by enable_all_libraries() (skipped during bootstrap) and by
        # _fire_library_enabled paths. Populated from HostStore by
        # apply_persisted_disabled_state() and mutated by
        # enable_library / disable_library at runtime.
        self._user_disabled: set[str] = set()
        # Reentrancy flag: True while apply_persisted_disabled_state() applies
        # values that came *from* the store, so disable_library() doesn't churn
        # the same list back to disk.
        self._suppress_disable_persist: bool = False

        # Loading configuration
        self.load_core_libraries = False  # Load core libraries from src/haywire/libraries
        self.load_pip_packages = True  # Load from pip installed packages
        self.core_libraries_path: Optional[str] = None  # Set during initialization

        # Post-enable callbacks: fired AFTER library.enable() returns
        # successfully. Used by LibraryStateContainer to learn "library X
        # has finished registering all its components" so it can catch up
        # on that library's state classes — the key timing point that
        # avoids the load-order race (see internals/superpowers/plans/...
        # state-container-late-subscription).
        self._library_enabled_callbacks: List[Callable[[BaseLibrary], None]] = []
        # Post-disable callbacks: mirror of the above, fired AFTER
        # library.disable() returns. By that point the CLASS_REMOVED events
        # from _detach_from_registries have drained; the callback is used by
        # LibraryStateContainer to drop the library id from its filter set
        # so events for the (now-disabled) library are subsequently rejected.
        self._library_disabled_callbacks: List[Callable[[BaseLibrary], None]] = []

    def _register(self, library_instance: Any):
        """Register a library instance with its path"""
        library_registry_id = library_instance.identity.id

        self._libraries[library_registry_id] = library_instance

        if library_registry_id not in self._load_order:
            self._load_order.append(library_registry_id)

    def _unregister(self, registry_id: str) -> BaseLibrary | None:
        """Remove a library from the registry"""
        delete_library = self._libraries.get(registry_id)
        if registry_id in self._libraries:
            del self._libraries[registry_id]
        if registry_id in self._load_order:
            self._load_order.remove(registry_id)
        return delete_library

    def list_names(self) -> list[str]:
        """List all registered library names"""
        return list(self._libraries.keys())

    def add_class_registry(self, cls: Type[BaseRegistry], instance: BaseRegistry):
        """
        Add a registry instance for a given registry class
        This allows to dynamically add registries that libraries can use

        Args:
            cls: The class of the registry
            instance: The instance of the registry
        """
        self._class_registries[cls] = instance

    def add_library_root_path(self, path: str):
        """
        Add a path to search for libraries
        Each library root path is scanned for subdirectories containing a library structure.

        Args:
            path: The root path to add
        """
        if path not in self._library_root_paths:
            self._library_root_paths.append(path)

    def enable_file_watching(self, debounce_delay: float = 0.5, force: bool = False):
        """
        Enable file watching for library directories
        This overrides library settings to enforce file watching.

        Args:
            debounce_delay: Delay in seconds to debounce file change events
            force: Force enable even if library settings disable it
        """
        self.debounce_delay = debounce_delay
        self.enforce_file_watching = force

    def add_library_disabled_callback(self, callback: Callable[[BaseLibrary], None]) -> None:
        """Register a callback fired AFTER each library's disable() returns.

        Mirror of ``add_library_enabled_callback``. Used by
        ``LibraryStateContainer`` to drop the library id from its
        ``_enabled_library_ids`` set so subsequent events for the (now
        disabled) library are rejected by the filter.

        Multiple subscribers allowed; callbacks fire in registration order.
        Callbacks that raise are logged but don't propagate.
        """
        self._library_disabled_callbacks.append(callback)

    def _fire_library_disabled(self, library: BaseLibrary) -> None:
        """Invoke every post-disable callback for *library*.

        Called as the last thing in ``disable_library`` after
        ``library.disable()`` has returned (i.e. after on_library_disable,
        _detach_from_registries, file_watcher.stop()). At this point the
        CLASS_REMOVED events from the registry have already drained and
        the container's instance dicts no longer hold this library's
        state instances.
        """
        for callback in self._library_disabled_callbacks:
            try:
                callback(library)
            except Exception as exc:
                logger.error(
                    f"Library '{library.identity.label}': post-disable callback {callback!r} raised: {exc}",
                    exc_info=True,
                )

    def add_library_enabled_callback(self, callback: Callable[[BaseLibrary], None]) -> None:
        """Register a callback fired AFTER each library's enable() returns successfully.

        Used by ``LibraryStateContainer`` to learn when a library has finished
        registering all its components (types, nodes, panels, state classes,
        editors), so it can safely query the state registry for that library's
        state classes and call ``on_enable`` on them. Doing this per-library
        AFTER the library's own ``enable()`` returns is what avoids the
        load-order race where a state ``on_enable`` would otherwise fire
        mid-enable, before the library's other components were available.

        Multiple subscribers are allowed; callbacks fire in registration order.
        Callbacks that raise are logged but don't stop subsequent callbacks
        from running, and don't propagate to the ``enable_*`` caller.
        """
        self._library_enabled_callbacks.append(callback)

    def _fire_library_enabled(self, library: BaseLibrary) -> None:
        """Invoke every post-enable callback for *library*.

        Called as the VERY LAST thing in enable_library / enable_all_libraries,
        after library.enable() has completed (register_components +
        _attach_to_registries + on_library_enable + file_watcher.start()).
        """
        for callback in self._library_enabled_callbacks:
            try:
                callback(library)
            except Exception as exc:
                logger.error(
                    f"Library '{library.identity.label}': post-enable callback {callback!r} raised: {exc}",
                    exc_info=True,
                )

    def enable_all_libraries(self):
        """Enable every loaded library except those the user has explicitly disabled.

        Libraries in ``self._user_disabled`` (populated from HostStore via
        ``apply_persisted_disabled_state`` and mutated at runtime by
        ``disable_library`` / ``enable_library``) skip the enable step.
        """
        for library_id, library in self._libraries.items():
            if library_id in self._user_disabled:
                continue
            library.enable()
            self._fire_library_enabled(library)

    def enable_library(self, library_registry_id: str) -> bool:
        """Enable a specific library. Removes it from the persisted-disabled set."""
        library = self._libraries.get(library_registry_id)
        if not library:
            return False
        self._user_disabled.discard(library_registry_id)
        self._persist_disabled_set()
        library.enable()
        logger.info(f"Library '{library.identity.label}': Enabled")
        self._fire_library_enabled(library)
        return True

    def disable_library(self, library_registry_id: str) -> bool:
        """Disable a specific library. Adds it to the persisted-disabled set."""
        library = self._libraries.get(library_registry_id)
        if not library:
            return False
        self._user_disabled.add(library_registry_id)
        self._persist_disabled_set()
        library.disable()
        logger.info(f"Library '{library.identity.label}': Disabled")
        self._fire_library_disabled(library)
        return True

    def apply_persisted_disabled_state(self) -> None:
        """Populate the user-disabled set from the host store.

        Called once between ``scan_for_libraries()`` and
        ``enable_all_libraries()``. The values being applied came *from* the
        store, so the write-back is suppressed for this call.
        """
        disabled = self._host_store.get(_HOST_STORE_SECTION, _HOST_STORE_KEY_DISABLED, [])
        if not isinstance(disabled, list):
            logger.warning(
                "HostStore: [%s].%s is not a list (got %r); ignoring",
                _HOST_STORE_SECTION,
                _HOST_STORE_KEY_DISABLED,
                disabled,
            )
            return
        self._suppress_disable_persist = True
        try:
            known = set(self._libraries.keys())
            for lib_id in disabled:
                if lib_id in known:
                    self._user_disabled.add(lib_id)
        finally:
            self._suppress_disable_persist = False

    def _persist_disabled_set(self) -> None:
        """Write the current ``_user_disabled`` set to the host store."""
        if self._suppress_disable_persist:
            return
        self._host_store.set(
            _HOST_STORE_SECTION,
            _HOST_STORE_KEY_DISABLED,
            sorted(self._user_disabled),
        )

    def remove_library(self, library_registry_id: str) -> bool:
        """Disable, unregister, and fully remove a library from all tracking dicts.

        After calling this, a subsequent scan_for_libraries() will rediscover
        and reimport the library from scratch, picking up any changes made to
        its source files (e.g. updated @library decorator values).
        """
        library = self._libraries.get(library_registry_id)
        if not library:
            return False
        library.disable()
        self._unregister(library_registry_id)
        source_path = self._library_sources.pop(library_registry_id, None)
        self._library_install_types.pop(library_registry_id, None)
        self._library_distribution_names.pop(library_registry_id, None)

        # Eject stale module objects so scan_for_libraries() does a fresh import
        # rather than returning the cached pre-upgrade module from sys.modules.
        if source_path:
            module_name = os.path.basename(source_path.rstrip("/\\"))
            to_remove = [k for k in sys.modules if k == module_name or k.startswith(module_name + ".")]
            for k in to_remove:
                del sys.modules[k]

        logger.info(f"Library '{library_registry_id}': Fully removed (ready for reload)")
        return True

    def is_library_enabled(self, library_registry_id: str) -> bool:
        """Check if a library is enabled"""
        library = self._libraries.get(library_registry_id)
        return library.enabled if library else False

    def scan_for_libraries(self):
        """
        Discover and load all libraries from multiple sources in priority order:
        1. Core libraries (hardcoded in src/haywire/libraries)
        2. Regular pip installs
        3. Editable pip installs (-e flag)
        4. Manual folder paths (avoiding duplicates)

        This method can be called multiple times to discover
        new libraries added or removed at runtime.
        """
        logger.info("=" * 60)
        logger.info("Starting library discovery and loading process")
        logger.info("=" * 60)

        all_discovered: Dict[str, DiscoveredLibrary] = {}

        # Priority 1: Core libraries (if enabled)
        if self.load_core_libraries and self.core_libraries_path:
            logger.info("\n📦 Priority 1: Loading core libraries...")
            core_libs = self._discover_core_libraries()
            for lib in core_libs:
                all_discovered[lib.identity.id] = lib
                logger.info(f"  ✓ Found core library: {lib.identity.label} ({lib.identity.id})")

        # Priority 2 & 3: Pip installed packages (if enabled)
        if self.load_pip_packages:
            logger.info("\n📦 Priority 2 & 3: Loading pip installed packages...")
            pip_libs = LibraryDiscovery.discover_installed_libraries()

            for lib in pip_libs:
                # Skip if already loaded (e.g., core library already handled)
                if lib.identity.id in all_discovered:
                    logger.info(
                        f"  ⊘ Skipping {lib.identity.label} - already loaded as "
                        f"{all_discovered[lib.identity.id].install_type.value}"
                    )
                    continue

                all_discovered[lib.identity.id] = lib
                install_type_label = (
                    "regular install" if lib.install_type == InstallType.REGULAR else "editable install"
                )
                logger.info(f"  ✓ Found {install_type_label}: {lib.identity.label} ({lib.identity.id})")

        # Priority 4: Manual folder paths
        if self._library_root_paths:
            logger.info("\n📦 Priority 4: Scanning manual folder paths...")
            folder_libs = self._discover_folder_libraries()

            for lib in folder_libs:
                # Skip if already loaded from pip or core
                if lib.identity.id in all_discovered:
                    logger.info(
                        f"  ⊘ Skipping {lib.identity.label} - already loaded as "
                        f"{all_discovered[lib.identity.id].install_type.value}"
                    )
                    continue

                all_discovered[lib.identity.id] = lib
                logger.info(f"  ✓ Found folder library: {lib.identity.label} ({lib.identity.id})")

        # Instantiate and load all discovered libraries
        logger.info("\n🔨 Instantiating and loading libraries...")
        instantiated_libraries = self._instantiate_libraries(all_discovered)

        # Register all instantiated libraries
        logger.info("\n📝 Registering libraries...")
        for library_id, library_instance in instantiated_libraries.items():
            self._register_library_instance(library_instance)

        # Check for removed libraries
        self._cleanup_removed_libraries(all_discovered)

        logger.info("\n" + "=" * 60)
        logger.info(f"Library discovery complete: {len(self._libraries)} libraries loaded")
        logger.info("=" * 60)

    def _scan_directory(self, directory: str) -> Dict[str, str]:
        """Scan a directory for library subdirectories

        Returns:
            Dict mapping library_id -> actual module path containing __init__.py
        """
        lib_folders = {}
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if (
                    os.path.isdir(item_path)
                    and not item.startswith(".")
                    and not item.startswith("__pycache__")
                ):
                    module_paths = self._check_library_structure(item, item_path)
                    for module_path in module_paths:
                        # Use the module folder name as the library_id
                        module_folder_name = os.path.basename(module_path)
                        lib_folders[module_folder_name] = module_path
                        logger.info(f"Valid library found: '{module_folder_name}' at {module_path}")

        except OSError as e:
            logger.error(f"Scanning library directory '{directory}': {e}")

        return lib_folders

    def _check_library_structure(self, library_id: str, library_path: str) -> list[str]:
        """
        Check if a directory follows a valid library structure and return module paths.

        Two patterns:
        1. Flat structure: library_path/__init__.py (e.g., core library)
           → Returns [library_path]

        2. Package structure with pyproject.toml: library_path/pyproject.toml
           → Scans one level deep for folders with __init__.py
           → Returns list of all found module paths (can be multiple libraries in one package)

        Returns:
            List of paths to module directories containing __init__.py
        """
        module_paths = []

        try:
            # Check 1: Flat structure - __init__.py directly in library_path
            flat_init = os.path.join(library_path, "__init__.py")
            if os.path.exists(flat_init):
                return [library_path]

            # Check 2: Package structure - look for pyproject.toml
            pyproject_path = os.path.join(library_path, "pyproject.toml")
            if os.path.exists(pyproject_path):
                # Scan one level deep for folders with __init__.py
                try:
                    for item in os.listdir(library_path):
                        item_path = os.path.join(library_path, item)
                        if (
                            os.path.isdir(item_path)
                            and not item.startswith(".")
                            and not item.startswith("__pycache__")
                        ):
                            init_path = os.path.join(item_path, "__init__.py")
                            if os.path.exists(init_path):
                                module_paths.append(item_path)

                except OSError as e:
                    logger.error(f"Error scanning package directory '{library_path}': {e}")

            if not module_paths:
                logger.error(
                    f"Library '{library_id}': "
                    f"Invalid library structure at '{library_path}'. "
                    f"Expected either '__init__.py' (flat) or "
                    f"'pyproject.toml' with nested modules (package)."
                )

        except Exception as e:
            logger.error(f"Library '{library_id}': Error checking library structure: {e}")

        return module_paths

    def _load_library_class(self, library_folder_name: str, library_path: str) -> type[BaseLibrary]:
        """Load a library class from its path"""
        try:
            # Use the existing metadata loading method to get both module and metadata
            module = self._load_module_and_metadata(library_folder_name, library_path)
            if not (module and hasattr(module, "Library")):
                raise LibraryLoadError(
                    f"Library with folder name '{library_folder_name}': "
                    f"Missing valid 'Library' class in '__init__.py' at '{library_path}'"
                )
            if not hasattr(module.Library, "class_identity"):
                raise LibraryLoadError(
                    f"Library '{library_folder_name}': "
                    f"Has no a valid 'class_identity'. "
                    f"Check if @library decorator is applied to the class in "
                    f"'__init__.py' at '{library_path}'"
                )
            return module.Library

        except Exception as e:
            logger.error(
                f"Library {library_folder_name}: Failed instantiating {e} \n {traceback.format_exc()}"
            )
            raise LibraryLoadError(f"Failed instantiating library {library_folder_name}: {e}")

    def _load_module_and_metadata(self, library_id: str, library_path: str) -> Optional[ModuleType]:
        """
        Load module from a library's __init__.py.
        Handles both flat and package structures automatically.
        """
        module = None
        parent_dir_added = False

        # Determine the proper module path for import
        # Check if this is a core library (in src/haywire/libraries/)
        if "src/haywire/libraries" in library_path:
            # For core libraries, use the haywire.libraries.X import path (flat structure)
            module_path = f"haywire.libraries.{library_id}"
        else:
            # For external libraries, check structure type
            flat_init = os.path.join(library_path, "__init__.py")
            package_init = os.path.join(library_path, library_id, "__init__.py")

            parent_dir = os.path.dirname(library_path)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                parent_dir_added = True

            # Determine if flat or package structure
            if os.path.exists(flat_init):
                # Flat structure: import library_id directly
                module_path = library_id
            elif os.path.exists(package_init):
                # Package structure: import library_id.library_id
                module_path = f"{library_id}.{library_id}"
            else:
                raise ImportError(f"Could not find __init__.py for library '{library_id}'")

        # Import the module using the proper path
        module = importlib.import_module(module_path)

        # Remove from sys.path if we added it
        if parent_dir_added and "src/haywire/libraries" not in library_path:
            parent_dir = os.path.dirname(library_path)
            if parent_dir in sys.path:
                sys.path.remove(parent_dir)

        return module

    def _discover_core_libraries(self) -> list[DiscoveredLibrary]:
        """Discover core libraries from src/haywire/libraries"""
        discovered: list[DiscoveredLibrary] = []

        if not self.core_libraries_path or not os.path.exists(self.core_libraries_path):
            logger.warning(f"Core libraries path not found: {self.core_libraries_path}")
            return discovered

        # Scan the core libraries directory
        lib_folders = self._scan_directory(self.core_libraries_path)

        for library_folder_name, library_path in lib_folders.items():
            try:
                library_cls = self._load_library_class(library_folder_name, library_path)
                identity = library_cls.class_identity

                discovered.append(
                    DiscoveredLibrary(
                        identity=identity,
                        library_cls=library_cls,
                        library_path=Path(library_path),
                        install_type=InstallType.FOLDER,
                        entry_point_name=None,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to load core library '{library_folder_name}': {e}")

        return discovered

    def _discover_folder_libraries(self) -> list[DiscoveredLibrary]:
        """Discover libraries from manual folder paths"""
        discovered = []

        for search_path in self._library_root_paths:
            # Skip core libraries path if it's in the list
            if (
                self.load_core_libraries
                and self.core_libraries_path
                and os.path.samefile(search_path, self.core_libraries_path)
            ):
                continue

            lib_folders = self._scan_directory(search_path)

            for library_folder_name, library_path in lib_folders.items():
                try:
                    library_cls = self._load_library_class(library_folder_name, library_path)
                    identity = library_cls.class_identity

                    discovered.append(
                        DiscoveredLibrary(
                            identity=identity,
                            library_cls=library_cls,
                            library_path=Path(library_path),
                            install_type=InstallType.FOLDER,
                            entry_point_name=None,
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to load folder library '{library_folder_name}': {e}")

        return discovered

    def _instantiate_libraries(self, discovered: Dict[str, DiscoveredLibrary]) -> Dict[str, BaseLibrary]:
        """Instantiate all discovered libraries"""
        instantiated = {}

        for lib_id, lib_info in discovered.items():
            # Skip if already instantiated
            if lib_id in self._libraries:
                continue

            try:
                # Regular pip installs live in site-packages and only change during
                # uv pip install operations. Watching them causes spurious hot-reload
                # events (file deletions, etc.) when other packages are installed.
                # Only enforce file watching for editable or folder-based installs.
                should_watch = self.enforce_file_watching and lib_info.install_type != InstallType.REGULAR

                # Instantiate the library
                library_instance = lib_info.library_cls(
                    str(lib_info.library_path), should_watch, self.debounce_delay
                )

                instantiated[lib_id] = library_instance

                # Track the source, install type, and distribution name
                self._library_sources[lib_id] = str(lib_info.library_path)
                self._library_install_types[lib_id] = lib_info.install_type
                if lib_info.distribution_name:
                    self._library_distribution_names[lib_id] = lib_info.distribution_name

            except Exception as e:
                logger.error(
                    f"Failed to instantiate library '{lib_info.identity.label}': {e}\n"
                    f"{format_external_exception()}"
                )

        return instantiated

    def _register_library_instance(self, library_instance: BaseLibrary):
        """Register a single library instance"""
        try:
            # Add registries to the library
            for reg_cls, ref_i in self._class_registries.items():
                library_instance.add_registry(reg_cls, ref_i)

            # Register the library
            self._register(library_instance)

            logger.info(
                f"  ✓ Registered library: '{library_instance.identity.label}' "
                f"(deps: {library_instance.identity.dependencies})"
            )

        except Exception as e:
            logger.error(
                f"Failed to register library '{library_instance.identity.label}': {e}\n"
                f"{format_external_exception()}"
            )

    def _cleanup_removed_libraries(self, current_discovered: Dict[str, DiscoveredLibrary]):
        """Remove libraries that are no longer discovered"""
        current_lib_ids = set(current_discovered.keys())
        registered_lib_ids = set(self._libraries.keys())

        removed_lib_ids = registered_lib_ids - current_lib_ids

        if removed_lib_ids:
            logger.info("\n🗑  Removing unregistered libraries...")

        for library_id in removed_lib_ids:
            library_instance = self._libraries.get(library_id)
            if library_instance:
                logger.info(f"  ⊘ Removing library '{library_instance.identity.label}'")

                # Disable and unregister
                library_instance.disable()
                self._unregister(library_id)

                # Remove from sources tracking
                if library_id in self._library_sources:
                    del self._library_sources[library_id]
                if library_id in self._library_distribution_names:
                    del self._library_distribution_names[library_id]

    def _has_library_with_path(self, path: str) -> bool:
        """Check if a library with the given path is already registered"""
        for lib in self._libraries.values():
            if lib.file_path == path:
                return True
        return False

    def get_load_order(self) -> list[str]:
        """Get the order in which libraries were loaded"""
        return self._load_order.copy()

    def get_library_identity(self, library_registry_id: str) -> LibraryIdentity:
        """Get metadata for a library.

        Raises:
            KeyError: If no library is registered under this id.
        """
        return self._libraries[library_registry_id].class_identity

    def get_library_source(self, library_id: str) -> str | None:
        """Get the source path for a library"""
        return self._library_sources.get(library_id)

    def get_library_install_type(self, library_id: str) -> InstallType | None:
        """Get the install type for a library"""
        return self._library_install_types.get(library_id)

    def get_library_distribution_name(self, library_id: str) -> str | None:
        """Get the pip distribution name for a library (e.g. 'haybale-visiongraph')"""
        return self._library_distribution_names.get(library_id)

    def find_library_by_distribution_name(self, dist_name: str) -> str | None:
        """Return the library_id for a given pip distribution name, or None."""
        return next(
            (lid for lid, d in self._library_distribution_names.items() if d == dist_name),
            None,
        )
