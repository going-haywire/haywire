---
name: Test runs used to persist into the developer's own workspace settings
description: create_test_injector temp-redirected only the GLOBAL settings tier; the workspace tier — the one the app writes back to — was derived from workspace_root, which the conftest fixtures pass as the real repo root. Fixed by splitting workspace_settings_path from workspace_root.
type: project
---

# Tests wrote into `<repo>/.haywire/settings.json`

## Symptom

Every node in the studio renders with the error skin:

```
Skin 'skin-fw' not found, using error skin as fallback
```

`skin-fw` is not a skin key — real ones are `library:skin:Name`. It appears
*only* in test files (`tests/core/test_node/test_node_skin_graph_tier.py`,
`tests/core/test_settings/test_graph_mirror.py`). A test run had written it
into the developer's real workspace settings, along with other artifacts like
`test.persistent.framework.name = "x"`.

## Cause

Two tiers, only one of them isolated:

- **global** — `settings_path`, which `create_test_injector` already redirected
  to a `tempfile.mkdtemp()` under `use_temp_settings`.
- **workspace** — derived as `<workspace_root>/.haywire/settings.json`, with no
  override. And `workspace_root` is what the conftest fixtures deliberately set
  to the real repo root (`workspace_root=str(project_root)`) so library
  discovery works.

The workspace tier is the one that *matters*: it is where the app writes back.
A settings descriptor's `__set__` calls `registry.save_to_json_debounced()`
(`descriptor.py`), so any test writing a mirrored/persistent setting persisted
into the developer's live configuration.

`registry.set_global()` alone does NOT write — it mutates the tier dict. The
disk write comes from the descriptor path, which is why the leak is invisible
when reading `set_global` in isolation.

## Fix

`HaywireModule` gained `workspace_settings_path`, split from `workspace_root`
so a caller can keep the real workspace (for library discovery) while sending
settings *writes* somewhere disposable. `create_test_injector` now redirects
both tiers under `use_temp_settings`, into two distinct files.

Guarded by `tests/core/test_di/test_settings_path_isolation.py`.

## How to apply

- A test needing a real `workspace_root` still gets isolated settings by
  default. Pass `workspace_settings_path=` only to point somewhere specific.
- When adding a new settings tier or a new path derived from `workspace_root`,
  ask whether the app ever *writes* it. If so it needs its own override, or
  tests will write to a developer's files.
- To verify isolation empirically, checksum both settings files around a full
  run:
  `shasum -a 256 .haywire/settings.json ~/.haywire/settings.json > /tmp/b.txt`
  … then `shasum -a 256 -c /tmp/b.txt`. Both must report OK.

## Related

An adjacent bug masked this one for a while: `_flatten` in
`settings/persistence.py` treated any table containing a `default` key as a
setting entry, so the real framework key `ui.node.default.skin.studio_skin`
stopped flattening at `ui.node`. The registry then tried to auto-define a whole
subtree as one setting and logged "no registered IType for Python type
<class 'dict'>", silently dropping every setting beneath it — including the bad
`skin-fw` value. Fixing the flattener is what made the pollution visible.
