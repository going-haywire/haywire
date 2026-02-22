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


def _find_git_root(start: Path) -> Path | None:
    """Walk up from *start* to find the nearest .git directory."""
    current = start.resolve()
    while current != current.parent:
        if (current / '.git').exists():
            return current
        current = current.parent
    return None


def _get_remote_url(git_root: Path) -> str | None:
    """Get the origin remote URL, or None if unavailable."""
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
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
    match = re.match(r'^git@([^:]+):(.+)$', url)
    if match:
        host, path = match.groups()
        return f'https://{host}/{path}'
    return url


def _find_module_dir(lib_dir: Path) -> Path | None:
    """Return the Python package directory inside lib_dir.

    Checks flat layout (lib_dir/<module>/__init__.py) and src layout
    (lib_dir/src/<module>/__init__.py).  Returns the first match, or None.
    """
    for search_root in (lib_dir, lib_dir / 'src'):
        if not search_root.is_dir():
            continue
        for child in sorted(search_root.iterdir()):
            if child.is_dir() and (child / '__init__.py').exists():
                return child
    return None


def _detect_library() -> Path:
    """Auto-detect the library path from libs/ in the current directory.

    If exactly one library exists, return its path.
    If multiple exist, print them and exit with usage hint.
    If none exist, print an error and exit.
    """
    libs_dir = Path.cwd() / 'libs'
    if not libs_dir.is_dir():
        print("Error: No libs/ directory found in the current project.")
        print("Are you running this from a haywire project root?")
        sys.exit(1)

    candidates = [
        d for d in sorted(libs_dir.iterdir())
        if d.is_dir() and (d / 'pyproject.toml').exists()
    ]

    if not candidates:
        print("Error: No libraries found in libs/.")
        sys.exit(1)

    if len(candidates) == 1:
        return candidates[0]

    # Multiple libraries — list them for the user
    print(f"Found {len(candidates)} libraries in libs/. Specify which one:\n")
    for lib in candidates:
        rel = lib.relative_to(Path.cwd())
        print(f"  haywire share {rel}")
    print()
    sys.exit(1)


def share_library(library_path: str | None):
    """Print a marketplace.toml snippet for the given library directory."""
    if library_path is None:
        lib_dir = _detect_library()
    else:
        lib_dir = Path(library_path).resolve()

    if not lib_dir.is_dir():
        print(f"Error: '{library_path}' is not a directory.")
        sys.exit(1)

    pyproject_path = lib_dir / 'pyproject.toml'
    if not pyproject_path.exists():
        print(f"Error: No pyproject.toml found in '{library_path}'.")
        sys.exit(1)

    # Read metadata
    data = toml.loads(pyproject_path.read_text())
    project = data.get('project', {})

    name = project.get('name', lib_dir.name)
    version = project.get('version', '0.0.0')
    description = project.get('description', '')
    tags = project.get('keywords', [])

    authors = project.get('authors', [])
    author = authors[0].get('name', '') if authors else ''

    # Detect git remote
    git_root = _find_git_root(lib_dir)
    if git_root:
        remote_url = _get_remote_url(git_root)
    else:
        remote_url = None

    if remote_url:
        https_url = _ssh_to_https(remote_url)
        # Strip trailing .git for cleaner URLs
        https_url = https_url.removesuffix('.git')
        subdirectory = lib_dir.relative_to(git_root)
        install_spec = f'{name} @ git+{https_url}.git#subdirectory={subdirectory}'
    else:
        print("Warning: No git remote found. Using placeholder URL.\n")
        subdirectory = lib_dir.relative_to(Path.cwd()) if lib_dir.is_relative_to(Path.cwd()) else lib_dir.name
        install_spec = f'{name} @ git+https://<REPO_URL>.git#subdirectory={subdirectory}'

    # Build docs_url — raw URL pointing to the Python package directory
    # (where OVERVIEW.md and docs/ live).  Only meaningful for GitHub/GitLab.
    docs_url = ''
    module_dir = _find_module_dir(lib_dir)
    if remote_url and module_dir:
        # https_url already computed above (stripped .git suffix)
        module_rel = module_dir.relative_to(git_root)
        if 'github.com' in https_url:
            raw_base = https_url.replace('github.com', 'raw.githubusercontent.com')
            docs_url = f'{raw_base}/main/{module_rel}/'
        elif 'gitlab.com' in https_url:
            docs_url = f'{https_url}/-/raw/main/{module_rel}/'

    # Build TOML snippet
    entry = {
        'name': name,
        'version': version,
        'description': description,
        'author': author,
        'source': 'git',
        'install_spec': install_spec,
        'tags': tags,
        'source_url': https_url if remote_url else '',
        'docs_url': docs_url,
    }

    # Format as TOML array-of-tables entry
    lines = ['[[packages]]']
    for key, value in entry.items():
        if isinstance(value, list):
            formatted = '[' + ', '.join(f'"{v}"' for v in value) + ']'
            lines.append(f'{key} = {formatted}')
        else:
            lines.append(f'{key} = "{value}"')

    snippet = '\n'.join(lines)

    print("# Copy this snippet into a marketplace.toml:\n")
    print(snippet)
