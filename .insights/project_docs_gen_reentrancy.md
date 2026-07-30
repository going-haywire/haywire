---
name: generate_docs() cannot run in-process in the studio — it hijacks the global injector
description: docs_gen builds a second LibrarySystemService whose initialize() repoints the live app's global injector and settings registry, and it instantiates every node. Shell out instead.
type: project
---

`generate_docs()` / `generate_all_docs()` (`packages/haywire-studio/src/haywire_studio/docs_gen/generate.py`) each call `create_library_system_service(...)`, which builds a **complete second library system**. That is fine from the CLI, where the process does nothing else. It is **not** safe to call from inside the running studio, for two independent reasons.

## 1. It repoints the live app's globals

`LibrarySystemService.initialize()` calls `set_library_system(self)` and `set_global_injector(self.injector)` (`packages/haywire-core/src/haywire/core/di/config.py:429-430`). The DI context is **module-level globals, not `ContextVar`** (see [project_di_context.md](project_di_context.md)), so there is no scoping escape — the throwaway system silently becomes the app's global system, and never gets restored.

Constructing the injector also builds a fresh `SettingsRegistry` (`config.py:120`), which is not inert: it repoints `FrameworkSettings._registry` and drains the global `_pending_global` queue (see [project_settings_registry_construction_side_effects.md](project_settings_registry_construction_side_effects.md)).

## 2. It instantiates every node

`_node_record` (`docs_gen/extract.py:95`) builds each node in a throwaway `BaseGraph` via `create_node_wrapper`, because ports and settings only exist on a live instance. In-process that means constructing real node instances against the live registries — including nodes that acquire hardware in `__init__` (the visiongraph/OAK-D camera nodes are the obvious case).

Worse, the instantiation is wrapped in a bare `except Exception` that degrades to `ports, settings = [], []`. A node that misbehaves therefore produces a *silently wrong doc* rather than an error.

## What to do instead

Shell out: `haywire docs --all <project_root>` as a subprocess. Total isolation, and hardware grabs die with the process. Use `--all` rather than one subprocess per library — it does the whole barn in **one** library-system load, and its root-relative filter (`generate.py:139`) naturally excludes site-packages installs and `--dev` mode's out-of-tree dev-repo libraries.

Note the boot prints freely to stdout and not all of it is ours (library `on_enable` hooks print too), so don't parse coverage results off stdout — the share wizard's design adds a `--json <path>` file sink for exactly this reason.

**If you ever do need an in-process path**, the seam already exists: `_generate_one(service, library_id, module_dir)` and `extract_library(service, library_id)` take a service and only use `service.get_library_registry()` and `service.injector.get(...)`, both of which the live `LibrarySystemService` provides. The blocker is the node instantiation above, not the plumbing.

Files:
- `packages/haywire-studio/src/haywire_studio/docs_gen/generate.py`
- `packages/haywire-studio/src/haywire_studio/docs_gen/extract.py`
- `packages/haywire-core/src/haywire/core/di/config.py`
