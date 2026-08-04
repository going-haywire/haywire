"""
Library management orchestration layer.

Wraps uv subprocess calls + entry point cache invalidation +
library registry operations into a single service API.
"""

import asyncio
import importlib
import importlib.metadata
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from haywire.core.library.registry import LibraryRegistry
from haywire.core.tomlio import edit_toml
from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType
from haywire.core.library.decorator_io import _set_decorator_bool_field, _set_decorator_list_field
from haywire.core.marketstall import Haybale
from haywire.ui.modals.install_progress_modal import PostInstallHints


def _sanitize_name(name: str) -> str:
    """Convert a name to a valid Python identifier suffix (mirrors init.py logic)."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized


_DECLARABLE_OS_VALUES = ("macos", "windows", "linux")

# Packages the marketplace must never move. Pinned to their installed exact
# versions on every install, so a haybale whose tree wants a different
# framework version fails at uv's resolver instead of silently swapping the
# framework out from under the running studio. Deliberately NOT the full
# publish set: the in-monorepo haybale-* libraries are exactly what a
# marketplace install is supposed to upgrade.
FRAMEWORK_PACKAGES: tuple[str, ...] = ("haywire-core", "haywire-studio", "nicegui")


def _parse_git_install_spec(install_spec: str) -> tuple[str, str | None, str | None]:
    """Parse a PEP 440 VCS URL into (git_url, tag|None, subdirectory|None).

    Accepts both the bare form (``git+https://…[@tag][#subdirectory=…]``) and
    the PEP 440 form with a leading ``name @ `` prefix. The tag is split out
    of the URL rather than left embedded — ``[tool.uv.sources]`` wants it as
    a separate ``tag`` key, and a URL with ``@tag`` glued on is not a valid
    git remote (uv/git tries to fetch that literal string as a host).
    """
    spec = install_spec.strip()
    if " @ " in spec:
        spec = spec.split(" @ ", 1)[1].strip()
    spec = spec.removeprefix("git+")
    sub: str | None = None
    if "#subdirectory=" in spec:
        spec, sub = spec.split("#subdirectory=", 1)
        spec = spec.strip()
        sub = sub.strip() or None
    tag: str | None = None
    if "@" in spec:
        spec, tag = spec.split("@", 1)
        spec = spec.strip()
        tag = tag.strip() or None
    return spec, tag, sub


def _write_install_to_pyproject(
    pyproject_path: Path,
    pkg_name: str,
    version: str | None,
    source: str,
    install_spec: str,
) -> None:
    """Write/update a project pyproject.toml entry for an installed haybale.

    Writes one of:
      - pypi → only ``[project] dependencies = "<name>>=X.Y.Z"``
      - git  → ``[project] dependencies`` + ``[tool.uv.sources]`` with git+subdirectory
      - local (heap outside barn) → ``[project] dependencies`` +
        ``[tool.uv.sources]`` with ``{ path = "...", editable = true }``

    The caller decides which rows apply; this helper just writes what it's told.

    Edited through ``edit_toml`` rather than a toml.loads/dumps round trip:
    this is the *user's* pyproject.toml, and rebuilding it from parsed dicts
    silently deletes every comment they wrote.
    """
    with edit_toml(pyproject_path) as data:
        project = data.setdefault("project", {})
        deps = project.setdefault("dependencies", [])

        # A floor (``>=``), not a compatible release (``~=``). ``~=X.Y.Z`` also
        # stamps a ceiling — ``~=0.0.33`` excludes 0.1.0 — and a ceiling written
        # by a tool at install time is not a policy anyone chose; it is just
        # what got emitted. It then persists in the user's pyproject and blocks
        # the next minor release. Same reasoning as ``_release_pin`` in
        # haywire_studio/init.py, which scaffolds ``>=`` for exactly this reason.
        # Authors who genuinely want a ceiling type it themselves.
        floor = f"{pkg_name}>={version}" if version else pkg_name
        new_deps: list[str] = []
        found = False
        for entry in deps:
            if _dep_name(str(entry)).lower() == pkg_name.lower():
                new_deps.append(floor)
                found = True
            else:
                new_deps.append(str(entry))
        if not found:
            new_deps.append(floor)
        project["dependencies"] = new_deps

        if source == "git":
            url, tag, subdir = _parse_git_install_spec(install_spec)
            git_entry: dict[str, Any] = {"git": url}
            if tag:
                git_entry["tag"] = tag
            if subdir:
                git_entry["subdirectory"] = subdir
            sources = data.setdefault("tool", {}).setdefault("uv", {}).setdefault("sources", {})
            sources[pkg_name] = git_entry
        elif source == "local":
            sources = data.setdefault("tool", {}).setdefault("uv", {}).setdefault("sources", {})
            sources[pkg_name] = {"path": install_spec, "editable": True}


def _remove_install_from_pyproject(pyproject_path: Path, pkg_name: str) -> None:
    """Remove a haybale's entry from [project] dependencies and [tool.uv.sources].

    Comment-preserving for the same reason as
    :func:`_write_install_to_pyproject` — see its docstring.
    """
    with edit_toml(pyproject_path) as data:
        project = data.get("project")
        if project:
            deps = project.get("dependencies", [])
            project["dependencies"] = [str(d) for d in deps if _dep_name(str(d)).lower() != pkg_name.lower()]

        sources = data.get("tool", {}).get("uv", {}).get("sources", {})
        sources.pop(pkg_name, None)
        # Also try a hyphen/underscore variant — uv normalizes these.
        sources.pop(pkg_name.replace("-", "_"), None)
        sources.pop(pkg_name.replace("_", "-"), None)


def _version_from_dist_info(site_packages: Path, package_name: str) -> str | None:
    """The version in ``<site-packages>/<name>-<version>.dist-info``, or None.

    Installers normalize the distribution name in that directory: runs of
    ``-``/``_``/``.`` collapse to a single ``_``. So ``haybale-core`` is found at
    ``haybale_core-0.0.34.dist-info``, and callers may pass either spelling.
    """
    normalized = re.sub(r"[-_.]+", "_", package_name).lower()
    for entry in site_packages.glob("*.dist-info"):
        stem = entry.name[: -len(".dist-info")]
        name, _, version = stem.rpartition("-")
        if not version:
            continue
        if re.sub(r"[-_.]+", "_", name).lower() == normalized:
            return version
    return None


def _dep_name(dep_entry: str) -> str:
    """Extract the bare package name from a PEP 508 dependency string."""
    # Strip extras, version specifiers, markers, and the ``name @ url`` form.
    head = dep_entry.split(";", 1)[0]
    head = head.split(" @ ", 1)[0]
    head = re.split(r"[\[<>=!~ ]", head, maxsplit=1)[0]
    return head.strip()


def _apply_os_to_pyproject(pyproject_path: Path, os_values: list[str]) -> None:
    """Write or remove [tool.haywire].os in the library's pyproject.toml.

    Rules:
      - Filter to allowed values (macos, windows, linux); silently drop others.
      - Empty list after filtering OR all three present → remove [tool.haywire].os
        entirely (absent = "all platforms").
      - Non-empty subset → write the filtered list in canonical order.
      - Preserves other [tool.*] sections (hatch, etc.) verbatim — including
        their comments, which a toml.loads/dumps round trip would delete.
    """
    # Filter to allowed values, then canonicalize order to (macos, windows, linux).
    filtered = [v for v in _DECLARABLE_OS_VALUES if v in os_values]

    with edit_toml(pyproject_path) as data:
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

        Read in chunks and split on BOTH ``\\n`` and ``\\r``, rather than
        iterating lines. uv renders download progress as a bar that rewrites
        itself with carriage returns and no newline, so a line-oriented reader
        emits nothing at all while a large package downloads — for
        haybale-visiongraph that is 30+ seconds of a log that looks hung.
        Splitting on ``\\r`` surfaces each bar update as it arrives.
        """
        cmd = self._uv_cmd(args)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout is not None
        last_lines: list[str] = []
        pending = ""

        def _emit(text: str) -> None:
            text = text.rstrip()
            if not text:
                return
            on_output(text)
            last_lines.append(text)
            # Keep only last few lines for error reporting
            if len(last_lines) > 10:
                last_lines.pop(0)

        while True:
            chunk = await proc.stdout.read(1024)
            if not chunk:
                break
            pending += chunk.decode(errors="replace")
            # Normalize CRLF first so a Windows line ending is one break, not two.
            pending = pending.replace("\r\n", "\n")
            while True:
                index = min(
                    (i for i in (pending.find("\n"), pending.find("\r")) if i != -1),
                    default=-1,
                )
                if index == -1:
                    break
                _emit(pending[:index])
                pending = pending[index + 1 :]

        _emit(pending)
        await proc.wait()
        return proc.returncode == 0, "\n".join(last_lines)

    def _parse_dry_run_removals(self, output: str) -> list[str]:
        """Parse `uv pip install --dry-run` stdout and return distribution names
        of packages that would be uninstalled (i.e. upgraded/replaced).

        Lines of interest look like: ' - haybale-core==0.0.5'
        """
        names = []
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                pkg_spec = stripped[2:].strip()
                dist_name = pkg_spec.split("==")[0].split("[")[0].strip()
                if dist_name:
                    names.append(dist_name)
        return names

    def _hints_for_library(self, library_id: str) -> PostInstallHints:
        """Read the post-install flags off a library's identity.

        Returns an empty PostInstallHints if the library is no longer registered
        (e.g. we're querying after it's been evicted).
        """
        try:
            identity = self.registry.get_library_identity(library_id)
        except KeyError:
            return PostInstallHints()
        return PostInstallHints(
            needs_refresh=identity.needs_refresh,
            needs_restart=identity.needs_restart,
        )

    FRAMEWORK_CONFLICT_MESSAGE = (
        "This library needs a different version of the Haywire framework than the "
        "one you are running. Update Haywire first — use “Check for updates” in the "
        "top bar — then install this library again."
    )

    def _framework_constraints(self) -> list[str]:
        """``name==version`` lines pinning every installed framework package.

        Read from the running venv, not from any declared ``Requires-Dist``:
        a declared want can itself be stale, whereas what is running cannot.
        A package that isn't installed contributes nothing — pinning a version
        we do not have would make every install unsatisfiable.
        """
        lines: list[str] = []
        for name in FRAMEWORK_PACKAGES:
            try:
                lines.append(f"{name}=={importlib.metadata.version(name)}")
            except importlib.metadata.PackageNotFoundError:
                continue
        return lines

    def _write_constraints_file(self) -> Path | None:
        """Write the framework constraints to a temp file; return its path.

        Returns None when nothing is installed to constrain, so the caller
        omits ``-c`` entirely rather than passing an empty file.
        """
        import tempfile

        lines = self._framework_constraints()
        if not lines:
            return None
        handle = tempfile.NamedTemporaryFile("w", suffix=".txt", prefix="haywire-constraints-", delete=False)
        with handle:
            handle.write("\n".join(lines) + "\n")
        return Path(handle.name)

    async def dry_run(self, install_spec: str) -> list[str]:
        """Run `uv pip install --dry-run` and return distribution names of packages
        that would be removed (upgraded) by the install.

        Returns:
            List of pip distribution names that would be uninstalled.
            Empty list when the spec is already satisfied.

        Raises:
            RuntimeError: when uv's dependency resolver fails (non-zero exit).
        """
        constraints = self._write_constraints_file()
        if Path(install_spec).is_dir():
            args = ["install", "--dry-run", "-e", install_spec]
        else:
            # --no-sources: ignore [tool.uv.sources] inside the resolved tree.
            # A published haybale's git+URL may clone into a workspace whose
            # root pyproject.toml has dev-time path overrides (uv treats the
            # subdirectory as a workspace member and applies them). Without
            # this flag the resolver replaces already-installed editable
            # haywire packages with bogus path-traversal git URLs.
            args = ["install", "--dry-run", "--no-sources", install_spec]
        if constraints is not None:
            args += ["-c", str(constraints)]

        collected: list[str] = []

        def _collect(line: str) -> None:
            collected.append(line)

        success, stderr = await self._run_uv_streaming(args, _collect)
        if not success:
            raise RuntimeError(f"{self.FRAMEWORK_CONFLICT_MESSAGE}\n\n{stderr}")

        full_output = "\n".join(collected)
        return self._parse_dry_run_removals(full_output)

    async def install(
        self,
        install_spec: str,
        on_output: Callable[[str], None],
        source_pkg: "Haybale | None" = None,
        known_removals: "list[str] | None" = None,
    ) -> tuple[bool, str, PostInstallHints]:
        """Install a package with live output streaming.

        Returns ``(success, message, hints)`` where ``hints`` is a
        :class:`PostInstallHints` unioned across newly-imported libraries
        (success path) and any evicted libraries (success OR failure path,
        for ``needs_restart`` only).

        Evicting a live library sets ``needs_restart`` regardless of what its
        author declared. An upgrade removes a library from the registry but
        cannot remove the module objects that mounted nodes, registered types,
        and DI singletons still hold, so post-eviction the two versions'
        classes coexist. That is a property of the operation, not of the
        library, so it is not the author's flag to withhold.

        ``known_removals`` lets a caller that has *already* run :meth:`dry_run`
        hand over its result instead of paying for a second resolver round —
        and, more importantly, guarantees that the eviction set acted on is
        the same one the user was shown and approved. Omit it (the default)
        and this computes its own, which is what every non-UI caller does.
        """
        constraints = self._write_constraints_file()
        if Path(install_spec).is_dir():
            args = ["install", "-e", install_spec]
        else:
            # --no-sources and -c: see dry_run() for rationale. Must match the
            # dry-run flags exactly or the pre-eviction set and the actual
            # install diverge.
            args = ["install", "--no-sources", install_spec]
        if constraints is not None:
            args += ["-c", str(constraints)]

        # Pre-evict libraries that pip is about to upgrade. Capture each
        # evicted library's hints BEFORE remove_library() drops the identity.
        if known_removals is not None:
            to_remove = list(known_removals)
        else:
            try:
                to_remove = await self.dry_run(install_spec)
            except RuntimeError:
                # Resolver failure — the actual install will also fail and report it.
                to_remove = []

        evicted_restart_hint = PostInstallHints()
        evicted: list[str] = []
        for dist_name in to_remove:
            lib_id = self.registry.find_library_by_distribution_name(dist_name)
            if lib_id and self.registry.get_library_install_type(lib_id) == InstallType.REGULAR:
                # Capture needs_restart only (per Q5/B: refresh is install-only,
                # and Q12.A: a failed install with an evicted restart-lib should
                # still surface the restart hint).
                lib_hints = self._hints_for_library(lib_id)
                evicted_restart_hint = evicted_restart_hint.merge(
                    PostInstallHints(needs_restart=lib_hints.needs_restart)
                )
                self.registry.remove_library(lib_id)
                evicted.append(dist_name)

        if evicted:
            on_output(f"Preparing upgrade: removing {', '.join(evicted)} from registry…")
            # Stale live objects survive the eviction — see the docstring.
            evicted_restart_hint = evicted_restart_hint.merge(PostInstallHints(needs_restart=True))

        # Capture post-eviction registered library_ids so we can compute the
        # newly-imported set after the scan. Evicted libs are absent from this
        # snapshot, so when the upgraded version reappears in the post-scan it
        # is correctly counted as "newly imported" and its flags propagate.
        pre_install_ids = set(self.registry.list_names())

        success, stderr = await self._run_uv_streaming(args, on_output)
        if not success:
            # Failure path: needs_refresh always False; needs_restart from evictions only.
            return False, f"Install failed: {stderr}", evicted_restart_hint

        on_output("Invalidating caches...")
        self._invalidate_caches()

        on_output("Scanning for libraries...")
        await asyncio.to_thread(self.registry.scan_for_libraries)

        on_output("Enabling libraries...")
        # Threaded for enabling imports every library's module tree, which
        # for a package like haybale-visiongraph (depthai, opencv) is seconds
        # of synchronous work. On the event loop it would stop NiceGUI answering
        # its heartbeat and the browser reports the connection lost mid-install.
        await asyncio.to_thread(self.registry.enable_all_libraries)

        if source_pkg is not None:
            self._sync_install_to_pyproject(source_pkg, on_output)

        # Success path: union evicted-restart with the freshly-imported set.
        post_install_ids = set(self.registry.list_names())
        new_ids = post_install_ids - pre_install_ids
        hints = evicted_restart_hint
        for lid in new_ids:
            hints = hints.merge(self._hints_for_library(lid))

        return True, f"Installed: {install_spec}", hints

    async def install_streaming(
        self,
        install_spec: str,
        on_output: Callable[[str], None],
        source_pkg: "Haybale | None" = None,
    ) -> tuple[bool, str, PostInstallHints]:
        """Deprecated alias for install(). Use install() directly."""
        return await self.install(install_spec, on_output, source_pkg)

    async def uninstall_streaming(
        self,
        library_id: str,
        on_output: Callable[[str], None],
    ) -> tuple[bool, str, PostInstallHints]:
        """Uninstall a library with live output streaming.

        Returns ``(success, message, hints)`` where ``hints.needs_refresh`` is
        always False (per Q5/B) and ``hints.needs_restart`` reflects the
        removed library's declared flag, captured before disable.
        """
        dist_name = self.registry.get_library_distribution_name(library_id)
        if not dist_name:
            return False, f"Cannot find pip package name for library '{library_id}'", PostInstallHints()

        # Capture the library's hints before disabling — registry may drop the identity.
        lib_hints = self._hints_for_library(library_id)
        # Per Q5/B: refresh is install-only for uninstall.
        hints = PostInstallHints(needs_restart=lib_hints.needs_restart)

        # disable_library() first: fires _fire_library_disabled (LibraryStateContainer
        # relies on it to drop this library from its instance-filter set) and persists
        # the disabled-set write. remove_library() then does the rest of the teardown —
        # unregister, drop tracking dicts, eject sys.modules — so a later reinstall of
        # the same library doesn't hand back a stale cached module (its own disable()
        # call is a no-op the second time; see BaseLibrary.disable()).
        self.registry.disable_library(library_id)
        self.registry.remove_library(library_id)

        success, stderr = await self._run_uv_streaming(
            ["uninstall", dist_name],
            on_output,
        )
        if not success:
            return False, f"Uninstall failed: {stderr}", hints

        on_output("Invalidating caches...")
        self._invalidate_caches()

        on_output("Scanning for libraries...")
        await asyncio.to_thread(self.registry.scan_for_libraries)

        self._sync_uninstall_from_pyproject(dist_name, on_output)

        return True, f"Uninstalled: {dist_name}", hints

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

        Reads the venv's ``*.dist-info`` off disk rather than asking
        ``importlib.metadata`` in this process. Both describe the same venv, but
        only one of them is guaranteed to describe it as it is *now*: this
        process imported these packages at startup, and the metadata cache it
        built then survives an install unless
        :meth:`_invalidate_caches` succeeds in clearing it — which it does
        through ``FastPath.__new__.cache_clear()``, a private CPython API
        swallowed by ``except AttributeError`` if it ever moves.

        The consequence of a stale read here is durable, not cosmetic: this
        feeds the version written into the user's pyproject.toml, so a stale
        number becomes a pin that outlives the process. Reading the directory
        cannot go stale.
        """
        site_packages = self._site_packages_dir()
        if site_packages is not None:
            version = _version_from_dist_info(site_packages, package_name)
            if version is not None:
                return version
        # No venv located (or no dist-info for this name, e.g. an editable
        # install laid out differently) — fall back to the in-process view.
        try:
            return importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            return None

    def _site_packages_dir(self) -> Path | None:
        """The venv's site-packages directory, or None if it can't be located."""
        if not self.venv_path:
            return None
        candidates = sorted((Path(self.venv_path) / "lib").glob("python*/site-packages"))
        if candidates:
            return candidates[0]
        # Windows layout.
        win = Path(self.venv_path) / "Lib" / "site-packages"
        return win if win.is_dir() else None

    @staticmethod
    def _norm(name: str) -> str:
        return re.sub(r"[-_.]+", "_", name).lower()

    def _lib_module_norm(self, lib_id: str) -> str:
        """Normalized TOP-LEVEL module name — the canonical dependency key.

        @library(dependencies=[...]) entries are top-level package names equal
        to the dependency's module_name top package. NOT distribution_name
        (empty for folder installs) and NOT the short id.
        """
        identity = self.registry.get_library_identity(lib_id)
        top = (identity.module_name or lib_id).split(".")[0]
        return self._norm(top)

    def get_installed_dependents(self, lib_id: str) -> list[LibraryInfo]:
        """Return all installed libraries whose @library dependencies include lib_id."""
        target_norm = self._lib_module_norm(lib_id)
        result = []
        for installed in self.list_installed():
            identity = self.registry.get_library_identity(installed.identity.id)
            for dep in identity.dependencies or []:
                if self._norm(dep.split(".")[0]) == target_norm:
                    result.append(installed)
                    break
        return result

    def get_missing_dependencies_for_package(self, pkg: "Haybale", *, require_enabled: bool) -> list[str]:
        """Unmet deps for a NOT-yet-installed marketplace package (install gating).

        Matches each declared dep (top-package-normalized) against installed
        libraries' module_name. Only counts libs with a distribution_name (i.e.
        proper pip installs) — dev-barn folder libs without a dist name are
        excluded so they don't silently satisfy marketplace dep checks.
        require_enabled=True => dep must also be enabled.
        """
        installed: set[str] = set()
        enabled: set[str] = set()
        for lid in self.registry.list_names():
            if not self.registry.get_library_distribution_name(lid):
                continue
            norm = self._lib_module_norm(lid)
            installed.add(norm)
            if self.registry.is_library_enabled(lid):
                enabled.add(norm)
        check = enabled if require_enabled else installed
        return [d for d in (pkg.dependencies or []) if self._norm(d.split(".")[0]) not in check]

    def get_missing_dependencies(self, lib_id: str, require_enabled: bool) -> list[str]:
        """Return dependency names from @library that are not satisfied.

        Matches each dep's top-level module name against installed libraries'
        module_name (top package normalized).
        """
        identity = self.registry.get_library_identity(lib_id)
        installed_norms: set[str] = set()
        enabled_norms: set[str] = set()
        for lid in self.registry.list_names():
            norm = self._lib_module_norm(lid)
            installed_norms.add(norm)
            if self.registry.is_library_enabled(lid):
                enabled_norms.add(norm)
        check_set = enabled_norms if require_enabled else installed_norms
        return [
            dep for dep in (identity.dependencies or []) if self._norm(dep.split(".")[0]) not in check_set
        ]

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
        """Build an install spec pinned to *version*, regardless of what pkg.install_spec holds.

        For PyPI: returns '{name}=={version}'.
        For git: replaces any existing '@tag' on the base URL with '@{version}', preserving
        any '#subdirectory=...' fragment.

        Use this — never pkg.install_spec directly — whenever a specific version is required
        (an update, a version-picker install). pkg.install_spec is often unpinned: a PyPI
        catalog entry with no explicit spec defaults to the bare package name
        (haywire.core.marketstall.parsing._parse_haybale_entry), which only asks uv for "any
        version that satisfies current constraints" — not this one. Passed unpinned to
        LibraryManager.install(), which always applies a constraints file pinning the framework
        packages (FRAMEWORK_PACKAGES) to whatever's currently installed, uv can legally resolve
        straight back to the already-installed version: the install reports success and nothing
        changes.
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
        (label, description, url, author, author_url, tags, dependencies,
        needs_refresh, needs_restart). Never touches version — that's set by
        Share/publish (lockstep bump). No directory rename, no pyproject.toml
        changes, no uv sync required.

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
        desc_val = identity.get("description", "")
        url_val = identity.get("url", "")
        author_val = identity.get("author", "")
        author_url_val = identity.get("author_url", "")
        tags_list: list[str] = identity.get("tags") or []
        deps_list: list[str] = identity.get("dependencies") or []
        needs_refresh_val = bool(identity.get("needs_refresh", False))
        needs_restart_val = bool(identity.get("needs_restart", False))

        # Update __init__.py decorator fields. version is deliberately excluded —
        # it's set by Share/publish (lockstep bump), which overwrites it on the
        # next publish regardless of what a caller passes here.
        try:
            init_file = pkg_dir / "__init__.py"
            if not init_file.exists():
                return False, f"__init__.py not found at {init_file}"
            content = init_file.read_text()
            content = re.sub(r"(    label=')[^']*(')", rf"\g<1>{label_val}\2", content)
            content = re.sub(r"(    description=')[^']*(')", rf"\g<1>{desc_val}\2", content)
            content = re.sub(r"(    url=')[^']*(')", rf"\g<1>{url_val}\2", content)
            content = re.sub(r"(    author=')[^']*(')", rf"\g<1>{author_val}\2", content)
            content = re.sub(r"(    author_url=')[^']*(')", rf"\g<1>{author_url_val}\2", content)
            content = _set_decorator_list_field(content, "tags", tags_list)
            content = _set_decorator_list_field(content, "dependencies", deps_list)
            content = _set_decorator_bool_field(content, "needs_refresh", needs_refresh_val)
            content = _set_decorator_bool_field(content, "needs_restart", needs_restart_val)
            init_file.write_text(content)
        except OSError as e:
            return False, f"Failed to update __init__.py: {e}"

        # Write [tool.haywire].os to the heap's pyproject.toml. This is editable
        # only on heaps (project libraries), which is where update_library_identity
        # operates.
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
                # Comment-preserving: the marketplace file is hand-editable
                # (the browser offers an Edit File button for it), so a
                # rebuild-from-dicts write would delete the user's notes.
                with edit_toml(marketplace_path) as data:
                    for heap in data.get("heaps", []):
                        if heap.get("name", "").lower() == dist_name.lower():
                            heap["label"] = label_val
                            heap["description"] = desc_val
                            break
        except (OSError, KeyError) as e:
            return False, f"Failed to update marketplace.toml: {e}"

        # Fully remove the library from the registry (disable + unregister + tracking
        # dicts cleared, sys.modules ejected) so scan_for_libraries() reimports fresh.
        self.registry.remove_library(library_id)

        return True, f"Updated identity for {dist_name}"
