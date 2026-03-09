# tests/core/test_settings/test_holder_cache.py
"""Tests for SettingsHolder attribute access, caching, and serialization."""

import pytest
from haywire.core.settings.enums import SettingMode
from haywire.core.di.test_config import create_test_settings_holder


# ---------------------------------------------------------------------------
# Basic attribute access
# ---------------------------------------------------------------------------

class TestHolderAccess:

    def test_default_returned_when_nothing_set(self):
        _, holder = create_test_settings_holder()
        assert holder.test.bg_color == '#ffffff'

    def test_local_override_returned(self):
        _, holder = create_test_settings_holder(
            predefined_local={'bg_color': '#ff0000'},
        )
        assert holder.test.bg_color == '#ff0000'

    def test_global_value_returned(self):
        _, holder = create_test_settings_holder(
            predefined_global={'test.node.bg_color': '#00ff00'},
        )
        assert holder.test.bg_color == '#00ff00'

    def test_local_beats_global(self):
        _, holder = create_test_settings_holder(
            predefined_global={'test.node.bg_color': '#00ff00'},
            predefined_local={'bg_color': '#0000ff'},
        )
        assert holder.test.bg_color == '#0000ff'

    def test_missing_field_raises(self):
        _, holder = create_test_settings_holder()
        with pytest.raises(AttributeError):
            _ = holder.test.nonexistent_field

    def test_multiple_fields(self):
        _, holder = create_test_settings_holder(
            predefined_local={'bg_color': '#aabbcc', 'font_size': 18},
        )
        assert holder.test.bg_color  == '#aabbcc'
        assert holder.test.font_size == 18

    def test_bool_field(self):
        _, holder = create_test_settings_holder(
            predefined_local={'verbose': True},
        )
        assert holder.test.verbose is True


# ---------------------------------------------------------------------------
# Caching (cache key is attr_name, not full_key)
# ---------------------------------------------------------------------------

class TestHolderCaching:

    def test_value_cached_after_first_access(self):
        _, holder = create_test_settings_holder()
        _ = holder.test.bg_color          # prime cache
        cache = object.__getattribute__(holder.test, '_cache')
        assert 'bg_color' in cache        # cache key = attr_name

    def test_cache_cleared_on_set(self):
        _, holder = create_test_settings_holder()
        _ = holder.test.bg_color          # prime cache
        holder.test.set('bg_color', '#aabbcc')
        assert holder.test.bg_color == '#aabbcc'

    def test_cache_cleared_on_reset(self):
        _, holder = create_test_settings_holder(
            predefined_local={'bg_color': '#ff0000'},
        )
        assert holder.test.bg_color == '#ff0000'
        holder.test.reset('bg_color')
        assert holder.test.bg_color == '#ffffff'   # back to default

    def test_is_locally_set(self):
        _, holder = create_test_settings_holder()
        assert not holder.test.is_locally_set('bg_color')
        holder.test.set('bg_color', '#112233')
        assert holder.test.is_locally_set('bg_color')


# ---------------------------------------------------------------------------
# get_info()
# ---------------------------------------------------------------------------

class TestHolderGetInfo:

    def test_source_default(self):
        _, holder = create_test_settings_holder()
        info = holder.test.get_info('bg_color')
        assert info.source == 'default'
        assert info.is_inherited is True
        assert info.is_overridden is False

    def test_source_local(self):
        _, holder = create_test_settings_holder(
            predefined_local={'bg_color': '#ff0000'},
        )
        info = holder.test.get_info('bg_color')
        assert info.source == 'local'
        assert info.is_inherited is False

    def test_source_global(self):
        _, holder = create_test_settings_holder(
            predefined_global={'test.node.bg_color': '#00ff00'},
        )
        info = holder.test.get_info('bg_color')
        assert info.source == 'global'
        assert info.is_inherited is True

    def test_source_workspace_override(self):
        registry, holder = create_test_settings_holder()
        registry.set_global('test.node.bg_color', '#000000', SettingMode.OVERRIDE, tier='workspace')
        info = holder.test.get_info('bg_color')
        assert info.source == 'workspace_override'
        assert info.is_overridden is True

    def test_source_global_override(self):
        registry, holder = create_test_settings_holder()
        registry.set_global('test.node.bg_color', '#000000', SettingMode.OVERRIDE, tier='global')
        info = holder.test.get_info('bg_color')
        assert info.source == 'global_override'
        assert info.is_overridden is True

    def test_definition_attached(self):
        _, holder = create_test_settings_holder()
        info = holder.test.get_info('bg_color')
        assert info.definition is not None
        assert info.definition._label == 'Background Color'

    def test_value_correct_in_info(self):
        _, holder = create_test_settings_holder(
            predefined_local={'bg_color': '#112233'},
        )
        info = holder.test.get_info('bg_color')
        assert info.value == '#112233'


# ---------------------------------------------------------------------------
# Serialization  (methods: to_dict / from_dict)
# ---------------------------------------------------------------------------

class TestHolderSerialization:

    def test_to_dict_empty(self):
        _, holder = create_test_settings_holder()
        data = holder.test.to_dict()
        assert 'schema_values' in data
        assert data['schema_values'] == {}

    def test_to_dict_with_local_override(self):
        _, holder = create_test_settings_holder(
            predefined_local={'bg_color': '#ff0000'},
        )
        data = holder.test.to_dict()
        assert data['schema_values'].get('bg_color') == '#ff0000'

    def test_from_dict_restores_value(self):
        _, holder = create_test_settings_holder()
        holder.test.from_dict({'schema_values': {'bg_color': '#aabbcc'}})
        assert holder.test.bg_color == '#aabbcc'

    def test_round_trip(self):
        _, holder = create_test_settings_holder()
        holder.test.set('bg_color', '#112233')
        data = holder.test.to_dict()

        _, holder2 = create_test_settings_holder()
        holder2.test.from_dict(data)
        assert holder2.test.bg_color == '#112233'

    def test_to_dict_does_not_include_global_values(self):
        """Values not locally overridden must not appear in to_dict output."""
        _, holder = create_test_settings_holder(
            predefined_global={'test.node.bg_color': '#009900'},
        )
        data = holder.test.to_dict()
        # global SET value is not serialized — only local overrides are
        assert 'bg_color' not in data['schema_values']
