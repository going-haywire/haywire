"""
Library management orchestration layer.

Wraps uv subprocess calls + entry point cache invalidation +
library registry operations into a single service API.
"""

import asyncio
import importlib
import importlib.metadata
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from haywire.core.library.registry import LibraryRegistry
from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType
from haywire.core.library.decorator_io import _set_decorator_list_field
from haywire.core.marketstall import Haybale
import toml


def _sanitize_name(name: str) -> str:
    """Convert a name to a valid Python identifier suffix (mirrors init.py logic)."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized


_DECLARABLE_OS_VALUES = ("macos", "windows", "linux")  # spec §2.1


def _parse_git_install_spec(install_spec: str) -> tuple[str, str | None]:
    """Parse a PEP 440 VCS URL into (git_url, subdirectory|None).

    Accepts both the bare form (``git+https://…[#subdirectory=…]``) and the
    PEP 440 form with a leading ``name @ `` prefix.
    """
    spec = install_spec.strip()
    if " @ " in spec:
        spec = spec.split(" @ ", 1)[1].strip()
    spec = spec.removeprefix("git+")
    if "#subdirectory=" in spec:
        url, sub = spec.split("#subdirectory=", 1)
        return url.strip(), sub.strip() or None
    return spec, None


def _write_install_to_pyproject(
    pyproject_path: Path,
    pkg_name: str,
    version: str | None,
    source: str,
    install_spec: str,
) -> None:
    """Write/update a project pyproject.toml entry for an installed haybale.

    Spec rows:
      - pypi → only ``[project] dependencies = "<name>~=X.Y.Z"``
      - git  → ``[project] dependencies`` + ``[tool.uv.sources]`` with git+subdirectory
      - local (heap outside barn) → ``[project] dependencies`` +
        ``[tool.uv.sources]`` with ``{ path = "...", editable = true }``

    The caller decides which rows apply; this helper just writes what it's told.
    """
    data = toml.loads(pyproject_path.read_text())
    project = data.setdefault("project", {})
    deps: list[str] = project.setdefault("dependencies", [])

    floor = f"{pkg_name}~={version}" if version else pkg_name
    new_deps: list[str] = []
    found = False
    for entry in deps:
        if _dep_name(entry).lower() == pkg_name.lower():
            new_deps.append(floor)
            found = True
        else:
            new_deps.append(entry)
    if not found:
        new_deps.append(floor)
    project["dependencies"] = new_deps

    if source == "git":
        url, subdir = _parse_git_install_spec(install_spec)
        git_entry: dict[str, Any] = {"git": url}
        if subdir:
            git_entry["subdirectory"] = subdir
        sources = data.setdefault("tool", {}).setdefault("uv", {}).setdefault("sources", {})
        sources[pkg_name] = git_entry
    elif source == "local":
        sources = data.setdefault("tool", {}).setdefault("uv", {}).setdefault("sources", {})
        sources[pkg_name] = {"path": install_spec, "editable": True}

    pyproject_path.write_text(toml.dumps(data))


def _remove_install_from_pyproject(pyproject_path: Path, pkg_name: str) -> None:
    """Remove a haybale's entry from [project] dependencies and [tool.uv.sources]."""
    data = toml.loads(pyproject_path.read_text())
    project = data.get("project")
    if project:
        deps = project.get("dependencies", [])
        project["dependencies"] = [d for d in deps if _dep_name(d).lower() != pkg_name.lower()]

    sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    sources.pop(pkg_name, None)
    # Also try a hyphen/underscore variant — uv normalizes these.
    sources.pop(pkg_name.replace("-", "_"), None)
    sources.pop(pkg_name.replace("_", "-"), None)

    pyproject_path.write_text(toml.dumps(data))


def _dep_name(dep_entry: str) -> str:
    """Extract the bare package name from a PEP 508 dependency string."""
    # Strip extras, version specifiers, markers, and the ``name @ url`` form.
    head = dep_entry.split(";", 1)[0]
    head = head.split(" @ ", 1)[0]
    head = re.split(r"[\[<>=!~ ]", head, maxsplit=1)[0]
    return head.strip()


def _apply_os_to_pyproject(pyproject_path: Path, os_values: list[str]) -> None:
    """Write or remove [tool.haywire].os in the library's pyproject.toml.

    Spec §2.1 rules:
      - Filter to allowed values (macos, windows, linux); silently drop others.
      - Empty list after filtering OR all three present → remove [tool.haywire].os
        entirely (absent = "all platforms").
      - Non-empty subset → write the filtered list in canonical order.
      - Preserves other [tool.*] sections (hatch, etc.) verbatim.
    """
    # Filter to allowed values, then canonicalize order to (macos, windows, linux).
    filtered = [v for v in _DECLARABLE_OS_VALUES if v in os_values]

    data = toml.loads(pyproject_path.read_text())
    tool = data.setdefault("tool", {})

    if not filtered or len(filtered) == len(_DECLARABLE_OS_VALUES):
        # Remove the section entirely.
        haywire = tool.get("haywire")
        if haywire is not None:
            haywire.pop("os", None)
            if not haywire:
                tool.pop("haywire", None)
        if not tool:
            data.pop("tool", None)
    else:
        haywire = tool.setdefault("haywire", {})
        haywire["os"] = filtered

    pyproject_path.write_text(toml.dumps(data))


class LibraryManager:
    """Orchestrates library install/uninstall/enable/disable operations.

    Bridges between uv package management (subprocess) and the
    haywire library registry (in-process).
    """

    def __init__(
        self, library_registry: LibraryRegistry, venv_path: str | None = None, project_dir: str | None = None
    ):
        self.registry: LibraryRegistry = library_registry
        self.venv_path = venv_path or self._detect_venv()
        self.project_dir = Path(project_dir) if project_dir else None

    def _detect_venv(self) -> str | None:
        """Detect the current virtual environment path."""
        return sys.prefix if hasattr(sys, "real_prefix") or (sys.prefix != sys.base_prefix) else None

    def _run_uv(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run a uv command and return the result."""
        return subprocess.run(self._uv_cmd(args), capture_output=True, text=True)

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

    def _uv_cmd(self, args: list[str]) -> list[str]:
        """Build the full uv command list."""
        cmd = ["uv", "pip"] + args
        if self.venv_path:
            cmd.extend(["--python", str(Path(self.venv_path) / "bin" / "python")])
        return cmd

    async def _run_uv_streaming(
        self,
        args: list[str],
        on_output: Callable[[str], None],
    ) -> tuple[bool, str]:
        """Run a uv command asynchronously, streaming output lines.

        uv writes progress/results to stderr, so we merge stderr into
        stdout to get a single stream for the UI log.
        """
        cmd = self._uv_cmd(args)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout is not None
        last_lines: list[str] = []
        async for line in proc.stdout:
            text = line.decode().rstrip()
            on_output(text)
            last_lines.append(text)
            # Keep only last few lines for error reporting
            if len(last_lines) > 10:
                last_lines.pop(0)
        await proc.wait()
        return proc.returncode == 0, "\n".join(last_lines)

    async def install_streaming(
        self,
        install_spec: str,
        on_output: Callable[[str], None],
        source_pkg: "Haybale | None" = None,
    ) -> tuple[bool, str]:
        """Install a package with live output streaming.

        When ``source_pkg`` is supplied and ``self.project_dir`` is set, the
        project's pyproject.toml is updated after a successful install so the
        next ``uv sync`` reproduces the install (spec: library-manager-install-sync).
        """
        if Path(install_spec).is_dir():
            args = ["install", "-e", install_spec]
        else:
            args = ["install", install_spec]

        success, stderr = await self._run_uv_streaming(args, on_output)
        if not success:
            return False, f"Install failed: {stderr}"

        on_output("Invalidating caches...")
        self._invalidate_caches()

        on_output("Scanning for libraries...")
        await asyncio.to_thread(self.registry.scan_for_libraries)

        on_output("Enabling libraries...")
        self.registry.enable_all_libraries()

        if source_pkg is not None:
            self._sync_install_to_pyproject(source_pkg, on_output)

        return True, f"Installed: {install_spec}"

    async def uninstall_streaming(
        self,
        library_id: str,
        on_output: Callable[[str], None],
    ) -> tuple[bool, str]:
        """Uninstall a library with live output streaming.

        After a successful uninstall, removes the corresponding entry from the
        project's pyproject.toml (spec: library-manager-install-sync).
        Workspace members under ``barn/`` are left untouched.
        """
        dist_name = self.registry.get_library_distribution_name(library_id)
        if not dist_name:
            return False, f"Cannot find pip package name for library '{library_id}'"

        self.registry.disable_library(library_id)

        success, stderr = await self._run_uv_streaming(
            ["uninstall", dist_name],
            on_output,
        )
        if not success:
            return False, f"Uninstall failed: {stderr}"

        on_output("Invalidating caches...")
        self._invalidate_caches()

        on_output("Scanning for libraries...")
        await asyncio.to_thread(self.registry.scan_for_libraries)

        self._sync_uninstall_from_pyproject(dist_name, on_output)

        return True, f"Uninstalled: {dist_name}"

    def _sync_install_to_pyproject(self, pkg: "Haybale", on_output: Callable[[str], None]) -> None:
        """Write a successful install back to the project's pyproject.toml.

        No-op outside a project, for project-local heaps (already workspace
        members via ``barn/*``), or if anything goes wrong — write-back is a
        best-effort convenience, the install itself already succeeded.
        """
        if self.project_dir is None:
            return
        pyproject = self.project_dir / "pyproject.toml"
        if not pyproject.is_file():
            return

        if pkg.source == "local":
            # Heap pointing inside the project's barn/ is already covered by the
            # workspace glob; skip. Outside-barn heaps get a path entry.
            try:
                heap_path = Path(pkg.install_spec).resolve()
                barn = (self.project_dir / "barn").resolve()
                if heap_path.is_relative_to(barn):
                    return
            except (OSError, ValueError):
                return

        version = self.get_installed_version(pkg.name)
        try:
            _write_install_to_pyproject(
                pyproject,
                pkg_name=pkg.name,
                version=version,
                source=pkg.source,
                install_spec=pkg.install_spec,
            )
            on_output(f"Updated {pyproject.name}")
        except (OSError, KeyError) as e:
            on_output(f"Warning: failed to update pyproject.toml — {e}")

    def _sync_uninstall_from_pyproject(self, dist_name: str, on_output: Callable[[str], None]) -> None:
        """Inverse of ``_sync_install_to_pyproject``. Best-effort."""
        if self.project_dir is None:
            return
        pyproject = self.project_dir / "pyproject.toml"
        if not pyproject.is_file():
            return
        try:
            _remove_install_from_pyproject(pyproject, dist_name)
            on_output(f"Updated {pyproject.name}")
        except (OSError, KeyError) as e:
            on_output(f"Warning: failed to update pyproject.toml — {e}")

    async def rename_project_library_streaming(
        self,
        library_id: str,
        new_name: str,
        workspace_root: str,
        on_output: Callable[[str], None],
        new_identity: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Rename the project's local library to a new name.

        Updates all affected files (lib pyproject.toml, __init__.py, project
        pyproject.toml, marketplace.toml), renames directories, and runs
        `uv sync` to register the new entry point.
        """
        workspace = Path(workspace_root)
        marketplace_path = workspace / ".haywire" / "marketplace.toml"

        # --- 1. Validate new_name ---
        new_name = new_name.strip()
        if not new_name:
            return False, "New name cannot be empty."
        if "/" in new_name or "\\" in new_name or ".." in new_name:
            return False, "New name must not contain path separators."
        sanitized = _sanitize_name(new_name)
        if not sanitized:
            return False, f'"{new_name}" produces an empty module name.'

        new_lib_name = f"haybale-{new_name}"
        new_module = f"haybale_{sanitized}"

        dist_name = self.registry.get_library_distribution_name(library_id) or ""
        if new_lib_name.lower() == dist_name.lower():
            return False, "New name is the same as the current name."

        installed = self.list_installed()
        if any(lib.distribution_name.lower() == new_lib_name.lower() for lib in installed):
            return False, f'"{new_lib_name}" is already installed.'

        from haywire.core.marketstall import parse_project_marketplace

        marketplace_pm = parse_project_marketplace(marketplace_path) if marketplace_path.exists() else None
        marketplace_entries = marketplace_pm.caches if marketplace_pm else []
        if any(
            pkg.name.lower() == new_lib_name.lower() and pkg.name.lower() != dist_name.lower()
            for pkg in marketplace_entries
        ):
            return False, f'"{new_lib_name}" already exists in the marketplace.'

        new_lib_dir = workspace / "barn" / new_lib_name
        if new_lib_dir.exists():
            return False, f'Directory "{new_lib_dir}" already exists.'

        # --- 2. Derive old paths ---
        old_name_part = (
            dist_name.removeprefix("haybale-") if dist_name.startswith("haybale-") else library_id
        )
        old_module = f"haybale_{_sanitize_name(old_name_part)}"
        old_lib_dir = workspace / "barn" / dist_name
        old_pkg_dir = old_lib_dir / old_module
        new_pkg_dir_tmp = old_lib_dir / new_module  # inside old lib dir before lib rename
        new_label = new_name.replace("-", " ").replace("_", " ").title()

        # Resolve all identity values (new_identity overrides auto-generated defaults)
        _id = new_identity or {}
        label_val = _id.get("label") or new_label
        version_val = _id.get("version") or "0.1.0"
        desc_val = _id.get("description") or f"Local library for {new_name} project"
        url_val = _id.get("url", "")
        author_val = _id.get("author", "")
        author_url_val = _id.get("author_url", "")
        tags_list: list[str] = _id.get("tags") or []
        deps_list: list[str] = _id.get("dependencies") or []

        # --- 3. Disable old library ---
        on_output(f"Disabling {library_id}...")
        self.registry.disable_library(library_id)

        # --- 4. Rename module directory ---
        on_output(f"Renaming module directory:  {old_module}  →  {new_module}")
        try:
            os.rename(old_pkg_dir, new_pkg_dir_tmp)
        except OSError as e:
            return False, f"Failed to rename module directory: {e}"

        # --- 5. Update __init__.py ---
        on_output("Updating __init__.py...")
        try:
            init_file = new_pkg_dir_tmp / "__init__.py"
            content = init_file.read_text()
            content = re.sub(r"(    id=')[^']*(')", rf"\g<1>{new_name}\2", content)
            content = re.sub(r"(    label=')[^']*(')", rf"\g<1>{label_val}\2", content)
            content = re.sub(r"(    version=')[^']*(')", rf"\g<1>{version_val}\2", content)
            content = re.sub(r"(    description=')[^']*(')", rf"\g<1>{desc_val}\2", content)
            content = re.sub(r"(    url=')[^']*(')", rf"\g<1>{url_val}\2", content)
            content = re.sub(r"(    author=')[^']*(')", rf"\g<1>{author_val}\2", content)
            content = re.sub(r"(    author_url=')[^']*(')", rf"\g<1>{author_url_val}\2", content)
            content = _set_decorator_list_field(content, "tags", tags_list)
            content = _set_decorator_list_field(content, "dependencies", deps_list)
            content = re.sub(
                r"(Local haybale library for the )[^\n]*(\.)",
                rf"\g<1>{new_name} project\2",
                content,
            )
            init_file.write_text(content)
        except OSError as e:
            return False, f"Failed to update __init__.py: {e}"

        # --- 6. Update lib's pyproject.toml ---
        on_output("Updating lib pyproject.toml...")
        try:
            lib_pyproject = old_lib_dir / "pyproject.toml"
            data = toml.loads(lib_pyproject.read_text())
            data["project"]["name"] = new_lib_name
            data["project"]["description"] = desc_val
            ep = data.get("project", {}).get("entry-points", {}).get("haywire.libraries", {})
            old_ep_key = next(iter(ep), None)
            if old_ep_key:
                del ep[old_ep_key]
            ep[new_name] = f"{new_module}:Library"
            data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] = [new_module]
            lib_pyproject.write_text(toml.dumps(data))
        except (OSError, KeyError) as e:
            return False, f"Failed to update lib pyproject.toml: {e}"

        # --- 7. Rename library directory ---
        on_output(f"Renaming library directory:  {dist_name}  →  {new_lib_name}")
        try:
            os.rename(old_lib_dir, new_lib_dir)
        except OSError as e:
            return False, f"Failed to rename library directory: {e}"

        # --- 8. Update project pyproject.toml ---
        on_output("Updating project pyproject.toml...")
        try:
            project_pyproject = workspace / "pyproject.toml"
            data = toml.loads(project_pyproject.read_text())
            deps = data.get("project", {}).get("dependencies", [])
            data["project"]["dependencies"] = [
                new_lib_name if d.lower() == dist_name.lower() else d for d in deps
            ]
            sources = data.get("tool", {}).get("uv", {}).get("sources", {})
            old_key = next((k for k in sources if k.lower() == dist_name.lower()), None)
            if old_key:
                del sources[old_key]
            sources[new_lib_name] = {"workspace": True}
            project_pyproject.write_text(toml.dumps(data))
        except (OSError, KeyError) as e:
            return False, f"Failed to update project pyproject.toml: {e}"

        # --- 9. Update marketplace.toml ---
        on_output("Updating marketplace.toml...")
        try:
            if marketplace_path.exists():
                data = toml.loads(marketplace_path.read_text())
                for heap in data.get("heaps", []):
                    if heap.get("name", "").lower() == dist_name.lower():
                        heap["name"] = new_lib_name
                        heap["path"] = str(new_lib_dir)
                        heap["label"] = label_val
                        heap["description"] = desc_val
                        break
                marketplace_path.write_text(toml.dumps(data))
        except (OSError, KeyError) as e:
            return False, f"Failed to update marketplace.toml: {e}"

        # --- 10. Run uv sync ---
        on_output("Running uv sync...")
        proc = await asyncio.create_subprocess_exec(
            "uv",
            "sync",
            cwd=workspace_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout is not None
        async for line in proc.stdout:
            on_output(line.decode().rstrip())
        await proc.wait()
        if proc.returncode != 0:
            return (
                False,
                f'uv sync failed — filesystem already renamed, run "uv sync" manually in {workspace_root}',
            )

        # --- 11. Rescan and re-enable ---
        on_output("Rescanning libraries...")
        self._invalidate_caches()
        await asyncio.to_thread(self.registry.scan_for_libraries)
        self.registry.enable_all_libraries()

        return True, f"Renamed to haybale-{new_name}"

    def list_installed(self) -> list[LibraryInfo]:
        """List all discovered libraries with their status."""
        libraries = []
        for lib_id in self.registry.list_names():
            libraries.append(self.get_installed_library(lib_id))
        return libraries

    def get_installed_library(self, library_id: str) -> LibraryInfo:
        """Return summary information for one installed library."""
        identity = self.registry.get_library_identity(library_id)
        install_type = self.registry.get_library_install_type(library_id)
        enabled = self.registry.is_library_enabled(library_id)
        dist_name = self.registry.get_library_distribution_name(library_id)

        return LibraryInfo(
            identity=identity,
            enabled=enabled,
            install_type=install_type or InstallType.FOLDER,
            distribution_name=dist_name or "",
        )

    def is_installed(self, library_id: str) -> bool:
        """Return whether a library id is currently discovered in the registry."""
        return library_id in self.registry.list_names()

    def get_installed_version(self, package_name: str) -> str | None:
        """Return the currently installed version of a pip package, or None.

        Uses importlib.metadata so it works for both PyPI and git installs.
        """
        try:
            return importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            return None

    @staticmethod
    def _norm(name: str) -> str:
        return re.sub(r"[-_.]+", "_", name).lower()

    def _lib_norm_aliases(self, lib_id: str) -> set[str]:
        """Return the set of normalized names that identify lib_id in @library deps.

        @library(dependencies=[...]) uses pip distribution names (e.g.
        ``"haybale_graph_editor"``), while the registry key is just the short id
        (e.g. ``"graph_editor"``).  Both normalized forms must be checked.
        """
        aliases = {self._norm(lib_id)}
        dist = self.registry.get_library_distribution_name(lib_id)
        if dist:
            aliases.add(self._norm(dist))
        return aliases

    def get_installed_dependents(self, lib_id: str) -> list[LibraryInfo]:
        """Return all installed libraries whose @library dependencies include lib_id.

        Checks all installed libraries regardless of enabled state — a disabled
        dependent still has a declared dependency that would break on re-enable.
        """
        targets = self._lib_norm_aliases(lib_id)
        result = []
        for installed in self.list_installed():
            identity = self.registry.get_library_identity(installed.identity.id)
            for dep in identity.dependencies or []:
                if self._norm(dep) in targets:
                    result.append(installed)
                    break
        return result

    def get_missing_dependencies(self, lib_id: str, require_enabled: bool) -> list[str]:
        """Return dependency names from @library that are not satisfied.

        Args:
            lib_id: The library whose dependencies to check.
            require_enabled: If True, a dep must be installed AND enabled.
                             If False, only installed (in registry) is required.

        Returns a list of unsatisfied dependency names (as declared in @library).
        """
        identity = self.registry.get_library_identity(lib_id)
        # Build lookup sets using all normalized aliases for each installed lib
        # so that deps declared as "haybale_foo" match the registry id "foo".
        installed_norms: set[str] = set()
        enabled_norms: set[str] = set()
        for lid in self.registry.list_names():
            installed_norms.update(self._lib_norm_aliases(lid))
            if self.registry.is_library_enabled(lid):
                enabled_norms.update(self._lib_norm_aliases(lid))
        check_set = enabled_norms if require_enabled else installed_norms
        return [dep for dep in (identity.dependencies or []) if self._norm(dep) not in check_set]

    async def fetch_versions(self, pkg: "Haybale") -> list[str]:
        """Fetch available versions for a marketplace package.

        Only called on demand (when the user requests a specific version).
        Returns versions in descending order (newest first).

        For PyPI packages: queries the PyPI JSON API.
        For git packages: queries the GitHub tags API (GitHub URLs only).
        Returns an empty list if the source is unreachable or unsupported.
        """
        import json
        import urllib.request
        import urllib.error

        if pkg.source == "pypi":
            url = f"https://pypi.org/pypi/{pkg.name}/json"

            def _fetch_pypi():
                try:
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        data = json.loads(resp.read())
                    versions = list(data.get("releases", {}).keys())
                    # Sort by PEP 440 if packaging is available, else lexicographic
                    try:
                        from packaging.version import Version

                        versions.sort(key=Version, reverse=True)
                    except Exception:
                        versions.sort(reverse=True)
                    return versions
                except urllib.error.URLError:
                    return []

            return await asyncio.to_thread(_fetch_pypi)

        elif pkg.source == "git":
            # Only handles GitHub URLs: git+https://github.com/{user}/{repo}.git[...]
            spec = pkg.install_spec
            # Strip git+ prefix and any @tag or #subdirectory suffix
            url = spec.removeprefix("git+").split("@")[0].split("#")[0].rstrip("/")
            if "github.com" not in url:
                return []
            # Convert https://github.com/user/repo.git → api.github.com/repos/user/repo/tags
            path = url.removeprefix("https://github.com/").removesuffix(".git")
            api_url = f"https://api.github.com/repos/{path}/tags"

            def _fetch_github():
                try:
                    req = urllib.request.Request(
                        api_url, headers={"Accept": "application/vnd.github.v3+json"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read())
                    return [tag["name"] for tag in data]
                except urllib.error.URLError:
                    return []

            return await asyncio.to_thread(_fetch_github)

        return []

    @staticmethod
    def build_versioned_spec(pkg: "Haybale", version: str) -> str:
        """Build a version-pinned install spec for a specific version.

        For PyPI: returns '{name}=={version}'.
        For git: appends '@{version}' to the base URL before any #subdirectory.
        """
        if pkg.source == "pypi":
            return f"{pkg.name}=={version}"
        elif pkg.source == "git":
            spec = pkg.install_spec.removeprefix("git+")
            base = spec.split("@")[0]  # strip any existing tag
            fragment = f"#{spec.split('#')[1]}" if "#" in spec else ""
            return f"git+{base}@{version}{fragment}"
        return pkg.install_spec

    def update_library_identity(
        self,
        library_id: str,
        workspace_root: str,
        identity: dict[str, Any],
    ) -> tuple[bool, str]:
        """Update identity metadata in __init__.py and marketplace.toml.

        Lightweight alternative to rename — only rewrites metadata fields
        (label, version, description, url, author, author_url).  No directory
        rename, no pyproject.toml changes, no uv sync required.

        After writing the files the library is disabled and its module is
        ejected from sys.modules so the caller can rescan to pick up the
        fresh decorator values.
        """
        workspace = Path(workspace_root)

        dist_name = self.registry.get_library_distribution_name(library_id) or ""
        if not dist_name:
            return False, f"Cannot find distribution name for library {library_id!r}"

        # Derive the package directory the same way rename does (most reliable)
        name_part = dist_name.removeprefix("haybale-") if dist_name.startswith("haybale-") else library_id
        module_name = f"haybale_{_sanitize_name(name_part)}"
        pkg_dir = workspace / "barn" / dist_name / module_name

        if not pkg_dir.exists():
            return False, f"Library package directory not found: {pkg_dir}"

        label_val = identity.get("label", "")
        version_val = identity.get("version", "0.1.0")
        desc_val = identity.get("description", "")
        url_val = identity.get("url", "")
        author_val = identity.get("author", "")
        author_url_val = identity.get("author_url", "")
        tags_list: list[str] = identity.get("tags") or []
        deps_list: list[str] = identity.get("dependencies") or []

        # Update __init__.py decorator fields
        try:
            init_file = pkg_dir / "__init__.py"
            if not init_file.exists():
                return False, f"__init__.py not found at {init_file}"
            content = init_file.read_text()
            content = re.sub(r"(    label=')[^']*(')", rf"\g<1>{label_val}\2", content)
            content = re.sub(r"(    version=')[^']*(')", rf"\g<1>{version_val}\2", content)
            content = re.sub(r"(    description=')[^']*(')", rf"\g<1>{desc_val}\2", content)
            content = re.sub(r"(    url=')[^']*(')", rf"\g<1>{url_val}\2", content)
            content = re.sub(r"(    author=')[^']*(')", rf"\g<1>{author_val}\2", content)
            content = re.sub(r"(    author_url=')[^']*(')", rf"\g<1>{author_url_val}\2", content)
            content = _set_decorator_list_field(content, "tags", tags_list)
            content = _set_decorator_list_field(content, "dependencies", deps_list)
            init_file.write_text(content)
        except OSError as e:
            return False, f"Failed to update __init__.py: {e}"

        # Write [tool.haywire].os to the heap's pyproject.toml.
        # Per spec §2.1: this is editable only on heaps (project libraries),
        # which is exactly where update_library_identity operates.
        os_list = identity.get("os")
        if os_list is not None:  # caller opted in
            try:
                _apply_os_to_pyproject(pkg_dir.parent / "pyproject.toml", os_list)
            except OSError as e:
                return False, f"Failed to update [tool.haywire].os: {e}"

        # Update matching entry in marketplace.toml
        marketplace_path = workspace / ".haywire" / "marketplace.toml"
        try:
            if marketplace_path.exists():
                data = toml.loads(marketplace_path.read_text())
                for heap in data.get("heaps", []):
                    if heap.get("name", "").lower() == dist_name.lower():
                        heap["label"] = label_val
                        heap["description"] = desc_val
                        break
                marketplace_path.write_text(toml.dumps(data))
        except (OSError, KeyError) as e:
            return False, f"Failed to update marketplace.toml: {e}"

        # Fully remove the library from the registry (disable + unregister + tracking
        # dicts cleared, sys.modules ejected) so scan_for_libraries() reimports fresh.
        self.registry.remove_library(library_id)

        return True, f"Updated identity for {dist_name}"
