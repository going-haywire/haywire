# Testing Guide

This guide covers how to test code that depends on the settings system.

## Overview

The settings system provides test utilities for:

- **Isolated registries** — Tests don't affect user settings
- **Predefined values** — Set up specific test scenarios
- **Temporary modifications** — Change settings and auto-restore
- **Mock holders** — Test node code without full DI setup

---

## Test Utilities

Import test utilities from the DI test config:

```python
from haywire.core.di.test_config import (
    create_test_injector,
    create_test_library_system,
    create_test_settings_registry,
    create_test_settings_holder,
    SettingsTestContext,
    MockExecutionContext,
)
```

---

## Creating Isolated Registries

### Basic Registry for Unit Tests

```python
from haywire.core.di.test_config import create_test_settings_registry


def test_setting_resolution():
    """Test that settings resolve correctly."""
    registry = create_test_settings_registry({
        'ui.node.bg_color': '#ff0000',
        'debug.verbose_logging': True,
    })
    
    # Test resolution
    value, source = registry.resolve('ui.node.bg_color')
    assert value == '#ff0000'
    assert source == 'global'
    
    value, source = registry.resolve('debug.verbose_logging')
    assert value == True


def test_setting_default():
    """Test that undefined settings use defaults."""
    registry = create_test_settings_registry()
    
    # Built-in setting with default
    value, source = registry.resolve('ui.node.bg_color')
    assert value == '#ffffff'  # Default from ui_node.py
    assert source == 'default'
```

### Registry Without Builtins

```python
def test_custom_settings_only():
    """Test with only custom settings (no builtins)."""
    registry = create_test_settings_registry(
        predefined_settings={'my.setting': 42},
        register_builtins=False
    )
    
    assert 'my.setting' in registry.all_definitions()
    assert 'ui.node.bg_color' not in registry.all_definitions()
```

---

## Creating Test Holders

### Basic Holder for Node Tests

```python
from haywire.core.di.test_config import create_test_settings_holder


def test_local_override():
    """Test that local values override global."""
    registry, holder = create_test_settings_holder(
        predefined_global={'ui.node.bg_color': '#ffffff'},
        predefined_local={'ui.node.bg_color': '#ff0000'}
    )
    
    # Local wins
    assert holder['ui.node.bg_color'] == '#ff0000'
    
    # Check info
    info = holder.get_info('ui.node.bg_color')
    assert info.source == 'local'
    assert not info.is_overridden
    assert not info.is_inherited


def test_global_override_wins():
    """Test that OVERRIDE mode forces value."""
    from haywire.core.settings import SettingMode
    
    registry, holder = create_test_settings_holder(
        predefined_local={'ui.node.bg_color': '#ff0000'}
    )
    
    # Set global override
    registry.set_global('ui.node.bg_color', '#000000', SettingMode.OVERRIDE)
    
    # Override wins over local
    assert holder['ui.node.bg_color'] == '#000000'
    
    info = holder.get_info('ui.node.bg_color')
    assert info.is_overridden
    assert info.source == 'global_override'
```

### Testing Local-Only Settings

```python
from haywire.core.settings import SettingScope


def test_local_only_setting():
    """Test LOCAL_ONLY settings."""
    registry, holder = create_test_settings_holder()
    
    # Define local-only setting
    holder.define(
        'node.my_option',
        default=100,
        scope=SettingScope.LOCAL_ONLY
    )
    
    # Access uses default
    assert holder['node.my_option'] == 100
    
    # Set local value
    holder['node.my_option'] = 200
    assert holder['node.my_option'] == 200
    
    # Verify not in global registry
    assert not registry.has_definition('node.my_option')
```

---

## Temporary Modifications

### Using SettingsTestContext

The `SettingsTestContext` automatically restores original values:

