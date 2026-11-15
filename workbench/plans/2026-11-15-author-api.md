# Author API: a declared public import path for library authors

Status: design settled 2026-11-15 (design session, Q1–Q9), nothing built.
Open: the three names marked "decide" in [Names to decide](#names-to-decide),
presented at the start of slice 1.

## Why

Libraries import from wherever a symbol lives. Once third parties write
libraries, every move or rename inside haywire-core breaks them. This is the
second finding of the pre-release architecture review (2026-11-10); the first
(graph files froze class facts) is fixed by graph format v5 (ADRs 0076–0078).

## Measured (master ec268a49c, 2026-11-15)

Regex over `from/import haywire...`; names by AST.

| Set | Distinct paths | Imports | 4+ levels deep |
|---|---|---|---|
| In-repo `barn/` | 193 | 1610 | 1083 |
| haybale-visiongraph + haybale-spandrel | 31 | 118 | 82 |
| All | 194 | 1728 | 1165 |

- 546 distinct names are imported. Two collide as different objects under one
  name (`get_settings_registry`, `CanvasSettings`); neither is a
  component-author name. 39 names arrive through more than one path.
- The two external libraries use 58 names. The seven node-authoring libraries
  (core, audio, image, example, models, visiongraph, spandrel) use 153 in
  total: 117 from component-tier modules, 36 from workbench-tier modules.
- `haybale-graph-editor` uses 273 names from 103 modules, `haybale-studio` 152
  from 86. The five workbench libraries make about 1340 of the 1610 in-repo
  imports.
- Six underscore-prefixed names are imported across package boundaries.
- 39 package `__init__.py` files carry `__all__`; they mix author names with
  engine internals (`BaseNode` beside `NodeWrapper`, `ExecutionContext` beside
  `HaywireVM`) and libraries bypass them (`ExecutionContext` 86 times by its
  deep path).
- `import haywire.core.node` already loads `haywire.ui` and NiceGUI. The tiers
  below differ in promise, not in import cost.
- All 194 imported modules load in one process. Imported first in a fresh
  interpreter, 93 of the 94 modules the non-workbench libraries use load;
  `haywire.core.edge.edge_wrapper` fails on a cycle that exists today
  (`edge_wrapper → graph → validation → types → port → edge_wrapper`).

## Decisions

| # | Question | Decision |
|---|---|---|
| Q1 | Who the promise is made to | Libraries released separately from core. Every in-repo library still moves onto the Author API, because its code is example code. The five workbench libraries (graph-editor, studio, haystack, marketplace, share) keep an allowlist of internals that a test lets shrink and never grow. |
| Q2 | One promise or tiers | Two tiers. The workbench tier is provisional. |
| Q3 | Library-to-library imports (`haybale_image`, `haybale_models`, `haybale_core`) | Out of scope; follow-up. The marking is chosen so a haybale can adopt it unchanged. |
| Q4 | Where it lives | `haywire.api` (component tier) and `haywire.api.workbench` (workbench tier). Flat modules of re-exports. |
| Q5 | How "not public" is marked | By rule (not importable from the two modules = internal) plus enforcement in this repository. |
| Q6 | What gets in | A name enters only if a library uses it and the docs teach it. Each used-but-undocumented name gets one decision. |
| Q7 | Migration | Modules first, then docs, then libraries one PR at a time with the lint switched on per library. |
| Q8 | Promise | A deprecation window from the first release. |
| Q9 | Deprecation notice | Python `DeprecationWarning`, recorded by the library loader into the error ledger. |

## Design

### The two modules

```
packages/haywire-core/src/haywire/api/__init__.py     component API
packages/haywire-core/src/haywire/api/workbench.py    workbench API (provisional)
```

- Both hold imports and an explicit `__all__`, no logic. `__all__` is what the
  snapshot test and mypy's re-export check read.
- `haywire/__init__.py` stays empty: Python runs it on every
  `import haywire.x`, core's own imports included.
- Import direction, one way: `haywire.api.workbench → haywire.api →
  core / ui / barn.builtin`. Nothing in `core`, `ui` or `barn.builtin` imports
  `haywire.api`.
- One exception: node templates under `barn/builtin/nodes/templates/` import
  `haywire.api`, because the New Node wizard copies them into authors'
  libraries. Safe because templates are loaded by the folder scan at
  registration, never by a module `haywire.api` imports.
- The module fixes the import order in one place, so the `edge_wrapper` cycle
  cannot be reached by an author ordering imports differently.
- A re-exported class is the same object as the original: framework classes are
  never hot-reloaded (builtin has `file_watcher=False`).

A node file's header becomes:

```python
from haywire.api import BaseNode, NodeType, node, ExecutionContext, FLOAT, NumberWidget
```

### What each tier holds

| Tier | Module | Holds | Size of the first cut |
|---|---|---|---|
| Component API | `haywire.api` | node, type, adapter, widget, skin, theme, settings, the library class and its registries, `ExecutionContext`, compatibility warnings, volumes, catalog, the builtin types (34), widgets (18) and wires | 95 names used by node-authoring libraries and documented, plus the decisions below |
| Workbench API | `haywire.api.workbench` | panel, editor, surface, session, signals, access, state, farmhand, modals, `hui` (`haywire.ui.elements`) | 30 names used by node-authoring libraries and documented, plus the decisions below |

Whole-block rule: everything in `haywire.barn.builtin.types.__all__` and
`haywire.barn.builtin.widgets.__all__` enters the component API together, so a
builtin type or widget is never half public.

### Not public

Anything not importable from `haywire.api` or `haywire.api.workbench` carries
no promise. The existing package `__all__` lists stay as internal convenience.
No runtime check and no renaming of internals: an internal import breaks
nothing, so the framework does not refuse it (design principles).

### Enforcement in this repository

Both mechanisms exist already; nothing new is introduced.

1. **Lint.** ruff `TID251` banned-api entries for `haywire.core`, `haywire.ui`
   and `haywire.barn`, switched on per library under `barn/**` as each one
   migrates. Same mechanism as the dependency-direction rule in
   `pyproject.toml`. A second entry bans `haywire.api` inside `packages/**`
   except the templates folder.
2. **Allowlist test.** One AST test (pattern: `tests/marketstall/test_layering.py`)
   holds, per workbench library, the internal `(module, name)` pairs it still
   imports. It fails when a pair is added and when a listed pair is no longer
   used, so the list only shrinks.
3. **Snapshot test.** The sorted `__all__` of both modules is compared with a
   checked-in list. Removing or renaming a name fails until the list is edited,
   which shows the break in review. The test also asserts every name resolves
   and that no name is exported by both modules as different objects.
4. **Scaffold default.** `haywire init` writes the same banned-api lines into
   the new project's ruff config. A third-party author can remove them; for
   them the marking is the rule and the promise.

### Promise

- **Component API.** A name is removed or changed incompatibly only after at
  least one minor release in which it was deprecated, never in a patch release.
  From 1.0 on, only in a major release.
- **Workbench API.** May change in any minor release, listed in the release
  notes, never in a patch release. It stays provisional until a library outside
  this repository has built an editor on it.
- **Covered:** the name is importable; its documented signatures, hooks and
  behaviour hold.
- **Not covered:** underscore members, undocumented attributes, anything
  outside the two modules.

### Deprecation

1. The deprecated name leaves `__all__` and is served by a module `__getattr__`
   in `haywire/api/__init__.py` (pattern: `haywire_studio/__init__.py`) that
   raises a `DeprecationWarning` naming the replacement and the release that
   removes it.
2. The library loader records warnings around its two import sites
   (`core/registry/folder_scan.py:128`, `core/library/registry.py:525`) and
   writes each as a `WARNING` entry to the error ledger with the library
   identity and module name (`report_failure`). It fires again on hot reload,
   because the reload re-executes the module.
3. The snapshot keeps a second list, "deprecated", so a deprecated name cannot
   vanish before its window ends.

To verify while building: `warnings.catch_warnings` changes process-global
state. If library imports can run off the main thread while another thread
imports, record through a filter installed once instead.

## Names to decide

Used by a node-authoring library, not mentioned in `docs/` (ADRs excluded).
Each needs: document and export, or keep internal and rewrite the user.

### Component tier

| Name | From | Used by | Lean |
|---|---|---|---|
| `CatalogEntry`, `ModelFile` | `core.catalog` | models | export, document in the catalog page |
| `CarrierValue` | `barn.builtin.carrier` | image | export, document (ADR 0075) |
| `fields_to_text`, `fields_from_text` | `barn.builtin.field_text` | image | export with `CarrierValue` |
| `ProgressSpan` | `barn.builtin.progress` | core | export with `ProgressSettings` |
| `SwitchWidget` | `barn.builtin.widgets` | example, testing | export (whole-block rule) |
| `element_from_dict` | `core.types.fields` | core, example | export, document in the datatype canon |
| `volume_name` | `core.volumes` | core, studio | export |
| `declaring_type_of` | `core.types.wire` | core | decide |
| `SKIN_TAG_SPECIAL`, `SKIN_TAG_STAGE_ONLY`, `SKIN_TAG_WIDGET_NODE` | `core.skin.tags` | core | export, document in the skin canon |
| `BUTTON_WIDGET`, `SWITCH_WIDGET`, `NUMBER_WIDGET`, `SLIDER_WIDGET`, `TEXT_WIDGET` | `barn.builtin.widget_keys` | core | export as a block |
| `FONTS`, `FONT_STACKS` | `core.skin.fonts` | core | decide |
| `H_ALIGNS` | `barn.builtin.nodes.annotation` | core | internal; move the constant to where both can reach it |
| `console_print` | `ui.console_bridge` | core | decide |

### Workbench tier

| Name | From | Used by | Lean |
|---|---|---|---|
| `set_hover_tip` | `ui.hover_tip` | graph-editor, models | export |
| `resolve_tier` | `core.access.resolver` | models | export |
| `MENU_CARD_CLASS` | `ui.elements.flyout` | models | internal; reach it through `hui` |
| `get_library_state_container`, `activity_tracker`, `get_catalog_registry` | `core.di.context` | models, haystack, studio | export (D1) |

The leans stand unless the maintainer changes one. The three rows marked
"decide" (`declaring_type_of`, `FONTS` / `FONT_STACKS`, `console_print`) are
presented to the maintainer as the first task of slice 1, each with what it
does, who calls it and the cost of either answer.

## Further decisions (2026-11-15)

| # | Question | Decision |
|---|---|---|
| D1 | Ambient accessors in `haywire.core.di.context` (16 imports) | The accessor functions libraries use are exported through the workbench API. The injector and its configuration stay internal. |
| D2 | Names only workbench libraries use (164 occur somewhere in the docs: 90 from component-tier modules, 74 from workbench-tier modules) | Decided per library in slice 5. Such a name enters the workbench API only if a canon or guide under `docs/components/` or `docs/guides/` teaches it to authors; otherwise it goes on the allowlist. |
| D3 | `haybale-testing` and `haybale-TEST_A` (sole non-workbench users of 24 names) | They get an allowlist like the workbench libraries: a test library reaches into internals on purpose. |

## Slices

Each is one PR, green on its own. No version changes. The old deep paths keep
working throughout, because no internal moves.

| # | Slice | Contents |
|---|---|---|
| 1 | The modules | `haywire/api/__init__.py`, `haywire/api/workbench.py` with the first cut; snapshot test; the `packages/**` lint entry; decisions from the tables above; ADRs and glossary terms |
| 2 | What authors read | node, haybale, datatype, settings, widget, adapter, skin, theme, panel, editor and farmhand canons and guides; the Data node template; the `haywire init` scaffold and its ruff lines; rebake the Farmhand docs |
| 3 | Deprecation path | module `__getattr__`, loader recording, ledger entry, tests. May merge into slice 1 if small |
| 4 | Node-authoring libraries | example, audio, image, core, models: codemod, then lint on for each. One PR per library |
| 5 | Workbench libraries | haystack, share, marketplace, studio, graph-editor: codemod, allowlist test, lint on with the allowlist as the only exception. One PR per library. Applies D2 |
| 6 | Test libraries | testing, TEST_A, with their allowlist (D3) |
| 7 | External libraries | visiongraph, spandrel, after the core release that ships slice 1; raise their `haywire-core` floor to that release |

The last task of each slice marks it done here (commit, date, deviations).

| Slice | Status |
|---|---|
| 1–7 | not started |

## Lands with the code

**Glossary** (`docs/reference/glossary.md`):

- **Author API**: the names a library may import with a compatibility promise;
  the two modules together. Avoid: "API surface", "public surface" ("surface"
  means a **Surface**).
- **Component API**: `haywire.api`.
- **Workbench API**: `haywire.api.workbench`; provisional.
- **Internal**: importable, not in the Author API, no promise.
- **Workbench library**: one of the five in-repo libraries that build the
  studio's workbench and ship in lockstep with core.
- Amend the "component overloaded" entry, which calls the registry meaning
  "public API".

**ADRs** (numbers assigned when written; 0083 is taken by the proposal in PR #105):

- "A library imports the framework through the Author API": Q1, Q2, Q4, Q5, Q6
  and the template exception.
- "A name leaves the Author API through a deprecation window": Q8, Q9.

## Not in this design

- Moving or renaming any internal module, or fixing the `edge_wrapper` cycle.
- A package split of haywire-core.
- A public import path for one haybale used by another (Q3).
- From the review, after this: identity aliases for renamed or moved node
  classes and a port-level "formerly"; authored `migrate()`; settings rename and
  retype handling.
