---
status: draft
doc_template: canonical-example
scope: Authoring a haybale — package layout, haybale.toml, the @library class, registries, hot-reload, compatibility warnings, the compliance contract
see-also:
  - ../reference/files/haybale-toml.md
  - ../reference/files/pyproject-toml.md
  - metadata-flow.md
  - ../architecture/library-system/library-system-arch.md
  - ../architecture/hot-reload/hot-reload-arch.md
  - marketplace/marketplace-canon.md
  - ../reference/glossary.md
---

# Haybale — Canonical Example

## 1. What it solves

A **haybale** is a Python package that contributes nodes, types, adapters,
widgets, skins, themes, settings, panels, editors, state and farmhands to a
running Haywire app. It declares an entry point under `haywire.libraries` and
contains exactly one `BaseLibrary` subclass decorated with `@library`.

The glossary lists **Library** (the class) and **Haybale package** (the
distribution) as meanings #1 and #3 of "library" — two views of one artifact,
and this page covers both. What they are *not*: the **Library System**, the
framework infrastructure that discovers and loads your class
([architecture/library-system](../architecture/library-system/library-system-arch.md)),
and the **Library Manager**, the in-app UI that installs it
([haybale/marketplace](marketplace/marketplace-canon.md)).

You package a haybale to distribute it on PyPI, share it by git URL, develop it
locally with hot-reload, or publish it through a marketstall that others
subscribe to.

## 2. Anatomy

```text
haybale-image/                  ← git repo / pip distribution name (hyphen)
├── pyproject.toml              ← dependencies, entry point, build config
├── README.md                   ← generated; NOT shipped in the wheel
└── haybale_image/              ← Python module (underscore)
    ├── __init__.py             ← @library + Library class + __all__
    ├── haybale.toml            ← all descriptive metadata
    ├── NOTES.md                ← hand-authored, ships in the wheel
    ├── OVERVIEW.md             ← generated, human-facing catalog
    ├── QUICKREF.md             ← generated, agent-facing index
    ├── docs/                   ← generated, one deep doc per component
    ├── nodes/
    ├── types/
    ├── adapters/
    ├── widgets/
    ├── skins/
    └── themes/
```

Omit any subfolder you do not use. The pip distribution name
(`haybale-image`) and the Python module name (`haybale_image`) are different
things — pip uses hyphens, Python imports use underscores, and the entry point
connects them.

### Three files, three jobs

| File | Holds | Edited by |
| --- | --- | --- |
| [`haybale.toml`](../reference/files/haybale-toml.md) | Everything descriptive: label, description, tags, os, paths, URLs, authors | You, or the studio's edit modal |
| [`pyproject.toml`](../reference/files/pyproject-toml.md) | `dependencies`, the entry point, build config. Its `[project]` block is generated | You (`dependencies` only) |
| `__init__.py` | The `Library` class; `@library(id=…)` | You |

The split is what makes a metadata edit cheap. `haybale.toml` ships **inside**
the package, so it reaches consumers in the wheel and is read from disk at the
point of use: editing it is a file write, visible on the next read, with no
`uv sync`, no reinstall, and no registry reload. `pyproject.toml` cannot do this
— it is not installed — which is why its descriptive fields are generated from
`haybale.toml` when you publish. See [ADR 0025](../adr/0025-haybale-toml-is-canon.md).

### How it is discovered

```text
Author writes                 pyproject.toml                Discovery
─────────────                 ──────────────                ─────────
haybale.toml            ┐     [project.entry-points         LibraryDiscovery scans
@library(id='image')    │      "haywire.libraries"]         installed packages at startup
class Library(...):     │     image = "haybale_image:Library"        ↓
  register_components() │                                   LibraryRegistry imports the
  validate()            ┘                                   module, instantiates Library,
                                                            calls register_components()
                                                                     ↓
                                                            Node / Type / Adapter / Widget /
                                                            Skin / Theme … registries fill;
                                                            nodes appear in the canvas menu.
```

**Boundaries.** What the registries do at runtime, how `InstallType` is
determined, and the discovery priority order — see
[architecture/library-system](../architecture/library-system/library-system-arch.md).
How metadata moves from your file to a consumer — see
[metadata-flow](metadata-flow.md).

