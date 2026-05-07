# Library Management System

This document covers the full lifecycle of Haywire libraries: how they are discovered at runtime,
how users install and publish them, how marketplace feeds are configured, and how documentation
is attached to each library.

---

## Table of Contents

1. [Architecture overview](#1-architecture-overview)
2. [Library discovery at runtime](#2-library-discovery-at-runtime)
3. [Install types and their differences](#3-install-types-and-their-differences)
4. [The marketplace.toml format](#4-the-marketplacetoml-format)
5. [Where marketplace files live and when they are created](#5-where-marketplace-files-live-and-when-they-are-created)
6. [Multi-source marketplace feeds](#6-multi-source-marketplace-feeds)
7. [Publishing a library](#7-publishing-a-library)
8. [Creating library documentation](#8-creating-library-documentation)
9. [Files and their roles](#9-files-and-their-roles)
10. [How source types differ](#10-how-source-types-differ)

---

## 1. Architecture overview

The library management system has three distinct layers that work together.

```text
┌─────────────────────────────────────────────────────────────┐
│  Layer 1 — Package layer  (uv / pip)                        │
│  Installs Python distributions into the virtual environment  │
│  and writes entry points to site-packages metadata.         │
└──────────────────────────┬──────────────────────────────────┘
                           │ importlib.metadata.entry_points()
┌──────────────────────────▼──────────────────────────────────┐
│  Layer 2 — Registry layer  (haywire-core)              │
│  LibraryRegistry scans entry points, loads Library classes, │
│  and populates NodeRegistry / WidgetRegistry / etc.         │
└──────────────────────────┬──────────────────────────────────┘
                           │ LibraryManager wraps both layers
┌──────────────────────────▼──────────────────────────────────┐
│  Layer 3 — UI layer  (haywire-app)                          │
│  Library Manager page lets users browse, install, enable,   │
│  disable, and uninstall libraries at runtime.               │
└─────────────────────────────────────────────────────────────┘
```

### Key classes and files

| Class / file | Location | Role |
| --- | --- | --- |
| `LibraryRegistry` | `haywire/core/library/registries/reg_library.py` | Discovers and loads libraries |
| `LibraryDiscovery` | `haywire/core/library/discovery.py` | Reads `haywire.libraries` entry points |
| `LibraryManager` | `haywire_app/library_manager.py` | Orchestrates uv + registry |
| `LibraryManagerPage` | `haywire_app/library_manager_ui.py` | NiceGUI UI at `/libraries` |
| `config.py` | `haywire_app/config.py` | Global + project config read/write |
| `init.py` | `haywire_app/init.py` | `haywire init` project scaffolding |
| `share.py` | `haywire_app/share.py` | `haywire share` snippet generator |

---

## 2. Library discovery at runtime

### Entry points

Every haybale library declares itself via a Python entry point in its `pyproject.toml`:

```toml
[project.entry-points."haywire.libraries"]
visiongraph = "haybale_visiongraph:Library"
```

The key on the left (`visiongraph`) becomes the **library ID** used throughout the system.
The value on the right is a dotted import path pointing to the `Library` class.

At startup, `LibraryRegistry.scan_for_libraries()` calls:

```python
importlib.metadata.entry_points(group='haywire.libraries')
```

This returns every entry point registered under that group across all installed packages.

### Priority order

When multiple sources provide a library with the same ID, the first one found wins:

| Priority | Source | Description |
| --- | --- | --- |
| 1 | Core libraries | Bundled with `haywire-core` (not user-facing) |
| 2 | Regular pip installs | Packages in site-packages |
| 3 | Editable pip installs | `pip install -e` pointing to source directories |
| 4 | Folder paths | Extra directories added via `library_paths` config |

### What happens after discovery

For each discovered library:

1. The `Library` class is loaded and its `@library(...)` decorator metadata is read.
2. `Library.register_components()` is called, which scans the `nodes/`, `widgets/`,
   `types/`, `adapters/`, and `renderers/` subfolders.
3. Each decorated class (`@node`, `@widget`, `@type`, etc.) is registered in the
   corresponding global registry (`NodeRegistry`, `WidgetRegistry`, …).
4. If `file_watcher=True` in the `@library(...)` decorator, a filesystem watcher is
   started on the source directory for hot-reload.

### Install type detection

`LibraryDiscovery` inspects the filesystem location of each entry point to classify how
the library was installed:

| `InstallType` | Value | How detected | Hot-reload |
| --- | --- | --- | --- |
| `REGULAR` | `"regular"` | Location is inside `site-packages` | No |
| `EDITABLE` | `"editable"` | Location is a path in the source tree (`.pth` file) | Yes |
| `FOLDER` | `"folder"` | Added via `library_paths` config, not an entry point | Yes |

The install type controls whether the **Uninstall** and **Save source** actions are
available in the Library Manager UI.

---

## 3. Install types and their differences

### Local folder (editable, via `uv pip install -e`)

The library source lives on the local filesystem and is installed in editable mode.
Python resolves imports directly from the source directory.

```text
myproject/
└── libs/
    └── haybale-mylib/
        ├── pyproject.toml
        └── haybale_mylib/
            ├── __init__.py   ← Library class
            ├── nodes/
            └── widgets/
```

When `LibraryManager.install("/abs/path/to/haybale-mylib")` is called, it runs:

```sh
uv pip install -e /abs/path/to/haybale-mylib
```

This registers the entry point and adds a `.pth` file so Python finds the source.
Changes to `.py` files inside the library take effect immediately (or after hot-reload
if `file_watcher=True`).

**Uninstall:** `uv pip uninstall haybale-mylib`

### PyPI package

A published package installed by name:

```sh
uv pip install haybale-visiongraph
```

Files land in `site-packages`. No live editing. Hot-reload is not available.

**Uninstall:** `uv pip uninstall haybale-visiongraph`

### Git repository (whole repo)

A package hosted in a Git repository, installed directly from the URL:

```toml
install_spec = "git+https://github.com/user/repo.git"
```

Runs:

```sh
uv pip install git+https://github.com/user/repo.git
```

The source is checked out into a local cache; it is treated the same as a regular pip
install (no hot-reload, no editable save).

### Git repository (subdirectory)

When a single Git repository contains multiple libraries, the `#subdirectory=` fragment
points `pip` at the right one:

```toml
install_spec = "haybale-visiongraph @ git+https://github.com/user/repo.git#subdirectory=libraries/haybale-visiongraph"
```

This is the format generated by `haywire share` when the library lives inside a
monorepo. The `#subdirectory=` path must point to the folder that contains
`pyproject.toml`.

### Comparison table

| Feature | Local editable | PyPI | Git (whole) | Git (subdir) |
| --- | --- | --- | --- | --- |
| `source` field in marketplace.toml | `"local"` | `"pypi"` | `"git"` | `"git"` |
| Requires network at install | No | Yes | Yes | Yes |
| Hot-reload | Yes (if `file_watcher=True`) | No | No | No |
| Save source in UI | Yes | No | No | No |
| Version pinning | Not applicable | `name==1.0.0` | `url@tag` | `url@tag#subdir=…` |
| `haywire share` generates it | Yes | No | Yes | Yes |
| Uninstall via UI | Yes | Yes | Yes | Yes |

---

## 4. The `marketplace.toml` format

A marketplace file is a TOML file with a `[[packages]]` array. Each entry describes
one installable library.

### Minimal entry

```toml
[[packages]]
name        = "haybale-visiongraph"
version     = "0.0.1"
description = "Camera, video, and OpenCV nodes"
author      = "Florian Bruggisser, Martin Froehlich"
source      = "git"
install_spec = "haybale-visiongraph @ git+https://github.com/user/repo.git#subdirectory=libraries/haybale-visiongraph"
tags        = ["vision", "camera", "video", "opencv"]
source_url  = "https://github.com/user/repo"
docs_url    = "https://raw.githubusercontent.com/user/repo/main/libraries/haybale-visiongraph/haybale_visiongraph/"
```

### Full field reference

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Pip distribution name (e.g. `haybale-visiongraph`) |
| `version` | string | Yes | Current version string, for display only |
| `description` | string | No | One-line human-readable description |
| `author` | string | No | Author name(s) |
| `source` | string | Yes | One of `"pypi"`, `"git"`, `"local"` |
| `install_spec` | string | Yes | Passed verbatim to `uv pip install` |
| `tags` | list of strings | No | Filter tags shown in the Library Manager |
| `source_url` | string | No | URL to the library's repository homepage |
| `docs_url` | string | No | URL or local path to the documentation directory |

### `source` values explained

**`"pypi"`** — Install by package name from the Python Package Index:

```toml
source       = "pypi"
install_spec = "haybale-visiongraph>=0.2.0"
```

**`"git"`** — Install from a Git URL:

```toml
source       = "git"
install_spec = "haybale-visiongraph @ git+https://github.com/user/repo.git#subdirectory=libraries/haybale-visiongraph"
```

**`"local"`** — Install from a local directory (editable):

```toml
source       = "local"
install_spec = "/abs/path/to/haybale-mylib"
```

Local entries are generated by `haywire init --dev` and are machine-specific. Do not
commit them to a shared marketplace.

### `docs_url` — local paths and remote URLs

`docs_url` can be either a remote URL or a local filesystem path.

**Remote URL (GitHub raw content):**

```toml
docs_url = "https://raw.githubusercontent.com/user/repo/main/libraries/haybale-visiongraph/haybale_visiongraph/"
```

If the URL ends with `/`, the Library Manager appends `OVERVIEW.md` and then
`QUICKREF.md` until one succeeds.
If the URL ends with `.md`, it is fetched directly.

**Local filesystem path (directory):**

```toml
docs_url = "/abs/path/to/haybale-visiongraph/haybale_visiongraph"
```

The Library Manager looks for `OVERVIEW.md`, then `QUICKREF.md` inside that directory.

**Local filesystem path (file):**

```toml
docs_url = "/abs/path/to/OVERVIEW.md"
```

The file is read directly.

`haywire share` writes a GitHub raw URL for hosted libraries.
`haywire init --dev` writes a local path for libraries in the dev repo.

---

## 5. Where marketplace files live and when they are created

### Project marketplace — `<project>/.haywire/marketplace.toml`

**Path:** `<workspace_root>/.haywire/marketplace.toml`

This is the primary marketplace for a Haywire project. It is read first by the Library
Manager. Entries here are labelled **"project"** in the UI.

**Created by:** `haywire init` — always, regardless of `--dev`.

- **Without `--dev`:** `_generate_project_marketplace()` writes a minimal file
  containing only the project's own scaffolded library (`libs/haybale-{name}`) with
  `source = "local"`, plus comment lines explaining the format. This gives the user
  a working template to extend.
- **With `--dev`:** `_generate_dev_marketplace()` writes the project's own library
  first, followed by all libraries found in the haywire dev repo, all with
  `source = "local"` and `docs_url` pointing to the local module directory.

**When not present:** The Library Manager shows the Available section as empty (no
error). To make libraries appear there, create the file and add `[[packages]]` entries,
or add a remote feed to `~/.haywire/marketplace.toml`.

**How the UI opens it:** The edit button next to a library's "Feed:" row opens the
project marketplace in an inline TOML editor dialog. Saving refreshes the Available
list immediately.

### Global marketplace — `~/.haywire/marketplace.toml`

**Path:** `~/.haywire/marketplace.toml`

Contains `[[sources]]` entries that point to additional marketplace files. The sources
are fetched at Library Manager startup.

**Created by:** `ensure_global_config()`, which is called by `haywire init` and on
first application launch.

**Default contents:**

```toml
[[sources]]
# No entries by default. Add remote marketplace URLs here.
# name  = "official"
# url   = "https://haywire.dev/marketplace.toml"
```

**Structure:**

```toml
[[sources]]
name = "my-team"
url  = "https://example.com/haywire/marketplace.toml"

[[sources]]
name = "official"
url  = "https://haywire.dev/marketplace.toml"
```

Each `url` must point to a file with the same `[[packages]]` format. The Library
Manager fetches them asynchronously at page load and labels each entry with the source
name. Remote entries can be installed but cannot be edited in the UI (the local
`~/.haywire/marketplace.toml` that references them is what gets edited).

### How the UI loads marketplace entries

```text
Library Manager page load
  │
  ├── 1. Project marketplace  (<workspace>/.haywire/marketplace.toml)
  │       Loaded synchronously; entries labelled source_label="project"
  │
  ├── 2. Global local sources  (~/.haywire/marketplace.toml, source.url is a local file)
  │       Loaded synchronously; entries labelled with source.name
  │
  └── 3. Global remote sources  (source.url starts with "http")
          Fetched asynchronously (asyncio.ensure_future);
          entries appended to _extra_marketplace_entries and left panel refreshed
```

---

## 6. Multi-source marketplace feeds

The `[[sources]]` mechanism in `~/.haywire/marketplace.toml` allows multiple curated
feeds to contribute to the same Available list.

### Adding a remote feed

Edit `~/.haywire/marketplace.toml` (click the edit button next to any remote entry's
"Feed:" label in the Library Manager, or open the file directly):

```toml
[[sources]]
name = "my-team"
url  = "https://intranet.example.com/haywire/marketplace.toml"

[[sources]]
name = "official"
url  = "https://haywire.dev/marketplace.toml"
```

### Source attribution in the UI

Each entry in the Available list shows:

```text
source_label  [version]
Library Name
```

In the center panel a "Feed:" row shows:

- For project entries: `Feed: ~/.haywire/marketplace.toml → https://...` with an edit
  button that opens `~/.haywire/marketplace.toml` (not the remote file).
- For project-local entries: `Feed: <project>/.haywire/marketplace.toml` with an edit
  button for the project file.

Clicking the edit button opens an inline TOML editor. Saving the file clears the
remote cache and re-fetches all sources.

---

## 7. Publishing a library

### Step 1 — Structure the library correctly

A haybale library must be a Python package with:

1. **`pyproject.toml`** declaring the `haywire.libraries` entry point.
2. **`__init__.py`** containing a `@library(...)` decorated `Library` class.
3. Subfolders for components: `nodes/`, `widgets/`, `types/`, `adapters/`, `renderers/`.

Minimal `pyproject.toml`:

```toml
[project]
name    = "haybale-mylib"
version = "0.1.0"
description = "My custom Haywire library"
requires-python = ">=3.10"
dependencies = ["haywire-core>=0.1.0"]

[project.entry-points."haywire.libraries"]
mylib = "haybale_mylib:Library"

[build-system]
requires      = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["haybale_mylib"]
```

Minimal `haybale_mylib/__init__.py`:

```python
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.node.registry import NodeRegistry

@library(
    label='My Library',
    id='mylib',
    version='0.1.0',
    description='My custom nodes',
    file_watcher=True,
)
class Library(BaseLibrary):
    def register_components(self):
        from pathlib import Path
        self.add_folder_to_registry(
            folder_path=str(Path(__file__).parent / 'nodes'),
            registry_cls=NodeRegistry,
        )
    def validate(self) -> bool:
        return True
```

`haywire init` scaffolds this structure automatically (see §5).

### Step 2 — Install it locally for development

From the project root:

```bash
uv pip install -e libs/haybale-mylib
```

Or use the Library Manager UI: add a `source = "local"` entry in the project
marketplace and click Install from the Available section.

After install, the Library Manager shows it in the **Enabled** section with install
type badge `editable`. Source files can be edited directly and changes hot-reload.

### Step 3 — Generate documentation

Invoke the `/docs` skill inside a Claude Code session. The skill is defined at
`.claude/skills/docs/` in the haywire dev repo and is therefore available to anyone
who has cloned that repo. It is not shipped with the published `haywire-app` package.

Claude Code loads skills from two places:

- **Project level:** `.claude/skills/` in the current repo (travels with the repo via git)
- **Personal level:** `~/.claude/skills/` (available across all your projects)

There is no standalone CLI command for generating docs — it is a Claude Code skill only.
This generates:

- **`OVERVIEW.md`** at the library root — discovery tier, one bullet per component.
- **`QUICKREF.md`** at the library root — compact reference, alphabetical.
- **`docs/nodes/<ClassName>.md`** — per-node documentation with ports table.
- **`docs/widgets/<ClassName>.md`** — per-widget documentation with config options.

See §8 for details.

### Step 4 — Publish to Git and generate a marketplace snippet

Commit the library to a Git repository (or push an existing local repository). Then:

```bash
# From the project root (auto-detects if one library in libs/)
uv run haywire share

# Or specify a path explicitly
uv run haywire share libs/haybale-mylib
```

`share` reads `pyproject.toml`, detects the git remote, and prints a ready-to-paste
`[[packages]]` block:

```toml
[[packages]]
name         = "haybale-mylib"
version      = "0.1.0"
description  = "My custom nodes"
author       = "Your Name"
source       = "git"
install_spec = "haybale-mylib @ git+https://github.com/user/repo.git#subdirectory=libs/haybale-mylib"
tags         = []
source_url   = "https://github.com/user/repo"
docs_url     = "https://raw.githubusercontent.com/user/repo/main/libs/haybale-mylib/haybale_mylib/"
```

`share` handles:

- **SSH → HTTPS conversion** (`git@github.com:user/repo` → `https://github.com/user/repo`)
- **Subdirectory fragment** (`#subdirectory=libs/haybale-mylib`) computed from the
  library's path relative to the git root.
- **`docs_url`** computed as the GitHub raw content URL pointing to the Python package
  directory (where `OVERVIEW.md` lives). Also supports GitLab raw URLs.
- **`source_url`** the clean repository homepage URL.

Paste the snippet into any marketplace.toml — your project's, your team's, or the
official one.

### Step 5 — Publish to PyPI (optional)

```bash
uv build
uv publish
```

Then update the marketplace entry:

```toml
[[packages]]
name         = "haybale-mylib"
version      = "0.1.0"
source       = "pypi"
install_spec = "haybale-mylib>=0.1.0"
```

---

## 8. Creating library documentation

Documentation is generated by the `/docs` skill (see `.claude/skills/docs/`). It is
designed to be regenerated at any time and is idempotent — only files whose source has
changed are rewritten.

### Output files

| File | Location | When generated | Content |
| --- | --- | --- | --- |
| `OVERVIEW.md` | Library root | Always (full overwrite) | Component index grouped by menu category |
| `QUICKREF.md` | Library root | Always (full overwrite) | Compact key-value reference, alphabetical |
| `docs/nodes/<ClassName>.md` | Library root | Only if source hash changed | Port table, dynamic port behaviour, description |
| `docs/widgets/<ClassName>.md` | Library root | Only if source hash changed | Config options, example usage |

### How the Library Manager reads documentation

#### Installed library — Overview tab

Reads `<source_path>/OVERVIEW.md` directly from the filesystem (no network needed).
`source_path` is the `location` field from the entry point, i.e. the root of the
library package directory.

#### Installed library — Nodes / Widgets tab → click a component → Docs tab

Reads `<source_path>/docs/nodes/<ClassName>.md` or
`<source_path>/docs/widgets/<ClassName>.md`.

#### Marketplace / Available library — center panel overview

The `docs_url` field in the marketplace entry is used. Priority:

1. If `docs_url` is a **local directory path** → read `OVERVIEW.md` or `QUICKREF.md`
   from that directory.
2. If `docs_url` is a **local file path** → read it directly.
3. If `docs_url` starts with `http` → fetch the URL (appending `/OVERVIEW.md` if it
   ends with `/`).
4. If `docs_url` is empty → heuristic GitHub raw URL derived from `source_url` /
   `install_spec`, trying `main` then `master` branches.
5. If all else fails → PyPI `long_description` fallback (for `source = "pypi"`).

### Source code viewer

In the right panel's **Source** tab, the Library Manager uses `inspect.getfile(cls)`
to locate the exact `.py` file for the selected component and displays it in a
CodeMirror editor with Python syntax highlighting (`vscodeDark` theme).

For **editable** libraries, a **Save** button writes changes back to the source file.
The file watcher then picks up the change and hot-reloads the library within ~0.5 s.

---

## 9. Files and their roles

### Application-level files

```text
packages/haywire-app/src/haywire_app/
├── app.py                  # Registers /libraries page; initialises LibraryManager
├── library_manager.py      # LibraryManager + MarketplaceEntry + InstalledLibrary
├── library_manager_ui.py   # NiceGUI 3-panel Library Manager page (/libraries)
├── config.py               # Read/write ~/.haywire/ and <project>/.haywire/
├── init.py                 # `haywire init` scaffolding (creates project skeleton)
└── share.py                # `haywire share` (generates marketplace.toml snippet)
```

### Per-project files

```text
<project>/
├── pyproject.toml          # uv workspace root, members = ["libs/*"]
├── .haywire/
│   ├── config.toml         # Project config (disabled library IDs, etc.)
│   └── marketplace.toml    # Project-local library feed  ← primary marketplace
├── graphs/                 # Saved graph files
└── libs/
    └── haybale-<name>/     # Auto-scaffolded local library
        ├── pyproject.toml
        └── haybale_<name>/
            ├── __init__.py
            ├── nodes/
            ├── widgets/
            ├── types/
            ├── adapters/
            └── renderers/
```

### Global user files

```text
~/.haywire/
├── config.toml             # Global preferences (theme, etc.)
├── marketplace.toml        # [[sources]] list of remote marketplace URLs
└── recent_projects.toml    # MRU project list
```

### Library package files

```text
<library-root>/
├── pyproject.toml          # entry-points."haywire.libraries" declaration
├── OVERVIEW.md             # Generated by /docs — component index
├── QUICKREF.md             # Generated by /docs — compact reference
├── LIBRARY_EXTRA.md        # Hand-authored notes (never overwritten by /docs)
└── <module_name>/          # Python package (haybale_visiongraph, haybale_core, …)
    ├── __init__.py         # @library(...) decorated Library class
    ├── nodes/              # @node decorated classes
    ├── widgets/            # @widget decorated classes
    ├── types/              # @type decorated classes
    ├── adapters/           # adapter classes
    ├── renderers/          # @renderer decorated classes
    └── docs/
        ├── nodes/
        │   └── <ClassName>.md   # Generated per-node docs
        └── widgets/
            └── <ClassName>.md   # Generated per-widget docs
```

---

## 10. How source types differ

### Installation command

| Source | Command run by `LibraryManager.install()` |
| --- | --- |
| Local path | `uv pip install -e /abs/path` |
| PyPI | `uv pip install haybale-lib>=1.0.0` |
| Git | `uv pip install git+https://github.com/u/r.git` |
| Git subdir | `uv pip install name @ git+https://...#subdirectory=path` |

### Runtime behaviour

The table below covers **installed** libraries (Enabled / Disabled sections).
For **Available** (pre-install) entries the Library Manager always uses `docs_url`
to fetch documentation regardless of source type — see §8.

`OVERVIEW.md`, `QUICKREF.md`, and the `docs/` folder all live **inside the Python
module directory** (e.g. `haybale_visiongraph/OVERVIEW.md`,
`haybale_visiongraph/docs/nodes/`). Because hatchling's `packages = ["haybale_visiongraph"]`
includes all files (not just `.py`), they are shipped in the wheel and are therefore
available in `site-packages` for regular and git installs too — provided the author
ran `/docs` before publishing.

| Feature | Local editable | PyPI | Git | Git subdir |
| --- | --- | --- | --- | --- |
| `install_type` | `EDITABLE` | `REGULAR` | `REGULAR` | `REGULAR` |
| Source path resolves to | Source directory | `site-packages/<module>` | `site-packages/<module>` | `site-packages/<module>` |
| `OVERVIEW.md` (installed, Overview tab) | Yes — from source dir | Yes — shipped in wheel | Yes — shipped in wheel | Yes — shipped in wheel |
| `OVERVIEW.md` (Available, pre-install) | Via `docs_url` | Via `docs_url` | Via `docs_url` | Via `docs_url` |
| Per-component docs (installed) | Yes — from source dir | Yes — shipped in wheel | Yes — shipped in wheel | Yes — shipped in wheel |
| Source viewer | Yes | Yes (read-only) | Yes (read-only) | Yes (read-only) |
| Save source | Yes | No | No | No |
| Hot-reload | Yes (file watcher) | No | No | No |
| Disable/Enable | Yes | Yes | Yes | Yes |
| Uninstall via UI | Yes | Yes | Yes | Yes |

### Version pinning

**PyPI** — append `==version` to the name:

```toml
install_spec = "haybale-visiongraph==0.2.0"
```

The Library Manager version picker calls the PyPI JSON API to list available versions.

**Git** — append `@tag` before any `#` fragment:

```toml
install_spec = "name @ git+https://github.com/u/r.git@v0.2.0#subdirectory=path"
```

The Library Manager version picker calls the GitHub Tags API to list tags.

**Local** — version pinning is not applicable; the installed version is always the
current state of the source directory.

### `docs_url` population

| Who sets it | Value |
| --- | --- |
| `haywire share` (Git remote found) | GitHub/GitLab raw content URL pointing to module directory |
| `haywire share` (no remote) | Placeholder `https://<REPO_URL>.git#subdirectory=…` |
| `haywire init --dev` | Local filesystem path to module directory |
| Hand-authored marketplace entry | Whatever the author puts in |

### What `haywire share` generates vs what `haywire init --dev` generates

`haywire share` targets **distribution** — it produces a snippet that any other user
can paste into their `marketplace.toml` to install the library from Git. It always
generates a `source = "git"` entry with a full GitHub URL.

`haywire init --dev` targets **development** — it produces a `marketplace.toml` for
the scaffolded project that lists libraries in the local dev repo with
`source = "local"` pointing to absolute paths. These paths are machine-specific and
should not be shared.