```python
from haywire.core.di.test_config import (
    create_test_library_system,
    SettingsTestContext,
)


def test_with_modified_settings():
    """Test with temporarily modified settings."""
    service = create_test_library_system(load_libraries=False)
    registry = service.get_settings_registry()
    
    # Verify original values
    original_verbose = registry.resolve('debug.verbose_logging')[0]
    original_font = registry.resolve('ui.node.font_size')[0]
    
    with SettingsTestContext(registry) as ctx:
        # Modify settings
        ctx.set('debug.verbose_logging', True)
        ctx.set_override('ui.node.font_size', 20)
        
        # Test with modified values
        assert registry.resolve('debug.verbose_logging')[0] == True
        assert registry.resolve('ui.node.font_size')[0] == 20
    
    # Values automatically restored
    assert registry.resolve('debug.verbose_logging')[0] == original_verbose
    assert registry.resolve('ui.node.font_size')[0] == original_font


def test_context_method_chaining():
    """Test that context methods can be chained."""
    service = create_test_library_system(load_libraries=False)
    registry = service.get_settings_registry()
    
    with SettingsTestContext(registry) as ctx:
        ctx.set('debug.verbose_logging', True) \
           .set('debug.show_execution_time', True) \
           .set_override('ui.node.font_size', 20)
        
        assert registry.resolve('debug.verbose_logging')[0] == True
        assert registry.resolve('debug.show_execution_time')[0] == True
        assert registry.resolve('ui.node.font_size')[0] == 20


def test_multiple_modifications():
    """Test multiple modifications and resets."""
    service = create_test_library_system(load_libraries=False)
    registry = service.get_settings_registry()
    
    with SettingsTestContext(registry) as ctx:
        ctx.set('debug.verbose_logging', True)
        ctx.set('debug.show_execution_time', True)
        ctx.set('execution.timeout_seconds', 999)
        
        # All modified
        assert registry.resolve('debug.verbose_logging')[0] == True
        assert registry.resolve('debug.show_execution_time')[0] == True
        assert registry.resolve('execution.timeout_seconds')[0] == 999
        
        # Reset one
        ctx.reset('debug.verbose_logging')
        assert registry.resolve('debug.verbose_logging')[0] == False  # Back to default
    
    # All restored after context exits
```

---

## Using MockExecutionContext

For testing node worker methods:

```python
from haywire.core.di.test_config import MockExecutionContext


def test_node_logging():
    """Test that node logs correctly."""
    ctx = MockExecutionContext()
    
    # Simulate node behavior
    ctx.log("Starting process")
    ctx.log("Step 1 complete")
    ctx.warn("Low memory")
    ctx.error("Failed to connect")
    
    # Verify logs
    assert len(ctx.logs) == 2
    assert "Starting" in ctx.logs[0]
    assert len(ctx.warnings) == 1
    assert len(ctx.errors) == 1
    
    # Clear and reuse
    ctx.clear()
    assert len(ctx.logs) == 0


def test_node_with_context_data():
    """Test context data storage."""
    ctx = MockExecutionContext()
    
    ctx.set('input_path', '/path/to/file')
    ctx.set('batch_size', 100)
    
    assert ctx.get('input_path') == '/path/to/file'
    assert ctx.get('batch_size') == 100
    assert ctx.get('missing', 'default') == 'default'
```

---

## Integration Tests

### Full System Test

```python
from haywire.core.di.test_config import create_test_library_system


def test_full_system_with_settings():
    """Integration test with full library system."""
    service = create_test_library_system(
        load_libraries=True,
        use_temp_settings=True  # Isolated from user settings
    )
    
    # Test service methods
    service.set_setting('execution.auto_execute', False)
    assert service.get_setting('execution.auto_execute') == False
    
    # Test registry access
    registry = service.get_settings_registry()
    assert registry.has_definition('execution.auto_execute')
    
    # Test node factory creates nodes with settings
    factory = service.get_node_factory()
    # ... create and test nodes


def test_settings_persist_through_save_load():
    """Test that settings survive serialization."""
    service = create_test_library_system(load_libraries=False)
    registry = service.get_settings_registry()
    
    # Modify settings
    registry.set_global('ui.node.bg_color', '#ff0000')
    
    # Serialize
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.toml', delete=False) as f:
        registry.save_to_toml(f.name)
        
        # Create new registry and load
        new_registry = create_test_settings_registry()
        new_registry.load_from_toml(f.name)
        
        # Verify value persisted
        value, _ = new_registry.resolve('ui.node.bg_color')
        assert value == '#ff0000'
```

### Testing Node Settings

