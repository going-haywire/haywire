---
name: haywire-settings
description: Load Haywire settings system docs into context. Use when the user wants to add settings to a node or library, use shadow()/watch() descriptors, work with GlobalSettingsRegistry, write settings-dependent tests, or build a settings UI panel.
---

# Load Haywire Settings Docs

Read the following documentation files in order and use them as the authoritative reference for any settings task. After reading, output a brief recap of key patterns before proceeding.

## Files to read

1. `docs/documentation/settings.md/01-overview.md` — architecture overview: three containers (NodeSettings, LibrarySettings, GlobalSettings), resolution chain (OVERRIDE > local > global SET > default), SettingsHolder, TOML tiers
2. `docs/documentation/settings.md/02-node-development.md` — adding settings to a node: `class node(NodeSettings)`, `setting()` descriptor, attribute access via `self.settings.field`, `on_change` callbacks, `self.cache`, `self.store`, serialization
3. `docs/documentation/settings.md/03-library-development.md` — library-level settings: `@library_settings(namespace=...)`, `class MyLibSettings(LibrarySettings)`, `shadow()` and `watch()` in node Settings, TOML config format, accessing via registry
4. `docs/documentation/settings.md/05-reference.md` — complete API: `Color`/`Icon` type aliases, all descriptor constructor params, `GlobalSettingsRegistry` methods, `SettingsHolder` methods, `SettingInfo` fields, resolution algorithm

## After reading

Summarise in 8–10 bullet points:
- Three descriptor types: `setting()` (local, stored, panel-visible), `shadow(Global.field)` (overridable global ref, stored when set, reset affordance), `watch(Global.field)` (read-only, invisible, never stored)
- Access pattern: `self.settings.field_name` — never `self.settings['full.key']` for schema fields
- `_full_key` for `setting()` is derived automatically: `{pkg}.{snake_node_name}.{field}` — set by `BaseNode.__init_subclass__`; for `LibrarySettings` it is set immediately by `@library_settings`
- Resolution order: global OVERRIDE beats everything → local instance value → global SET / project TOML → schema default
- `on_change='method_name'` callback signature: `method(self, value, field='')` — field param is optional
- `shadow()` subscribes the holder to `GlobalSettingsRegistry` namespace changes — cache auto-invalidated; plain `setting()` fields do NOT auto-invalidate on global changes
- `register_schema(cls)` adds a `GlobalSettings` class to the registry; `@library_settings` marks `LibrarySettings` for auto-discovery
- `get_info(attr_name)` returns `SettingInfo` with `.source` (`'default'`, `'local'`, `'global'`, `'global_override'`), `.is_overridden`, `.is_inherited`, `.definition`
- `to_dict()` / `from_dict(data)` for serialization; only locally-set fields appear in `schema_values`
- Test helpers: `create_test_settings_registry()`, `create_test_settings_holder(predefined_local={attr: v}, predefined_global={full_key: v})`

Then proceed with the user's task using these patterns as the guide.
