# tests/core/test_settings/test_schema_rebasing.py
"""
Tests for GlobalSettings and LibrarySettings rebased on Settings.

Verifies:
- GlobalSettings/LibrarySettings extend Settings (setting descriptor works)
- _prop_fields() returns expected descriptors
- namespace= kwarg sets _field_key on all settings
- Deep inheritance (subclassing a GS/LS subclass) raises TypeError
- Class-level access returns the setting descriptor (for mirrors=)
- Registry reads _prop_fields() correctly
"""

import pytest
from haywire.core.settings import Settings, setting, GlobalSettings, LibrarySettings, FieldDescriptor
from haywire.core.settings.registry import GlobalSettingsRegistry
from haywire.core.settings.decorator import settings


# ---------------------------------------------------------------------------
# GlobalSettings extends Settings
# ---------------------------------------------------------------------------


class TestGlobalSettingsExtendsSettings:
    def test_globalSettings_is_settings_subclass(self):
        assert issubclass(GlobalSettings, Settings)

    def test_direct_subclass_is_settings_subclass(self):
        class FooGS(GlobalSettings, namespace="foo"):
            x: int = setting(1)

        assert issubclass(FooGS, Settings)

    def test_prop_fields_returns_descriptors(self):
        class BarGS(GlobalSettings, namespace="bar"):
            alpha: int = setting(7, label="Alpha")
            beta: str = setting("hello", label="Beta")

        fields = BarGS._prop_fields()
        assert "alpha" in fields
        assert "beta" in fields
        assert isinstance(fields["alpha"], setting)
        assert isinstance(fields["beta"], setting)

    def test_namespace_sets_field_key(self):
        class NsGS(GlobalSettings, namespace="ns.test"):
            val: float = setting(3.14)

        fields = NsGS._prop_fields()
        assert fields["val"]._field_key == "ns.test.val"

    def test_class_level_access_returns_descriptor(self):
        """Class-level access returns the setting descriptor (used for mirrors=)."""

        class ClsGS(GlobalSettings, namespace="cls.gs"):
            count: int = setting(0)

        assert isinstance(ClsGS.count, setting)

    def test_no_namespace_does_not_set_field_key(self):
        """Without namespace=, _field_key is empty (set by decorator or register_schema)."""

        class NoNsGS(GlobalSettings):
            val: int = setting(5)

        fields = NoNsGS._prop_fields()
        # _field_key should NOT be set since no namespace
        assert fields["val"]._field_key == ""


# ---------------------------------------------------------------------------
# LibrarySettings extends Settings
# ---------------------------------------------------------------------------


class TestLibrarySettingsExtendsSettings:
    def test_librarySettings_is_settings_subclass(self):
        assert issubclass(LibrarySettings, Settings)

    def test_prop_fields_returns_descriptors(self):
        class FooLS(LibrarySettings):
            rate: int = setting(4, min=1, max=20)

        fields = FooLS._prop_fields()
        assert "rate" in fields
        assert isinstance(fields["rate"], setting)


# ---------------------------------------------------------------------------
# Deep inheritance blocking
# ---------------------------------------------------------------------------


class TestDeepInheritanceBlocked:
    def test_globalSettings_direct_subclass_allowed(self):
        """Directly subclassing GlobalSettings must succeed."""

        class DirectGS(GlobalSettings, namespace="direct.gs"):
            x: int = setting(0)

        assert issubclass(DirectGS, GlobalSettings)

    def test_globalSettings_deep_subclass_raises(self):
        """Subclassing a GlobalSettings subclass must raise TypeError."""

        class DirectGS(GlobalSettings, namespace="deep.gs"):
            x: int = setting(0)

        with pytest.raises(TypeError, match="Subclassing a GlobalSettings subclass"):

            class DeepGS(DirectGS):
                y: int = setting(1)

    def test_librarySettings_direct_subclass_allowed(self):
        """Directly subclassing LibrarySettings must succeed."""

        class DirectLS(LibrarySettings):
            x: int = setting(0)

        assert issubclass(DirectLS, LibrarySettings)

    def test_librarySettings_deep_subclass_raises(self):
        """Subclassing a LibrarySettings subclass must raise TypeError."""

        class DirectLS(LibrarySettings):
            x: int = setting(0)

        with pytest.raises(TypeError, match="Subclassing a LibrarySettings subclass"):

            class DeepLS(DirectLS):
                y: int = setting(1)


# ---------------------------------------------------------------------------
# Registry integration: _prop_fields()
# ---------------------------------------------------------------------------


class TestRegistryReadsPropFields:
    def test_register_schema_reads_prop_fields(self):
        """register_schema() correctly reads _prop_fields() from GlobalSettings class."""

        class RegGS(GlobalSettings, namespace="reg.gs"):
            value: int = setting(99)

        registry = GlobalSettingsRegistry()
        registry.register_schema(RegGS)

        val, _ = registry.resolve("reg.gs.value")
        assert val == 99

    def test_define_returns_setting_instance(self):
        """registry.define() returns a setting instance."""
        registry = GlobalSettingsRegistry()
        d = registry.define("prog.val", 42)
        assert isinstance(d, setting)
        assert d._default == 42

    def test_auto_define_creates_setting_instance(self):
        """TOML auto-define creates setting instances."""
        import importlib.util
        import tempfile
        import os

        if importlib.util.find_spec("toml") is None:
            pytest.skip("toml not installed")

        registry = GlobalSettingsRegistry()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[auto]\nval = 123\n")
            path = f.name

        try:
            registry.load_from_toml(path, tier="workspace")
            defn = registry.get_definition("auto.val")
            assert defn is not None
            assert isinstance(defn, setting)
            assert defn._default == 123
        finally:
            os.unlink(path)

    def test_settings_decorator_sets_field_keys(self):
        """@settings decorator sets _field_key on all settings via _prop_fields()."""

        @settings(namespace="dec.ls")
        class DecLS(LibrarySettings):
            speed: float = setting(1.0)
            mode: str = setting("fast")

        fields = DecLS._prop_fields()
        assert fields["speed"]._field_key == "dec.ls.speed"
        assert fields["mode"]._field_key == "dec.ls.mode"

    def test_no_setting_descriptor_in_codebase(self):
        """SettingDescriptor no longer exists — importing it raises ImportError."""
        with pytest.raises(ImportError):
            from haywire.core.settings.descriptors import SettingDescriptor  # noqa: F401
