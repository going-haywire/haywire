---
name: @library linked_libraries are package names, not library ids
description: The `@library(linked_libraries=[...])` list contains Python package names (haybale_core, haybale_studio), not the library `id` from the same decorator. The framework concatenates each entry with a "." and matches it as a module-path prefix for hot-reload scope tracking.
type: project
---
The `@library` decorator takes two superficially-similar arguments:

- `id="graph_editor"` — a short library identifier used in logs, error messages, and as a registry key.
- `linked_libraries=["haybale_graph_editor", ...]` — a list of **Python package names**, NOT library ids.

These are different. Every existing library uses its full package name here (e.g. `haybale-example` declares `["haybale_core"]`, `haybale-haystack` declares `["haybale_studio", "haybale_graph_editor"]`).

**Why package names:** `packages/haywire-core/src/haywire/core/registry/base.py:_get_tracked_scopes` consumes each entry by appending `"."` and using it as a Python module-path prefix to determine which modules' hot-reload events this library should react to. So `"haybale_studio"` becomes `"haybale_studio."`, matching `haybale_studio.editors.foo` etc. A bare library id like `"graph_editor"` becomes `"graph_editor."` and matches nothing — hot-reload events from the dependency are silently dropped.

**Symptom if you get this wrong:** No test failure, no startup error. Hot-reload simply doesn't propagate from the misspelled dependency, so you only notice during dev iteration when editing a file in the dependency doesn't cause the dependent library to re-register its components. Easy to miss for sessions.

**The field used to be `dependencies=`.** Renamed to `linked_libraries` in the metadata consolidation (ADR 0024), which also removed a second, worse collision: `dependencies` is *also* the `[project]` key naming pip distributions with version specifiers — a completely different list that these entries were never valid in. `@library(dependencies=...)` now raises `TypeError` rather than being silently accepted.

**Discovered:** during the GraphEditor carve-out (master, commit `803c7fae`). Task 14 originally added `dependencies=["haybale_core", "haybale_studio", "graph_editor"]` to haystack — using the new library's `id`. The single-character difference between package name and id (underscore vs. dash, presence of `haybale_` prefix) made the mistake easy.

**How to apply:** When adding to `@library(linked_libraries=...)`, use the **directory's Python package name** (the folder under `barn/<lib>/` that contains `__init__.py`, with underscores), not the `id=` value from the decorator. Quick check: `find barn -maxdepth 3 -name "__init__.py" -path "*/haybale_*/__init__.py"` lists all valid values.
