# Haywire Node System

Haywire is a Blueprint-inspired visual programming system that combines **execution flow** with **data flow** in a dual-flow architecture. Unlike pure dataflow systems, it uses explicit control connections to define execution order while maintaining data connections for value passing.

Created by Martin Froehlich (aka maybites), released under [CC-BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/4.0/). (c) 2025

Notable open source projects with similar goals but different use cases:

* [Floppy](https://github.com/JLuebben/Floppy) — Python
* [Box](https://github.com/p-ranav/box) — Python
* [CablesGL](https://cables.gl/) — JavaScript

---

## For Users

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager

### Create a New Project

```sh
# Scaffold a new haywire project (no permanent install needed)
uvx haywire-app init my-project

# Enter the project and install dependencies
cd my-project
uv sync

# Launch the editor
uv run haywire
```

This creates the following project structure:

```
my-project/
├── pyproject.toml              # project manifest (dependencies, workspace config)
├── uv.lock                     # pinned dependency versions
├── .haywire/                   # project settings
│   ├── marketplace.toml        # marketplace library sources (cincluding the local one)
│   └── config.toml
├── graphs/                     # saved graphs
└── libs/
    └── haybale-my-project/     # your local node library (auto-scaffolded)
        ├── pyproject.toml
        └── haybale_my_project/
            ├── __init__.py     # library registration
            └── nodes/          # add your custom nodes here
```

### Managing Libraries

From within the running app, navigate to **Libraries** (button in the header, or go to `http://localhost:8082/libraries`) to:

- Browse available haybale libraries from the marketplace
- Install / uninstall libraries
- Enable / disable installed libraries

Libraries are installed into your project's virtual environment — nothing is shared globally.

### Sharing a Library

If you've built custom nodes in your project's local library and want to share them, use `haywire share` to generate a marketplace snippet that others can paste into their `marketplace.toml`:

```sh
cd my-project
uv run haywire share
```

This reads the library's `pyproject.toml` metadata and detects the git remote URL to produce a ready-to-use entry:

```toml
# Copy this snippet into a marketplace.toml:

[[packages]]
name = "haybale-my-project"
version = "0.1.0"
description = "Local library for my-project"
author = "Your Name"
source = "git"
install_spec = "haybale-my-project @ git+https://github.com/you/my-project.git#subdirectory=libs/haybale-my-project"
tags = []
```

Recipients paste this into their `.haywire/marketplace.toml` and install the library from the Library Manager UI. Works with any git host (GitHub, GitLab, Bitbucket, etc.) and automatically converts SSH remote URLs to HTTPS.

### Global Configuration

User-level settings are stored in `~/.haywire/`:

```
~/.haywire/
├── config.toml             # default theme, preferences
├── marketplace.toml        # marketplace source URLs
└── recent_projects.toml    # recently opened projects
```

### For Developers

the following will create a new project in /tmp/myTestProject with the haybale-myTestProject library scaffolded inside it:

´´´
cd /tmp
uv run --project <absolute filepath to this repo folder> haywire init myTestProject --dev
´´´
---

## For Developers

### Repository Structure

Haywire is organized as a **uv workspace monorepo**:

```
haywire-repo/
├── pyproject.toml                  # workspace root (not a package itself)
├── uv.lock
├── tests/                          # framework tests
├── playground/                     # scratch scripts and experiments
├── docs/
├── scripts/
├── saves/
│
├── packages/
│   ├── haywire-framework/          # core framework (publishable to PyPI)
│   │   ├── pyproject.toml
│   │   └── src/haywire/
│   │       ├── core/               # graph engine, DI, nodes, edges, ports
│   │       │   ├── node/           # node architecture and base classes
│   │       │   ├── graph/          # graph structures and validation
│   │       │   ├── library/        # library discovery and registration
│   │       │   ├── data/           # data types, specs, enums
│   │       │   ├── adapter/        # external system adapters
│   │       │   ├── settings/       # TOML-based settings system
│   │       │   ├── execution/      # interpreter and flow execution
│   │       │   └── di/             # dependency injection (injector)
│   │       ├── ui/                 # NiceGUI user interface
│   │       │   ├── editor/         # graph editor components
│   │       │   ├── pan_zoom/       # canvas navigation
│   │       │   ├── themes/         # TOML theme system
│   │       │   ├── renderer/       # node renderers
│   │       │   └── widget/         # UI widgets
│   │       └── undo/               # undo/redo system
│   │
│   └── haywire-app/                # application (publishable to PyPI)
│       ├── pyproject.toml          # CLI entry point: haywire
│       └── src/haywire_app/
│           ├── app.py              # main application
│           ├── init.py             # haywire init command
│           ├── share.py            # haywire share command
│           ├── config.py           # global/project config
│           ├── library_manager.py  # runtime library management
│           └── library_manager_ui.py # library management UI
│
└── libraries/                      # haybale plugin libraries
    ├── haybale-core/               # standard types, nodes, widgets, renderers
    ├── haybale-example/            # example library
    ├── haybale-testing/            # test nodes for development
    ├── haybale-visiongraph/        # vision/camera nodes
    └── haybale-TEST_A/             # test library
```

### Setup

```sh
git clone <repository-url>
cd haywire-repo
uv sync
```

All workspace packages are installed as editable — changes take effect immediately.

### Running

```sh
# Launch the app
uv run haywire

# Run tests
uv run pytest

# Run with module syntax
uv run python -m haywire_app

# Playground scripts still work
uv run python playground/app_graph_canvas.py
```

### Key Architecture Concepts

- **Dual-flow model**: Control pins define execution order; data pins pass values
- **Node types**: DATA, CONTROL, EVENT, OUTPUT, LOOPBACK — determined by control port configuration
- **Library system**: Plugin libraries discovered via `haywire.libraries` entry points, with hot-reload for editable installs
- **DI container**: `injector` library manages registries, factories, and services
- **Edge lifecycle**: Three-tier (`link`, `unlink`, `detach`) with two-tier port storage (`_linked_edges` + `_all_edges`)
- **Lazy propagation**: Per-edge `is_lazy` flag; dirty model defers `on_change` to execution time

### Creating a Library

Each haybale library follows this pattern:

```python
# haybale_mylib/__init__.py
from pathlib import Path
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.node.registry import NodeRegistry

@library(
    label='My Library',
    id='mylib',
    version='1.0.0',
    file_watcher=True,  # enable hot-reload
)
class Library(BaseLibrary):
    def register_components(self):
        base_path = Path(__file__).parent
        self.add_folder_to_registry(
            folder_path=str(base_path / 'nodes'),
            registry_cls=NodeRegistry,
        )

    def validate(self) -> bool:
        return True
```

Register it via entry point in `pyproject.toml`:

```toml
[project.entry-points."haywire.libraries"]
mylib = "haybale_mylib:Library"
```

### Testing

```sh
uv run pytest                    # all tests
uv run pytest tests/ -k "edge"   # filtered
uv run pytest --cov              # with coverage
```

### Code Quality

```sh
uv run ruff check .              # lint (line-length = 109)
uv run mypy .                    # type checking
```

### Development Notes

- VS Code: add `code` to PATH for source-link navigation (Cmd+Shift+P > "Shell Command: Install 'code' command in PATH")
- `create_node_wrapper()` leaves pending `NODE_ADDED` in the dirty queue — tests must call `force_immediate_validation()` after setup
- Build individual packages: `uv build --package haywire-framework`
