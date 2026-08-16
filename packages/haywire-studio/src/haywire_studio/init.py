"""
Project scaffolding for Haywire.

Creates a new haywire project with:
- pyproject.toml (uv workspace with haywire-studio dependency)
- .haywire/ config directory
- graphs/ directory
- barn/ directory with auto-scaffolded local haybale library
"""

import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import toml

from .config import ensure_global_config, ensure_project_config, add_recent_project


def _release_pin(dist: str = "haywire-studio") -> str:
    """Return a floor specifier (``>=X.Y.Z``) for the running haywire release,
    so scaffolded projects pin to the version that created them rather than a
    stale hardcoded literal.

    A floor, not a compatible-release (``~=``): ``~=X.Y.Z`` also stamps a
    ceiling, and a ceiling written at scaffold time becomes a lie the moment
    the excluded version ships — nobody will remember to update it. Authors
    who want one type it themselves.

    Reads the installed version of ``dist`` — when invoked via
    ``uvx --from haywire-studio[==X] haywire init``, that is exactly the
    version the user chose. Raises if it can't be determined, rather than
    guessing a pin that would mislead the generated pyproject.
    """
    try:
        return f">={version(dist)}"
    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"Cannot determine the installed {dist} version to pin scaffolded "
            f"dependencies. Is haywire installed correctly?"
        ) from exc


def _get_dev_repo_root() -> str:
    """Resolve the haywire dev repo root from this module's location.

    Works because this file lives at:
    <repo>/packages/haywire-studio/src/haywire_studio/init.py
    """
    return str(Path(__file__).resolve().parents[4])


#: Strict — lowercase only. Used for ``--distname``, which is the author's
#: deliberate, verbatim override: no easing, no silent casing changes.
_SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

#: Eased — same shape, but each hyphen-separated segment may also start with
#: (and contain) uppercase letters. Used for the project name, which is a
#: directory/display name an author may reasonably want to capitalize
#: (``My-App``); it never appears in a registry key or pip distribution name
#: verbatim — :func:`_lib_basename` lowercases it before that.
_PROJECT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(-[A-Za-z0-9]+)*$")


class InvalidSlugError(ValueError):
    """*value* is not a valid pip distribution name slug.

    Raised instead of silently correcting the input — a project or dist name
    the author typed is meaningful (it becomes the published package name,
    or is cast into one), so guessing what they "meant" would surprise them
    later at publish time.
    """


def _validate_slug(value: str, what: str) -> None:
    """Reject anything that isn't a lowercase, hyphen-separated slug.

    ``what`` names the field in the error message so the failure is
    unambiguous about which argument was wrong. No spaces, no underscores
    (reserved for the derived module name — see :func:`_distmodule`), no
    other special characters. Used for ``--distname``, which is returned
    verbatim by :func:`_resolve_distname` — strict on purpose.
    """
    if not _SLUG_RE.match(value):
        raise InvalidSlugError(
            f"Invalid {what} '{value}': must be lowercase letters, digits, and single "
            f"hyphens only (e.g. 'my-app'), starting with a letter. No spaces, "
            f"underscores, or other special characters."
        )


def _validate_project_name(value: str) -> None:
    """Reject anything that isn't a hyphen-separated slug, uppercase allowed.

    Eased relative to :func:`_validate_slug`: the project name is a
    directory/display name, not a pip distribution name in its own right —
    it is cast to lowercase (via :func:`_lib_basename`) before it ever feeds
    the scaffolded library's identity. Still no spaces, underscores, or other
    special characters — only the case restriction is relaxed.
    """
    if not _PROJECT_NAME_RE.match(value):
        raise InvalidSlugError(
            f"Invalid project name '{value}': must be letters, digits, and single "
            f"hyphens only (e.g. 'My-App'), starting with a letter. No spaces, "
            f"underscores, or other special characters."
        )


