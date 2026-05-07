# Haywire Library System - Developer Guide

## Quick Start

### Using Existing Libraries

Install any Haywire library from pip:

```bash
uv pip install haybale-my-library
```

That's it! The library is automatically discovered and loaded when you run your Haywire application.

##  Creating a New Library

### Library Structure Options

#### Option 1: Package Structure (Recommended for Distribution)

Use this when you want to publish your library to PyPI or share it with others.


```
📁 haybale-MYLIBRARY/                     # Git repo name / unique pip package name
├── pyproject.toml
│   [project]
│   name = "haybale-MYLIBRARY"            # pip install haybale-TEST_B
│   
│   [project.entry-points."haywire.libraries"]
│   MYLIBRARY = "haybale_MYLIBRARY:Library"  # ID matches module
│   
│   [tool.hatch.build.targets.wheel]
│   packages = ["haybale_MYLIBRARY"]
│   
│   [tool.hatch.build.targets.sdist]
│   include = [
│       "haybale_MYLIBRARY/",
│       "README.md",
│   ]
│
├── README.md                               # Documentation
└── 📁 haybale_MYLIBRARY/                   # Python module
    ├── __init__.py                         # Library class with @library decorator
    │   @library(
    │       label='My Library',
    │       id='MYLIBRARY',
    │
    ├── 📁 adapters/
    │   ├── __init__.py
    │   └── my_adapater.py
    ├── 📁 nodes/
    │   ├── __init__.py
    │   └── my_node.py
    ├── 📁 renderers/
    │   ├── __init__.py
    │   └── my_renderer.py
    ├── 📁 types/
    │   ├── __init__.py
    │   └── my_type.py
    └── 📁 widgets/
        ├── __init__.py
        └── my_widget.py
```


**When to use:**
- ✅ Publishing to PyPI
- ✅ Sharing with others
- ✅ Need version management
- ✅ Want hot-reload during development

**Install:**
```bash
cd my_library
uv pip install -e .  # Development (hot-reload)
uv pip install .     # Production
```

#### Option 2: Flat Structure (Core Libraries Only)

This is simpler but only used for libraries bundled with Haywire core or libraries that need to be loaded by provide the path to the root folder 

```
~/libraries/
└── 📁 haybale_MYLIBRARY/                   # Python module
    ├── __init__.py                         # Library class with @library decorator
    │   @library(
    │       label='My Library',
    │       id='MYLIBRARY',
    │
    ├── 📁 adapters/
    │   ├── __init__.py
    │   └── my_adapater.py
    ├── 📁 nodes/
    │   ├── __init__.py
    │   └── my_node.py
    ├── 📁 renderers/
    │   ├── __init__.py
    │   └── my_renderer.py
    ├── 📁 types/
    │   ├── __init__.py
    │   └── my_type.py
    └── 📁 widgets/
        ├── __init__.py
        └── my_widget.py
```

**When to use:**
- ✅ Adhoc Library
- ✅ Library is part of Haywire core
- ✅ Never distributed separately
- ✅ Maintained in main repo

**If you plan to distribute:**  use the package structure instead.

### Step by Step Guilde

**1. Create the library structure:**

```bash
mkdir -p my_library/my_library/nodes
cd my_library
```

**2. Create `my_library/__init__.py`:**

```python
from pathlib import Path
from haywire.core.library.library import BaseLibrary, library
from haywire.core.library.registries.reg_node import NodeRegistry

@library(
    label='My Library',
    id='my_library',
    version='1.0.0',
    description='My custom Haywire library',
    dependencies=['haywire.core'],
    file_watcher=True  # Enable hot-reload
)
class Library(BaseLibrary):
    """My library implementation"""
    
    def register_components(self):
        """Register your nodes, widgets, etc."""
        base_path = Path(__file__).parent
        
        # Register nodes folder
        self.add_folder_to_registry(
            folder_path=str(base_path / 'nodes'),
            registry_cls=NodeRegistry
        )
    
    def validate(self) -> bool:
        """Validate library structure"""
        return True

# Required: Export for entry point
__all__ = ['Library']
```

