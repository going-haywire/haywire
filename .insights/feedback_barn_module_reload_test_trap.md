---
name: Barn modules reload during HaywireApp bootstrap — top-of-file imports go stale
description: Tests that import a class from barn/haybale-* at module top and then patch it by string path will fail under polluter sequences because importlib.reload swaps a new module object into sys.modules
type: feedback
originSessionId: 6710b6b6-aab5-4d5c-ace5-c791b746f8f0
---
When tests import a class from `barn/haybale-*/...` at the top of the file and a later test in the suite (or the same session) instantiates `HaywireApp` or otherwise triggers library bootstrap, `BaseRegistry` calls `importlib.reload(sys.modules[module_name])` on those barn modules. After that reload:

- The class object referenced by the test's top-of-file import is **stale** — it's no longer the same object as `sys.modules[module].Foo`.
- The stale class's methods close over the **stale module's `__globals__` dict**, so any name lookup inside those methods (e.g. `Popup` in `_build_popup`) goes to the stale dict.
- `patch("haybale_xxx.module.Foo", ...)` patches the **live** module in `sys.modules`, NOT the stale globals dict. So patches don't reach instances of the stale class.

Symptom: tests pass in isolation, fail under the full suite. The traceback shows the *real* class running where a mock was expected, often with NiceGUI errors like "slot stack for this task is empty."

**Why:** I learned this debugging the move of `ui/graph_canvas` from haywire-core into `barn/haybale-studio/`. Pre-move the module wasn't subject to reload; post-move it is. Took a while to pin down because the bug only triggers under specific test orderings.

**How to apply:** When writing or reviewing tests that touch barn modules:

1. If the test patches a class in a barn module: resolve the class AND the patch target through `importlib.import_module(...)` inside the test helper, then use `patch.object(module, "Foo", ...)`. Don't rely on top-of-file imports for the class under test.
2. Patches on attributes that resolve to global singletons (e.g. `nicegui.ui.notify` accessed as `haystack_editor.ui.notify`) are reload-safe — `ui` is the same `nicegui.ui` everywhere, so the global mutation survives reload. No special handling needed.
3. `isinstance` checks against Protocol/ABC classes are reload-safe (structural, not identity-based).

Reference implementation: `tests/ui/test_canvas_handlers/test_session_context_menu_provider.py` — uses `_current_context_menu()` / `_current_focuses()` / `_current_actions()` helpers that re-import the live module on each call. Also documented in CLAUDE.md "Testing" section.