def _lib_basename(name: str) -> str:
    """Lowercase *name* and strip a leading ``hay-``/``hay_``/``haybale-``/
    ``haybale_`` so the scaffolded library isn't double-prefixed.

    The default local library dist name is ``hay-<base>``; if the user
    already named their project ``hay-weather`` (or ``Hay-Weather`` — the
    project name may carry uppercase, see :func:`_validate_project_name`) we
    want the library to be ``hay-weather``, not ``hay-hay-weather`` or
    ``hay-Weather``. Every scaffolded folder under ``barn/`` is lowercase
    regardless of how the project itself was cased. The legacy ``haybale-``/
    ``haybale_`` prefixes are stripped too, for the same reason, even though
    the local scaffold no longer generates that prefix itself. Applied only
    when composing library names/modules/paths — the project name itself
    (directory, root ``[project].name``) is kept verbatim, case included.
    """
    lowered = name.lower()
    for prefix in ("hay-", "hay_", "haybale-", "haybale_"):
        if lowered.startswith(prefix):
            return lowered[len(prefix) :]
    return lowered


def _resolve_distname(projectname: str, distname: str | None) -> str:
    """The scaffolded local library's pip distribution name.

    No ``--distname`` override: defaults to ``hay-<base>``, where ``<base>``
    has any existing ``hay-``/``haybale-`` prefix stripped so the result is
    never doubled. This is what keeps a locally-scaffolded library from
    colliding with an installed ``haybale-*`` marketplace library — ``name``
    is now the sole library identifier and prefixes every registry key, so
    the two namespaces must never overlap.

    With an override: returned verbatim. This is the author's way to bypass
    the ``hay-`` automatism entirely (e.g. to scaffold directly under a
    name they intend to publish as-is). Both branches assume the caller
    already validated the relevant value(s) with :func:`_validate_slug`.
    """
    if distname is not None:
        return distname
    return f"hay-{_lib_basename(projectname)}"


def _distmodule(distname: str) -> str:
    """The importable module name derived from a (valid, hyphenated) dist name.

    Pure string transform — hyphens are the only character a valid slug (see
    :data:`_SLUG_RE`) can contain besides lowercase letters and digits, so a
    straight replace is sufficient once the input has been validated.
    """
    return distname.replace("-", "_")


def render_scaffold_tree(projectname: str, lib_name: str, module_name: str) -> str:
    """A preview of the directory tree ``init_project`` is about to create.

    Built from the same resolved names ``init_project`` writes to disk, so
    the CLI's confirm-before-scaffold prompt (``cli/init.py``) can never drift
    from what actually gets generated — there is exactly one place that knows
    the shape of a scaffolded project.
    """
    root_name = _project_root_name(projectname, lib_name)
    return (
        f"{projectname}/\n"
        f'├── pyproject.toml                  (project = "{root_name}")\n'
        f"├── graphs/\n"
        f"├── .haywire/\n"
        f"│   ├── config.toml\n"
        f'│   └── marketplace.toml            (heap name = "{lib_name}")\n'
        f"└── barn/\n"
        f"    └── {lib_name}/\n"
        f'        ├── pyproject.toml          (project = "{lib_name}")\n'
        f"        ├── README.md\n"
        f"        └── {module_name}/\n"
        f'            ├── __init__.py         (@library, entry-point "{lib_name}")\n'
        f'            └── haybale.toml        (name = "{lib_name}")\n'
    )


def _project_root_name(name: str, lib_name: str) -> str:
    """Return the name to use for the root pyproject.toml ``[project]`` section.

    The root project must not collide with the barn workspace member, whose
    name is ``lib_name`` — the resolved distname (``hay-<base>`` by default,
    or the ``--distname`` override verbatim). uv rejects duplicate workspace
    member names, so when the project name IS the library's dist name,
    appending ``-dev`` makes the root distinct.
    """
    if name == lib_name:
        return f"{name}-dev"
    return name


def _generate_project_pyproject(name: str, lib_name: str, dev_repo: str | None = None) -> str:
    """Generate the project's pyproject.toml content.

    Args:
        name: Project name.
        lib_name: The scaffolded local library's resolved dist name.
        dev_repo: If set, absolute path to the haywire dev repo.
            Adds [tool.uv.sources] pointing to local editable packages.
    """
    pin = _release_pin()
    sources: dict[str, dict[str, object]] = {lib_name: {"workspace": True}}
    data: dict[str, Any] = {
        "project": {
            "name": _project_root_name(name, lib_name),
            "version": "0.1.0",
            "requires-python": ">=3.12",
            "dependencies": [
                f"haywire-studio{pin}",
                # this makes sure the studio comes with a baseline set of haybale libraries
                f"haybale-studio{pin}",
                f"haybale-marketplace{pin}",
                lib_name,
            ],
        },
        "tool": {
            "uv": {
                "workspace": {
                    "members": ["barn/*"],
                },
                "sources": sources,
            },
        },
    }

    if dev_repo:
        data["project"]["dependencies"] += ["haybale-core"]
        sources.update(
            {
                "haywire-studio": {"path": f"{dev_repo}/packages/haywire-studio", "editable": True},
                "haywire-core": {"path": f"{dev_repo}/packages/haywire-core", "editable": True},
                "haybale-core": {"path": f"{dev_repo}/barn/haybale-core", "editable": True},
                "haybale-studio": {"path": f"{dev_repo}/barn/haybale-studio", "editable": True},
                "haybale-marketplace": {"path": f"{dev_repo}/barn/haybale-marketplace", "editable": True},
            }
        )

    return toml.dumps(data)