## 3. `haybale.toml`

Beside `__init__.py`, inside the package:

```toml
name = "haybale-image"
id = "image"
label = "Image Processing"
description = "Image processing nodes for haywire — resize, filter, convert."
tags = ["image", "vision"]

# Empty or absent = every platform. The only field that blocks installation.
os = ["macos", "linux"]

# "none" (default) | "refresh" (reload the tab) | "restart" (restart the studio)
on_reload = "none"

# Sibling haybales whose classes you subscribe to, as MODULE names.
# Required for hot-reload: without it a subscriber holds a stale class
# reference after a reload. NOT [project] dependencies, which are pip packages.
linked_libraries = ["haybale_core"]

notes = "NOTES.md"             # one supplementary page, a bare filename here
examples_path = "examples/"    # relative to the PROJECT root, not this directory
tests_path = "tests/"

homepage_url = "https://github.com/you/haybale-image"
documentation_url = "https://you.github.io/haybale-image/"
issues_url = "https://github.com/you/haybale-image/issues"

[[authors]]
name = "Your Name"
url = "https://your.site"      # optional
```

The smallest valid file is four keys — `name`, `id`, `label`, and a
`description` worth reading. `id` is the only one whose absence is fatal.

**Written for you, not by you.** The share wizard writes `version`, `origin` and
`origin_provider`; the drift detector maintains `linked_libraries`. `name` and
`id` are immutable — they key saved graphs and every consumer's install spec.
`[deprecated]` is hand-edited, since retiring a library should not be one stray
click.

Every field, its type, and which files it reaches:
[reference/files/haybale.toml](../reference/files/haybale-toml.md).

## 4. The Library class

```python
# haybale_image/__init__.py
from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.node.registry import NodeRegistry


@library(id='image')
class Library(BaseLibrary):
    def register_components(self):
        self.add_folder_to_registry(
            folder_path=str(Path(__file__).parent / 'nodes'),
            registry_cls=NodeRegistry,
        )

    def validate(self) -> bool:
        return True


__all__ = ['Library']
```

**The decorator takes three arguments, and only three.** Everything descriptive
lives in `haybale.toml`; passing a descriptive field here raises `TypeError`
naming the file it moved to.

| Parameter | Required | Purpose |
| --- | --- | --- |
| `id` | yes | Prefixes every component's `registry_key`. Also in `haybale.toml`, which wins; a mismatch is reported rather than guessed at |
| `version` | no | Use `importlib.metadata.version("haybale-yourlib")`. Read from the distribution, never authored here |
| `file_watcher` | no | Hot-reload via filesystem observer. Development only; no publishing meaning |

**Always use parentheses.** `@library` without them is unsupported — as with
every component decorator (`@node()`, `@adapter()`, `@widget()`, …), even when
you pass no arguments.

**`register_components()`** calls `add_folder_to_registry()` once per category.
It scans the folder, imports each `.py` file, and lets the decorators
self-register; you never enumerate classes. The `exclude_patterns=['test_',
'__']` kwarg skips matching files.

**`validate() -> bool`** returns `False` to abort loading. Most libraries return
`True` unconditionally; use it for sanity checks like "the folder I need
exists".

**`__all__ = ['Library']`** exports the class so the entry point can find it.
The entry point names the **class**, not an instance — the framework
instantiates it.

### The eleven registries

| Registry class | Import path | Folder | Registers |
| --- | --- | --- | --- |
| `NodeRegistry` | `haywire.core.node.registry` | `nodes/` | `@node` classes |
| `TypeRegistry` | `haywire.core.types.registry` | `types/` | `@type` classes |
| `AdapterRegistry` | `haywire.core.adapter.registry` | `adapters/` | `@adapter` classes |
| `WidgetRegistry` | `haywire.ui.widget.registry` | `widgets/` | `@widget` classes |
| `SkinRegistry` | `haywire.ui.skin.registry` | `skins/` | skin classes |
| `ThemeRegistry` | `haywire.ui.themes.registry` | `themes/` | `WorkbenchTheme` / `NodeTheme` |
| `SettingsRegistry` | `haywire.core.settings.registry` | `settings/` | `@settings` classes |
| `LibraryStateRegistry` | `haywire.core.state` | `state/` | `AppState` / `SessionState` |
| `EditorTypeRegistry` | `haywire.ui.editor.registry` | `editors/` | `@editor` classes |
| `PanelRegistry` | `haywire.ui.panel.registry` | `panels/` | `@panel` classes |
| `FarmhandRegistry` | `haywire.core.farmhand` | `farmhands/` | MCP tool classes |

