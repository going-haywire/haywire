"""
Library discovery system for installed Haywire libraries via entry points.

This module provides functionality to discover libraries installed as pip packages
through the standard Python entry points mechanism.
"""
from __future__ import annotations
import sys
import logging
from pathlib import Path
from typing import Iterator, Tuple
from importlib.metadata import entry_points, EntryPoint, PackageNotFoundError
from importlib import import_module
from dataclasses import dataclass
from enum import Enum

from .base import BaseLibrary
from .identity import LibraryIdentity

logger = logging.getLogger(__name__)


class InstallType(Enum):
    """Types of library installations"""
    REGULAR = "regular"      # Installed in site-packages
    EDITABLE = "editable"    # Installed with -e flag
    FOLDER = "folder"        # Discovered via folder scanning


@dataclass
class DiscoveredLibrary:
    """Information about a discovered library"""
    identity: LibraryIdentity
    library_cls: type[BaseLibrary]
    library_path: Path
    install_type: InstallType
    entry_point_name: str | None = None  # Name from entry point (if applicable)


class LibraryDiscovery:
    """Discovers installed Haywire libraries via entry points"""
    
    ENTRY_POINT_GROUP = 'haywire.libraries'
    
    @classmethod
    def discover_installed_libraries(cls) -> list[DiscoveredLibrary]:
        """
        Discover all installed Haywire libraries via entry points.
        
        Returns:
            List of DiscoveredLibrary objects, separated by install type
        """
        discovered = []
        
        try:
            # Get entry points for Python 3.10+
            if sys.version_info >= (3, 10):
                eps = entry_points(group=cls.ENTRY_POINT_GROUP)
            else:
                # Fallback for Python 3.9
                eps = entry_points().get(cls.ENTRY_POINT_GROUP, [])
            
            for ep in eps:
                try:
                    lib_info = cls._load_library_from_entry_point(ep)
                    if lib_info:
                        discovered.append(lib_info)
                except Exception as e:
                    logger.error(
                        f"Failed to load library from entry point '{ep.name}': {e}",
                        exc_info=True
                    )
        
        except Exception as e:
            logger.error(f"Entry point discovery failed: {e}", exc_info=True)
        
        # Sort by install type: regular first, then editable
        discovered.sort(key=lambda x: (x.install_type.value, x.identity.id))
        
        return discovered
    
    @classmethod
    def _load_library_from_entry_point(cls, ep: EntryPoint) -> DiscoveredLibrary | None:
        """Load library class and metadata from entry point"""
        
        try:
            # Load the library class
            library_cls = ep.load()
            
            # Validate it's a BaseLibrary subclass
            if not issubclass(library_cls, BaseLibrary):
                logger.warning(
                    f"Entry point '{ep.name}' does not point to BaseLibrary subclass"
                )
                return None
            
            # Get library identity from decorator
            if not hasattr(library_cls, 'class_identity'):
                logger.warning(
                    f"Library class {library_cls.__name__} missing @library decorator"
                )
                return None
            
            identity: LibraryIdentity = library_cls.class_identity
            
            # Get library file path and determine install type
            library_path, install_type = cls._get_library_path_and_type(library_cls)
            
            logger.info(
                f"Discovered library '{identity.label}' (id: {identity.id}) "
                f"at {library_path} [{install_type.value}]"
            )
            
            return DiscoveredLibrary(
                identity=identity,
                library_cls=library_cls,
                library_path=library_path,
                install_type=install_type,
                entry_point_name=ep.name
            )
        
        except Exception as e:
            logger.error(f"Error loading entry point '{ep.name}': {e}", exc_info=True)
            return None
    
    @classmethod
    def _get_library_path_and_type(cls, library_cls: type[BaseLibrary]) -> Tuple[Path, InstallType]:
        """
        Get library path and determine if it's an editable or regular install.
        
        Returns:
            Tuple of (library_path, install_type)
        """
        module = import_module(library_cls.__module__)
        
        if not hasattr(module, '__file__') or not module.__file__:
            raise RuntimeError(
                f"Cannot determine path for library {library_cls.__name__}"
            )
        
        module_file = Path(module.__file__)
        library_path = module_file.parent
        
        # Determine if editable install by checking if it's in site-packages
        install_type = cls._detect_install_type(library_path)
        
        if install_type == InstallType.REGULAR:
            logger.debug(
                f"Library '{library_cls.__name__}' is a regular install "
                f"(hot-reload disabled)"
            )
        else:
            logger.debug(
                f"Library '{library_cls.__name__}' is an editable install "
                f"(hot-reload enabled)"
            )
        
        return library_path, install_type
    
    @classmethod
    def _detect_install_type(cls, library_path: Path) -> InstallType:
        """
        Detect if library is a regular or editable install.
        
        Editable installs are outside site-packages.
        Regular installs are inside site-packages.
        """
        # Get site-packages locations
        try:
            import site
            site_packages = [Path(p) for p in site.getsitepackages()]
            
            # Also check user site-packages
            if site.ENABLE_USER_SITE:
                site_packages.append(Path(site.getusersitepackages()))
            
            # Check if library_path is within any site-packages directory
            for sp in site_packages:
                try:
                    library_path.relative_to(sp)
                    return InstallType.REGULAR  # Inside site-packages
                except ValueError:
                    continue  # Not relative to this site-packages
            
            # Not in any site-packages = editable install
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