**3. Create `pyproject.toml`:**

```toml
[project]
name = "haybale-my-library"
version = "1.0.0"
description = "My custom Haywire library"
requires-python = ">=3.9"

dependencies = [
    "haywire>=0.0.1",
]

# This makes your library auto-discoverable!
[project.entry-points."haywire.libraries"]
my_library = "my_library:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["my_library"]
```

**4. Install for development:**

```bash
uv pip install -e .
```

**5. Add your nodes:**

Create `my_library/nodes/my_node.py`:

```python
from haywire.core.node.base_node import BaseNode, node

@node(
    label='My Node',
    description='Does something cool',
    menu='my_library/basic'
)
class MyNode(BaseNode):
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        # Configure your node
```

**6. Done!** 

## Configuration

### Library Metadata (@library decorator)

```python
@library(
    label='My Library',              # Required: Display name
    id='my_library',                 # Optional: Defaults to label
    version='1.0.0',                 # Optional: Defaults to '1.0.0'
    description='What it does',      # Optional: Description
    dependencies=['haywire.core'],   # Optional: Required libraries
    file_watcher=True,               # Optional: Enable hot-reload
    url='https://...',               # Optional: Library website
    help_url='https://...',          # Optional: Documentation
    author='Your Name',              # Optional: Author name
    author_url='https://...',        # Optional: Author website
)
class Library(BaseLibrary):
    ...
```

### Entry Point Configuration (pyproject.toml)

The entry point tells Haywire where to find your Library class:

```toml
[project.entry-points."haywire.libraries"]
library_id = "package_name:Library"
```

**Examples:**

```toml
# Simple package (Library class in __init__.py)
[project.entry-points."haywire.libraries"]
my_library = "my_library:Library"

# Nested module
[project.entry-points."haywire.libraries"]
my_library = "my_library.core:Library"

# Multiple libraries in one package
[project.entry-points."haywire.libraries"]
lib_one = "my_package.lib_one:Library"
lib_two = "my_package.lib_two:Library"
```

### Decorator Convention: Always Use Parentheses

All component decorators (`@library`, `@node`, `@adapter`, `@skin`, `@widget`,
`@editor`, `@panel`, `@theme`, `@type`) must be invoked with parentheses,
even when no arguments are needed:

```python
# Correct
@node()
class EmptyNode(BaseNode): ...

@adapter(converts_from=Temperature, converts_to=FLOAT)
class TempAdapter(BaseAdapter): ...

# Wrong — bare @decorator form is not supported
@node
class EmptyNode(BaseNode): ...
```

The bare `@decorator` form (without parens) is intentionally unsupported.
Most component decorators require at least one keyword argument anyway
(`label=`, `converts_from=`, etc.) so this is rarely visible in practice.

### Component Registration

In your Library class's `register_components()` method:

```python
def register_components(self):
    base_path = Path(__file__).parent
    
    # Register nodes
    self.add_folder_to_registry(
        folder_path=str(base_path / 'nodes'),
        registry_cls=NodeRegistry,
        exclude_patterns=['test_', '__']  # Optional
    )
    
    # Register widgets
    self.add_folder_to_registry(
        folder_path=str(base_path / 'widgets'),
        registry_cls=WidgetRegistry
    )
    
    # Register renderers
    self.add_folder_to_registry(
        folder_path=str(base_path / 'renderers'),
        registry_cls=SkinRegistry
    )
    
    # Register adapters
    self.add_folder_to_registry(
        folder_path=str(base_path / 'adapters'),
        registry_cls=AdapterRegistry
    )
```

### Hot-Reload Configuration

**Enable in library:**

```python
@library(
    label='My Library',
    file_watcher=True,  # Enable file watching
)
```

**Enable globally in application:**

```python
from haywire.core.di.config import create_library_system_service

service = create_library_system_service(
    enable_file_watching=True,
    debounce_delay=0.5  # Wait 0.5s after file change
)
```

## Installation Methods

### Method 1: Editable Install (Development)

**Best for:** Active development with hot-reload

```bash
cd my_library
uv pip install -e .
```

