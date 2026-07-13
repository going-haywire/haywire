# Constructing a `SettingsRegistry()` mutates global FrameworkSettings state

**TL;DR:** `SettingsRegistry.__init__` is *not* side-effect-free. Every construction
repoints the class-level `FrameworkSettings._registry` at the new instance and
**drains** the module-level `_pending_global` queue into it. A throwaway registry
(e.g. a test fallback) therefore silently steals framework-schema registration from
whatever registry the app/session actually uses — and later-defined
`FrameworkSettings` subclasses register into the throwaway instead of the real one.

## The mechanism (spread across two files)

1. `FrameworkSettings.__init_subclass__` — [settings_framework.py:98-103](../packages/haywire-core/src/haywire/core/settings/settings_framework.py#L98)
   When a `FrameworkSettings` subclass (e.g. `NodeDefaultSkinSettings`, which owns
   `ui.node.default.skin.studio_skin`) is *defined*:
   - if `FrameworkSettings._registry is not None` → register into it immediately;
   - else → append the class to the module-level `_pending_global` list.

2. `SettingsRegistry.__init__` → `_drain_pending_global()` — [registry.py:132-142](../packages/haywire-core/src/haywire/core/settings/registry.py#L134)
   On *every* registry construction:
   - sets `FrameworkSettings._registry = self` (the class-level singleton pointer), and
   - **pops** every queued class out of `_pending_global` and registers it into `self`.

So `_pending_global` is a one-shot queue and `FrameworkSettings._registry` is a
process-global pointer. Both are rewritten by *any* `SettingsRegistry()` you build,
not just the "real" one.

## How it bites (the bug we hit)

A pytest autouse fixture installed a throwaway `SettingsRegistry()` as an ambient
fallback for DI-less tests. Constructing it drained `_pending_global` into the
throwaway and repointed `FrameworkSettings._registry` at it. After the fixture
discarded the throwaway, the real session registry no longer had those schemas —
symptom: `KeyError: 'Unknown setting: ui.node.default.skin.studio_skin'` in an
*unrelated* later test, only under full-suite ordering (passed in isolation).

## Don't

- Build a bare `SettingsRegistry()` "just to have one" in tests, tooling, or a
  second code path, expecting it to be inert. It hijacks framework-schema
  registration globally.

## Do

- Get the registry from DI (`get_settings_registry()` / the injector), which
  constructs exactly one and owns the drain.
- If a test genuinely must construct a throwaway registry, snapshot **all three**
  pieces of global state first and restore them in teardown:
  `di_context._settings_registry`, `FrameworkSettings._registry`, and
  `list(_pending_global)` (restore contents with `_pending_global[:] = saved`).
  This is what the `_ambient_settings_registry` autouse fixture in
  [tests/conftest.py](../tests/conftest.py) now does.

Related: [project_di_context.md](project_di_context.md) (ambient DI uses module-level
globals, not ContextVar — same "global state persists across tests" family).
