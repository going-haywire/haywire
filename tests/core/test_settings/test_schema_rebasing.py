# tests/core/test_settings/test_schema_rebasing.py
"""
Tests for FrameworkSettings and LibrarySettings rebased on Settings.

Verifies:
- FrameworkSettings/LibrarySettings extend Settings (setting descriptor works)
- _prop_fields() returns expected descriptors
- namespace= kwarg sets _field_key on all settings
- Deep inheritance (subclassing a GS/LS subclass) raises TypeError
- Class-level access returns the setting descriptor (for mirrors=)
- Registry reads _prop_fields() correctly
"""

import pytest
from haywire.core.settings import Settings, field, FrameworkSettings, LibrarySettings
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.decorator import settings


# ---------------------------------------------------------------------------
# FrameworkSettings extends Settings
# ---------------------------------------------------------------------------


class TestFrameworkSettingsExtendsSettings:
    def test_globalSettings_is_settings_subclass(self):
        assert issubclass(FrameworkSettings, Settings)

    def test_direct_subclass_is_settings_subclass(self):
        class FooGS(FrameworkSettings, namespace="foo"):
            x: int = field(1)

        assert issubclass(FooGS, Settings)

    def test_prop_fields_returns_descriptors(self):
        class BarGS(FrameworkSettings, namespace="bar"):
            alpha: int = field(7, label="Alpha")
            beta: str = field("hello", label="Beta")

        fields = BarGS._property_fields()
        assert "alpha" in fields
        assert "beta" in fields
        assert isinstance(fields["alpha"], field)
        assert isinstance(fields["beta"], field)

    def test_namespace_sets_field_key(self):
        class NsGS(FrameworkSettings, namespace="ns.test"):
            val: float = field(3.14)

        fields = NsGS._property_fields()
        assert fields["val"]._field_key == "ns.test.val"

    def test_class_level_access_returns_descriptor(self):
        """Class-level access returns the setting descriptor (used for mirrors=)."""

        class ClsGS(FrameworkSettings, namespace="cls.gs"):
            count: int = field(0)

        assert isinstance(ClsGS.count, field)

    def test_no_namespace_does_not_set_field_key(self):
        """Without namespace=, _field_key is empty (set by decorator or register_schema)."""

        class NoNsGS(FrameworkSettings):
            val: int = field(5)

        fields = NoNsGS._property_fields()
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
            rate: int = field(4, min=1, max=20)

        fields = FooLS._property_fields()
        assert "rate" in fields
        assert isinstance(fields["rate"], field)


# ---------------------------------------------------------------------------
# Deep inheritance blocking
# ---------------------------------------------------------------------------


class TestDeepInheritanceBlocked:
    def test_globalSettings_direct_subclass_allowed(self):
        """Directly subclassing FrameworkSettings must succeed."""

        class DirectGS(FrameworkSettings, namespace="direct.gs"):
            x: int = field(0)

        assert issubclass(DirectGS, FrameworkSettings)

    def test_globalSettings_deep_subclass_raises(self):
        """Subclassing a FrameworkSettings subclass must raise TypeError."""

        class DirectGS(FrameworkSettings, namespace="deep.gs"):
            x: int = field(0)

        with pytest.raises(TypeError, match="Subclassing a FrameworkSettings subclass"):

            class DeepGS(DirectGS):
                y: int = field(1)

    def test_librarySettings_direct_subclass_allowed(self):
        """Directly subclassing LibrarySettings must succeed."""

        class DirectLS(LibrarySettings):
            x: int = field(0)

        assert issubclass(DirectLS, LibrarySettings)

    def test_librarySettings_deep_subclass_raises(self):
        """Subclassing a LibrarySettings subclass must raise TypeError."""

        class DirectLS(LibrarySettings):
            x: int = field(0)

        with pytest.raises(TypeError, match="Subclassing a LibrarySettings subclass"):

            class DeepLS(DirectLS):
                y: int = field(1)


# ---------------------------------------------------------------------------
# Registry integration: _prop_fields()
# ---------------------------------------------------------------------------


class TestRegistryReadsPropFields:
    def test_register_schema_reads_prop_fields(self):
        """register_schema() correctly reads _prop_fields() from FrameworkSettings class."""

        class RegGS(FrameworkSettings, namespace="reg.gs"):
            value: int = field(99)

        registry = SettingsRegistry()
        registry.register_schema(RegGS)

        val, _ = registry.resolve("reg.gs.value")
        assert val == 99

    def test_define_returns_setting_instance(self):
        """registry.define() returns a setting instance."""
        registry = SettingsRegistry()
        d = registry.define("prog.val", 42)
        assert isinstance(d, field)
        assert d._default == 42

    def test_auto_define_creates_setting_instance(self):
        """TOML auto-define creates setting instances."""
        import importlib.util
        import tempfile
        import os

        if importlib.util.find_spec("toml") is None:
            pytest.skip("toml not installed")

        registry = SettingsRegistry()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[auto]\nval = 123\n")
            path = f.name

        try:
            registry.load_from_toml(path, tier="workspace")
            defn = registry.get_definition("auto.val")
            assert defn is not None
            assert isinstance(defn, field)
            assert defn._default == 123
        finally:
            os.unlink(path)

    def test_settings_decorator_sets_field_keys(self):
        """@settings decorator sets _field_key on all settings via _prop_fields()."""

        @settings(namespace="dec.ls")
        class DecLS(LibrarySettings):
            speed: float = field(1.0)
            mode: str = field("fast")

        fields = DecLS._property_fields()
        assert fields["speed"]._field_key == "dec.ls.speed"
        assert fields["mode"]._field_key == "dec.ls.mode"

    def test_no_setting_descriptor_in_codebase(self):
        """SettingDescriptor no longer exists — importing it raises ImportError."""
        with pytest.raises(ImportError):
            from haywire.core.settings.descriptors import SettingDescriptor  # noqa: F401
