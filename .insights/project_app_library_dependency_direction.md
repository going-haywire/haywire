---
name: App/library dependency direction
description: Barn libraries depend on haywire-core and may depend on the app package haywire-studio; the app must NEVER depend on a barn library, which would close a package cycle. Only a library can register components, so app-owned state needing a panel or tool is imported "up" by a library. Declare in pyproject.toml only — never in haybale.toml's linked_libraries.
type: project
---

**Barn libraries depend on the core and may depend on the app package. The app package must never depend on a barn library.**

`haybale-* → haywire-studio → haywire-core`, one direction, always. The reverse
edge looks harmless in a pyproject and is not: combined with the forward edge it
is a package cycle, and uv/pip will happily lock one until something needs to
resolve the two independently.

## Why libraries reach "up" into the app (and the core)

It reads backwards — a *plugin* depending on the *application* — but it is
forced by two facts that are not going to change soon:

1. **Only a library can register components.** Panels, nodes, widgets, skins,
   editors and farmhands enter their registries exclusively through
   `BaseLibrary.add_folder_to_registry`, called from `register_components()`.
   Every library lives under `barn/` or in `haywire.barn.builtin`.
2. **The app package declares no library of its own.** `haywire_studio` has no
   `@library` class, so there is nowhere inside it that a component can be
   declared.

So whenever the app *owns* some state and that state *needs a UI surface or a
tool*, the component must live in a barn library and import upward. That is the
sanctioned shape, not a smell. `FrameworkSettings`' own docstring blesses the
ownership half of it: settings may be "defined in haywire-core **or
haywire-studio**".

If you find yourself wanting to put a panel in `packages/haywire-studio/`, that
is the signal you've hit this rule — put it in a barn library and import the
app-owned thing.

## Declaring the dependency

`pyproject.toml` **only**.

Do NOT add `haywire_studio` to `haybale.toml`'s `linked_libraries`. That field
is scoped to *registered haywire libraries* — it exists so hot-reload can track
stale class references across sibling haybales. `haywire-studio` registers
nothing, so it has no reload scope to track.
`packages/haywire-core/src/haywire/core/library/dep_detect.py` has an explicit
branch for this, naming `import haywire_studio` as a framework dist that belongs
in pyproject alone. `haywire deps check` enforces it: a `linked_libraries` entry
here is wrong, not merely redundant.

See [project_library_dependencies_use_package_names.md](project_library_dependencies_use_package_names.md)
for the module-name-vs-dist-name trap on that field.

## Guaranteeing baseline presence

Since the app cannot depend on the libraries it needs to be useful, "this
install has a working studio" is guaranteed by the **project scaffold**, not by
packaging: `_generate_project_pyproject()` in
`packages/haywire-studio/src/haywire_studio/init.py` writes `haybale-studio`
(and `haybale-marketplace`) into every generated project. Pinned by
`TestProjectPyproject::test_studio_baseline_dependency`.

Consequence, accepted: a bare `pip install haywire-studio` with no scaffold has
no settings panels and no `studio_*` MCP tools.

## Worked example — the cycle that existed

`NetworkSettingsPanel` in
`barn/haybale-studio/haybale_studio/panels/properties/setting/app.py` renders
`FarmhandSettings` and `NetworkSettings` (MCP enable/auth, studio port/loopback)
— app-owned settings, consumed by `haywire_studio/app.py` and
`haywire_studio/farmhand/host.py`. Only a library can host a panel, so the panel
sits in `haybale-studio` and imports up. Correct by the rule above.

The bug was the *other* edge: `haywire-studio`'s pyproject listed
`haybale-studio`, added in `5340fc61` to make the nine `studio_*` farmhand tools
"packaging-enforced". That plus the panel's import formed the cycle. The
undeclared upward import also showed as a DEP003 finding, which made the
upward arrow look like the problem — it wasn't.

Resolution: delete the app→library edge, declare the library→app edge in
pyproject, move baseline presence into the scaffold. The panel's local
(in-method) import became a plain top-of-file import once the dependency was
honest.