def _generate_library_pyproject(
    name: str, lib_name: str, module_name: str, dev_repo: str | None = None
) -> str:
    """Generate the local haybale library's pyproject.toml content.

    Commented so an author can tell what's safe to hand-edit from what a
    publish regenerates — see docs/reference/files/pyproject-toml.md for the
    full field-by-field breakdown.

    Args:
        name: Project name.
        lib_name: The scaffolded local library's resolved dist name
            (``hay-<base>`` by default, or the ``--distname`` override).
        module_name: Python module name (e.g. hay_my_project).
        dev_repo: If set, absolute path to the haywire dev repo.
    """
    pin = _release_pin()
    sources_section = ""
    if dev_repo:
        sources_section = f'''
[tool.uv.sources]
haywire-core = {{ path = "{dev_repo}/packages/haywire-core", editable = true }}
'''

    return f'''# Full field reference: docs/reference/files/pyproject-toml.md
[project]
# ── generated from haybale.toml at publish; hand-edits are reported as drift ─
name = "{lib_name}"  # from haybale.name
description = "Local library for {name} project"  # from haybale.description
keywords = ["experimental", "project-local"]  # from haybale.tags

# CANON, but owned by the release machinery — synced to haybale.toml
version = "0.0.1"

# ── authored here ────────────────────────────────────────────────────────────
requires-python = ">=3.12"
license = {{text = "MIT"}}

# CANON — pip requirements. Add third-party packages and sibling haybales here.
dependencies = ["haywire-core{pin}"]

# The key is the entry-point name (unique within the group; need not match the
# library id). The value is <module>:<class>.
[project.entry-points."haywire.libraries"]
{name} = "{module_name}:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

# Declares the package DIRECTORY, so everything not VCS-ignored inside it
# reaches the wheel, including haybale.toml — do not add include/exclude here.
[tool.hatch.build.targets.wheel]
packages = ["{module_name}"]
{sources_section}'''


def _generate_haybale_toml(name: str, lib_name: str, label: str) -> str:
    """Generate the local haybale library's `haybale.toml` content.

    Every field the file may declare, commented — see
    docs/reference/files/haybale-toml.md for the full field table. `version`
    is seeded to match `_generate_library_pyproject()`'s hardcoded `"0.0.1"` —
    the two files must agree from the first write, since nothing else
    reconciles them until the author's first version bump.

    Args:
        name: Project name.
        lib_name: The scaffolded local library's resolved dist name.
        label: Human display name.
    """
    return f'''# Library metadata. Canon for everything descriptive about this haybale; ships
# in the wheel beside __init__.py and is read from disk at runtime. Full field
# reference: docs/reference/files/haybale-toml.md

# ── identity — immutable ──────────────────────────────────────────────────
name = "{lib_name}"  # pip distribution name; also prefixes every
# component's registry key, e.g. {lib_name}:node:Add

# ── written by scripts/bump_version.py / the share wizard, not by hand ──────
version = "0.0.1"  # PEP 440, no "v" — canon here; pyproject.toml carries the synced copy

# ── display ───────────────────────────────────────────────────────────────
label = "{label}"  # human display name
description = "Local library for {name} project"  # one line
tags = ["experimental", "project-local"]  # filter tags in the library browser

# ── behaviour ─────────────────────────────────────────────────────────────
# os = ["macos", "linux"]  # macos/linux/windows; empty/absent = every platform
# on_reload = "none"  # none (default) / refresh (reload tab) / restart (restart studio)

# Sibling haybales this library subscribes to, as MODULE names (not
# distribution names). Required for hot-reload scope tracking.
linked_libraries = []

# ── declared paths, relative to the project root ────────────────────────────
# examples_path = "examples/"
# tests_path = "tests/"

# One supplementary human-readable page: a bare filename in this directory.
# notes = "NOTES.md"

# ── absolute URLs, used verbatim ─────────────────────────────────────────────
# homepage_url = "https://example.com"
# documentation_url = "https://example.com/docs/"
# issues_url = "https://example.com/issues"

# Repeatable; url is optional. Written by the studio's library overview edit modal.
# [[authors]]
# name = "Your Name"
# url = "https://your.site"

# Omitted unless the library is being retired — hand-edited, no edit-modal field.
# [deprecated]
# since = "0.1.0"
# reason = "Superseded by haybale-successor."
# successor = "haybale-successor"
'''