**Features:**
- ✅ Changes apply immediately (hot-reload)
- ✅ No reinstall needed after code changes
- ✅ Links to your source directory
- ✅ Perfect for debugging

**Verify:**
```bash
uv pip list --editable
# Should show: haybale-my-library  1.0.0  /path/to/my_library
```

### Method 2: Regular Install (Production)

**Best for:** Using published libraries, production deployments

```bash
# From PyPI
uv pip install haybale-my-library

# From local directory
cd my_library
uv pip install .

# From wheel file
uv pip install dist/haywire_my_library-1.0.0-py3-none-any.whl
```

**Features:**
- ✅ Standard installation
- ✅ Clean deployment
- ❌ No hot-reload (requires reinstall for changes)
- ✅ Installed in site-packages

### Method 3: From Git Repository

```bash
# Install from GitHub
uv pip install git+https://github.com/username/haybale-my-library.git

# Install specific branch/tag
uv pip install git+https://github.com/username/haybale-my-library.git@main
uv pip install git+https://github.com/username/haybale-my-library.git@v1.0.0

# Editable from git
uv pip install -e git+https://github.com/username/haybale-my-library.git#egg=haybale-my-library
```

## Publishing Your Library

### 1. Prepare Your Package

Ensure you have:
- ✅ `pyproject.toml` with correct metadata
- ✅ `README.md` with documentation
- ✅ Entry point configured
- ✅ Version number set
- ✅ Dependencies listed

### 2. Build

```bash
cd my_library

# Install build tools
uv pip install build

# Build package
python -m build

# Creates:
# dist/haywire_my_library-1.0.0-py3-none-any.whl
# dist/haywire_my_library-1.0.0.tar.gz
```

### 3. Test Locally

```bash
# Install the wheel
uv pip install dist/haywire_my_library-1.0.0-py3-none-any.whl

# Test in your app
python your_app.py
```

### 4. Publish to PyPI

```bash
# Install twine
uv pip install twine

# Upload to PyPI
python -m twine upload dist/*

# Or upload to Test PyPI first
python -m twine upload --repository testpypi dist/*
```

### 5. Install from PyPI

Once published, anyone can install:

```bash
uv pip install haybale-my-library
```

## Dependencies

### Declaring Dependencies

In `pyproject.toml`:

```toml
[project]
dependencies = [
    "haywire>=0.0.1",           # Haywire itself
    "numpy>=1.20.0",            # External packages
    "pillow>=9.0.0",
]

# Optional dependencies
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=22.0.0",
]
extra-features = [
    "tensorflow>=2.10.0",
]
```

### Library Dependencies

Declare other Haywire libraries your library needs:

```python
@library(
    label='My Library',
    dependencies=['haywire.core', 'other_library'],
)
```

**Note:** Currently, dependencies are informational. Load order is by discovery priority, not dependency graph. Future versions will support topological sorting.

## Common Workflows

### Development Workflow

```bash
# 1. Create library structure
mkdir -p my_library/my_library/nodes
cd my_library

# 2. Create files
# - pyproject.toml
# - my_library/__init__.py (with @library)
# - my_library/nodes/my_node.py

# 3. Install in editable mode
uv pip install -e .

# 4. Develop with hot-reload
# Make changes, they apply immediately!

# 5. Test
python -m pytest tests/

# 6. Build when ready
python -m build
```

### Publishing Workflow

```bash
# 1. Update version in pyproject.toml
# version = "1.0.1"

# 2. Build
python -m build

# 3. Test installation
uv pip install dist/haywire_my_library-1.0.1-py3-none-any.whl

# 4. Publish
python -m twine upload dist/*

# 5. Tag release
git tag v1.0.1
git push origin v1.0.1
```

### User Installation Workflow

```bash
# 1. Find library
# - Browse PyPI
# - Check library documentation

# 2. Install
uv pip install haybale-my-library

# 3. Use in application
python your_haywire_app.py
# Library auto-discovered and loaded!
```

## Troubleshooting

### Library Not Discovered

**Check if installed:**
```bash
uv pip list | grep my-library
```