```python
def test_node_settings_integration():
    """Test node settings in realistic scenario."""
    from haywire.core.di.test_config import create_test_settings_holder
    from haywire.core.settings import SettingScope
    
    registry, holder = create_test_settings_holder(
        predefined_global={
            'debug.verbose_logging': False,
            'ui.node.bg_color': '#ffffff'
        }
    )
    
    # Simulate node initialization
    holder.define(
        'node.cache_size',
        default=100,
        scope=SettingScope.LOCAL_ONLY,
        min_value=10,
        max_value=1000
    )
    
    # Test access patterns
    assert holder['debug.verbose_logging'] == False
    assert holder['ui.node.bg_color'] == '#ffffff'
    assert holder['node.cache_size'] == 100
    
    # Test local override
    holder['ui.node.bg_color'] = '#ff0000'
    assert holder['ui.node.bg_color'] == '#ff0000'
    
    # Test reset
    holder.reset('ui.node.bg_color')
    assert holder['ui.node.bg_color'] == '#ffffff'
    
    # Test serialization
    data = holder.to_dict()
    
    # Create new holder and restore
    _, new_holder = create_test_settings_holder()
    new_holder.define('node.cache_size', 100, scope=SettingScope.LOCAL_ONLY)
    new_holder.from_dict(data)
    
    # Verify state restored
    assert new_holder['node.cache_size'] == 100
```

---

## Testing Validation

```python
import pytest


def test_validation_constraints():
    """Test that validation is enforced."""
    registry = create_test_settings_registry()
    
    # Test min/max
    with pytest.raises(ValueError):
        registry.set_global('ui.node.font_size', 1)  # Below min
    
    with pytest.raises(ValueError):
        registry.set_global('ui.node.font_size', 100)  # Above max
    
    # Test choices
    with pytest.raises(ValueError):
        registry.set_global('ui.edge.curve_style', 'invalid')


def test_custom_validator():
    """Test custom validation function."""
    def validate_even(value: int) -> bool:
        return value % 2 == 0
    
    registry = create_test_settings_registry(register_builtins=False)
    registry.define(
        'test.even_number',
        default=2,
        validator=validate_even
    )
    
    # Valid
    registry.set_global('test.even_number', 4)
    assert registry.resolve('test.even_number')[0] == 4
    
    # Invalid
    with pytest.raises(ValueError):
        registry.set_global('test.even_number', 3)
```

---

## Testing Change Callbacks

```python
def test_change_callbacks():
    """Test that change callbacks are fired."""
    registry, holder = create_test_settings_holder()
    
    changes = []
    
    def on_change(name, value, source):
        changes.append((name, value, source))
    
    holder.on_change(on_change)
    
    # Make changes
    holder.set('ui.node.bg_color', '#ff0000')
    holder.set('ui.node.font_size', 16)
    
    # Verify callbacks fired
    assert len(changes) == 2
    assert changes[0] == ('ui.node.bg_color', '#ff0000', 'local')
    assert changes[1] == ('ui.node.font_size', 16, 'local')


def test_global_change_propagates():
    """Test that global changes notify holders."""
    from haywire.core.settings import SettingMode
    
    registry, holder = create_test_settings_holder()
    
    changes = []
    holder.on_change(lambda n, v, s: changes.append((n, v, s)))
    
    # Change global setting
    registry.set_global('ui.node.bg_color', '#00ff00', SettingMode.SET)
    
    # Holder should be notified
    assert len(changes) == 1
    assert changes[0][0] == 'ui.node.bg_color'
```

---

## Pytest Fixtures

Create reusable fixtures for your test suite:

```python
# conftest.py
import pytest
from haywire.core.di.test_config import (
    create_test_settings_registry,
    create_test_settings_holder,
    create_test_library_system,
    SettingsTestContext,
    MockExecutionContext,
)
from haywire.core.settings import SettingsHolder


@pytest.fixture
def settings_registry():
    """Isolated settings registry for tests."""
    return create_test_settings_registry()


@pytest.fixture
def settings_holder(settings_registry):
    """Settings holder with registry."""
    return SettingsHolder(settings_registry, owner=None, owner_name='test')


@pytest.fixture
def library_system():
    """Full library system for integration tests."""
    return create_test_library_system(
        load_libraries=False,
        use_temp_settings=True
    )


@pytest.fixture
def settings_context(library_system):
    """Context manager for temporary setting changes."""
    registry = library_system.get_settings_registry()
    return SettingsTestContext(registry)


@pytest.fixture
def execution_context():
    """Mock execution context for node tests."""
    return MockExecutionContext()


# Usage in tests:

def test_with_fixtures(settings_registry, settings_holder):
    """Test using fixtures."""
    from haywire.core.settings import SettingScope
    
    settings_holder.define('test.option', 42, scope=SettingScope.LOCAL_ONLY)
    assert settings_holder['test.option'] == 42


def test_temporary_changes(library_system, settings_context):
    """Test with temporary changes."""
    with settings_context as ctx:
        ctx.set('debug.verbose_logging', True)
        # Test code here


def test_node_worker(execution_context):
    """Test node worker with mock context."""
    ctx = execution_context
    
    # Simulate worker
    ctx.log("Processing...")
    
    assert len(ctx.logs) == 1
```