_README_MARKER_START = "<!-- marketstall:share-url:start -->"
_README_MARKER_END = "<!-- marketstall:share-url:end -->"
_README_PLACEHOLDER = (
    "*Subscribe URL not yet published — run `haywire share --save` after pushing this repo to a git remote.*"
)


def _generate_gitignore() -> str:
    """Generate a default .gitignore for a scaffolded haywire project.

    Root-only patterns are ANCHORED with a leading slash. An unanchored pattern
    matches at every depth, including inside ``barn/<lib>/<module>/``, and since
    consumers install from a clone, anything ignored there is absent for
    everyone. See ``.insights/project_git_url_publishing_traps.md``.
    """
    return """\
# Patterns below are anchored with a leading slash (/build/) so they match only
# at the repo root. An unanchored pattern (build/) matches at EVERY depth —
# including inside barn/, where it would silently exclude your library's own
# files. See the note at the end of this file before adding patterns.

# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging (root only)
/build/
/dist/
*.egg-info/
*.egg

# Virtual environments (root only)
/.venv/
/venv/
/env/

# Test / type-check caches
.pytest_cache/
.ruff_cache/
.mypy_cache/
.tox/
.coverage
htmlcov/

# Editor / OS
.DS_Store
.idea/
.vscode/

# Haywire per-session UI state (open graph, pan/zoom) — not project state
.haywire/workspace_state.json

# ── Before you add a pattern ────────────────────────────────────────────────
# Anything ignored inside barn/<your-library>/ will be MISSING for everyone who
# installs your library — haywire share publishes by git URL, so consumers get
# a clone of this repo, not a built package. If a pattern is only meant for the
# repo root, anchor it with a leading slash: /build/ not build/.
"""


def _generate_gitattributes() -> str:
    """Generate a default .gitattributes: text normalization, and NO LFS.

    LFS is deliberately not armed. git stores a ~130-byte pointer file, and a
    consumer cloning WITHOUT git-lfs installed receives that pointer instead of
    the asset — the install succeeds and the library breaks at runtime. Whether
    uv's clone runs the smudge filter depends on the consumer's global LFS
    config, which neither the publisher nor Haywire controls or can detect. And
    ``*.png`` is exactly what a node library's icons and skins match, so the
    trap would fire on the most common case.

    The trade-off is documented here instead, where the decision gets made.
    """
    return """\
# Normalize line endings on commit; check out with the platform's native EOL.
* text=auto

# Binary assets — never diffed, never EOL-converted.
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.pdf binary
*.woff binary
*.woff2 binary
*.mp4 binary
*.onnx binary
*.blob binary

# ── About Git LFS ───────────────────────────────────────────────────────────
# Do NOT add LFS smudge-filter directives here without understanding the
# consequence. `haywire share` publishes by git URL, so consumers clone this
# repo. Git stores an LFS-tracked file as a ~130-byte pointer, and a consumer
# without the LFS system receives that pointer text instead of the real asset.
# The clone succeeds; your library breaks at runtime when it loads the file.
# Whether the clone resolves the pointer depends on the consumer's own git
# config — something you cannot control or detect from here.
#
# If your library genuinely needs large assets, download them at runtime into a
# cache directory instead of committing them.
"""


