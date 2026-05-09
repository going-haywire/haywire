---
status: draft
doc_template: canonical-example
scope: Packaging a Haybale — pyproject.toml shape, folder layout, entry points, install/build/publish workflow
see-also:
  - ../libraries/library-canon.md
  - ../../architecture/library-system/library-system-arch.md
  - ../../architecture/library-manager/library-manager-arch.md
  - ../../reference/glossary.md
---

# Haybale Package — Canonical Example

## 1. What it solves

A **Haybale package** is the distribution unit of a haywire library — a Python package whose `pyproject.toml` declares an entry point under `haywire.libraries`, containing exactly one `BaseLibrary` subclass. It is meaning **#3** of the five "library" concepts in haywire (see [reference/glossary §Library — five distinct meanings](../../reference/glossary.md#library-five-distinct-meanings)).

You package a haybale when you want to:

- Distribute your library on PyPI (`uv pip install haybale-mylib`).
- Share it via a Git URL (`uv pip install git+https://...#subdirectory=...`).
- Develop it locally with hot-reload (`uv pip install -e .`).
- Publish it through a `marketplace.toml` feed for the studio's library manager.

The naming convention is **`haybale-<name>`** for the pip distribution and **`haybale_<name>`** for the Python module — the framework expects this prefix and the library manager UI surfaces it. The `haybale-` prefix is conventional, not required, but tools assume it.

## 2. How it fits

```text
Source layout                  pyproject.toml                 Distribution
─────────────                  ──────────────                 ────────────
haybale-mylib/                 [project]                      uv pip install:
  pyproject.toml               name = "haybale-mylib"           - editable: -e .
  README.md                    [project.entry-points.            (hot-reload)
  haybale_mylib/                "haywire.libraries"]             - regular: .
    __init__.py                mylib =                          - PyPI: package name
       @library(...)             "haybale_mylib:Library"        - git: URL
       class Library:                                            - subdir: URL#subdirectory=
                               [tool.hatch.build.targets.wheel]
    nodes/                     packages = ["haybale_mylib"]    haywire share — emits
    types/                                                       a marketplace.toml
    adapters/                                                    snippet for any of
    widgets/                                                     the four sources
    skins/                                                       above.
    themes/
```

The pip distribution name (`haybale-mylib`) and the Python module name (`haybale_mylib`) are *different things*. Pip uses hyphens, Python imports use underscores; the entry point connects them.

**Boundaries.** What `BaseLibrary`, `register_components()`, and `validate()` actually do — see [components/libraries](../libraries/library-canon.md). What `LibraryDiscovery` reads at runtime, the install-type rules, hot-reload mechanics — see [architecture/library-system](../../architecture/library-system/library-system-arch.md). The studio's library manager UI that consumes `marketplace.toml` and runs `uv pip install` — see [architecture/library-manager](../../architecture/library-manager/library-manager-arch.md).

## 3. Important concepts

**The conventional folder layout.** A haybale package has these subfolders, each scanned by the matching call in `register_components()`:

```text
haybale-mylib/                  ← git repo / pip distribution name
  pyproject.toml                ← entry point + build config
  README.md
  haybale_mylib/                ← Python module (note underscore)
    __init__.py                 ← @library + Library class + __all__ = ['Library']
    nodes/
    types/
    adapters/
    widgets/
    skins/
    themes/
```

You can omit any subfolder you don't use. The `Library.register_components()` method makes one `add_folder_to_registry()` call per category (see [components/libraries §4](../libraries/library-canon.md#4-live-example-from-the-codebase)).

**Two valid layouts: package or flat.** *Package* layout is what you want for any distributable library — `haybale-mylib/` contains a `pyproject.toml` and the Python module nested below it. *Flat* layout (the Python module sitting alone in a directory, no `pyproject.toml`) is only useful for ad-hoc libraries loaded via the framework's `library_paths` config — they get the `FOLDER` install type and skip the pip layer entirely. Use package layout unless you have a specific reason not to.

**The entry point is what makes the library discoverable.** In `pyproject.toml`:

```toml
[project.entry-points."haywire.libraries"]
mylib = "haybale_mylib:Library"
```

- The **key** (`mylib`) is the entry-point name. Its only job is to be unique within the entry-point group; it doesn't have to match the library `id`.
- The **value** (`haybale_mylib:Library`) is `<python_module>:<class_name>` — a dotted module path, a colon, then the attribute name to import.

When the framework runs `importlib.metadata.entry_points(group='haywire.libraries')`, every haybale package on the Python path appears.

**Multiple libraries per package** are supported by listing multiple entry points:

```toml
[project.entry-points."haywire.libraries"]
lib_a = "my_package.lib_a:Library"
lib_b = "my_package.lib_b:Library"
```

Each entry imports a different module/class pair from the same distribution.

**Four install types, three commands.** From the user's perspective:

