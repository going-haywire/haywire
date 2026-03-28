# PRD: Unify Descriptor Hierarchy & Add Settings Scope

## Problem Statement

The settings system has two parallel descriptor classes (`prop` and `SettingDescriptor`) that both inherit from `FieldDescriptor` and share ~80% of their constructor parameters. This creates confusion:

- Node authors use `prop()` on `Bag` subclasses for per-node settings
- Framework/library authors use `SettingDescriptor` on `FrameworkSettings`/`LibrarySettings` classes for TOML-tier settings
- The `setting()` name means two different things depending on import path (`haywire.core.settings` returns `prop`, `haywire.core.settings.descriptors` returns `SettingDescriptor`)
- Two separate base classes (`Bag` vs `_SettingsSchema`) collect descriptors differently (`_prop_fields()` vs `_fields`)

Additionally, node-defined settings bags (`class filter(Settings): ...`) have full backend support (TOML resolution, serialization, change callbacks) but zero UI — no panel discovers or renders them.

## Solution

1. **Unify to a single descriptor class**: `prop` absorbs `SettingDescriptor`'s extra parameters (`type_=`, `stored=`, `validator=`). `SettingDescriptor` and `descriptors.py` are deleted.

2. **Rebase schema classes on `Bag`**: `FrameworkSettings` and `LibrarySettings` become `Bag` subclasses (using `prop` descriptors), replacing the parallel `_SettingsSchema` hierarchy. They remain class-only (never instantiated) — the registry reads their `_prop_fields()` for metadata.

3. **Add a `settings` scope and panel**: A new scope in the properties editor (order 65, icon `tune`) appears when the selected node has settings bags. A single panel calls `list_setting_bags()` and renders each bag as a collapsible section via `render_reactive()`.

4. **Extend `render_reactive()`**: Skip `read_only=True` fields, show a reset-to-global affordance for `mirrors=` fields when locally overridden, delete dead `render_sub_holder()`.

## User Stories

1. As a node author, I want to use the same `setting()` function for both node-local and library-wide settings, so that I don't need to learn two different APIs.
2. As a node author, I want my `class filter(Settings)` fields to appear in a panel when the node is selected, so that users can configure them without code.
3. As a node author, I want `mirrors=` fields to show a "reset to global" button in the panel, so that users can revert per-node overrides.
4. As a node author, I want `read_only=True` fields to be hidden from the settings panel, so that internal cached globals don't clutter the UI.
5. As a node author, I want to declare `validator=lambda v: v > 0` on a `setting()`, so that invalid values are rejected at write time.
6. As a node author, I want to mark a field as `stored=False`, so that computed/derived fields are excluded from serialization.
7. As a framework developer, I want `FrameworkSettings` and `LibrarySettings` to use the same descriptor class as node settings, so that the codebase has one field-descriptor hierarchy instead of two.
8. As a framework developer, I want `FrameworkSettings` subclassing to be forbidden (no `class MySettings(NodeUISettings)`), so that namespace collisions from inherited fields are impossible.
9. As a framework developer, I want the registry to store `prop` instances in `_definitions` instead of `SettingDescriptor`, so that there is one descriptor type throughout the system.
10. As a user, I want to see a dedicated "Settings" tab (tune icon) in the properties editor when I select a node that has settings bags, so that I can find and edit node-specific settings.
11. As a user, I want each settings bag (e.g., "filter", "output") rendered as a collapsible section within the settings panel, so that multi-bag nodes are organized clearly.
12. As a user, I want the settings tab to disappear when the selected node has no settings bags, so that the UI doesn't show an empty tab.
13. As a user, I want mirrored settings that I've overridden locally to show a visual indicator and reset affordance, so that I can tell which values differ from the global default and revert them.
14. As a framework developer, I want `render_sub_holder()` removed from `_settings_panel_base.py`, so that dead code referencing deleted modules is cleaned up.
15. As a library author, I want `LibrarySettings` to use `prop()` descriptors (via the `setting()` alias), so that my settings schema uses the same mechanism as everything else.
16. As a framework developer, I want `_auto_define()` and `define()` in the registry to create `prop` instances, so that programmatically created settings use the unified descriptor.
17. As a node author, I want node-framework properties (`node.props` — muted, collapsed, position) to remain in the `node` scope, separate from my custom settings bags in the `settings` scope, so that framework infrastructure and domain settings don't mix.

## Implementation Decisions

### Descriptor unification

- `prop` gains three new optional parameters: `type_` (explicit type override, defaults to `type(default)`), `stored` (bool, default `True` — controls serialization inclusion), `validator` (callable, default `None`). A `validate(value)` method is added that delegates to the validator or returns `True`.
- `SettingDescriptor` class and `descriptors.py` module are deleted entirely. No re-exports or backwards-compatibility shims.
- The `setting` alias in `haywire.core.settings.__init__` continues to point to `prop`. There is no longer a second `setting()` factory function anywhere.
- The registry imports `prop` from `haywire.core.property` for programmatic descriptor creation in `_auto_define()` and `define()`.

### Schema class rebasing