def _generate_root_readme(name: str, label: str) -> str:
    """Generate the root README.md for a haywire-init scaffolded project.

    Includes the marketstall:share-url marker pair with placeholder, so the
    author's first `haywire share --save` replaces it with the real URL.
    """
    return (
        f"# {label}\n"
        f"\n"
        f"A haywire project.\n"
        f"\n"
        f"## Subscribe\n"
        f"\n"
        f"{_README_MARKER_START}\n"
        f"```sh\n"
        f"{_README_PLACEHOLDER}\n"
        f"```\n"
        f"{_README_MARKER_END}\n"
        f"\n"
        f"## Getting started\n"
        f"\n"
        f"```sh\n"
        f"uv sync\n"
        f"uv run haywire\n"
        f"```\n"
        f"## Share your library\n"
        f"\n"
        f"this will bump all the files to the specified version, commit, and sets the git-tag\n"
        f"then it generates and saves the marketstall.toml file and updates the above\n"
        f"subscribe link with the url to get this library. The version can be an explicit\n"
        f"`x.y.z` or an npm-style `major`/`minor`/`patch` keyword.\n"
        f"```sh\n"
        f"uv run haywire share --bump patch --save\n"
        f"```\n"
    )


def _generate_library_readme(name: str, label: str) -> str:
    """Generate the barn library README.md with marker pair."""
    return (
        f"# {label}\n"
        f"\n"
        f"Local haybale library for the {name} project.\n"
        f"\n"
        f"## Subscribe\n"
        f"\n"
        f"{_README_MARKER_START}\n"
        f"{_README_PLACEHOLDER}\n"
        f"{_README_MARKER_END}\n"
    )


def _generate_library_init(name: str, label: str) -> str:
    """Generate the local haybale library's __init__.py content."""
    return f'''"""
Local haybale library for the {name} project.

Add your custom components in the corresponding folders:
- nodes/      — node definitions
- types/      — custom data types
- widgets/    — UI widgets for data types
- skins/      — custom node skins
- adapters/   — type-to-type conversion adapters
- settings/   — library settings definitions
- states/     — library app and session states
- themes/     — workbench and node themes
- panels/     — custom UI panels
- editors/    — custom UI editors
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.types.registry import TypeRegistry
from haywire.core.state import LibraryStateRegistry

from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.themes.registry import ThemeRegistry
from haywire.ui.widget.registry import WidgetRegistry


@library(
    file_watcher=True,
)
class Library(BaseLibrary):
    """Local project library — add your components in the subfolders."""

    def register_components(self):
        """Register all components with the global registries."""
        base_path = Path(__file__).parent

        self.add_folder_to_registry(
            folder_path=str(base_path / 'settings'),
            registry_cls=SettingsRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / 'states'),
            registry_cls=LibraryStateRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / 'themes'),
            registry_cls=ThemeRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / 'types'),
            registry_cls=TypeRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / 'adapters'),
            registry_cls=AdapterRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / 'widgets'),
            registry_cls=WidgetRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / 'skins'),
            registry_cls=SkinRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / 'nodes'),
            registry_cls=NodeRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / 'panels'),
            registry_cls=PanelRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / 'editors'),
            registry_cls=EditorTypeRegistry,
        )

    def validate(self) -> bool:
        """Validate library structure."""
        return True
'''


def _local_entry(name: str, path: Path, label: str = "", description: str = "") -> dict:
    """Build a [[heaps]] entry.

    Heaps have a different schema than [[caches]]: only `name` and `path` are
    required; label and description are optional metadata. Heaps are always
    installed editably from the path; they're never published.
    """
    entry: dict[str, object] = {
        "name": name,
        "path": str(path),
    }
    if label:
        entry["label"] = label
    if description:
        entry["description"] = description
    return entry


