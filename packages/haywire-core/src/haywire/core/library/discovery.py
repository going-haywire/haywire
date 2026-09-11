"""Discovery of Haywire libraries installed as pip packages.

Libraries are found through the ``haywire.libraries`` entry point group, and
classified as a regular or an editable install by where their module sits.
"""

from __future__ import annotations
import sys
import logging
from pathlib import Path
from typing import Tuple
from importlib.metadata import entry_points, EntryPoint
from importlib import import_module
from dataclasses import dataclass

from .base import BaseLibrary
from .identity import LibraryIdentity
from .install_type import InstallType

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredLibrary:
    """Information about a discovered library"""

    identity: LibraryIdentity
    library_cls: type[BaseLibrary]
    library_path: Path
    install_type: InstallType
    entry_point_name: str | None = None  # Name from entry point (if applicable)
    distribution_name: str | None = None  # Pip package name (e.g. "haybale-visiongraph")


class LibraryDiscovery:
    """Discovers installed Haywire libraries via entry points"""

    ENTRY_POINT_GROUP = "haywire.libraries"

    @classmethod
    def discover_installed_libraries(cls) -> list[DiscoveredLibrary]:
        """Discover all installed Haywire libraries via entry points.

        An entry point that fails to load is logged and skipped, so one broken
        library does not hide the rest. The result is sorted by install type,
        then by library name.
        """
        discovered = []

        try:
            if sys.version_info >= (3, 10):
                eps = entry_points(group=cls.ENTRY_POINT_GROUP)
            else:
                eps = entry_points().get(cls.ENTRY_POINT_GROUP, [])

            for ep in eps:
                try:
                    lib_info = cls._load_library_from_entry_point(ep)
                    if lib_info:
                        discovered.append(lib_info)
                except Exception as e:
                    logger.error(f"Failed to load library from entry point '{ep.name}': {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Entry point discovery failed: {e}", exc_info=True)

        discovered.sort(key=lambda x: (x.install_type.value, x.identity.name))

        return discovered

    @classmethod
    def _load_library_from_entry_point(cls, ep: EntryPoint) -> DiscoveredLibrary | None:
        """Load a library class and its identity from an entry point, or None if either is unusable."""

        try:
            library_cls = ep.load()

            if not issubclass(library_cls, BaseLibrary):
                logger.warning(f"Entry point '{ep.name}' does not point to BaseLibrary subclass")
                return None

            if not hasattr(library_cls, "class_identity"):
                logger.warning(f"Library class {library_cls.__name__} missing @library decorator")
                return None

            identity: LibraryIdentity = library_cls.class_identity

            library_path, install_type = cls._get_library_path_and_type(library_cls)

            logger.info(
                f"Discovered library '{identity.label}' (name: {identity.name}) "
                f"at {library_path} [{install_type.value}]"
            )

            return DiscoveredLibrary(
                identity=identity,
                library_cls=library_cls,
                library_path=library_path,
                install_type=install_type,
                entry_point_name=ep.name,
                distribution_name=ep.dist.name if ep.dist else None,
            )

        except Exception as e:
            logger.error(f"Error loading entry point '{ep.name}': {e}", exc_info=True)
            return None

    @classmethod
    def _get_library_path_and_type(cls, library_cls: type[BaseLibrary]) -> Tuple[Path, InstallType]:
        """Return the directory holding the library's module and its install type.

        Raises:
            RuntimeError: the library's module has no ``__file__``.
        """
        module = import_module(library_cls.__module__)

        if not hasattr(module, "__file__") or not module.__file__:
            raise RuntimeError(f"Cannot determine path for library {library_cls.__name__}")

        module_file = Path(module.__file__)
        library_path = module_file.parent

        install_type = cls._detect_install_type(library_path)

        if install_type == InstallType.REGULAR:
            logger.debug(f"Library '{library_cls.__name__}' is a regular install (hot-reload disabled)")
        else:
            logger.debug(f"Library '{library_cls.__name__}' is an editable install (hot-reload enabled)")

        return library_path, install_type

    @classmethod
    def _detect_install_type(cls, library_path: Path) -> InstallType:
        """Classify a library path as a regular (inside site-packages) or editable install.

        A path that cannot be compared against site-packages is reported as
        editable, with a warning logged.
        """
        try:
            import site

            site_packages = [Path(p) for p in site.getsitepackages()]

            if site.ENABLE_USER_SITE:
                site_packages.append(Path(site.getusersitepackages()))

            for sp in site_packages:
                try:
                    library_path.relative_to(sp)
                    return InstallType.REGULAR
                except ValueError:
                    continue

            return InstallType.EDITABLE

        except Exception as e:
            logger.warning(f"Could not detect install type: {e}, assuming editable")
            return InstallType.EDITABLE

    @classmethod
    def get_regular_installs(cls) -> list[DiscoveredLibrary]:
        """Get only regular (non-editable) installed libraries"""
        all_libs = cls.discover_installed_libraries()
        return [lib for lib in all_libs if lib.install_type == InstallType.REGULAR]

    @classmethod
    def get_editable_installs(cls) -> list[DiscoveredLibrary]:
        """Get only editable installed libraries"""
        all_libs = cls.discover_installed_libraries()
        return [lib for lib in all_libs if lib.install_type == InstallType.EDITABLE]
