"""
Generate a marketplace.toml snippet for sharing a haybale library.

Reads metadata from the library's pyproject.toml and detects the git
remote URL to produce a ready-to-paste TOML block.
"""

import re
import subprocess
import sys
from pathlib import Path

import toml

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


def _find_module_dir(lib_dir: Path) -> Path | None:
    """Return the Python package directory inside lib_dir.

    Checks flat layout (lib_dir/<module>/__init__.py) and src layout
    (lib_dir/src/<module>/__init__.py).  Returns the first match, or None.
    """
    for search_root in (lib_dir, lib_dir / "src"):
        if not search_root.is_dir():
            continue
        for child in sorted(search_root.iterdir()):
            if child.is_dir() and (child / "__init__.py").exists():
                return child
    return None


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

    module_dir = _find_module_dir(lib_dir)
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


def share_library(library_path: str | None):
    """Print a marketplace.toml snippet for the given library directory."""
    if library_path is None:
        lib_dir = _detect_library()
    else:
        lib_dir = Path(library_path).resolve()

    if not lib_dir.is_dir():
        print(f"Error: '{library_path}' is not a directory.")
        sys.exit(1)

    entry = _build_entry_for_library(lib_dir)
    if entry is None:
        print(f"Error: No pyproject.toml found in '{library_path}'.")
        sys.exit(1)

    # Warn when no git remote — the original behavior surfaces this to the user.
    git_root = _find_git_root(lib_dir)
    if not git_root or not _get_remote_url(git_root):
        print("Warning: No git remote found. Using placeholder URL.\n")

    print("# Copy this snippet into a marketplace.toml:\n")
    print(toml.dumps({"packages": [entry]}).strip())


class NoBarnError(RuntimeError):
    """Raised when `share --save` is invoked on a repo with no `barn/` directory."""


def share_save_repo(repo_root: Path) -> Path:
    """Aggregate every library under `<repo_root>/barn/*` into one marketstall.toml.

    Walks `barn/*` (sorted), builds a marketplace entry for each directory that
    contains a `pyproject.toml` (via `_build_entry_for_library`), and writes the
    aggregated list to `<repo_root>/marketstall.toml`. Directories without a
    pyproject are silently skipped. Returns the output path.

    Raises NoBarnError if `<repo_root>/barn/` doesn't exist.
    """
    barn = repo_root / "barn"
    if not barn.is_dir():
        raise NoBarnError(f"no barn/ directory at {repo_root}")

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