def _register_dev_repo_locals_in_project(dev_repo: str, project_dir: Path) -> None:
    """In --dev mode, register every dev-repo barn library as a [[heaps]] in the project marketplace.

    Walks ``<dev_repo>/barn/*`` and calls add_heap_to_project per library. Dev
    libraries are project-scoped because they pin the dev workspace this
    project was scaffolded against; they should not leak into the user-global
    marketplace where they'd surface in unrelated projects.

    Idempotent: DuplicateHeapNameError per library is swallowed so re-running
    init against an existing project marketplace doesn't fail.
    """
    from haywire.core.library.dep_detect import find_module_dir
    from haywire.core.marketstall import DuplicateHeapNameError, add_heap_to_project

    from haywire.core.publishing import _read_library_dependencies

    project_mp = project_dir / ".haywire" / "marketplace.toml"

    barn = Path(dev_repo) / "barn"
    if not barn.is_dir():
        return

    for lib_dir in sorted(barn.iterdir()):
        if not lib_dir.is_dir() or not (lib_dir / "pyproject.toml").exists():
            continue
        # Read the package name from pyproject — don't trust the directory name.
        pyproject = toml.loads((lib_dir / "pyproject.toml").read_text())
        project = pyproject.get("project", {})
        lib_name = project.get("name", lib_dir.name)
        label = lib_name.removeprefix("haybale-").replace("-", " ").replace("_", " ").title()
        description = project.get("description", "")
        # The @library(linked_libraries=[...]) decorator is the definitive
        # source for the marketplace install gate — a version-less subset of the
        # pyproject deps (share.py keeps the two in sync).
        # _read_library_dependencies returns pip-package form (hyphens), which
        # the gate normalizes.
        module_dir = find_module_dir(lib_dir)
        linked_libraries = _read_library_dependencies(module_dir) if module_dir else []

        try:
            add_heap_to_project(
                project_mp,
                name=lib_name,
                path=lib_dir,
                label=label,
                description=description,
                linked_libraries=linked_libraries,
            )
        except DuplicateHeapNameError:
            continue


def _check_git_available() -> bool:
    """Check if git is available in PATH. Return True if available, False otherwise."""
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _generate_project_marketplace_locals_only(name: str, lib_name: str, project_dir: Path) -> str:
    """Generate <project>/.haywire/marketplace.toml with the project's library only.

    The project marketplace owns the project's own [[heaps]] (scaffolded
    here) plus, in ``--dev`` mode, the dev-repo barn libraries (appended by
    _register_dev_repo_locals_in_project after this file is written).
    [[caches]] is the refresh cache and stays empty at init time.

    Args:
        name: Project name.
        lib_name: The scaffolded local library's resolved dist name.
        project_dir: The project's root directory.
    """
    label = name.replace("-", " ").replace("_", " ").title()
    entry = _local_entry(
        name=lib_name,
        path=project_dir / "barn" / lib_name,
        label=label,
        description=f"Local library for the {name} project",
    )
    header = (
        "# Project marketplace — managed by haywire.\n"
        "# [[heaps]] are project-scoped editable libraries, written at `haywire init` time.\n"
        "# [[caches]] is the cache populated by the Library Manager's refresh action;\n"
        "# leave it empty here until you've added remote sources to ~/.haywire/marketplace.toml.\n\n"
    )
    return header + toml.dumps({"heaps": [entry]})


