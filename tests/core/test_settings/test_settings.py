# Unit test for settings-dependent code
from haywire.core.di.test_config import create_test_library_system, create_test_settings_holder, create_test_settings_registry


def test_node_uses_setting():
    registry = create_test_settings_registry({
        'ui.node.bg_color': '#ff0000'
    })
    
    value, source = registry.resolve('ui.node.bg_color')
    assert value == '#ff0000'
    assert source == 'global'


# Test local vs global resolution
def test_local_overrides_global():
    registry, holder = create_test_settings_holder(
        predefined_global={'ui.node.bg_color': '#ffffff'},
        predefined_local={'ui.node.bg_color': '#ff0000'}
    )
    
    assert holder['ui.node.bg_color'] == '#ff0000'
    
    info = holder.get_info('ui.node.bg_color')
    assert info.source == 'local'
    assert not info.is_overridden


# Test global override behavior
def test_global_override_wins():
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


# Temporarily modify settings in a test
def test_with_modified_settings():
    service = create_test_library_system(load_libraries=False)
    registry = service.get_settings_registry()
    
    with SettingsTestContext(registry) as ctx:
        ctx.set('debug.verbose_logging', True)
        ctx.set_override('ui.node.font_size', 20)
        
        assert registry.resolve('debug.verbose_logging')[0] == True
        assert registry.resolve('ui.node.font_size')[0] == 20
    
    # Original values restored
    assert registry.resolve('debug.verbose_logging')[0] == False
    assert registry.resolve('ui.node.font_size')[0] == 12


# Integration test with full system
def test_full_system_with_settings():
    service = create_test_library_system(
        load_libraries=True,
        use_temp_settings=True  # Isolated from user settings
    )
    
    # Modify settings
    service.set_setting('execution.auto_execute', False)
    
    # Verify
    assert service.get_setting('execution.auto_execute') == False