- `_SettingsSchema` base class is deleted. `FrameworkSettings` and `LibrarySettings` extend `Bag` directly.
- `FrameworkSettings.__init_subclass__` accepts `namespace=` kwarg, iterates `_prop_fields()`, and sets `_field_key = f'{namespace}.{name}'` on each `prop` descriptor.
- Deep inheritance is blocked: if a `FrameworkSettings` or `LibrarySettings` subclass's immediate base is not `FrameworkSettings` or `LibrarySettings` itself, `__init_subclass__` raises `TypeError`.
- `FrameworkSettings` and `LibrarySettings` remain class-only (never instantiated). The `prop.__get__` instance path exists but is irrelevant for these classes.

### Registry migration

- `_register_schema_fields()` reads `schema_cls._prop_fields()` instead of `schema_cls._fields`.
- `_unregister_schema_fields()` likewise uses `_prop_fields()`.
- `_class_filter()` checks `issubclass(cls, (LibrarySettings, FrameworkSettings))` — unchanged in logic, but these are now `Bag` subclasses.
- `_definitions: dict[str, prop]` — type annotation changes from `SettingDescriptor` to `prop`.
- `_auto_define()` and `define()` call `prop(...)` instead of `_setting_cls(...)`.
- All other registry logic (two-tier value storage, resolution, TOML load/save, namespace subscriptions) is unchanged.

### Settings scope

- New `ScopeDescriptor` registered in `haybale-studio/editors/scopes.py`: `scope_id='settings'`, `label='Settings'`, `icon='tune'`, `order=65`, `poll=lambda ctx: ctx.active_node is not None and bool(ctx.active_node.list_setting_bags())`.
- Positioned between `node` (60) and `edge` (70) in the scope toolbar.
- Scope is only available when the selected node has at least one settings bag.

### Settings panel

- New `NodeSettingsBagsPanel` registered under `scope='settings'`, `order=10`, `default_open=True`.
- Calls `node.list_setting_bags()` to discover all user-defined `Bag` instances.
- Iterates bags; each bag is rendered as a collapsible section with the bag class name as header.
- Each bag's fields are rendered via `render_reactive(bag)`.

### `render_reactive()` extensions

- Fields with `descriptor._read_only is True` are skipped (not rendered).
- Fields with `descriptor._mirror_key` show a reset button when `bag.is_locally_set(attr_name)` is `True`. Clicking the button calls `bag.reset(attr_name)`.
- `render_sub_holder()` function is deleted (dead code importing from deleted modules).

### Bag `to_dict()` update

- `to_dict()` skips fields where `descriptor._stored is False` (in addition to existing `_read_only` skip).

## Testing Decisions

Tests should verify external behavior (public API contracts), not implementation details. A good test creates an instance, exercises the public interface, and asserts observable outcomes.

### Module 1: `prop` descriptor extensions

- Test `validator=` rejects invalid values (both via `validate()` method and in `__set__` if wired)
- Test `stored=False` fields are excluded from `to_dict()`
- Test `type_=` explicit override is stored on the descriptor
- Prior art: existing `tests/core/test_reactive.py` and `tests/core/test_settings/test_bag_settings.py`

### Module 2: Schema rebasing on `Bag`

- Test that `FrameworkSettings` subclass with `namespace=` has correct `_field_key` on all props
- Test that `_prop_fields()` returns the expected descriptors (not inherited from parent schemas)
- Test that extending a `FrameworkSettings` subclass raises `TypeError`
- Test that extending a `LibrarySettings` subclass raises `TypeError`
- Prior art: existing `tests/core/test_settings/`

### Module 3: Registry migration

- Existing registry tests should pass with minimal changes (import path updates)
- Test that `define()` returns a `prop` instance
- Test that `_auto_define()` from TOML creates `prop` instances
- Test that `_register_schema_fields()` correctly reads `_prop_fields()` from a `FrameworkSettings` class
- Prior art: existing `tests/core/test_settings/test_registry.py`

### Module 6: Settings scope and panel

- Not unit tested (NiceGUI rendering). Verified manually by selecting a node with settings bags and confirming the scope tab appears and fields render correctly.

## Out of Scope

- **LibrarySettings panels**: Dynamic panel discovery for library-registered settings schemas. Deferred to a future iteration.
- **Merging `render_reactive()` and `render_schema()`**: They serve different use cases (instance vs global class). Kept separate.
- **Instantiating `FrameworkSettings`**: They remain class-only metadata containers. The registry manages values in flat tier dicts.
- **`FrameworkSettings` inheritance chains**: Actively prevented. No use case identified.
- **Migration tooling**: No automated migration for external libraries using `SettingDescriptor` directly. Clean break — the old API is removed.

## Further Notes

- The `setting` name in `haywire.core.settings.__init__` continues to be the public node-author API (alias for `prop`). Library authors use the same `setting()` function on their `LibrarySettings` classes.
- `Bag` and `prop` remain the implementation names in `haywire.core.property`. `Settings` and `setting` are public-facing aliases in `haywire.core.settings`.
- This builds on the prior refactoring that replaced `NodeSettings`/`SubHolder`/`SettingsHolder`/`ResolutionChain` with the extended `Bag` + `prop()` system. That work is complete (320 tests passing). This PRD covers the remaining unification and UI gap.
