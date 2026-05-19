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


class ProjectNameCollisionError(RuntimeError):
    """Raised when haywire init would create a [[locals]] whose name already exists.

    The collision is against the user-global marketplace (~/.haywire/marketplace.toml).
    """


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
    """Build a [[locals]] entry per spec §6.

    Locals have a different schema than [[packages]]: only `name` and `path` are
    required; label and description are optional metadata. Locals are always
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


def _check_global_collision(name: str) -> None:
    """Raise ProjectNameCollisionError if `haybale-{name}` is already in the user-global locals."""
    from .config import GLOBAL_CONFIG_DIR, ensure_global_config

    ensure_global_config()
    global_mp = GLOBAL_CONFIG_DIR / "marketplace.toml"
    data = toml.loads(global_mp.read_text())
    locals_ = data.get("locals", [])
    target_name = f"haybale-{name}"
    for existing in locals_:
        if existing.get("name") == target_name:
            raise ProjectNameCollisionError(
                f'A project library named "{target_name}" is already registered '
                f"at {existing.get('path')} in the user-global marketplace. "
                f"Rename your new project or remove the conflicting entry from "
                f"{global_mp}."
            )


def _register_local_in_global(name: str, project_dir: Path) -> None:
    """Append a [[locals]] entry for this project to ~/.haywire/marketplace.toml.

    Refuses with ProjectNameCollisionError if a [[locals]] entry with the same
    name already exists (spec § 6 G5 — name collision between projects).

    Reads/writes via haywire_studio.config.GLOBAL_CONFIG_DIR so tests can patch
    the location.
    """
    from .config import GLOBAL_CONFIG_DIR, ensure_global_config

    ensure_global_config()
    global_mp = GLOBAL_CONFIG_DIR / "marketplace.toml"
    data = toml.loads(global_mp.read_text())

    locals_ = data.get("locals", [])
    label = name.replace("-", " ").replace("_", " ").title()
    new_entry = _local_entry(
        name=f"haybale-{name}",
        path=project_dir / "barn" / f"haybale-{name}",
        label=label,
        description=f"Local library for the {name} project",
    )

    for existing in locals_:
        if existing.get("name") == new_entry["name"]:
            raise ProjectNameCollisionError(
                f'A project library named "{new_entry["name"]}" is already registered '
                f"at {existing.get('path')} in the user-global marketplace. "
                f"Rename your new project or remove the conflicting entry from "
                f"{global_mp}."
            )

    locals_.append(new_entry)
    data["locals"] = locals_
    global_mp.write_text(toml.dumps(data))


def _register_dev_repo_locals_in_global(dev_repo: str) -> None:
    """In --dev mode, register every dev-repo barn library as a [[locals]] in the user-global marketplace.

    Walks `<dev_repo>/barn/*` and adds a [[locals]] entry for each directory
    with a pyproject.toml. Entries that already exist (by name) in the user-
    global marketplace are skipped silently — this is idempotent so multiple
    --dev projects on the same machine don't double-register or fail.
    """
    from .config import GLOBAL_CONFIG_DIR, ensure_global_config

    ensure_global_config()
    global_mp = GLOBAL_CONFIG_DIR / "marketplace.toml"
    data = toml.loads(global_mp.read_text())
    locals_ = data.get("locals", [])
    existing_names = {entry.get("name") for entry in locals_}

    barn = Path(dev_repo) / "barn"
    if not barn.is_dir():
        return

    for lib_dir in sorted(barn.iterdir()):
        if not lib_dir.is_dir() or not (lib_dir / "pyproject.toml").exists():
            continue
        # Read the package name from pyproject — don't trust the directory name.
        pyproject = toml.loads((lib_dir / "pyproject.toml").read_text())
        lib_name = pyproject.get("project", {}).get("name", lib_dir.name)
        if lib_name in existing_names:
            continue  # Idempotent: already registered, leave it alone.

        label = lib_name.removeprefix("haybale-").replace("-", " ").replace("_", " ").title()
        description = pyproject.get("project", {}).get("description", "")
        locals_.append(
            _local_entry(
                name=lib_name,
                path=lib_dir,
                label=label,
                description=description,
            )
        )
        existing_names.add(lib_name)

    data["locals"] = locals_
    global_mp.write_text(toml.dumps(data))


def _generate_project_marketplace_locals_only(name: str, project_dir: Path) -> str:
    """Generate <project>/.haywire/marketplace.toml with the project's library only.

    Per spec §6, the project marketplace has [[locals]] (the project's own library,
    written here at init time) and [[packages]] (populated by refresh — Plan E).
    This emitter writes [[locals]] only; the [[packages]] section is empty.
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
        "# [[locals]] are project-scoped editable libraries, written at `haywire init` time.\n"
        "# [[packages]] is the cache populated by the Library Manager's refresh action;\n"
        "# leave it empty here until you've added remote sources to ~/.haywire/marketplace.toml.\n\n"
    )
    return header + toml.dumps({"locals": [entry]})


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

    # G5 collision check (spec §6) — refuse if a [[locals]] with the same name
    # already exists in the user-global marketplace.
    try:
        _check_global_collision(name)
    except ProjectNameCollisionError as exc:
        print(f"Error: {exc}")
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

    # Project-level .haywire config
    ensure_project_config(project_dir)

    # Project marketplace — locals-only (the project's scaffolded library).
    # Dev-repo libraries (in --dev mode) are registered in the user-global
    # marketplace instead, by _register_local_in_global below (Task 6+).
    (project_dir / ".haywire" / "marketplace.toml").write_text(
        _generate_project_marketplace_locals_only(name, project_dir)
    )

    # Register the project's library in the user-global marketplace so the
    # Library Manager (and other haywire installs) can find it.
    _register_local_in_global(name, project_dir)

    if dev_repo:
        _register_dev_repo_locals_in_global(dev_repo)

    # Global ~/.haywire config
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