| Install command | Result | Hot-reload? | Use when… |
|---|---|---|---|
| `uv pip install -e /abs/path` | Editable — symlink to source | Yes (with `file_watcher=True`) | Local development |
| `uv pip install <name>` | Regular — copied into `site-packages` | No | Production / using a published library |
| `uv pip install git+https://...` | Regular — checked out into pip cache | No | Installing from git without publishing |
| `uv pip install <name> @ git+...#subdirectory=...` | Regular — monorepo subdirectory | No | When one repo holds many haybales |

The studio's [library manager](../../architecture/library-manager/library-manager-arch.md) wraps these commands behind a UI; users rarely run them directly.

**Hot-reload requires editable install.** `file_watcher=True` only does something when the framework can find the live source directory. For pip-from-wheel (`REGULAR` install type), there is no source path to watch — the wheel is unpacked into `site-packages`. Editable installs (`EDITABLE`) and folder-loaded packages (`FOLDER`) both work.

**`marketplace.toml` is how libraries are listed for the studio.** A marketplace TOML file lists `[[packages]]` entries with metadata + an `install_spec` that gets passed verbatim to `uv pip install`. The Library Manager UI reads these feeds at startup and surfaces them as the "Available" list. Full coverage in [architecture/library-manager §2.2–2.5](../../architecture/library-manager/library-manager-arch.md#22-the-marketplacetoml-format).

**`haywire share`** generates a marketplace snippet for a published library:

```bash
uv run haywire share libs/haybale-mylib
```

It reads your `pyproject.toml`, detects the git remote, computes the `#subdirectory=` fragment, and prints a ready-to-paste `[[packages]]` block. SSH→HTTPS conversion is automatic.

**`haywire init`** scaffolds a new project with a starter haybale:

```bash
uv run haywire init my_project           # basic project marketplace
uv run haywire init my_project --dev     # dev marketplace including local libs
```

Creates `<project>/.haywire/marketplace.toml` and a `libs/haybale-<name>/` skeleton.

## 4. One comprehensive example

A complete haybale `haybale-image` exercising every packaging concept: package layout, entry point, build configuration, dependency declaration, all six conventional subfolders (the `Library` class lives in [components/libraries §4](../libraries/library-canon.md#4-live-example-from-the-codebase)), the README format the library manager renders, and a recommended `marketplace.toml` snippet for distribution.

### Folder layout

```text
haybale-image/
├── pyproject.toml
├── README.md
├── haybale_image/
│   ├── __init__.py              ← @library + Library class
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── resize_node.py
│   │   └── filter_node.py
│   ├── types/
│   │   ├── __init__.py
│   │   └── image_data.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── image_adapters.py
│   ├── widgets/
│   │   ├── __init__.py
│   │   └── image_preview_widget.py
│   ├── skins/
│   │   └── __init__.py
│   ├── themes/
│   │   └── __init__.py
│   └── settings.py              ← @settings(LibrarySettings) classes
└── tests/
    ├── conftest.py
    └── test_resize.py
```

### `pyproject.toml`

```toml
[project]
name = "haybale-image"
version = "1.0.0"
description = "Image processing nodes for haywire — resize, filter, format convert."
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [{name = "Author Name", email = "you@example.com"}]
keywords = ["haywire", "image", "vision"]

dependencies = [
    "haywire-core>=0.1.0",
    "numpy>=1.20.0",
    "pillow>=9.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "ruff>=0.1.0",
]

[project.urls]
Homepage = "https://github.com/me/haybale-image"
Repository = "https://github.com/me/haybale-image"
Documentation = "https://github.com/me/haybale-image/blob/main/README.md"

# ── This is the line that makes the library discoverable ──────────────
[project.entry-points."haywire.libraries"]
image = "haybale_image:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["haybale_image"]

[tool.hatch.build.targets.sdist]
include = [
    "haybale_image/",
    "README.md",
]
```

### `README.md` (rendered by the library manager Overview tab)

```markdown
# haybale-image

Image processing nodes for haywire — resize, filter, format convert.

## Installation

\`\`\`bash
uv pip install haybale-image
\`\`\`

## Nodes provided

- **Resize Image** — resize using nearest, bilinear, bicubic, or lanczos
- **Filter Image** — gaussian blur, sharpen, edge detect
- **Convert Format** — JPEG/PNG/WebP encoding

## Library settings

- `image_lib.jpeg_quality` — default JPEG quality (1–100)
- `image_lib.resize_algorithm` — default resize algorithm
- `image_lib.gpu_acceleration` — enable CUDA when available

## Development

\`\`\`bash
git clone https://github.com/me/haybale-image
cd haybale-image
uv pip install -e ".[dev]"
\`\`\`

Editable install enables hot-reload — edit `.py` files and the canvas
rebuilds nodes automatically.

## License

MIT
```

### Build, test, publish

```bash
# 1. Develop locally with hot-reload
cd haybale-image
uv pip install -e ".[dev]"

# 2. Run tests
uv run pytest

# 3. Build wheel + sdist
python -m build
# → dist/haybale_image-1.0.0-py3-none-any.whl
# → dist/haybale_image-1.0.0.tar.gz

# 4. Verify the built wheel installs cleanly
uv pip install dist/haybale_image-1.0.0-py3-none-any.whl

# 5. Publish to PyPI (after `uv pip install twine`)
python -m twine upload dist/*

# 6. Tag the release in git
git tag v1.0.0
git push origin v1.0.0
```

### Distribution via `marketplace.toml`

Generate a snippet with `haywire share`:

```bash
uv run haywire share libs/haybale-image
```

Output (ready to paste into any `marketplace.toml`):

```toml
[[packages]]
name         = "haybale-image"
version      = "1.0.0"
description  = "Image processing nodes for haywire — resize, filter, format convert."
author       = "Author Name"
source       = "git"
install_spec = "haybale-image @ git+https://github.com/me/haybale-image.git#subdirectory=libs/haybale-image"
tags         = ["image", "vision"]
source_url   = "https://github.com/me/haybale-image"
docs_url     = "https://raw.githubusercontent.com/me/haybale-image/main/libs/haybale-image/haybale_image/"
```

Or for a PyPI-published version:

```toml
[[packages]]
name         = "haybale-image"
version      = "1.0.0"
source       = "pypi"
install_spec = "haybale-image>=1.0.0"
docs_url     = ""   # falls back to PyPI long_description
```

What this example exercises:

| Concept | Where |
|---|---|
| Conventional package layout (`haybale-name/haybale_name/...`) | folder tree |
| `[project.entry-points."haywire.libraries"]` declaration | `pyproject.toml` |
| `[tool.hatch.build.targets.wheel]` packages list | `pyproject.toml` |
| Optional dev dependencies under `[project.optional-dependencies]` | `pyproject.toml` |
| `[project.urls]` populating the library manager UI | `pyproject.toml` |
| README format consumed by the library manager Overview tab | `README.md` |
| `uv pip install -e ".[dev]"` for editable + dev deps | build/test/publish workflow |
| `python -m build` + `python -m twine upload` for PyPI | build/test/publish workflow |
| `haywire share` generating a marketplace snippet | distribution |
| Both `source = "git"` (subdirectory) and `source = "pypi"` snippet variants | distribution |

For the `Library` class that lives in `__init__.py`, see [components/libraries](../libraries/library-canon.md). For the framework that loads your published package at app startup, see [architecture/library-system](../../architecture/library-system/library-system-arch.md). For the studio's library manager UI that consumes the marketplace snippet, see [architecture/library-manager](../../architecture/library-manager/library-manager-arch.md).

---

## Quick reference

### Packaging checklist

- [ ] Distribution name `haybale-<name>` (with hyphen)
- [ ] Python module name `haybale_<name>` (with underscore)
- [ ] `pyproject.toml` at the repo root
- [ ] `[project.entry-points."haywire.libraries"]` line referencing `<module>:Library`
- [ ] `[tool.hatch.build.targets.wheel]` listing the package
- [ ] `dependencies` includes `haywire-core` (or `haywire>=...`)
- [ ] README.md with installation + node list (used by Library Manager UI)
- [ ] `Library` class in `__init__.py` exporting via `__all__ = ['Library']`
- [ ] Conventional subfolders for the categories you contribute (`nodes/`, `types/`, etc.)

### Install commands by intent

```bash
# Local development (editable; hot-reload works)
uv pip install -e .

# From local wheel (regular)
uv pip install dist/haybale_mylib-1.0.0-py3-none-any.whl

# From PyPI (regular)
uv pip install haybale-mylib

# From git (whole repo)
uv pip install git+https://github.com/user/haybale-mylib.git

# From git (subdirectory of a monorepo)
uv pip install "haybale-mylib @ git+https://github.com/user/repo.git#subdirectory=libs/haybale-mylib"
```

### `haywire share` and `haywire init`

| Command | What it does |
|---|---|
| `uv run haywire share libs/haybale-mylib` | Generate a marketplace.toml snippet for a git-published library. Auto-detects remote, converts SSH→HTTPS, computes `#subdirectory=` |
| `uv run haywire init my_project` | Scaffold a new project with `<project>/.haywire/marketplace.toml` and `libs/haybale-<name>/` |
| `uv run haywire init my_project --dev` | Same, but the marketplace lists every haybale in the local dev repo with `source="local"` |

### Common pitfalls

| Pitfall | Why it matters |
|---|---|
| Using `_` in the pip distribution name | Convention is hyphen for distribution, underscore for module |
| Entry point pointing to the wrong attribute (`Library` vs the class name) | Discovery silently skips the library |
| Bumping `version=` in `@library(...)` but not in `pyproject.toml` (or vice versa) | Confusing reports in the library manager UI |
| Committing a `source = "local"` marketplace entry to a shared repo | Path is machine-specific; breaks for everyone else |