---

## Testing Node Classes

```python
# tests/test_my_node.py
import pytest
from haywire.core.di.test_config import (
    create_test_settings_holder,
    MockExecutionContext,
)
from haywire.core.settings import SettingScope


class TestMyNode:
    """Tests for MyNode."""
    
    @pytest.fixture
    def node_settings(self):
        """Create settings holder for node tests."""
        registry, holder = create_test_settings_holder(
            predefined_global={
                'debug.verbose_logging': False,
                'execution.timeout_seconds': 60,
            }
        )
        
        # Define node-specific settings
        holder.define('my_node.multiplier', 1.0, scope=SettingScope.LOCAL_ONLY)
        holder.define('my_node.cache_enabled', True, scope=SettingScope.LOCAL_ONLY)
        
        return registry, holder
    
    @pytest.fixture
    def context(self):
        """Create mock execution context."""
        return MockExecutionContext()
    
    def test_default_settings(self, node_settings):
        """Test node works with default settings."""
        registry, holder = node_settings
        
        assert holder['my_node.multiplier'] == 1.0
        assert holder['my_node.cache_enabled'] == True
        assert holder['debug.verbose_logging'] == False
    
    def test_custom_multiplier(self, node_settings):
        """Test node with custom multiplier."""
        registry, holder = node_settings
        holder['my_node.multiplier'] = 2.5
        
        # Simulate worker logic
        input_value = 10.0
        result = input_value * holder['my_node.multiplier']
        
        assert result == 25.0
    
    def test_verbose_logging(self, node_settings, context):
        """Test verbose logging behavior."""
        registry, holder = node_settings
        
        # Without verbose logging
        if holder['debug.verbose_logging']:
            context.log("Processing...")
        assert len(context.logs) == 0
        
        # Enable verbose logging
        holder['debug.verbose_logging'] = True
        
        if holder['debug.verbose_logging']:
            context.log("Processing...")
        assert len(context.logs) == 1
    
    def test_global_override_respected(self, node_settings):
        """Test that global override is respected."""
        from haywire.core.settings import SettingMode
        
        registry, holder = node_settings
        
        # Set local value
        holder['debug.verbose_logging'] = True
        assert holder['debug.verbose_logging'] == True
        
        # Global override should win
        registry.set_global('debug.verbose_logging', False, SettingMode.OVERRIDE)
        assert holder['debug.verbose_logging'] == False
        
        # Check info shows override
        info = holder.get_info('debug.verbose_logging')
        assert info.is_overridden
    
    def test_settings_serialization(self, node_settings):
        """Test that settings serialize correctly."""
        registry, holder = node_settings
        
        # Modify some settings
        holder['my_node.multiplier'] = 3.0
        holder['my_node.cache_enabled'] = False
        
        # Serialize
        data = holder.to_dict()
        
        # Verify structure
        assert 'local_values' in data
        assert 'my_node.multiplier' in data['local_values']
        
        # Create new holder and restore
        _, new_holder = create_test_settings_holder()
        new_holder.define('my_node.multiplier', 1.0, scope=SettingScope.LOCAL_ONLY)
        new_holder.define('my_node.cache_enabled', True, scope=SettingScope.LOCAL_ONLY)
        new_holder.from_dict(data)
        
        # Verify restored
        assert new_holder['my_node.multiplier'] == 3.0
        assert new_holder['my_node.cache_enabled'] == False
```

---

## Summary

| Utility | Use Case |
|---------|----------|
| `create_test_settings_registry()` | Unit tests for settings logic |
| `create_test_settings_holder()` | Testing holder/resolution behavior |
| `create_test_library_system()` | Integration tests |
| `SettingsTestContext` | Temporary modifications with auto-restore |
| `MockExecutionContext` | Testing node workers |

**Best Practices:**

1. Always use `use_temp_settings=True` to isolate from user settings
2. Use fixtures for common setup
3. Test both default values and custom values
4. Test validation and error cases
5. Test serialization round-trips
6. Test change callbacks when relevant
7. Use `MockExecutionContext` for node worker tests
