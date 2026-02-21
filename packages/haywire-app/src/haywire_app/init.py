"""
Project scaffolding for Haywire.

Creates a new haywire project with:
- pyproject.toml (uv workspace with haywire-app dependency)
- .haywire/ config directory
- graphs/ directory
- libs/ directory with auto-scaffolded local haybale library
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import toml

from .config import ensure_global_config, ensure_project_config, add_recent_project


def _get_dev_repo_root() -> str:
    """Resolve the haywire dev repo root from this module's location.

    Works because this file lives at:
    <repo>/packages/haywire-app/src/haywire_app/init.py
    """
    return str(Path(__file__).resolve().parents[4])


def _sanitize_name(name: str) -> str:
    """Convert project name to a valid Python identifier for the library module."""
    # Replace hyphens and spaces with underscores, strip non-alphanumeric
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
    # Ensure it doesn't start with a digit
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    return sanitized


def _generate_project_pyproject(name: str, dev_repo: str | None = None) -> str:
    """Generate the project's pyproject.toml content.

    Args:
        name: Project name.
        dev_repo: If set, absolute path to the haywire dev repo.
            Adds [tool.uv.sources] pointing to local editable packages.
    """
    data = {
        'project': {
            'name': name,
            'version': '0.1.0',
            'requires-python': '>=3.10',
            'dependencies': [
                'haywire-app>=0.1.0',
            ],
        },
        'tool': {
            'uv': {
                'workspace': {
                    'members': ['libs/*'],
                },
            },
        },
    }

    if dev_repo:
        data['tool']['uv']['sources'] = {
            'haywire-app': {'path': f'{dev_repo}/packages/haywire-app', 'editable': True},
            'haywire-framework': {'path': f'{dev_repo}/packages/haywire-framework', 'editable': True},
        }

    return toml.dumps(data)


def _generate_library_pyproject(name: str, module_name: str, dev_repo: str | None = None) -> str:
    """Generate the local haybale library's pyproject.toml content.

    Args:
        name: Project name.
        module_name: Python module name (e.g. haybale_my_project).
        dev_repo: If set, absolute path to the haywire dev repo.
    """
    lib_name = f'haybale-{name}'
    sources_section = ''
    if dev_repo:
        sources_section = f'''
[tool.uv.sources]
haywire-framework = {{ path = "{dev_repo}/packages/haywire-framework", editable = true }}
'''

    return f'''[project]
name = "{lib_name}"
version = "0.1.0"
description = "Local library for {name} project"
requires-python = ">=3.10"
license = {{text = "MIT"}}

dependencies = ["haywire-framework>=0.1.0"]

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
- renderers/  — custom node renderers
- adapters/   — type-to-type conversion adapters
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.types.registry import TypeRegistry

from haywire.ui.renderer.registry import RendererRegistry
from haywire.ui.widget.registry import WidgetRegistry


@library(
    label='{label}',
    id='{name}',
    version='0.1.0',
    description='Local library for {name} project',
    file_watcher=True,
)
class Library(BaseLibrary):
    """Local project library — add your components in the subfolders."""

    def register_components(self):
        """Register all components with the global registries."""
        base_path = Path(__file__).parent

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
            folder_path=str(base_path / 'renderers'),
            registry_cls=RendererRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / 'nodes'),
            registry_cls=NodeRegistry,
        )

    def validate(self) -> bool:
        """Validate library structure."""
        return True
'''


def _generate_dev_marketplace(dev_repo: str) -> str:
    """Generate a marketplace.toml pointing to dev repo libraries.

    Lists all libraries in the dev repo so developers can install them
    from the library manager UI.
    """
    libraries = [
        {
            'name': 'haybale-core',
            'version': '1.0.0',
            'description': 'Core Haywire library with fundamental components',
            'author': 'maybites',
            'source': 'local',
            'install_spec': f'{dev_repo}/libraries/haybale-core',
            'tags': ['core', 'types', 'widgets', 'renderers'],
        },
        {
            'name': 'haybale-example',
            'version': '0.1.0',
            'description': 'Example library for demonstrating multi-library support',
            'author': 'Example Author',
            'source': 'local',
            'install_spec': f'{dev_repo}/libraries/haybale-example',
            'tags': ['example', 'demo', 'tutorial'],
        },
        {
            'name': 'haybale-testing',
            'version': '1.0.0',
            'description': 'Test library for test support',
            'author': 'Haywire Team',
            'source': 'local',
            'install_spec': f'{dev_repo}/libraries/haybale-testing',
            'tags': ['testing', 'development', 'debug'],
        },
        {
            'name': 'haybale-visiongraph',
            'version': '0.0.1',
            'description': 'Visiongraph library — camera, video, OpenCV nodes',
            'author': 'Florian Bruggisser, Martin Froehlich',
            'source': 'local',
            'install_spec': f'{dev_repo}/libraries/haybale-visiongraph',
            'tags': ['vision', 'camera', 'video', 'opencv'],
        },
        {
            'name': 'haybale-TEST_A',
            'version': '1.0.0',
            'description': 'Test library A for demonstrating multi-library support',
            'author': 'Haywire Team',
            'source': 'local',
            'install_spec': f'{dev_repo}/libraries/haybale-TEST_A',
            'tags': ['testing', 'development'],
        },
    ]
    data = {'packages': libraries}
    return toml.dumps(data)


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

    module_name = f'haybale_{_sanitize_name(name)}'
    label = name.replace('-', ' ').replace('_', ' ').title()

    print(f"Creating haywire project: {name}")

    # Create directory structure
    project_dir.mkdir()
    (project_dir / 'graphs').mkdir()

    lib_dir = project_dir / 'libs' / f'haybale-{name}'
    pkg_dir = lib_dir / module_name
    pkg_dir.mkdir(parents=True)

    # Create all component folders
    component_folders = ['nodes', 'types', 'widgets', 'renderers', 'adapters']
    for folder in component_folders:
        folder_dir = pkg_dir / folder
        folder_dir.mkdir()
        (folder_dir / '__init__.py').write_text('')

    # Generate files
    (project_dir / 'pyproject.toml').write_text(
        _generate_project_pyproject(name, dev_repo=dev_repo)
    )

    (lib_dir / 'pyproject.toml').write_text(
        _generate_library_pyproject(name, module_name, dev_repo=dev_repo)
    )

    (pkg_dir / '__init__.py').write_text(
        _generate_library_init(name, label)
    )

    # Project-level .haywire config
    ensure_project_config(project_dir)

    # Dev marketplace manifest
    if dev_repo:
        (project_dir / '.haywire' / 'marketplace.toml').write_text(
            _generate_dev_marketplace(dev_repo)
        )

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
            ['uv', 'sync'],
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