**Check entry points:**
```bash
python -c "from importlib.metadata import entry_points; print([ep.name for ep in entry_points(group='haywire.libraries')])"
```

**Verify Library class:**
```python
from my_library import Library
print(hasattr(Library, 'class_identity'))  # Should be True
```

**Check logs:**
Look for messages like:
- `✓ Found pip install: My Library (my_library)`
- `ERROR: Failed to load entry point 'my_library'`

### Hot-Reload Not Working

**For editable installs:**

```bash
# Verify editable
uv pip list --editable | grep my-library

# Check file_watcher=True in @library decorator
```

**For regular installs:**

Hot-reload doesn't work with regular installs. Reinstall after changes:

```bash
uv pip install --force-reinstall .
```

### Import Errors

**ModuleNotFoundError:**

Check your entry point matches your structure:

```toml
# If Library is in my_library/__init__.py:
[project.entry-points."haywire.libraries"]
my_library = "my_library:Library"

# If Library is in my_library/core.py:
[project.entry-points."haywire.libraries"]
my_library = "my_library.core:Library"
```

**Circular imports:**

Avoid importing your Library class in submodules:

```python
# ❌ Bad - circular import
# my_library/nodes/my_node.py
from my_library import Library  # Don't do this

# ✅ Good - import what you need
from haywire.core.node.base_node import BaseNode, node
```

### Dependency Conflicts

**Check installed versions:**
```bash
uv pip show haywire
uv pip show my-library
```

**Update dependencies:**
```bash
uv pip install --upgrade haywire haybale-my-library
```

### Library Loaded from Wrong Source

If you have the same library in multiple places (folder + pip), check which loaded:

```python
from haywire.core.di.config import create_library_system_service

service = create_library_system_service()
registry = service.get_library_registry()

# Check source
source = registry.get_library_source('my_library')
print(f"Loaded from: {source}")
```

**Fix:** Remove from lower priority source (usually uninstall pip or remove folder path).

## Best Practices

### Project Structure

✅ **Do:**
- Use package structure for distributable libraries
- Keep Library class in `__init__.py`
- Organize components in subfolders (nodes/, widgets/, etc.)
- Include README.md with usage examples
- Add tests in `tests/` directory

❌ **Don't:**
- Mix multiple Library classes in one package
- Put Library class in deeply nested modules
- Hardcode file paths
- Import Library class in submodules

### Naming Conventions

**Package name** (PyPI):
- `haybale-my-library` (lowercase, hyphens)

**Library ID**:
- `my_library` (lowercase, underscores, matches package folder)

**Display label**:
- `My Library` (title case, spaces ok)

**Node menu paths**:
- `my_library/category/subcategory`

### Versioning

