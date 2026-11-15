---
name: a-library-imports-the-framework-through-the-author-api
description: Two modules, haywire.api (components) and haywire.api.workbench (panels, editors, Farmhand tools; provisional), are the only import paths with a compatibility promise; a name enters when a library uses it and the docs teach it; everything else under haywire is internal by rule, enforced in this repository by lint and two tests
status: accepted
see-also: ADR-0005, ADR-0085
level: framework
---

# A library imports the framework through the Author API

**Context.**

- A library imported a symbol from wherever it lived. Measured on 2026-11-15: 194 distinct module paths, 1728 imports, 1165 of them four or more levels deep, 546 distinct names, six of them underscore-prefixed.
- Once a library is released separately from core, every move or rename inside core breaks it. Nothing said which names core may move.
- 39 package `__init__` files carry `__all__`, mixing author names with engine internals (`BaseNode` beside `NodeWrapper`'s state classes, `ExecutionContext` beside `HaywireVM`), and libraries bypass them.
- The seven node-authoring libraries (five in this repository, two outside) use 153 names. `haybale-graph-editor` alone uses 273: a workbench library reaches far deeper than a node library, and ships in lockstep with core.
- Importing `haywire.core.node` already loads `haywire.ui` and NiceGUI, and one import order (`haywire.core.edge.edge_wrapper` first) fails on a cycle.

**Decision.**

- **Two modules are the Author API.** `haywire.api` is the component API: node, type, adapter, widget, skin, theme, settings, catalog, volumes, the library class and its registries, `ExecutionContext`, and the builtin types, widgets, widget keys and wires. `haywire.api.workbench` is the workbench API: panel, editor, session, signals, state, access, Farmhand, and the design system as `hui`.
- **Both are flat modules of re-exports** with an explicit `__all__`. A re-exported object is the original object.
- **Everything else is internal, by rule.** A name not importable from the two modules carries no promise. An internal import is not refused at runtime, and internals are not renamed to mark them.
- **A name enters when a library uses it and the docs teach it to authors.** A used but undocumented name gets one decision: document and export, or keep internal and rewrite its user.
- **A builtin block is exported whole.** Everything in `haywire.barn.builtin.types.__all__`, `haywire.barn.builtin.widgets.__all__` and `haywire.barn.builtin.widget_keys` enters together.
- **Imports point one way:** `haywire.api.workbench → haywire.api → core / ui / barn.builtin`. The framework does not import the Author API. The node templates under `barn/builtin/nodes/templates/` are the exception, because the New Node wizard copies them into authors' libraries.
- **The promise is made to libraries released separately from core.** Every library in this repository still imports through the Author API, because its code is what authors copy. The five workbench libraries and the two test libraries keep a list of the internals they still import; a test lets the list shrink and never grow.
- **Enforced here by three checks.** ruff `TID251` bans `haywire.core`, `haywire.ui` and `haywire.barn` per migrated library and bans `haywire.api` inside `packages/`; an AST test holds the allowlists; `tests/api/` compares both `__all__` lists with a checked-in list, so a removed or renamed name shows in review.
- **What the promise is** is [ADR 0085](0085-a-name-leaves-the-author-api-through-a-deprecation-window.md).

**Considered.**

- *One promise for everything.* The workbench names are many, taught by few docs, and no library outside this repository has built an editor on them. Promising them now would freeze what has one user.
- *Cleaning up the existing package `__all__` lists.* 39 places to keep honest instead of two, and a deep path would still be the documented one.
- *An underscore prefix on every internal module.* A rename of most of core, breaking every existing import for a marking the rule already gives.
- *A runtime check that refuses internal imports.* An internal import breaks nothing today; refusing it would break libraries to protect them.
- *A separate `haywire-api` package.* A package split of core is a larger decision and not needed for the promise.
- *Exporting `haywire.core.volumes` as a namespace*, so that `volumes.resolve(path)` keeps reading well. The promise would then cover the whole package. Its two functions whose names said little in a flat module were renamed instead: `resolve` to `resolve_volume_path`, `location_of` to `volume_location`.

**Consequences.**

- Core can move and rename any internal without a library noticing, as long as the two modules keep resolving the names.
- `haywire.api` fixes one import order, so an author cannot reach the `edge_wrapper` cycle.
- The tiers differ in promise, not in import cost: `import haywire.api` loads NiceGUI.
- `print()` is the way to write to the studio log; `haywire.ui.console_bridge.console_print` is internal. A widget class is looked up with `get_widget_class()`; the `WIDGET_REGISTRY` dict is internal.
- A public import path for one haybale used by another (`haybale_image`, `haybale_models`) is not part of this decision.