Most libraries need only the first six. **Scan `state/` first** when you
register it — farmhand and editor modules transitively import state classes, and
scanning state first keeps a single class object live.

## 5. Naming and versioning

Each of the four names has its own casing rule:

| Name | Convention | Example |
| --- | --- | --- |
| Pip distribution (`name`) | `haybale-<lowercase-hyphenated>` | `haybale-image-tools` |
| Python module | `haybale_<lowercase_underscored>` | `haybale_image_tools` |
| Library `id` | lowercase; the module name without `haybale_` | `image_tools` |
| Display `label` | Human-readable, title case | `"Image Tools"` |

The `haybale-` prefix is conventional, not required, but tools assume it.

**`id` is load-bearing and stable.** It becomes the prefix of every component's
`registry_key` — `image_tools:node:Resize`. Changing it after publishing orphans
every saved graph that references those keys, which is why it is immutable and
there is no supported rename path today.

**SemVer.** MAJOR for breaking changes (renamed nodes, changed port types,
removed components), MINOR for backward-compatible additions, PATCH for fixes.
You never keep the two copies in sync by hand: `haywire share` bumps
`haybale.toml`, generates `[project] version` from it, and tags `v<version>`.

## 6. Hot-reload

With `file_watcher=True`, the framework starts a `watchdog` observer rooted at
your library's source directory. On a `.py` change it re-imports the module,
re-runs the decorators against the same `registry_key`, rebuilds existing
wrappers from their recipes, and revalidates the graph. Editing `haybale.toml`
refreshes that library's identity without reloading any module.

Two switches must both be on: `file_watcher=True` on your decorator, and the
system-level `enable_file_watching` in `create_library_system_service()` (`True`
by default in `haywire-studio`).

It only works for **editable** installs (`uv pip install -e .`) or
folder-loaded libraries. A wheel unpacked into `site-packages` has no writable
source path for the watcher to observe.

Declare `linked_libraries` for every sibling haybale whose classes you subclass
or import. Without it, your library is outside the reload scope of the library
it depends on, and a subscriber holds a stale class reference after that library
reloads. The names are **module** names — a hyphen produces a scope matching
nothing, and is rejected at read time.

Full pipeline: [architecture/hot-reload](../architecture/hot-reload/hot-reload-arch.md).

## 7. Compatibility warnings

Advisory notices for users who open graphs saved by an older version of your
library. When a node's saved library version predates a behavioural change,
Haywire shows an amber badge on the affected nodes and a summary when the graph
opens. It never modifies the user's saved graph.

Override `compatibility_warnings()` to return an **append-only** history:

```python
from haywire.core.library.compatibility import CompatibilityWarning
from .nodes import FrameDisplayNode


class Library(BaseLibrary):
    def compatibility_warnings(self) -> list[CompatibilityWarning]:
        return [
            CompatibilityWarning(
                version="0.0.14",            # the version the change landed in
                component=FrameDisplayNode,  # a node class, or None for library-wide
                message="The 'frame' inlet widget strategy became author-declared; "
                        "graphs saved before 0.0.14 may hide the preview widget. "
                        "Reset the node to re-derive it from current code.",
            ),
        ]
```

- **`version`** is strict `MAJOR.MINOR.PATCH` — the version the change *landed
  in*. A graph saved *below* it triggers the warning. Malformed fails loudly at
  library load.
- **Always explicit, never derived** from your library's current version, which
  would re-date every entry on each release.
- **Append-only.** Never remove or re-date an entry; a graph saved at any past
  version must still trigger the right historical entries.
- **`component`** is a node class, a registry-key string, or `None` for a
  library-wide notice.

Distinct from `[deprecated]` in `haybale.toml`, which is library-wide, checked
against **installed libraries** rather than saved graphs, and says "stop using
this" rather than "this changed". See [ADR-0005](../adr/0005-compatibility-warnings.md).

