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


def _sanitize_name(name: str) -> str:
    """Convert project name to a valid Python identifier for the library module."""
    # Replace hyphens and spaces with underscores, strip non-alphanumeric
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
    # Ensure it doesn't start with a digit
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    return sanitized


def _generate_project_pyproject(name: str) -> str:
    """Generate the project's pyproject.toml content."""
    data = {
        'project': {
            'name': name,
            'version': '0.1.0',
            'requires-python': '>=3.10',
            'dependencies': [
                'haywire-app>=0.1.0',
                'haybale-core>=1.0.0',
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
    return toml.dumps(data)


def _generate_library_pyproject(name: str, module_name: str) -> str:
    """Generate the local haybale library's pyproject.toml content."""
    lib_name = f'haybale-{name}'
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
'''


def _generate_library_init(name: str, label: str) -> str:
    """Generate the local haybale library's __init__.py content."""
    return f'''"""
Local haybale library for the {name} project.

Add your custom nodes in the nodes/ folder.
They will be automatically discovered and registered.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.node.registry import NodeRegistry


@library(
    label='{label}',
    id='{name}',
    version='0.1.0',
    description='Local library for {name} project',
    file_watcher=True,
)
class Library(BaseLibrary):
    """Local project library — add your nodes in the nodes/ folder."""

    def register_components(self):
        """Register all components with the global registries."""
        base_path = Path(__file__).parent

        self.add_folder_to_registry(
            folder_path=str(base_path / 'nodes'),
            registry_cls=NodeRegistry,
        )

    def validate(self) -> bool:
        """Validate library structure."""
        return True
'''


def init_project(name: str, auto_sync: bool = True):
    """Scaffold a new haywire project.

    Args:
        name: Project name (used as directory name and package name).
        auto_sync: If True, run `uv sync` after scaffolding.
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
    nodes_dir = pkg_dir / 'nodes'
    nodes_dir.mkdir(parents=True)

    # Generate files
    (project_dir / 'pyproject.toml').write_text(
        _generate_project_pyproject(name)
    )

    (lib_dir / 'pyproject.toml').write_text(
        _generate_library_pyproject(name, module_name)
    )

    (pkg_dir / '__init__.py').write_text(
        _generate_library_init(name, label)
    )

    (nodes_dir / '__init__.py').write_text('')

    # Project-level .haywire config
    ensure_project_config(project_dir)

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
