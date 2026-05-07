---
name: haywire-settings
description: Load Haywire settings system docs into context. Use when the user wants to add settings to a node or library, use shadow()/watch() descriptors, work with SettingsRegistry, write settings-dependent tests, or build a settings UI panel.
---

# Load Haywire Settings Docs

Read the following documentation files in order and use them as the authoritative reference for any settings task. After reading, output a brief recap of key patterns before proceeding.

## Files to read

1. `docs/components/settings/setting-canon.md` — authoring guide: three Settings classes (`NodeSettings` / `LibrarySettings` / `FrameworkSettings`), three descriptors (`setting()` / `shadow()` / `watch()`), the inner-class accessor pattern, `on_change` callbacks, the three per-node containers (`cache` / `store` / settings), panel rendering rules, complete worked example with all concepts
2. `docs/architecture/settings/settings-arch.md` — framework mechanics: six-step resolution chain, `SettingsRegistry`, `_pending_global` auto-registration, the four key identifiers (`namespace`, `_setting_key`, `registry_key`, `scope`), TOML format, hot-reload behaviour, mirror cache invalidation, full registry API reference, test utilities (`create_test_settings_registry`, `create_test_bag`, `SettingsTestContext`), Playwright UI harness

## After reading

Summarise in 8–10 bullet points:
- Three descriptor types: `setting()` (local, stored, panel-visible), `shadow(Global.field)` (overridable global ref, stored when set, reset affordance), `watch(Global.field)` (read-only, invisible, never stored)
- Access pattern: `self.settings.field_name` — never `self.settings['full.key']` for schema fields
- `_field_key` for `setting()` is derived automatically: `{pkg}.{snake_node_name}.{field}` — set by `BaseNode.__init_subclass__`; for `LibrarySettings` it is set immediately by `@settings`
- Resolution order: global OVERRIDE beats everything → local instance value → global SET / project TOML → schema default
- `on_change='method_name'` callback signature: `method(self, value, field='')` — field param is optional
- `shadow()` subscribes the holder to `SettingsRegistry` namespace changes — cache auto-invalidated; plain `setting()` fields do NOT auto-invalidate on global changes
- `register_schema(cls)` adds a `FrameworkSettings` class to the registry; `@settings` marks `LibrarySettings` for auto-discovery
- `get_info(attr_name)` returns `SettingInfo` with `.source` (`'default'`, `'local'`, `'global'`, `'global_override'`), `.is_overridden`, `.is_inherited`, `.definition`
- `to_dict()` / `from_dict(data)` for serialization; only locally-set fields appear in `schema_values`
- Test helpers: `create_test_settings_registry()`, `create_test_settings_holder(predefined_local={attr: v}, predefined_global={full_key: v})`

Then proceed with the user's task using these patterns as the guide.
