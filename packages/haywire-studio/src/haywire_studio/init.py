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
from pathlib import Path
from typing import Any

import toml

from .config import ensure_global_config, ensure_project_config, add_recent_project


def _get_dev_repo_root() -> str:
    """Resolve the haywire dev repo root from this module's location.

    Works because this file lives at:
    <repo>/packages/haywire-studio/src/haywire_studio/init.py
    """
    return str(Path(__file__).resolve().parents[4])


def _sanitize_name(name: str) -> str:
    """Convert project name to a valid Python identifier for the library module."""
    # Replace hyphens and spaces with underscores, strip non-alphanumeric
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower())
    # Ensure it doesn't start with a digit
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized


def _generate_project_pyproject(name: str, dev_repo: str | None = None) -> str:
    """Generate the project's pyproject.toml content.

    Args:
        name: Project name.
        dev_repo: If set, absolute path to the haywire dev repo.
            Adds [tool.uv.sources] pointing to local editable packages.
    """
    lib_name = f"haybale-{name}"
    sources: dict[str, dict[str, object]] = {lib_name: {"workspace": True}}
    data: dict[str, Any] = {
        "project": {
            "name": name,
            "version": "0.1.0",
            "requires-python": ">=3.10",
            "dependencies": [
                "haywire-studio~=0.0.1",
                "haybale-marketplace~=0.0.1",
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
        data["project"]["dependencies"] += ["haybale-core", "haybale-studio"]
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


def _generate_library_pyproject(name: str, module_name: str, dev_repo: str | None = None) -> str:
    """Generate the local haybale library's pyproject.toml content.

    Args:
        name: Project name.
        module_name: Python module name (e.g. haybale_my_project).
        dev_repo: If set, absolute path to the haywire dev repo.
    """
    lib_name = f"haybale-{name}"
    sources_section = ""
    if dev_repo:
        sources_section = f'''
[tool.uv.sources]
haywire-core = {{ path = "{dev_repo}/packages/haywire-core", editable = true }}
'''

    return f'''[project]
name = "{lib_name}"
version = "0.0.1"
description = "Local library for {name} project"
requires-python = ">=3.10"
license = {{text = "MIT"}}

dependencies = ["haywire-core~=0.0.1"]

[project.entry-points."haywire.libraries"]
{name} = "{module_name}:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["{module_name}"]
{sources_section}'''


_README_MARKER_START = "<!-- marketstall:share-url:start -->"
_README_MARKER_END = "<!-- marketstall:share-url:end -->"
_README_PLACEHOLDER = (
    "*Subscribe URL not yet published — run `haywire share --save` after pushing this repo to a git remote.*"
)


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
        f"{_README_PLACEHOLDER}\n"
        f"{_README_MARKER_END}\n"
        f"\n"
        f"## Getting started\n"
        f"\n"
        f"```sh\n"
        f"uv sync\n"
        f"uv run haywire\n"
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

from importlib.metadata import version as _pkg_version
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
    label='{label}',
    id='{name}',
    version=_pkg_version('haybale-{name}'),
    description='Local library for {name} project',
    url='',
    help_url='',
    author='',
    author_url='',
    dependencies=['haybale_core'],
    tags=['experimental', 'project-local'],
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
    """Build a [[heaps]] entry per spec §3.2.

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
    from haywire.core.marketstall import DuplicateHeapNameError, add_heap_to_project

    project_mp = project_dir / ".haywire" / "marketplace.toml"

    barn = Path(dev_repo) / "barn"
    if not barn.is_dir():
        return

    for lib_dir in sorted(barn.iterdir()):
        if not lib_dir.is_dir() or not (lib_dir / "pyproject.toml").exists():
            continue
        # Read the package name from pyproject — don't trust the directory name.
        pyproject = toml.loads((lib_dir / "pyproject.toml").read_text())
        lib_name = pyproject.get("project", {}).get("name", lib_dir.name)
        label = lib_name.removeprefix("haybale-").replace("-", " ").replace("_", " ").title()
        description = pyproject.get("project", {}).get("description", "")

        try:
            add_heap_to_project(
                project_mp,
                name=lib_name,
                path=lib_dir,
                label=label,
                description=description,
            )
        except DuplicateHeapNameError:
            continue


def _generate_project_marketplace_locals_only(name: str, project_dir: Path) -> str:
    """Generate <project>/.haywire/marketplace.toml with the project's library only.

    The project marketplace owns the project's own [[heaps]] (scaffolded
    here) plus, in ``--dev`` mode, the dev-repo barn libraries (appended by
    _register_dev_repo_locals_in_project after this file is written).
    [[caches]] is the refresh cache and stays empty at init time.
    """
    label = name.replace("-", " ").replace("_", " ").title()
    entry = _local_entry(
        name=f"haybale-{name}",
        path=project_dir / "barn" / f"haybale-{name}",
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


def init_project(name: str, auto_sync: bool = True, dev_repo: str | None = None):
    """Scaffold a new haywire project.

    Args:
        name: Project name (used as directory name and package name).
        auto_sync: If True, run `uv sync` after scaffolding.
        dev_repo: If set, absolute path to the haywire dev repo.
            Generated pyproject.toml files will use editable path sources.
    """
    project_dir = Path.cwd() / name

    if project_dir.exists():
        print(f"Error: Directory '{name}' already exists.")
        sys.exit(1)

    module_name = f"haybale_{_sanitize_name(name)}"
    label = name.replace("-", " ").replace("_", " ").title()

    print(f"Creating haywire project: {name}")

    # Create directory structure
    project_dir.mkdir()
    (project_dir / "graphs").mkdir()

    lib_dir = project_dir / "barn" / f"haybale-{name}"
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
    (project_dir / "pyproject.toml").write_text(_generate_project_pyproject(name, dev_repo=dev_repo))

    (lib_dir / "pyproject.toml").write_text(
        _generate_library_pyproject(name, module_name, dev_repo=dev_repo)
    )

    (pkg_dir / "__init__.py").write_text(_generate_library_init(name, label))

    # README.md at repo root (with marketstall share-url marker pair per spec §6.6)
    (project_dir / "README.md").write_text(_generate_root_readme(name, label))

    # README.md inside the scaffolded barn library (with marker pair)
    (lib_dir / "README.md").write_text(_generate_library_readme(name, label))

    # Project-level .haywire config
    ensure_project_config(project_dir)

    # Project marketplace — [[heaps]] section. Holds the project's own
    # scaffolded library, plus (under --dev) every dev-repo barn library so
    # they're scoped to this project rather than leaking into the user-global
    # marketplace.
    (project_dir / ".haywire" / "marketplace.toml").write_text(
        _generate_project_marketplace_locals_only(name, project_dir)
    )

    if dev_repo:
        _register_dev_repo_locals_in_project(dev_repo, project_dir)

    # Global ~/.haywire config (just ensures the directory + an empty
    # marketplace.toml exist; init no longer writes [[heaps]] there).
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
        result = subprocess.run(
            ["uv", "sync"],
            cwd=str(project_dir),
            capture_output=False,
        )
        if result.returncode != 0:
            print("\nWarning: uv sync failed. Run it manually:")
            print(f"  cd {name} && uv sync")

    print(f"\nProject '{name}' created successfully!")
    print("\nNext steps:")
    if not auto_sync:
        print(f"  cd {name}")
        print("  uv sync")
    else:
        print(f"  cd {name}")
    print("  uv run haywire")
