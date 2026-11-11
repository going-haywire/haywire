# Haywire Node System

[![PyPI version](https://img.shields.io/pypi/v/haywire-studio?label=pypi)](https://pypi.org/project/haywire-studio/)
[![Tests](https://github.com/going-haywire/haywire/actions/workflows/publish.yml/badge.svg)](https://github.com/going-haywire/haywire/actions/workflows/publish.yml)
[![ruff](https://github.com/going-haywire/haywire/actions/workflows/ruff.yml/badge.svg?branch=master)](https://github.com/going-haywire/haywire/actions/workflows/ruff.yml)
[![mypy](https://github.com/going-haywire/haywire/actions/workflows/mypy.yml/badge.svg?branch=master)](https://github.com/going-haywire/haywire/actions/workflows/mypy.yml)
[![ty](https://github.com/going-haywire/haywire/actions/workflows/ty.yml/badge.svg?branch=master)](https://github.com/going-haywire/haywire/actions/workflows/ty.yml)

Haywire is a Blueprint-inspired visual programming system that combines **execution flow** with **data flow** in a dual-flow architecture. Unlike pure dataflow systems, it uses explicit control connections to define execution order while maintaining data connections for value passing.

**Documentation:** <https://going-haywire.github.io/haywire/docs/>

---

## For Users

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager (it downloads Python 3.12+ for you if you don't have one)
- [git](https://git-scm.com/) (for version control and sharing projects)

### Create a New Project

Scaffold a new haywire project (installs haywire from PyPI, runs uv sync). The project comes with the essential libraries preinstalled (`haybale-core`, `haybale-graph-editor`, `haybale-haystack`, plus the studio and marketplace libraries), so you can start patching right away.

This command creates a project folder named 'my-project':
```sh
uvx --python 3.12 --from haywire-studio haywire init my-project
```

change into new directory:
```sh
cd my-project
```

Launch the editor:
```sh
uv run haywire
```

The folder has the following project structure:

```text
my-project/
├── readme.md                   # project readme
├── pyproject.toml              # project manifest (dependencies, workspace config)
├── uv.lock                     # pinned dependency versions
├── .haywire/                   # project settings
│   ├── marketplace.toml        # marketplace library sources (cincluding the local one)
│   └── config.toml
├── graphs/                     # saved graphs
└── barn/
    └── haybale-my-project/     # your local node library (auto-scaffolded)
        ├── pyproject.toml
        └── haybale_my_project/
            ├── __init__.py     # library registration
            └── nodes/          # add your custom nodes here
```

### Managing Libraries

From within the haywire studio app, navigate to **marketplace** (icon in the left action bar):

- Browse available haybale libraries from the marketplace
- Install / uninstall libraries
- Enable / disable installed libraries

Libraries are installed into your project's virtual environment — nothing is shared globally.

### Sharing a Project

Publish your project's libraries with `haywire share`. See the
[sharing guide](https://going-haywire.github.io/haywire/docs/guides/sharing-libraries/).

### Global Configuration

User-level settings are stored in `~/.haywire/`:

```text
~/.haywire/
├── config.toml             # default theme, preferences
├── marketplace.toml        # marketplace source URLs
└── recent_projects.toml    # recently opened projects
```

---

## For Developers

Repository layout, setup, running, testing and the docs workflow are in
[Developing Haywire](https://going-haywire.github.io/haywire/docs/guides/development/).