def init_project(
    name: str,
    auto_sync: bool = True,
    dev_repo: str | None = None,
    distname: str | None = None,
):
    """Scaffold a new haywire project.

    Args:
        name: Project name (used as directory name and, verbatim, the root
            ``[project].name``). May carry uppercase letters — see
            :func:`_validate_project_name` — but is lowercased when it feeds
            the scaffolded library's identity (:func:`_lib_basename`).
        auto_sync: If True, run `uv sync` after scaffolding.
        dev_repo: If set, absolute path to the haywire dev repo.
            Generated pyproject.toml files will use editable path sources.
        distname: If set, the scaffolded local library's pip distribution
            name, used verbatim — bypasses the default ``hay-<base>``
            automatism entirely. Must already be a valid, lowercase slug
            (see :func:`_validate_slug` — strict, no case easing); the
            caller (``cli/init.py``) validates before showing the confirm
            preview, but ``init_project`` itself re-validates so it stays
            safe to call directly (as the test suite does).
    """
    _validate_project_name(name)
    if distname is not None:
        _validate_slug(distname, "--distname")

    if not _check_git_available():
        print(
            "Error: 'haywire init' requires git to be installed.\n"
            "\n"
            "Git is used to initialize your project repository and version your work.\n"
            "\n"
            "Install git:\n"
            "  macOS (Homebrew):  brew install git\n"
            "  Ubuntu/Debian:     sudo apt-get install git\n"
            "  Windows:           https://git-scm.com/download/win\n"
            "\n"
            "Or using your system package manager. Then try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    project_dir = Path.cwd() / name

    if project_dir.exists():
        print(f"Error: Directory '{name}' already exists.")
        sys.exit(1)

    lib_name = _resolve_distname(name, distname)
    module_name = _distmodule(lib_name)
    label = name.replace("-", " ").replace("_", " ").title()

    print(f"Creating haywire project: {name}")

    # Create directory structure
    project_dir.mkdir()
    (project_dir / "graphs").mkdir()

    lib_dir = project_dir / "barn" / lib_name
    pkg_dir = lib_dir / module_name
    pkg_dir.mkdir(parents=True)

    # Create all component folders
    component_folders = [
        "nodes",
        "types",
        "widgets",
        "skins",
        "adapters",
        "settings",
        "themes",
        "panels",
        "editors",
    ]
    for folder in component_folders:
        folder_dir = pkg_dir / folder
        folder_dir.mkdir()
        (folder_dir / "__init__.py").write_text("")

    # Generate files
    (project_dir / "pyproject.toml").write_text(
        _generate_project_pyproject(name, lib_name, dev_repo=dev_repo)
    )

    (lib_dir / "pyproject.toml").write_text(
        _generate_library_pyproject(name, lib_name, module_name, dev_repo=dev_repo)
    )

    (pkg_dir / "__init__.py").write_text(_generate_library_init(name, label))
    (pkg_dir / "haybale.toml").write_text(_generate_haybale_toml(name, lib_name, label))

    # README.md at repo root (with marketstall share-url marker pair)
    (project_dir / "README.md").write_text(_generate_root_readme(name, label))

    # Default .gitignore (Python caches, virtualenvs, editor/OS cruft)
    (project_dir / ".gitignore").write_text(_generate_gitignore())

    # .gitattributes — EOL normalization + binary markers. No LFS: see the
    # comment block in _generate_gitattributes().
    (project_dir / ".gitattributes").write_text(_generate_gitattributes())

    # README.md inside the scaffolded barn library (with marker pair)
    (lib_dir / "README.md").write_text(_generate_library_readme(name, label))

    # Project-level .haywire config
    ensure_project_config(project_dir)

    # Project marketplace — [[heaps]] section. Holds the project's own
    # scaffolded library, plus (under --dev) every dev-repo barn library so
    # they're scoped to this project rather than leaking into the user-global
    # marketplace.
    (project_dir / ".haywire" / "marketplace.toml").write_text(
        _generate_project_marketplace_locals_only(name, lib_name, project_dir)
    )

    if dev_repo:
        _register_dev_repo_locals_in_project(dev_repo, project_dir)

    # Initialize git repository and create initial commit
    print("\nInitializing git repository...")
    subprocess.run(["git", "init"], cwd=str(project_dir), check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(project_dir), check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Haywire Scaffold",
            "-c",
            "user.email=scaffold@haywire.local",
            "commit",
            "-m",
            "Initial commit: haywire project scaffold",
        ],
        cwd=str(project_dir),
        check=True,
        capture_output=True,
    )

    # Global ~/.haywire config (just ensures the directory + defaults exist;
    # init no longer writes [[heaps]] there).
    ensure_global_config()

    # Track as recent project
    add_recent_project(str(project_dir))

    print(f"  Created {project_dir}/")
    print(f"  Created {project_dir / 'pyproject.toml'}")
    print(f"  Created {project_dir / '.haywire/'}")
    print(f"  Created {project_dir / 'graphs/'}")
    print(f"  Created {lib_dir}/")

    if auto_sync:
        print("\nRunning uv sync...")
        # --refresh forces uv to re-query the package index rather than trust a
        # cached view. A project scaffolded right after a release pins the just-
        # published version; a stale index cache (common on machines that used
        # haywire before the release) would otherwise fail to resolve it.
        result = subprocess.run(
            ["uv", "sync", "--refresh"],
            cwd=str(project_dir),
            capture_output=False,
        )
        if result.returncode != 0:
            print("\nWarning: uv sync failed. Run it manually:")
            print(f"  cd {name} && uv sync --refresh")

    print(f"\nProject '{name}' created successfully!")
    print("\nNext steps:")
    print(f"  cd {name}")
    if not auto_sync:
        print("  uv sync")
    print("  uv run haywire")
    print("\nTo publish your library:")
    print("  git remote add origin <your-repo-url>")
    print("  git push -u origin master")
    print("  uv run haywire share --save")
    print("\nCheck your current security exposure:")
    print("  uv run haywire security status")