## 8. Installing

| Command | Result | Hot-reload | Use when |
| --- | --- | --- | --- |
| `uv pip install -e /abs/path` | Editable — source stays on disk | yes | Local development |
| `uv pip install <name>` | Regular — copied into site-packages | no | Using a published library |
| `uv pip install git+https://…` | Regular — checked out into the pip cache | no | Installing from git |
| `uv pip install "<name> @ git+…#subdirectory=…"` | Regular — monorepo subdirectory | no | One repo, many haybales |

The studio's [library manager](marketplace/marketplace-canon.md) wraps these
behind a UI; users rarely run them directly.

## 9. Compliance contract

What a third-party haybale MUST satisfy to participate. Tooling-independent: any
author meeting it works with the shipped Library Manager and the marketstall
pipeline.

### Required

- **`pyproject.toml`** with `[project] name` (`haybale-*` by convention),
  `version`, `requires-python`, and a
  `[project.entry-points."haywire.libraries"]` entry resolving to a
  `BaseLibrary` subclass.
- **`haybale.toml`** inside the package, declaring at least `name`, `id` and
  `label`. Missing or malformed, that library alone fails to load and the error
  names the file.
- **`@library`** carrying only `id`, `version`, `file_watcher`.
- **For PyPI publishing**: a valid PyPI package (Trusted Publisher recommended).
- **For marketstall publishing**: a valid `marketstall.toml`.

A library meeting only this is installable, importable and resolvable. It may
render with minimal UI affordances.

### Recommended

- `haybale.toml` fields beyond the required three: `description`, `tags`,
  `linked_libraries`, `on_reload`, and the URL fields.
- **Generated documentation** via `haywire docs`.
- **Hand-authored `NOTES.md`** — your "what and why", which the generator
  prepends to `README.md`.
- **Semver discipline** — `>=X.Y.Z` constraints depend on it.

### Partial compliance

The Library Manager hints rather than gates: "No description provided", "No
tags", "No documentation available". A library with no recommended fields still
installs, enables and runs.

### Private repos

Subscribers configure their own git credentials. The Library Manager delegates
entirely to `uv pip install` and the underlying git client; any auth failure
surfaces as the raw clone error. Document required credentials in your
`NOTES.md`.

## 10. Documentation files

All except `NOTES.md` are produced deterministically by `haywire docs` — pure
extraction from identity fields, live instance introspection, and verbatim
docstrings. Never an agent, never inferred prose.

```sh
uv run haywire docs barn/haybale-foo   # one library
uv run haywire docs --all              # every in-repo library, one load
```

| File | Location | In wheel | Audience |
| --- | --- | :-: | --- |
| `README.md` | package root | | Pre-install discovery — PyPI, git platforms |
| `OVERVIEW.md` | module dir | ● | Humans — components by `label`, grouped by category |
| `QUICKREF.md` | module dir | ● | Agents — components by `registry_key`, with search tags |
| `docs/<key>.md` | module dir | ● | One deep doc per component, all 11 kinds |
| `NOTES.md` | module dir | ● | Hand-authored; never touched by the generator |

`README.md` is `NOTES.md` verbatim followed by the same catalog `OVERVIEW.md`
renders. It is the universal fallback: the PyPI JSON API returns it as
`info.description`, the only discovery path for a package with no git reference.

Each run ends with a coverage report naming components with no description or
docstring. The generator never fabricates missing prose — it flags the gap for
you to fill in the decorator or docstring, then re-run.

## 11. Live example

Source: `barn/haybale-testing/haybale_testing/__init__.py`
— the framework's own test library, and the most complete `Library` subclass in
the codebase. Pulled in live, so it cannot drift:

```python
--8<-- "barn/haybale-testing/haybale_testing/__init__.py:testing_library"
```

| Concept | Where |
| --- | --- |
| `@library(id=…, version=…, file_watcher=True)` | decoration |
| `BaseLibrary` subclass with both required hooks | `class Library(BaseLibrary)` |
| One `add_folder_to_registry` call per category | nine calls |
| State scanned before farmhands and editors | comment in `register_components` |
| `validate()` returning `True` | `def validate` |
| `__all__` exporting the class | last line |

