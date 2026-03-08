# Testing Guide

This guide covers how to test code that depends on the settings system.

---

## Test Utilities

Import from `haywire.core.di.test_config`:

```python
from haywire.core.di.test_config import (
    create_test_injector,
    create_test_library_system,
    create_test_settings_registry,
    create_test_settings_holder,
    SettingsTestContext,
)
```

---

## Isolated Registries

### Unit test: registry only

```python
from haywire.core.di.test_config import create_test_settings_registry


def test_setting_resolution():
    registry = create_test_settings_registry({'ui.node.bg_color': '#ff0000'})

    value, source = registry.resolve('ui.node.bg_color')
    assert value == '#ff0000'
    assert source == 'global'


def test_setting_default():
    registry = create_test_settings_registry()

    value, source = registry.resolve('ui.node.bg_color')
    assert value == '#ffffff'   # default from NodeUISettings
    assert source == 'default'
```

`predefined_settings` keys are full keys; values are applied in `SET` mode.

### Without builtins

```python
def test_custom_settings_only():
    registry = create_test_settings_registry(
        predefined_settings={'my.setting': 42},
        register_builtins=False
    )
    assert registry.has_definition('my.setting')
    assert not registry.has_definition('ui.node.bg_color')
```

---

## Settings Holders

`create_test_settings_holder()` uses `_TestNodeSettings(namespace='test.node')` by default, which defines `bg_color`, `font_size`, and `verbose` fields.

- `predefined_local` keys are **attr names** (`'bg_color'`, `'font_size'`)
- `predefined_global` keys are **full keys** (`'test.node.bg_color'`)

### Basic holder

```python
from haywire.core.di.test_config import create_test_settings_holder


def test_local_overrides_global():
    registry, holder = create_test_settings_holder(
        predefined_global={'test.node.bg_color': '#aaaaaa'},
        predefined_local={'bg_color': '#ff0000'},
    )

    assert holder.bg_color == '#ff0000'

    info = holder.get_info('bg_color')
    assert info.source == 'local'
    assert not info.is_overridden


def test_global_override_wins():
    from haywire.core.settings import SettingMode

    registry, holder = create_test_settings_holder(
        predefined_local={'bg_color': '#ff0000'},
    )

    registry.set_global('test.node.bg_color', '#000000', SettingMode.OVERRIDE)

    assert holder.bg_color == '#000000'

    info = holder.get_info('bg_color')
    assert info.is_overridden
    assert info.source == 'global_override'
```

### Custom schema

```python
from haywire.core.settings import NodeSettings, setting, Color


class MyNodeSettings(NodeSettings, namespace='my_lib.my_node'):
    threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold')
    color:     Color = setting('#ffffff', label='Color')


def test_custom_schema():
    registry, holder = create_test_settings_holder(
        schema_cls=MyNodeSettings,
        predefined_local={'threshold': 0.8},
    )

    assert holder.threshold == 0.8
    assert holder.color == '#ffffff'   # default
```

---

## Temporary Modifications with `SettingsTestContext`

Automatically restores original values after the block:

```python
from haywire.core.di.test_config import create_test_library_system, SettingsTestContext


def test_with_modified_settings():
    service  = create_test_library_system(load_libraries=False)
    registry = service.get_settings_registry()

    with SettingsTestContext(registry) as ctx:
        ctx.set('debug.verbose_logging', True)
        ctx.set_override('ui.node.font_size', 20)

        assert registry.resolve('debug.verbose_logging')[0] is True
        assert registry.resolve('ui.node.font_size')[0] == 20

    # Restored automatically
    assert registry.resolve('debug.verbose_logging')[0] is False
    assert registry.resolve('ui.node.font_size')[0] == 12
```

`SettingsTestContext` methods:

- `ctx.set(full_key, value)` — SET mode
- `ctx.set_override(full_key, value)` — OVERRIDE mode
- `ctx.reset(full_key)` — reset to AUTO

---

## Integration Tests

```python
def test_full_system_with_settings():
    service = create_test_library_system(load_libraries=True, use_temp_settings=True)

    service.set_setting('execution.auto_execute', False)
    assert service.get_setting('execution.auto_execute') is False
```

Always use `use_temp_settings=True` to avoid reading from `~/.haywire/settings.toml`.

---

## Pytest Fixtures

```python
# conftest.py
import pytest
from haywire.core.di.test_config import (
    create_test_settings_registry,
    create_test_settings_holder,
    create_test_library_system,
    SettingsTestContext,
)


@pytest.fixture
def settings_registry():
    return create_test_settings_registry()


@pytest.fixture
def settings_holder():
    _, holder = create_test_settings_holder()
    return holder


@pytest.fixture
def library_system():
    return create_test_library_system(load_libraries=False, use_temp_settings=True)


@pytest.fixture
def settings_context(library_system):
    return SettingsTestContext(library_system.get_settings_registry())
```

Usage:

```python
def test_with_fixtures(settings_registry):
    value, _ = settings_registry.resolve('ui.node.bg_color')
    assert value == '#ffffff'


def test_temporary_changes(settings_context):
    with settings_context as ctx:
        ctx.set('debug.verbose_logging', True)
        # ... assertions


def test_holder_access(settings_holder):
    assert settings_holder.bg_color == '#ffffff'
    assert settings_holder.font_size == 12
    assert settings_holder.verbose is False
```

---

## Testing Change Callbacks

```python
def test_on_change_callback():
    registry, holder = create_test_settings_holder()

    calls = []
    holder.on_change(lambda name, value, source: calls.append((name, value, source)))

    holder.set('bg_color', '#ff0000')

    assert len(calls) == 1
    assert calls[0] == ('bg_color', '#ff0000', 'local')
```

---

## Summary

| Utility | Use Case |
|---------|----------|
| `create_test_settings_registry()` | Unit tests for registry and resolution |
| `create_test_settings_holder()` | Unit tests for holder, caching, override logic |
| `create_test_library_system()` | Integration tests with full DI stack |
| `SettingsTestContext` | Temporary global setting changes with auto-restore |

Best practices:

- Always use `use_temp_settings=True` to isolate from user settings
- Use **attr names** for `predefined_local` and `holder.get_info()`
- Use **full keys** for `predefined_global` and `registry.set_global()`
- Test both default values and local overrides
- Test that `is_overridden` is set correctly when OVERRIDE mode is active
