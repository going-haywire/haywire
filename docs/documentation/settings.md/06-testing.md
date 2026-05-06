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
    create_test_bag,
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

## Testing with Settings Instances

`create_test_bag()` creates an isolated registry + `Settings` instance. By default it uses a minimal settings object with `bg_color`, `font_size`, and `verbose` fields.

- `predefined_local` keys are **attr names** (`'bg_color'`, `'font_size'`)
- `predefined_global` keys are **full keys** (`'test.global.font_size'`)

### Basic bag

```python
from haywire.core.di.test_config import create_test_bag


def test_local_overrides_global():
    registry, bag = create_test_bag(
        predefined_global={'test.global.font_size': 16},
        predefined_local={'font_size': 20},
    )

    assert bag.font_size == 20
    assert bag.is_locally_set('font_size')


def test_reset_falls_back_to_default():
    registry, bag = create_test_bag(predefined_local={'bg_color': '#ff0000'})
    bag.reset('bg_color')
    assert bag.bg_color == '#ffffff'
```

### Custom schema

```python
from haywire.core.settings import Settings, setting, shadow, watch, Color


class MySettings(Settings):
    threshold = setting[float](0.5, min=0.0, max=1.0, label='Threshold')
    color = setting[Color]('#ffffff', label='Color')


def test_custom_settings():
    registry, s = create_test_bag(
        bag_cls=MySettings,
        predefined_local={'threshold': 0.8},
    )

    assert s.threshold == 0.8
    assert s.color == '#ffffff'   # default
```

### Testing on_change callbacks

```python
from haywire.core.settings import Settings, setting, shadow, watch


class SettingsWithCallback(Settings):
    scale = setting[float](1.0, on_change='_on_scale')

    def __init__(self, registry=None):
        super().__init__(registry)
        self.calls = []

    def _on_scale(self, value, field=''):
        self.calls.append((value, field))


def test_on_change_fires():
    s = SettingsWithCallback()
    s.scale = 2.0
    assert s.calls == [(2.0, 'scale')]


def test_on_change_not_fired_same_value():
    s = SettingsWithCallback()
    s.scale = 1.0   # same as default
    assert s.calls == []
```

### Testing serialization

```python
def test_round_trip():
    from haywire.core.settings import Settings, setting, shadow, watch

    class MySettings(Settings):
        threshold = setting[float](0.5)
        mode = setting[str]('fast')

    s = MySettings()
    s.threshold = 0.8
    s.mode = 'precise'

    data = s.to_dict()
    assert data == {'threshold': 0.8, 'mode': 'precise'}

    s2 = MySettings()
    s2.from_dict(data)
    assert s2.threshold == 0.8
    assert s2.mode == 'precise'
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

## Testing Nodes with Settings

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, shadow, watch


def test_node_settings_direct_access():
    @node(label='Test Node')
    class _TestNode(BaseNode):
        class filter(NodeSettings):
            threshold = setting[float](0.7)

    wrapper = type('W', (), {'node_id': 'w1', 'notify': lambda *a: None})()
    n = _TestNode('n1', wrapper)

    assert n.filter.threshold == 0.7

    n.filter.threshold = 0.9
    assert n.filter.threshold == 0.9


def test_node_settings_serialization():
    @node(label='Serial Node')
    class _SerialNode(BaseNode):
        class filter(NodeSettings):
            strength = setting[float](0.5)

    wrapper = type('W', (), {'node_id': 'w1', 'notify': lambda *a: None})()
    n = _SerialNode('n1', wrapper)
    n.filter.strength = 0.9

    data = n._to_dict()
    assert data['settings']['filter']['strength'] == 0.9

    n2 = _SerialNode('n2', wrapper)
    n2._initialize_from_dict({'settings': data['settings']})
    assert n2.filter.strength == 0.9
```

---

## Pytest Fixtures

