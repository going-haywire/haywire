# tests/core/test_settings/test_hot_reload.py
"""Tests for GlobalSettingsRegistry hot-reload: register_schema / unregister."""

import pytest
from haywire.core.settings.descriptors import setting
from haywire.core.settings.schema import GlobalSettings, LibrarySettings
from haywire.core.settings.decorator import settings
from haywire.core.settings.enums import SettingMode
from haywire.core.settings.registry import GlobalSettingsRegistry


# ---------------------------------------------------------------------------
# register_schema for GlobalSettings
# ---------------------------------------------------------------------------

class _HotGS(GlobalSettings, namespace='hot.gs'):
    alpha: int = setting(7, label='Alpha')
    beta: str  = setting('abc', label='Beta')


class TestRegisterSchema:

    def test_register_defines_fields(self):
        registry = GlobalSettingsRegistry()
        registry.register_schema(_HotGS)

        val_alpha, _ = registry.resolve('hot.gs.alpha')
        assert val_alpha == 7

        val_beta, _ = registry.resolve('hot.gs.beta')
        assert val_beta == 'abc'

    def test_registered_field_setable(self):
        registry = GlobalSettingsRegistry()
        registry.register_schema(_HotGS)

        registry.set_global('hot.gs.alpha', 42, SettingMode.SET)
        val, _ = registry.resolve('hot.gs.alpha')
        assert val == 42

    def test_class_identity_created_on_register(self):
        registry = GlobalSettingsRegistry()
        registry.register_schema(_HotGS)

        assert hasattr(_HotGS, 'class_identity')
        assert _HotGS.class_identity.namespace == 'hot.gs'


# ---------------------------------------------------------------------------
# register_schema for LibrarySettings
# ---------------------------------------------------------------------------

@settings(namespace='hot.lib')
class _HotLib(LibrarySettings):
    rate: int = setting(4, min=1, max=20)


class TestRegisterLibrarySchema:

    def test_library_schema_fields_registered(self):
        registry = GlobalSettingsRegistry()
        registry.register_schema(_HotLib)

        val, _ = registry.resolve('hot.lib.rate')
        assert val == 4

    def test_existing_class_identity_preserved(self):
        """@settings already set class_identity; register_schema must not overwrite."""
        registry = GlobalSettingsRegistry()
        original_key = _HotLib.class_identity.registry_key
        registry.register_schema(_HotLib)
        assert _HotLib.class_identity.registry_key == original_key


# ---------------------------------------------------------------------------
# Unregister / hot-reload cycle
# ---------------------------------------------------------------------------

class TestHotReloadCycle:

    def test_fields_gone_after_unregister(self):
        registry = GlobalSettingsRegistry()
        registry.register_schema(_HotGS)
        registry.set_global('hot.gs.alpha', 42, SettingMode.SET)

        # Simulate unregister (library removal)
        registry_key = _HotGS.class_identity.registry_key
        registry._unregister_class(registry_key)

        # Definition should be gone; registry.resolve raises KeyError
        assert not registry.has_definition('hot.gs.alpha')

    def test_re_register_restores_defaults(self):
        registry = GlobalSettingsRegistry()
        registry.register_schema(_HotGS)
        registry.set_global('hot.gs.alpha', 42, SettingMode.SET)

        registry_key = _HotGS.class_identity.registry_key
        registry._unregister_class(registry_key)

        # Re-register — default resumes
        registry.register_schema(_HotGS)
        val, _ = registry.resolve('hot.gs.alpha')
        assert val == 7   # back to schema default
