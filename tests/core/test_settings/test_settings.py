# Unit tests for the settings system
from haywire.core.settings import SettingMode
from haywire.core.di.test_config import (
    create_test_library_system,
    create_test_settings_holder,
    create_test_settings_registry,
    SettingsTestContext,
)


def test_node_uses_setting():
    """Values pre-set in the global registry are returned by resolve()."""
    registry = create_test_settings_registry({'ui.node.bg_color': '#ff0000'})

    value, source = registry.resolve('ui.node.bg_color')
    assert value == '#ff0000'
    assert source == 'global'


def test_local_overrides_global():
    """A local instance value beats a global SET value."""
    registry, holder = create_test_settings_holder(
        predefined_global={'test.node.bg_color': '#aaaaaa'},
        predefined_local={'bg_color': '#ff0000'},
    )

    assert holder.bg_color == '#ff0000'

    info = holder.get_info('bg_color')
    assert info.source == 'local'
    assert not info.is_overridden


def test_global_override_wins():
    """OVERRIDE mode in the workspace tier beats any local instance value."""
    registry, holder = create_test_settings_holder(
        predefined_local={'bg_color': '#ff0000'},
    )

    # workspace-tier OVERRIDE (set via UI) forces value on all nodes
    registry.set_global('test.node.bg_color', '#000000', SettingMode.OVERRIDE, tier='workspace')

    assert holder.bg_color == '#000000'

    info = holder.get_info('bg_color')
    assert info.is_overridden
    assert info.source == 'workspace_override'


def test_with_modified_settings():
    """SettingsTestContext restores original registry values after the block."""
    service = create_test_library_system(load_libraries=False)
    registry = service.get_settings_registry()

    with SettingsTestContext(registry) as ctx:
        ctx.set('debug.verbose_logging', True)
        ctx.set_override('ui.node.font_size', 20)

        assert registry.resolve('debug.verbose_logging')[0] is True
        assert registry.resolve('ui.node.font_size')[0] == 20

    assert registry.resolve('debug.verbose_logging')[0] is False
    assert registry.resolve('ui.node.font_size')[0] == 12


def test_full_system_with_settings():
    """Integration: set_setting / get_setting round-trip through the full DI stack."""
    service = create_test_library_system(load_libraries=True, use_temp_settings=True)

    service.set_setting('execution.auto_execute', False)

    assert service.get_setting('execution.auto_execute') is False