"""
Project scaffolding for Haywire.

Creates a new haywire project with:
- pyproject.toml (uv workspace with haywire-app dependency)
- .haywire/ config directory
- graphs/ directory
- barn/ directory with auto-scaffolded local haybale library
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
    lib_name = f'haybale-{name}'
    data = {
        'project': {
            'name': name,
            'version': '0.1.0',
            'requires-python': '>=3.10',
            'dependencies': [
                'haywire-app>=0.1.0',
                lib_name,
            ],
        },
        'tool': {
            'uv': {
                'workspace': {
                    'members': ['barn/*'],
                },
                'sources': {
                    lib_name: {'workspace': True},
                },
            },
        },
    }

    if dev_repo:
        data['tool']['uv']['sources'].update({
            'haywire-app': {'path': f'{dev_repo}/packages/haywire-app', 'editable': True},
            'haywire-framework': {'path': f'{dev_repo}/packages/haywire-framework', 'editable': True},
        })

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
- skins/      — custom node skins
- adapters/   — type-to-type conversion adapters
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.types.registry import TypeRegistry

from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.widget.registry import WidgetRegistry


@library(
    label='{label}',
    id='{name}',
    version='0.1.0',
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

    def validate(self) -> bool:
        """Validate library structure."""
        return True
'''


def _project_lib_entry(name: str, module_name: str, project_dir: Path) -> dict:
    """Build a marketplace entry for the project's own scaffolded library."""
    lib_path = project_dir / 'barn' / f'haybale-{name}'
    label = name.replace('-', ' ').replace('_', ' ').title()
    return {
        'name': f'haybale-{name}',
        'label': label,
        'version': '0.1.0',
        'description': f'Local library for the {name} project',
        'source': 'local',
        'install_spec': str(lib_path),
        'docs_url': str(lib_path / module_name),
    }


def _generate_project_marketplace(name: str, module_name: str, project_dir: Path) -> str:
    """Generate a minimal marketplace.toml for a regular (non-dev) project.

    Contains only the project's own scaffolded library, plus a commented
    template showing how to add more entries.
    """
    entry = _project_lib_entry(name, module_name, project_dir)
    header = (
        '# Project marketplace — add [[packages]] entries here to make libraries\n'
        '# available in the Library Manager (Available section).\n'
        '#\n'
        '# source = "local"  →  install_spec is a local path (editable install)\n'
        '# source = "pypi"   →  install_spec is a PyPI package name/specifier\n'
        '# source = "git"    →  install_spec is a git URL (with optional #subdirectory=)\n'
        '#\n'
        '# To pull in a remote marketplace feed, add [[sources]] entries to\n'
        '# ~/.haywire/marketplace.toml instead.\n\n'
    )
    return header + toml.dumps({'packages': [entry]})


def _generate_dev_marketplace(dev_repo: str, name: str, module_name: str, project_dir: Path) -> str:
    """Generate a marketplace.toml pointing to dev repo libraries.

    Lists the project's own library first, followed by all libraries in the
    dev repo, so developers can install any of them from the Library Manager.
    """
    def _lib(lib_name, version, description, author, tags):
        label = lib_name.removeprefix('haybale-').replace('-', ' ').replace('_', ' ').title()
        lib_module = lib_name.replace('-', '_')
        lib_path = f'{dev_repo}/barn/{lib_name}'
        return {
            'name': lib_name,
            'label': label,
            'version': version,
            'description': description,
            'author': author,
            'source': 'local',
            'install_spec': lib_path,
            'tags': tags,
            'docs_url': f'{lib_path}/{lib_module}',
        }

    libraries = [
        # Project's own library first
        _project_lib_entry(name, module_name, project_dir),
        # Dev repo libraries
        _lib('haybale-core', '1.0.0',
             'Core Haywire library with fundamental components',
             'maybites', ['core', 'types', 'widgets', 'skins']),
        _lib('haybale-example', '0.1.0',
             'Example library for demonstrating multi-library support',
             'Example Author', ['example', 'demo', 'tutorial']),
        _lib('haybale-testing', '1.0.0',
             'Test library for test support',
             'Haywire Team', ['testing', 'development', 'debug']),
        _lib('haybale-visiongraph', '0.0.1',
             'Visiongraph library — camera, video, OpenCV nodes',
             'Florian Bruggisser, Martin Froehlich', ['vision', 'camera', 'video', 'opencv']),
        _lib('haybale-TEST_A', '1.0.0',
             'Test library A for demonstrating multi-library support',
             'Haywire Team', ['testing', 'development']),
    ]
    return toml.dumps({'packages': libraries})


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

    lib_dir = project_dir / 'barn' / f'haybale-{name}'
    pkg_dir = lib_dir / module_name
    pkg_dir.mkdir(parents=True)

    # Create all component folders
    component_folders = ['nodes', 'types', 'widgets', 'skins', 'adapters']
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

    # Marketplace manifest — always written; dev variant includes dev-repo libs
    if dev_repo:
        marketplace = _generate_dev_marketplace(dev_repo, name, module_name, project_dir)
    else:
        marketplace = _generate_project_marketplace(name, module_name, project_dir)
    (project_dir / '.haywire' / 'marketplace.toml').write_text(marketplace)

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
