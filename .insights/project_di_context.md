---
name: DI context uses module-level globals, not ContextVar
description: The DI context state lives in module-level globals on purpose — ContextVar broke hot-reload. Don't switch it back without understanding why.
type: project
---

The DI context (`packages/haywire-core/src/haywire/core/di/context.py`) is implemented as **module-level globals**, not as `ContextVar`. This is deliberate.

An earlier implementation used `ContextVar` for the DI state. It looked cleaner (per-task isolation, no global mutation) but broke hot-reload: when `BaseRegistry` reloads a barn module via `importlib.reload`, the `ContextVar` instance the new module captured was a different object from the one the rest of the app was reading. Lookups missed, DI bindings vanished, and the symptom was hard to trace because nothing crashed — code just silently got the wrong injector.

Module-level globals work because `importlib.reload` reuses the existing module object (mutates `__dict__` in place) for `haywire.core.di.context` itself — that module isn't reloaded by the registry, only barn modules are. The globals stay stable across hot-reload.

**Don't switch back to ContextVar** without solving the reload-identity problem. If you genuinely need per-task isolation later, the right approach is probably to layer it on top of the globals (push/pop) rather than replace them.

Files:
- `packages/haywire-core/src/haywire/core/di/config.py`
- `packages/haywire-core/src/haywire/core/di/context.py`