```python
# conftest.py
import pytest
from haywire.core.di.test_config import (
    create_test_settings_registry,
    create_test_bag,
    create_test_library_system,
    SettingsTestContext,
)


@pytest.fixture
def settings_registry():
    return create_test_settings_registry()


@pytest.fixture
def test_bag():
    _, bag = create_test_bag()
    return bag


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


def test_bag_access(test_bag):
    assert test_bag.bg_color == '#ffffff'
    assert test_bag.font_size == 12
    assert test_bag.verbose is False
```

---

## UI Testing with the Settings Harness

The settings UI harness in `tests/ui/harness/` lets you verify rendered panel behavior with Playwright — without spinning up the full Haywire app.

### How it works

The harness is a standalone NiceGUI app (`app.py`) that boots the full library system and exposes three routes:

- `GET /node?class=<dotted.ClassName>&bag=<bag_name>` — renders a `NodeSettings` bag via `render_reactive()`
- `GET /schema?class=<dotted.ClassName>` — renders a `LibrarySettings` schema via `render_schema()`
- `POST /api/set?key=<key>&value=<value>` — writes a value to the registry (for mirror propagation tests)

The pytest fixture in `conftest.py` starts the harness as a subprocess and polls `/status` until it's ready. All tests in the suite share one server instance (session-scoped).

### Running the UI tests

```sh
uv run pytest tests/ui/harness/ -m ui -v
```

Or start the harness manually to inspect in a browser:

```sh
uv run python tests/ui/harness/app.py
# then open http://localhost:8090/node?class=haybale_testing.nodes.testbed.settings_node.SettingsNode&bag=example
```

### Writing a Playwright test

Use `data-field` to locate a row, `data-value` to read the current value:

```python
from playwright.sync_api import Page, expect

_NODE_URL = (
    "http://localhost:8090/node"
    "?class=haybale_testing.nodes.testbed.settings_node.SettingsNode"
    "&bag=example"
)

def test_float_renders_default(page: Page, harness):
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    nd = page.locator('[data-field="example_float"] [data-number_drag]')
    expect(nd).to_have_attribute("data-value", "0.5")
```

For mirror propagation tests, use the `reset_setting` fixture to restore the registry after the test:

```python
import requests

def test_global_change_propagates(page: Page, harness, reset_setting):
    reset_setting("testing.default_intensity", 0.5)   # restores after test
    requests.post(
        "http://localhost:8090/api/set",
        params={"key": "testing.default_intensity", "value": "0.9"},
    )
    page.goto(_NODE_URL)
    page.wait_for_selector("[data-field]")

    nd = page.locator('[data-field="intensity"] [data-number_drag]')
    expect(nd).to_have_attribute("data-value", "0.9")
```

### DOM attributes reference

| Attribute | Element | Value |
| --------- | ------- | ----- |
| `data-field="<attr_name>"` | Row container `div` | Field name as declared on the `Settings` class |
| `data-value="<current>"` | Widget element | Current rendered value as a string |
| `data-number_drag=""` | `NumberDrag` root | Present on all `NumberDrag` widgets |
| `data-error="true"` | Error label | Present when last write was rejected by validator |

### Test files

| File | What it covers |
| ---- | -------------- |
| `test_structural.py` | Field presence, widget types, category headings, read-only exclusion |
| `test_interaction.py` | `data-value` on render, mirror `•` prefix, reset button |
| `test_mirror.py` | Global setting change propagates to mirror fields on re-render |
| `test_validation.py` | Validator rejection shows `data-error`, clears on valid input |

---

## Summary

| Utility | Use Case |
| ------- | -------- |
| `create_test_settings_registry()` | Unit tests for registry and resolution |
| `create_test_bag()` | Unit tests for settings fields, overrides, callbacks, serialization |
| `create_test_library_system()` | Integration tests with full DI stack |
| `SettingsTestContext` | Temporary global setting changes with auto-restore |

Best practices:

- Always use `use_temp_settings=True` to isolate from user settings
- Use **attr names** for `predefined_local` and `settings.is_locally_set()`
- Use **full keys** for `predefined_global` and `registry.set_global()`
- Test both default values and local overrides
- Test `read_only` fields raise `AttributeError` on write
