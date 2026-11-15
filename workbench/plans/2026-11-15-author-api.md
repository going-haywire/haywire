# Author API: a declared public import path for library authors

Status: design settled 2026-11-15 (design session, Q1–Q9). Slices 1, 3 and 4
are built and slice 2 is built in part (see [Slices](#slices)); the names are
decided ([Names decided](#names-decided)). Next: the rest of slice 2, then
slice 5.

## Picking this up

Branch `refactor-API-surface`, draft PR
[#108](https://github.com/going-haywire/haywire/pull/108) (plan and slices 1–4).

- **The name lists** are in the appendix
  [2026-11-15-author-api-names.md](2026-11-15-author-api-names.md): the first
  cut of each tier, the names to decide, and what only test or workbench
  libraries use. Regenerate it after any change to a library's imports:
  `python3 workbench/playground/author_api_names.py <path to haybale-visiongraph> <path to haybale-spandrel>`
  (the two external checkouts are optional arguments; without them their names
  drop out). Its "documented" test is a word match over `docs/`, so read each
  first-cut name once before exporting it.
- **The codemod** is `workbench/playground/author_api_codemod.py`:
  `.venv/bin/python workbench/playground/author_api_codemod.py [--write] <dir> ...`
  rewrites the imports of every `.py` and `.md` file under a directory and
  lists the names the Author API lacks. Each listed name needs a decision
  (export and document, or rewrite the user); adding a name needs an edit to
  `tests/api/names.py`. Afterwards run `ruff format`, and re-check every
  line-range snippet (`--8<-- "path:a:b"`) in `docs/` that points into a
  changed file: the import lines shrink, so the ranges move.
- **Next steps:** the rest of slice 2 (see its status row), then slice 5 one
  library at a time: run the codemod, decide the leftovers under D2, remove
  the library's line from `barn/ruff.toml` or write its allowlist.
- **Each slice gets its own detailed plan** in `workbench/plans/` before code;
  this file is the design, not a task list.
- **Patterns to copy,** all named again where they apply below:
  `pyproject.toml` `[tool.ruff.lint.flake8-tidy-imports.banned-api]` (lint),
  `tests/marketstall/test_layering.py` (AST test),
  `packages/haywire-studio/src/haywire_studio/__init__.py` (module
  `__getattr__`), `core/errors/boundary.py` `report_failure` (ledger entry).
- **Do not reopen** Q1–Q9 and D1–D3.

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
   migrates. ruff holds one banned list per configuration file, and the root
   one is taken by the dependency-direction rule for `packages/**`, so the
   library rule lives in `barn/ruff.toml`, which extends the root file. Its
   per-file-ignores name the libraries not yet migrated; the list only
   shrinks. A second entry, in the root file, bans `haywire.api` inside
   `packages/**` except the module itself and the templates folder.
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

## Names decided

Used by a node-authoring library, not mentioned in `docs/` (ADRs excluded).
Each was decided: document and export, or keep internal and rewrite the user.
The maintainer left the three open rows to the implementer (2026-11-15); the
"Decision" column is what slice 1 built. Documenting the exported ones is
slice 2; rewriting the users is slice 4.

### Component tier

| Name | From | Used by | Decision |
|---|---|---|---|
| `CatalogEntry`, `ModelFile` | `core.catalog` | models | export, document in the catalog page |
| `CarrierValue` | `barn.builtin.carrier` | image | export, document (ADR 0075) |
| `fields_to_text`, `fields_from_text` | `barn.builtin.field_text` | image | export with `CarrierValue` |
| `ProgressSpan` | `barn.builtin.progress` | core | export with `ProgressSettings` |
| `SwitchWidget` | `barn.builtin.widgets` | example, testing | export (whole-block rule) |
| `element_from_dict` | `core.types.fields` | core, example | export, document in the datatype canon |
| `volume_name` | `core.volumes` | core, studio | export |
| `declaring_type_of` | `core.types.wire` | core | export, document in the datatype canon: a container type (array, drain, pooled) written outside core needs it to give its ports the element type's wire |
| `SKIN_TAG_SPECIAL`, `SKIN_TAG_STAGE_ONLY`, `SKIN_TAG_WIDGET_NODE` | `core.skin.tags` | core | export all five tags as a block, with `skin_choices` (the skin canon teaches it) |
| `_widget_node_stage_skin_choices` | `core.skin.settings` | core | renamed `widget_node_stage_skin_choices` and exported: a third-party widget node offers the same skin list |
| `BUTTON_WIDGET`, `SWITCH_WIDGET`, `NUMBER_WIDGET`, `SLIDER_WIDGET`, `TEXT_WIDGET` | `barn.builtin.widget_keys` | core | export all 17 keys as a block (tested like types and widgets) |
| `FONTS`, `FONT_STACKS` | `core.skin.fonts` | core | export: a skin that styles text offers the same choices as the annotation and the widget nodes, and they are four strings and a dict that rarely change |
| `H_ALIGNS` | `barn.builtin.nodes.annotation` | core | moved with `V_ALIGNS` to `core.skin.fonts` beside `FONTS`, and exported with them as the text style choices |
| `console_print` | `ui.console_bridge` | core | internal: its body is `print(*args, **kwargs)`, and the studio log already shows `print()`. The Print node calls `print()` (slice 4) |
| `WIDGET_REGISTRY` | `ui.widget.globals` | core | internal (it was in the first cut by a loose word match): export `get_widget_class()`, which the widget canon teaches; `array_widget` calls it (slice 4) |
| `Event` | `core.types.event` | core | export: it is the type of `DataField.on_changed`, and a widget that hands its rows a field of their own (`array_widget`) builds one |
| `WireType`, `EdgeSettings`, `NO_HEAD`, `dash_choices` | `core.types`, `core.settings`, `core.edge` | testing | export: the setting canon teaches a custom wire with them |
| `theme`, `BaseTheme`, `watch` | `ui.themes`, `core.settings` | studio, testing | exported now: the theme and settings canons teach them to authors |

### Workbench tier

| Name | From | Used by | Decision |
|---|---|---|---|
| `set_hover_tip` | `ui.hover_tip` | graph-editor, models | export |
| `resolve_tier` | `core.access.resolver` | models | export |
| `MENU_CARD_CLASS` | `ui.elements.flyout` | models | internal; `hui.menu()` is a `ui.menu` carrying the class |
| `Surface`, `AppSettings`, `CanvasSettings`, `ExecutionInspector` | `ui.surface`, `barn.builtin.surfaces` | graph-editor, studio, haystack | export (D2): the panel canon teaches them. `CanvasSettings` is the surface; the settings class of the same name stays internal |
| `redraw_on`, `reveal_on`, `signal_field`, `EditorCommand`, `RevealSignal`, the observation, reveal and close signals, the eight keyboard commands | `core.session`, `core.signals` | workbench libraries | export (D2): the editor canon and the signals guide teach them |
| `LibraryState`, `SessionState`, `OpenBehavior`, `truncation_note` | `core.state`, `ui.editor`, `core.farmhand` | workbench libraries | export (D2): the state, editor and farmhand canons teach them |
| `get_library_state_container`, `activity_tracker`, `get_catalog_registry` | `core.di.context` | models, haystack, studio | export (D1) |

The design system is exported as `hui`
(`from haywire.api.workbench import hui`), the name every library already
gives `haywire.ui.elements`.

`resolve` and `location_of` (`core.volumes`) were renamed `resolve_volume_path`
and `volume_location` on the maintainer's word (2026-11-15), in core and every
caller, so the flat module reads on its own.

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
| 1 | done 2026-11-15, PR #108. 170 component names, 64 workbench names after slices 2 and 4 added theirs; ADRs 0084 and 0085; glossary terms. The checked-in list is `tests/api/names.py` |
| 2 | in part, 2026-11-15, PR #108. Done: every import line in `docs/components`, `docs/guides` and `docs/haybale`; the Author API section and registry table in the haybale canon; the Data node template; the `haywire init` scaffold and its ruff lines. Open: (a) six names the docs teach and no library uses stay on internal imports in the docs and need a decision each: `IAdapter`, `GraphProperties`, `graph` (the graph-settings descriptor), `promote_setting`, `demote_setting`, `HaywireDarkTheme`; (b) the canons do not yet document the exported names the tables above mark "document"; (c) prose that names an internal module path was left as it is; (d) `.claude/skills/haywire-themes/SKILL.md` has one internal import line |
| 3 | done 2026-11-15, PR #108 (merged into slice 1, as allowed). Deviations: notices are collected in a `ContextVar` (`core/library/deprecated_names.py`), not with `warnings.catch_warnings`; the warning is `HaywireDeprecationWarning`, a `DeprecationWarning` subclass, so third-party deprecations stay out of the ledger; the entry is written with `report_loss` |
| 4 | done 2026-11-15, PR #108, one commit per library instead of one PR (the PR for slice 1 was still open, and stacked PRs do not survive squash merges). example, audio, image, core and models import only the Author API; `barn/ruff.toml` enforces it. 748 names moved by the codemod; four users rewritten by hand (Print node, `array_widget`, models editor menu, one docstring) |
| 5–7 | not started. For slice 5, ruff cannot hold an allowlist of names: either the library keeps TID251 off and the AST test is its only check, or each allowlisted import carries `# noqa: TID251` |

## Lands with the code

**Glossary** (`docs/reference/glossary.md`, added in slice 1):

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

**ADRs** (written in slice 1):

- [ADR 0084](../../docs/adr/0084-a-library-imports-the-framework-through-the-author-api.md),
  "A library imports the framework through the Author API": Q1, Q2, Q4, Q5, Q6
  and the template exception.
- [ADR 0085](../../docs/adr/0085-a-name-leaves-the-author-api-through-a-deprecation-window.md),
  "A name leaves the Author API through a deprecation window": Q8, Q9.

## Not in this design

- Moving or renaming any internal module, or fixing the `edge_wrapper` cycle.
- A package split of haywire-core.
- A public import path for one haybale used by another (Q3).
- From the review, after this: identity aliases for renamed or moved node
  classes and a port-level "formerly"; authored `migrate()`; settings rename and
  retype handling.
