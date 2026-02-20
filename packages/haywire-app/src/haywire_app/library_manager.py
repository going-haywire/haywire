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


class LibraryManager:
    """Orchestrates library install/uninstall/enable/disable operations.

    Bridges between uv package management (subprocess) and the
    haywire library registry (in-process).
    """

    def __init__(self, library_registry, venv_path: str | None = None):
        self.registry = library_registry
        self.venv_path = venv_path or self._detect_venv()

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
        """Invalidate Python's import and metadata caches after install/uninstall."""
        importlib.invalidate_caches()
        # importlib.metadata caches distributions internally;
        # clearing is version-dependent but invalidate_caches covers most cases.

    def install(self, install_spec: str) -> tuple[bool, str]:
        """Install a package and register it with the library system.

        Args:
            install_spec: pip-style install specifier
                (e.g. "haybale-opencv>=0.2.0" or "git+https://...")

        Returns:
            (success, message) tuple.
        """
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

    def uninstall(self, package_name: str) -> tuple[bool, str]:
        """Disable and uninstall a package.

        Args:
            package_name: The pip package name (e.g. "haybale-opencv").

        Returns:
            (success, message) tuple.
        """
        # Find matching library by scanning identities
        for lib_id in self.registry.list_names():
            identity = self.registry.get_library_identity(lib_id)
            if identity and identity.label and package_name in (
                lib_id, identity.label
            ):
                self.registry.disable_library(lib_id)
                break

        result = self._run_uv(['uninstall', package_name])

        if result.returncode != 0:
            return False, f"Uninstall failed: {result.stderr.strip()}"

        self._invalidate_caches()

        # Re-scan to update registry state
        self.registry.scan_for_libraries()

        return True, f"Uninstalled: {package_name}"

    def list_installed(self) -> list[InstalledLibrary]:
        """List all discovered libraries with their status."""
        libraries = []
        for lib_id in self.registry.list_names():
            identity = self.registry.get_library_identity(lib_id)
            install_type = self.registry.get_library_install_type(lib_id)
            source = self.registry.get_library_source(lib_id)
            enabled = self.registry.is_library_enabled(lib_id)

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
            ))
        return libraries

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
