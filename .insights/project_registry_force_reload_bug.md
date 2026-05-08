---
name: BaseRegistry force_reload duplicate-class bug (FIXED)
description: BaseRegistry._on_creation used to force-reload modules on initial scan, producing duplicate class objects when test modules pre-imported production code. Fixed in commit 7b7d86e (2026-05-06).
type: project
originSessionId: b120cd54-3d75-4716-ba18-500b173d1d46
---
**FIXED in commit `7b7d86e` (2026-05-06).** Previous behaviour: `_on_creation` at `packages/haywire-core/src/haywire/core/registry/base.py:471-473` passed `force_reload=True` to `module_scan_for_classes`. When the module was already in `sys.modules` (because some earlier import path loaded it), the registry deleted it and re-imported it — producing a fresh class object. Anyone holding a reference to the pre-scan class was left dangling.

The fix: drop the `True` argument so `force_reload` defaults to `False`. Hot-reload of changed files still uses `force_reload=True` via `_reload_managed_module` (correct — a file actually changed on disk).

**Discovered during v1.2 EditState migration.** Two workarounds were applied at the time:
1. C2.5 (`cf7e8e5`) reordered haybale-studio's `register_components()` so `state/` is scanned first. Still in place — defensible "load dependencies before consumers" ordering, no longer load-bearing.
2. The `register_edit_state` fixture in `tests/conftest.py` walked `gc.get_objects()` to find every `EditState` class and registered each with a shared instance. **Replaced** in `7b7d86e` with a 5-line single-class registration.

**Regression test:** `tests/core/test_libraries/test_registries.py::TestBaseRegistryClassIdentity::test_panel_pre_imported_class_matches_registered_class`. The haybale-testing library deliberately registers `state/` LAST in its `register_components()` (the placement that broke v1.2), and a panel pre-imports `TestSessionState` at module level. The test asserts the panel's class reference is the same Python object as the one the container holds. Verified to fail if `force_reload=True` is reintroduced — the assertion message reads `assert <class TestSessionState> is <class TestSessionState>` (same name, distinct objects).

**How to apply:** Future "weird KeyError on a class that should be registered" bugs should first check whether something on the importing side ran before the registry scan. The framework no longer creates the trap, but the *symptom* (importing module captures a different class object than the registry sees) could still happen if someone ever passes `force_reload=True` from a new call site.
