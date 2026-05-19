"""
Generate a marketplace.toml snippet for sharing a haybale library.

Reads metadata from the library's pyproject.toml and detects the git
remote URL to produce a ready-to-paste TOML block.
"""

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import toml

from haywire.core.library.dep_detect import (
    DetectedDeps,
    EntryPointLibrarySource,
    detect_deps,
    find_module_dir,
    set_pyproject_dependencies,
)
from haywire.core.marketplace import MarketplaceEntry


def _find_git_root(start: Path) -> Path | None:
    """Walk up from *start* to find the nearest .git directory."""
    current = start.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def _get_remote_url(git_root: Path) -> str | None:
    """Get the origin remote URL, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(git_root),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def _ssh_to_https(url: str) -> str:
    """Convert SSH-style git URLs to HTTPS.

    git@github.com:user/repo.git  →  https://github.com/user/repo.git
    git@gitlab.com:user/repo.git  →  https://gitlab.com/user/repo.git
    """
    match = re.match(r"^git@([^:]+):(.+)$", url)
    if match:
        host, path = match.groups()
        return f"https://{host}/{path}"
    return url


def _read_library_label(module_dir: Path, fallback: str) -> str:
    """Read the label from the @library decorator in module_dir/__init__.py.

    Falls back to *fallback* if the file is missing or the field can't be found.
    """
    init_file = module_dir / "__init__.py"
    if not init_file.exists():
        return fallback
    content = init_file.read_text()
    match = re.search(r"label\s*=\s*['\"]([^'\"]+)['\"]", content)
    return match.group(1) if match else fallback


def _read_library_dependencies(module_dir: Path) -> list[str]:
    """Read dependencies from the @library decorator in module_dir/__init__.py.

    Returns pip package names (hyphens), converted from the module names
    (underscores) used in the decorator.  Returns [] if none declared.
    """
    init_file = module_dir / "__init__.py"
    if not init_file.exists():
        return []
    content = init_file.read_text()
    match = re.search(r"dependencies\s*=\s*\[([^\]]*)\]", content, re.DOTALL)
    if not match:
        return []
    raw = match.group(1)
    modules = re.findall(r"['\"]([^'\"]+)['\"]", raw)
    return [m.replace("_", "-") for m in modules]


def _detect_library() -> Path:
    """Auto-detect the library path from barn/ in the current directory.

    If exactly one library exists, return its path.
    If multiple exist, print them and exit with usage hint.
    If none exist, print an error and exit.
    """
    barn_dir = Path.cwd() / "barn"
    if not barn_dir.is_dir():
        print("Error: No barn/ directory found in the current project.")
        print("Are you running this from a haywire project root?")
        sys.exit(1)

    candidates = [d for d in sorted(barn_dir.iterdir()) if d.is_dir() and (d / "pyproject.toml").exists()]

    if not candidates:
        print("Error: No libraries found in barn/.")
        sys.exit(1)

    if len(candidates) == 1:
        return candidates[0]

    # Multiple libraries — list them for the user
    print(f"Found {len(candidates)} libraries in barn/. Specify which one:\n")
    for lib in candidates:
        rel = lib.relative_to(Path.cwd())
        print(f"  haywire share {rel}")
    print()
    sys.exit(1)


def _build_entry_for_library(lib_dir: Path) -> dict | None:
    """Build a marketplace entry for one library directory.

    Returns the entry dict (TOML-serializable), or None if `lib_dir` lacks a
    pyproject.toml. Used by both `haywire share` (single library, stdout) and
    `haywire share --save` (every barn library, aggregated to file).
    """
    pyproject_path = lib_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    data = toml.loads(pyproject_path.read_text())
    project = data.get("project", {})

    name = project.get("name", lib_dir.name)
    version = project.get("version", "0.0.0")
    description = project.get("description", "")
    tags = project.get("keywords", [])

    authors = project.get("authors", [])
    author = authors[0].get("name", "") if authors else ""

    git_root = _find_git_root(lib_dir)
    remote_url = _get_remote_url(git_root) if git_root else None

    subdirectory: Path | str
    if remote_url:
        assert git_root is not None
        https_url = _ssh_to_https(remote_url)
        https_url = https_url.removesuffix(".git")
        subdirectory = lib_dir.relative_to(git_root)
        install_spec = f"{name} @ git+{https_url}.git#subdirectory={subdirectory}"
    else:
        https_url = ""
        subdirectory = (
            lib_dir.relative_to(Path.cwd()) if lib_dir.is_relative_to(Path.cwd()) else lib_dir.name
        )
        install_spec = f"{name} @ git+https://<REPO_URL>.git#subdirectory={subdirectory}"

    module_dir = find_module_dir(lib_dir)
    label_fallback = name.removeprefix("haybale-").replace("-", " ").replace("_", " ").title()
    label = _read_library_label(module_dir, label_fallback) if module_dir else label_fallback
    dependencies = _read_library_dependencies(module_dir) if module_dir else []

    docs_url = ""
    if remote_url and module_dir:
        assert git_root is not None
        module_rel = module_dir.relative_to(git_root)
        if "github.com" in https_url:
            raw_base = https_url.replace("github.com", "raw.githubusercontent.com")
            docs_url = f"{raw_base}/main/{module_rel}/"
        elif "gitlab.com" in https_url:
            docs_url = f"{https_url}/-/raw/main/{module_rel}/"

    return MarketplaceEntry(
        name=name,
        label=label,
        min_version=version,
        description=description,
        author=author,
        source="git",
        install_spec=install_spec,
        tags=tags,
        dependencies=dependencies,
        source_url=https_url if remote_url else "",
        docs_url=docs_url,
    ).to_dict()


# ──────────────────────────────────────────────────────────────────────────────
# Dependency-drift gate (Plan E follow-up, piece 3)
#
# `haywire share` is the publish boundary: whatever the user emits here is what
# downstream consumers will install. If the library's pyproject.toml or its
# @library decorator are out of sync with the actual source imports, the
# published library will fail to install or to enable for consumers. The gate
# below detects that drift at share time so the user can fix it before
# emitting.
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DepDrift:
    """Drift between a library's declared deps and what its imports require.

    All four lists are sorted. ``has_drift`` is True iff any list is non-empty.
    """

    lib_dir: Path
    pyproject_missing: list[str] = field(default_factory=list)
    decorator_missing: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return bool(self.pyproject_missing or self.decorator_missing)


def detect_share_drift(lib_dir: Path) -> DepDrift:
    """Compute the drift between detected and declared dependencies for one library.

    Drift surfaces only ``missing`` entries — items that detect_deps found in
    the source but are NOT declared in the library's pyproject.toml or
    @library decorator. Extra declarations (declared but unused) are not
    flagged: they are common (transitive deps, optional features) and false
    positives would block users unfairly. `share` is about correctness for
    consumers, which means "everything imported must be declared," not
    "everything declared must be imported."

    Uses :class:`EntryPointLibrarySource` so the gate works without a live
    haywire registry — any installed dist with a ``haywire.libraries`` entry
    point counts as a haywire library.

    Returns an empty :class:`DepDrift` when no module dir is found (the
    library has no inspectable source). Callers should still treat that as
    "nothing to gate" rather than an error.
    """
    libraries = EntryPointLibrarySource()
    detected: DetectedDeps = detect_deps(lib_dir, libraries=libraries)

    # Read current declarations
    pyproject_path = lib_dir / "pyproject.toml"
    declared_pyproject: list[str] = []
    if pyproject_path.is_file():
        try:
            pyproject_data = toml.loads(pyproject_path.read_text())
            declared_pyproject = list(pyproject_data.get("project", {}).get("dependencies", []))
        except toml.TomlDecodeError:
            # Malformed pyproject — treat declarations as empty so the drift
            # report still surfaces what's missing. The malformed-file error
            # will be raised by downstream emit if it's still broken there.
            pass

    module_dir = find_module_dir(lib_dir)
    declared_decorator: list[str] = []
    if module_dir:
        declared_decorator = _read_library_dependencies(module_dir)

    # Convert declared_pyproject specs ("haywire-core~=0.0.1") to bare dist names
    # so we can compare against detected entries by name.
    decl_py_names = {_strip_specifier(s) for s in declared_pyproject}
    detected_py_names = {_strip_specifier(s) for s in detected.pyproject}
    pyproject_missing = sorted(detected_py_names - decl_py_names)

    # Decorator deps round-trip as bare module names in detect_deps output;
    # _read_library_dependencies already converts to pip-package form. Re-
    # normalize both sides so "haybale_core" and "haybale-core" compare equal.
    decl_dec_norm = {_norm_dep(d) for d in declared_decorator}
    detected_dec_norm = {_norm_dep(d) for d in detected.library_decorator}
    decorator_missing = sorted(detected_dec_norm - decl_dec_norm)

    return DepDrift(
        lib_dir=lib_dir,
        pyproject_missing=pyproject_missing,
        decorator_missing=decorator_missing,
        unresolved=list(detected.unresolved),
    )


def _strip_specifier(spec: str) -> str:
    """Strip PEP 440 version operators and extras from a requirement string."""
    return re.split(r"[~>=<!;\s\[]", spec)[0]


def _norm_dep(name: str) -> str:
    """Normalize a dep name to a comparable form (underscores, lowercase)."""
    return re.sub(r"[-_.]+", "_", name).lower()


def _format_drift_report(drift: DepDrift) -> str:
    """Format a :class:`DepDrift` as a multi-line human-readable string."""
    lines: list[str] = [f"Dependency drift in {drift.lib_dir.name}:"]
    if drift.pyproject_missing:
        lines.append("  pyproject.toml [project] dependencies missing:")
        for s in drift.pyproject_missing:
            lines.append(f"    + {s}")
    if drift.decorator_missing:
        lines.append("  @library(dependencies=[...]) missing:")
        for s in drift.decorator_missing:
            lines.append(f"    + {s}")
    if drift.unresolved:
        lines.append("  Unresolved imports (not mapped to any distribution — likely dynamic):")
        for s in drift.unresolved:
            lines.append(f"    ? {s}")
    return "\n".join(lines)


def apply_drift_fix(drift: DepDrift) -> None:
    """Apply a :class:`DepDrift` by writing missing deps to disk.

    Updates the library's pyproject.toml with the union of currently declared
    and detected dependencies, and rewrites the @library decorator to include
    any missing names. Existing declarations are preserved — the gate's
    "missing-only" definition makes this an additive operation.
    """
    if not drift.has_drift:
        return

    lib_dir = drift.lib_dir

    # 1. pyproject.toml: re-run detect_deps to get the proper specifiers, then
    #    union with what's already declared.
    if drift.pyproject_missing:
        libraries = EntryPointLibrarySource()
        detected = detect_deps(lib_dir, libraries=libraries)
        pyproject_path = lib_dir / "pyproject.toml"
        declared: list[str] = []
        if pyproject_path.is_file():
            try:
                data = toml.loads(pyproject_path.read_text())
                declared = list(data.get("project", {}).get("dependencies", []))
            except toml.TomlDecodeError:
                declared = []
        # Union, preserving any user-specified version pins that detect_deps
        # would otherwise overwrite with the running interpreter's version.
        declared_names = {_strip_specifier(s) for s in declared}
        unioned = list(declared)
        for spec in detected.pyproject:
            if _strip_specifier(spec) not in declared_names:
                unioned.append(spec)
        set_pyproject_dependencies(lib_dir, sorted(unioned))

    # 2. @library decorator: import the helper from library_manager so we
    #    delegate to the same rewriter used by the Edit dialog.
    if drift.decorator_missing:
        module_dir = find_module_dir(lib_dir)
        if module_dir is None:
            return
        from .library_manager import _set_decorator_list_field

        init_file = module_dir / "__init__.py"
        if not init_file.is_file():
            return
        content = init_file.read_text()
        current = _read_library_dependencies(module_dir)
        current_norm = {_norm_dep(d) for d in current}
        new_list = list(current)
        for missing in drift.decorator_missing:
            if _norm_dep(missing) not in current_norm:
                new_list.append(missing)
        content = _set_decorator_list_field(content, "dependencies", sorted(new_list))
        init_file.write_text(content)


def share_library(library_path: str | None, *, strict: bool = False, fix: bool = False) -> None:
    """Print a marketplace.toml snippet for the given library directory.

    Runs the dependency-drift gate before emitting. Default behavior is
    warn-only: drift is printed to stderr and the snippet still emits. With
    ``strict=True`` drift causes a non-zero exit. With ``fix=True`` drift is
    auto-corrected (pyproject.toml and @library decorator are rewritten) and
    the share continues against the fresh state.
    """
    if library_path is None:
        lib_dir = _detect_library()
    else:
        lib_dir = Path(library_path).resolve()

    if not lib_dir.is_dir():
        print(f"Error: '{library_path}' is not a directory.")
        sys.exit(1)

    if not _run_drift_gate(lib_dir, strict=strict, fix=fix):
        sys.exit(1)

    entry = _build_entry_for_library(lib_dir)
    if entry is None:
        print(f"Error: No pyproject.toml found in '{library_path}'.")
        sys.exit(1)

    # Warn when no git remote — the original behavior surfaces this to the user.
    git_root = _find_git_root(lib_dir)
    if not git_root or not _get_remote_url(git_root):
        print("Warning: No git remote found. Using placeholder URL.\n", file=sys.stderr)

    print("# Copy this snippet into a marketplace.toml:\n")
    print(toml.dumps({"packages": [entry]}).strip())


def _run_drift_gate(lib_dir: Path, *, strict: bool, fix: bool) -> bool:
    """Run the drift gate for a single library.

    Returns False when the caller should refuse to proceed (strict mode with
    unresolved drift). Otherwise returns True; if ``fix`` was requested and
    drift was present, the library has been auto-corrected before return.
    """
    drift = detect_share_drift(lib_dir)
    if not drift.has_drift and not drift.unresolved:
        return True

    report = _format_drift_report(drift)
    if drift.has_drift:
        if fix:
            apply_drift_fix(drift)
            print(f"Auto-fixed:\n{report}", file=sys.stderr)
            return True
        if strict:
            print(f"Refusing to share due to drift (use --fix to auto-correct):\n{report}", file=sys.stderr)
            return False
        # Warn-only.
        print(f"Warning: {report}\n  (rerun with --fix to apply, or --strict to fail)", file=sys.stderr)
        return True

    # Only unresolved imports — no drift to fix, just inform.
    print(report, file=sys.stderr)
    return True


class NoBarnError(RuntimeError):
    """Raised when `share --save` is invoked on a repo with no `barn/` directory."""


def share_save_repo(repo_root: Path, *, strict: bool = False, fix: bool = False) -> Path:
    """Aggregate every library under `<repo_root>/barn/*` into one marketstall.toml.

    Walks `barn/*` (sorted), builds a marketplace entry for each directory that
    contains a `pyproject.toml` (via `_build_entry_for_library`), and writes the
    aggregated list to `<repo_root>/marketstall.toml`. Directories without a
    pyproject are silently skipped. Returns the output path.

    Runs the dependency-drift gate against each library before emitting. In
    ``strict=True`` mode, any drift causes the function to raise
    :class:`DriftError` without writing the output file. With ``fix=True``
    drift is auto-corrected in place. Default behavior is warn-only.

    Raises NoBarnError if `<repo_root>/barn/` doesn't exist.
    Raises DriftError when ``strict=True`` and any library has drift.
    """
    barn = repo_root / "barn"
    if not barn.is_dir():
        raise NoBarnError(f"no barn/ directory at {repo_root}")

    # Pre-flight: run the drift gate on every library before emitting anything.
    drift_reports: list[DepDrift] = []
    for lib_dir in sorted(barn.iterdir()):
        if not lib_dir.is_dir() or not (lib_dir / "pyproject.toml").exists():
            continue
        drift = detect_share_drift(lib_dir)
        if drift.has_drift or drift.unresolved:
            drift_reports.append(drift)

    drift_with_changes = [d for d in drift_reports if d.has_drift]
    if drift_with_changes:
        if fix:
            for d in drift_with_changes:
                apply_drift_fix(d)
                print(f"Auto-fixed: {_format_drift_report(d)}", file=sys.stderr)
        elif strict:
            joined = "\n\n".join(_format_drift_report(d) for d in drift_with_changes)
            raise DriftError(
                f"Refusing to write marketstall.toml due to drift (use --fix to auto-correct):\n\n{joined}"
            )
        else:
            joined = "\n\n".join(_format_drift_report(d) for d in drift_with_changes)
            print(
                f"Warning:\n\n{joined}\n\n(rerun with --fix to apply, or --strict to fail)",
                file=sys.stderr,
            )

    # Inform about unresolved imports even if no actionable drift.
    unresolved_only = [d for d in drift_reports if not d.has_drift and d.unresolved]
    for d in unresolved_only:
        print(_format_drift_report(d), file=sys.stderr)

    entries: list[dict] = []
    for lib_dir in sorted(barn.iterdir()):
        if not lib_dir.is_dir():
            continue
        entry = _build_entry_for_library(lib_dir)
        if entry is None:
            continue
        entries.append(entry)

    out_path = repo_root / "marketstall.toml"
    header = (
        "# marketstall.toml — share this file's raw URL so others can subscribe to your library feed\n"
        "# Run: haywire share --save   to update this file\n\n"
    )
    out_path.write_text(header + toml.dumps({"packages": entries}))
    return out_path


class DriftError(RuntimeError):
    """Raised when `share --save --strict` is invoked and at least one library has drift."""