Follow [Semantic Versioning](https://semver.org/):

- `1.0.0` - Major.Minor.Patch
- `1.0.1` - Bug fixes
- `1.1.0` - New features (backward compatible)
- `2.0.0` - Breaking changes

### Documentation

Include in your `README.md`:

```markdown
# Haywire My Library

Short description

## Installation

\`\`\`bash
uv pip install haybale-my-library
\`\`\`

## Nodes Provided

- **My Node**: Does X
- **Another Node**: Does Y

## Usage Examples

\`\`\`python
# Example code
\`\`\`

## Development

\`\`\`bash
uv pip install -e .
\`\`\`

## License

MIT
```

### Testing

```python
# tests/test_library.py
from my_library import Library

def test_library_metadata():
    assert Library.class_identity.label == 'My Library'
    assert Library.class_identity.id == 'my_library'

def test_library_validation():
    lib = Library(...)
    assert lib.validate() == True
```

## Examples

### Minimal Library

Simplest possible library:

```python
# my_library/__init__.py
from haywire.core.library.library import library, BaseLibrary

@library(label='My Library', id='my_library')
class Library(BaseLibrary):
    def register_components(self):
        pass  # No components yet
    
    def validate(self) -> bool:
        return True

__all__ = ['Library']
```

```toml
# pyproject.toml
[project]
name = "haybale-my-library"
version = "1.0.0"
dependencies = ["haywire>=0.0.1"]

[project.entry-points."haywire.libraries"]
my_library = "my_library:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["my_library"]
```

### Complete Library

Full-featured example:

```python
# my_library/__init__.py
from pathlib import Path
from haywire.core.library.library import library, BaseLibrary
from haywire.core.library.registries.reg_node import NodeRegistry
from haywire.core.library.registries.reg_widget import WidgetRegistry

@library(
    label='My Complete Library',
    id='my_library',
    version='1.0.0',
    description='A full-featured example',
    dependencies=['haywire.core'],
    file_watcher=True,
    url='https://github.com/user/my-library',
    author='Your Name',
)
class Library(BaseLibrary):
    
    def register_components(self):
        base = Path(__file__).parent
        
        self.add_folder_to_registry(
            folder_path=str(base / 'nodes'),
            registry_cls=NodeRegistry
        )
        
        self.add_folder_to_registry(
            folder_path=str(base / 'widgets'),
            registry_cls=WidgetRegistry
        )
    
    def validate(self) -> bool:
        # Custom validation logic
        required_folders = ['nodes', 'widgets']
        base = Path(__file__).parent
        return all((base / folder).exists() for folder in required_folders)

__all__ = ['Library']
```

## Advanced Topics

### Custom Component Types

You can create custom registries for your own component types. See the technical documentation for details.

### Multiple Libraries Per Package

You can define multiple libraries in one package:

```toml
[project.entry-points."haywire.libraries"]
lib_a = "my_package.lib_a:Library"
lib_b = "my_package.lib_b:Library"
```

### Programmatic Configuration

If you need to configure the library system programmatically:

```python
from haywire.core.di.config import create_haywire_injector
from haywire.core.library.registries.reg_library import LibraryRegistry

injector = create_haywire_injector(
    library_paths=['/custom/path'],
    enable_file_watching=True
)

registry = injector.get(LibraryRegistry)
registry.load_core_libraries = True
registry.load_pip_packages = True
registry.scan_for_libraries()

service = injector.get(LibrarySystemService)
service.initialize()
```

## Getting Help

- **Documentation**: Check the Haywire docs
- **Examples**: Look at `libraries/example` in the Haywire repo
- **Issues**: Report bugs on GitHub
- **Discussions**: Ask questions in GitHub Discussions

## Reference

### @library Decorator Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `label` | str | Yes | - | Human-readable name |
| `id` | str | No | label | Unique identifier |
| `version` | str | No | '1.0.0' | Semantic version |
| `description` | str | No | '' | Library description |
| `dependencies` | list | No | [] | Required library IDs |
| `file_watcher` | bool | No | False | Enable hot-reload |
| `url` | str | No | '' | Library website |
| `help_url` | str | No | '' | Documentation URL |
| `author` | str | No | '' | Author name |
| `author_url` | str | No | '' | Author website |

### pyproject.toml Template

```toml
[project]
name = "haybale-{library-name}"
version = "{version}"
description = "{description}"
requires-python = ">=3.9"
authors = [{name = "{author}", email = "{email}"}]
license = {text = "MIT"}
readme = "README.md"

dependencies = [
    "haywire>=0.0.1",
]

[project.urls]
Homepage = "{url}"
Documentation = "{docs-url}"
Repository = "{repo-url}"

[project.entry-points."haywire.libraries"]
{library_id} = "{package_name}:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["{package_name}"]
```

### Useful Commands

```bash
# Package management
uv pip install haybale-my-library          # Install
uv pip install -e .                        # Editable install
uv pip uninstall haybale-my-library        # Uninstall
uv pip list                                # List installed
uv pip list --editable                     # List editable only
uv pip show haybale-my-library             # Show details

# Building
python -m build                            # Build package
python -m build --wheel                    # Build wheel only
python -m build --sdist                    # Build source dist only

# Publishing
python -m twine upload dist/*              # Upload to PyPI
python -m twine upload --repository testpypi dist/*  # Test PyPI

# Development
python -m pytest                           # Run tests
python -m pytest --cov                     # With coverage
python -m black .                          # Format code
python -m ruff check .                     # Lint code
```