---

## Quick reference

### Authoring checklist

- [ ] Distribution `haybale-<name>` (hyphen); module `haybale_<name>` (underscore)
- [ ] `haybale.toml` inside the package with `name`, `id`, `label`
- [ ] `@library(id='…')` — parens always; only `id` / `version` / `file_watcher`
- [ ] `Library(BaseLibrary)` in `__init__.py` implementing `register_components` and `validate`
- [ ] `__all__ = ['Library']`
- [ ] `[project.entry-points."haywire.libraries"]` pointing at `<module>:Library`
- [ ] `[tool.hatch.build.targets.wheel] packages = ["<module>"]`
- [ ] `dependencies` includes `haywire-core`
- [ ] `linked_libraries` lists sibling haybales, as module names
- [ ] Conventional subfolders for the categories you contribute

### Imports

```python
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.node.registry import NodeRegistry
from haywire.core.types.registry import TypeRegistry
from haywire.core.adapter.registry import AdapterRegistry
from haywire.ui.widget.registry import WidgetRegistry
from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.themes.registry import ThemeRegistry
```

### Commands

| Command | Does |
| --- | --- |
| `uv run haywire init my-project` | Scaffold a project with a starter haybale |
| `uv run haywire init my-project --dev` | Also register every dev-repo sibling as a project heap |
| `uv run haywire docs barn/haybale-mylib` | Generate docs for one library |
| `uv run haywire docs --all` | Generate docs for every in-repo library |
| `uv run haywire deps check` | Read-only drift check; exits 1 on drift. A PR gate |
| `uv run haywire share --bump patch` | Publish the whole project in lockstep |
| `uv run haywire share --dry-run` | Report what a publish would do; write nothing |

### Common pitfalls

| Pitfall | Why it matters |
| --- | --- |
| Bare `@library` without parens | Unsupported — always invoke with `()` |
| Passing `label`/`description`/`tags` to `@library(...)` | Raises `TypeError` — they live in `haybale.toml` |
| Shipping a wheel without `haybale.toml` | Read from disk at runtime; the library cannot load |
| Confusing `linked_libraries` with `[project] dependencies` | The first is hot-reload scope and module names; the second is pip requirements |
| Hyphens in `linked_libraries` | Produces a scope matching no module; rejected at read time |
| Changing `id` after publishing | Orphans saved graphs referencing `<old_id>:node:…` |
| `file_watcher=True` on a non-editable install | No effect — no watchable source |
| Hand-editing generated `[project]` fields | Preflight reports the drift; publishing overwrites them |
| Importing from `haywire.core.library.library` | Out of date — use `haywire.core.library.base` |
| Scanning `editors/` before `state/` | Editor modules import state classes; wrong order leaves stale objects |

---

## Troubleshooting

### Library not discovered

1. **Is the package installed?** `uv pip list | grep haybale-`
2. **Is the entry point registered?**

   ```sh
   python -c "from importlib.metadata import entry_points; print([ep.name for ep in entry_points(group='haywire.libraries')])"
   ```

   If your name is missing, the package was installed without entry-point
   metadata — reinstall it.
3. **Does the class load?** `python -c "from haybale_mylib import Library; print(Library.class_identity)"`
4. **Check startup logs** for `Failed to load entry point` or a
   `LibraryLoadError` — the latter means it was discovered but failed during
   `register_components()` or `validate()`.

### `HaybaleTomlError` at startup

The file is missing, malformed, or declares no `id`. It is fatal for that
library alone — the studio still starts and the error names the file. Check that
`haybale.toml` sits **inside** the package directory, beside `__init__.py`, and
that no `[tool.hatch.build.targets.wheel] include` excludes it.

### Hot-reload not working

1. Editable install? `uv pip list --editable | grep haybale-`
2. `file_watcher=True` on the decorator?
3. `enable_file_watching` on at the system level?
4. A syntax error in a reloaded module fails the reload silently, leaving the
   old class registered. Check the logs after saving.

### Editing the wrong copy

Check the **Source** path printed at startup. If it points into `site-packages`
rather than your checkout, you have both an editable and a regular install —
`uv pip uninstall` the regular one and re-install with `-e`.
