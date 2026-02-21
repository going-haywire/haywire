"""
Library management orchestration layer.

Wraps uv subprocess calls + entry point cache invalidation +
library registry operations into a single service API.
"""

import importlib
import importlib.metadata
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import toml


@dataclass
class MarketplaceEntry:
    """A package available for installation from a marketplace manifest."""
    name: str
    version: str
    description: str = ''
    author: str = ''
    source: str = 'pypi'
    install_spec: str = ''
    tags: list[str] = field(default_factory=list)


@dataclass
class InstalledLibrary:
    """Summary info for an installed library."""
    library_id: str
    label: str
    version: str
    description: str
    author: str
    enabled: bool
    install_type: str  # 'REGULAR', 'EDITABLE', 'FOLDER'
    source_path: str
    tags: list[str] = field(default_factory=list)
    distribution_name: str = ''  # Pip package name (e.g. "haybale-visiongraph")


class LibraryManager:
    """Orchestrates library install/uninstall/enable/disable operations.

    Bridges between uv package management (subprocess) and the
    haywire library registry (in-process).
    """

    def __init__(self, library_registry, venv_path: str | None = None, project_dir: str | None = None):
        self.registry = library_registry
        self.venv_path = venv_path or self._detect_venv()
        self.project_dir = Path(project_dir) if project_dir else None

    def _detect_venv(self) -> str | None:
        """Detect the current virtual environment path."""
        return sys.prefix if hasattr(sys, 'real_prefix') or (
            sys.prefix != sys.base_prefix
        ) else None

    def _run_uv(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run a uv command and return the result."""
        cmd = ['uv', 'pip'] + args
        if self.venv_path:
            cmd.extend(['--python', str(Path(self.venv_path) / 'bin' / 'python')])
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

    def _invalidate_caches(self):
        """Invalidate Python's import and metadata caches after install/uninstall.

        Editable installs create .pth files in site-packages that add source
        directories to sys.path.  These are only processed at interpreter
        startup, so we must manually re-process them for newly installed
        packages to be importable in the running process.
        """
        importlib.invalidate_caches()

        # Re-process .pth files so new editable installs appear on sys.path
        import site
        for sp in site.getsitepackages():
            if Path(sp).is_dir():
                site.addsitedir(sp)

        # Clear importlib.metadata's FastPath cache so freshly installed
        # entry points are visible.  importlib.invalidate_caches() does NOT
        # cover this because MetadataPathFinder isn't in sys.meta_path.
        try:
            importlib.metadata.FastPath.__new__.cache_clear()  # type: ignore[attr-defined]
        except AttributeError:
            pass

    def install(self, install_spec: str) -> tuple[bool, str]:
        """Install a package and register it with the library system.

        Local paths are installed as editable (-e) for hot-reload support.

        Args:
            install_spec: pip-style install specifier
                (e.g. "haybale-opencv>=0.2.0", "git+https://...",
                or "/path/to/local/library")

        Returns:
            (success, message) tuple.
        """
        # Use editable install for local paths
        if Path(install_spec).is_dir():
            result = self._run_uv(['install', '-e', install_spec])
        else:
            result = self._run_uv(['install', install_spec])

        if result.returncode != 0:
            return False, f"Install failed: {result.stderr.strip()}"

        # Invalidate caches so new entry points are visible
        self._invalidate_caches()

        # Re-scan to pick up the new library
        self.registry.scan_for_libraries()

        # Try to enable the newly discovered library
        # We don't know the exact library_id, so enable all new ones
        self.registry.enable_all_libraries()

        return True, f"Installed: {install_spec}"

    def uninstall(self, library_id: str) -> tuple[bool, str]:
        """Disable and uninstall a library by its registry ID.

        Args:
            library_id: The haywire library ID (e.g. "visiongraph").

        Returns:
            (success, message) tuple.
        """
        # Resolve pip distribution name from registry
        dist_name = self.registry.get_library_distribution_name(library_id)
        if not dist_name:
            return False, f"Cannot find pip package name for library '{library_id}'"

        # Disable the library first
        self.registry.disable_library(library_id)

        # Uninstall using the pip distribution name
        result = self._run_uv(['uninstall', dist_name])

        if result.returncode != 0:
            return False, f"Uninstall failed: {result.stderr.strip()}"

        self._invalidate_caches()

        # Re-scan to update registry state
        self.registry.scan_for_libraries()

        return True, f"Uninstalled: {dist_name}"

    def list_installed(self) -> list[InstalledLibrary]:
        """List all discovered libraries with their status."""
        libraries = []
        for lib_id in self.registry.list_names():
            identity = self.registry.get_library_identity(lib_id)
            install_type = self.registry.get_library_install_type(lib_id)
            source = self.registry.get_library_source(lib_id)
            enabled = self.registry.is_library_enabled(lib_id)

            dist_name = self.registry.get_library_distribution_name(lib_id)

            libraries.append(InstalledLibrary(
                library_id=lib_id,
                label=identity.label if identity else lib_id,
                version=identity.version if identity else '',
                description=identity.description if identity else '',
                author=identity.author if identity else '',
                enabled=enabled,
                install_type=install_type.name if install_type else 'UNKNOWN',
                source_path=str(source) if source else '',
                tags=identity.tags if identity and identity.tags else [],
                distribution_name=dist_name or '',
            ))
        return libraries

    def enable_library(self, library_id: str):
        """Enable a library and persist the state."""
        self.registry.enable_library(library_id)
        self._persist_disabled_state()

    def disable_library(self, library_id: str):
        """Disable a library and persist the state."""
        self.registry.disable_library(library_id)
        self._persist_disabled_state()

    def apply_persisted_state(self):
        """Apply persisted disabled state after library discovery.

        Call this after scan_for_libraries() to disable libraries
        that the user previously disabled.
        """
        if not self.project_dir:
            return
        from .config import get_disabled_libraries
        disabled_ids = get_disabled_libraries(self.project_dir)
        for lib_id in disabled_ids:
            if lib_id in self.registry.list_names():
                self.registry.disable_library(lib_id)

    def _persist_disabled_state(self):
        """Save the current disabled library IDs to project config."""
        if not self.project_dir:
            return
        from .config import set_disabled_libraries
        disabled_ids = [
            lib_id for lib_id in self.registry.list_names()
            if not self.registry.is_library_enabled(lib_id)
        ]
        set_disabled_libraries(self.project_dir, disabled_ids)

    @staticmethod
    def load_marketplace(manifest_path: str) -> list[MarketplaceEntry]:
        """Parse a TOML marketplace manifest file.

        Args:
            manifest_path: Path to a marketplace .toml file.

        Returns:
            List of available packages.
        """
        path = Path(manifest_path)
        if not path.exists():
            return []

        data = toml.loads(path.read_text())
        entries = []
        for pkg in data.get('packages', []):
            entries.append(MarketplaceEntry(
                name=pkg.get('name', ''),
                version=pkg.get('version', ''),
                description=pkg.get('description', ''),
                author=pkg.get('author', ''),
                source=pkg.get('source', 'pypi'),
                install_spec=pkg.get('install_spec', pkg.get('name', '')),
                tags=pkg.get('tags', []),
            ))
        return entries
