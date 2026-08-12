# tests/core/test_settings/test_schema_rebasing.py
"""
Tests for FrameworkSettings and LibrarySettings rebased on Settings.

Verifies:
- FrameworkSettings/LibrarySettings extend Settings (setting descriptor works)
- _prop_fields() returns expected descriptors
- namespace= kwarg sets _setting_key on all settings
- Deep inheritance (subclassing a GS/LS subclass) raises TypeError
- Class-level access returns the setting descriptor (for mirrors=)
- Registry reads _prop_fields() correctly
"""

import pytest
from haywire.core.settings import setting, FrameworkSettings, LibrarySettings
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.decorator import settings
from haywire.barn.builtin.types import FLOAT, INT, STRING


# ---------------------------------------------------------------------------
# FrameworkSettings extends Settings
# ---------------------------------------------------------------------------


class TestFrameworkSettingsExtendsSettings:
    def test_prop_fields_returns_descriptors(self):
        class BarGS(FrameworkSettings, namespace="bar"):
            alpha = setting[INT](7, label="Alpha")
            beta = setting[STRING]("hello", label="Beta")

        fields = BarGS._property_settings()
        assert "alpha" in fields
        assert "beta" in fields
        assert isinstance(fields["alpha"], setting)
        assert isinstance(fields["beta"], setting)

    def test_namespace_sets_setting_key(self):
        class NsGS(FrameworkSettings, namespace="ns.test"):
            val = setting[FLOAT](3.14)

        fields = NsGS._property_settings()
        assert fields["val"]._setting_key == "ns.test.val"

    def test_class_level_access_returns_descriptor(self):
        """Class-level access returns the setting descriptor (used for mirrors=)."""

        class ClsGS(FrameworkSettings, namespace="cls.gs"):
            count = setting[INT](0)

        assert isinstance(ClsGS.count, setting)

    def test_no_namespace_does_not_set_setting_key(self):
        """Without namespace=, _setting_key is empty (set by decorator or register_schema)."""

        class NoNsGS(FrameworkSettings):
            val = setting[INT](5)

        fields = NoNsGS._property_settings()
        # _setting_key should NOT be set since no namespace
        assert fields["val"]._setting_key == ""


# ---------------------------------------------------------------------------
# LibrarySettings extends Settings
# ---------------------------------------------------------------------------


class TestLibrarySettingsExtendsSettings:
    def test_prop_fields_returns_descriptors(self):
        class FooLS(LibrarySettings):
            rate = setting[INT](4, min=1, max=20)

        fields = FooLS._property_settings()
        assert "rate" in fields
        assert isinstance(fields["rate"], setting)


# ---------------------------------------------------------------------------
# Deep inheritance blocking
# ---------------------------------------------------------------------------


class TestDeepInheritanceBlocked:
    def test_globalSettings_direct_subclass_allowed(self):
        """Directly subclassing FrameworkSettings must succeed and configure namespace."""

        class DirectGS(FrameworkSettings, namespace="direct.gs"):
            x = setting[INT](0)

        assert DirectGS._namespace == "direct.gs"

    def test_globalSettings_deep_subclass_raises(self):
        """Subclassing a FrameworkSettings subclass must raise TypeError."""

        class DirectGS(FrameworkSettings, namespace="deep.gs"):
            x = setting[INT](0)

        with pytest.raises(TypeError, match="Subclassing a FrameworkSettings subclass"):

            class DeepGS(DirectGS):
                y = setting[INT](1)

    def test_librarySettings_direct_subclass_allowed(self):
        """Directly subclassing LibrarySettings must succeed; descriptors are collected."""

        class DirectLS(LibrarySettings):
            x = setting[INT](0)

        assert "x" in DirectLS._property_settings()

    def test_librarySettings_deep_subclass_raises(self):
        """Subclassing a LibrarySettings subclass must raise TypeError."""

        class DirectLS(LibrarySettings):
            x = setting[INT](0)

        with pytest.raises(TypeError, match="Subclassing a LibrarySettings subclass"):

            class DeepLS(DirectLS):
                y = setting[INT](1)


# ---------------------------------------------------------------------------
# Registry integration: _prop_fields()
# ---------------------------------------------------------------------------


class TestRegistryReadsPropFields:
    def test_register_schema_reads_prop_fields(self):
        """register_schema() correctly reads _prop_fields() from FrameworkSettings class."""

        class RegGS(FrameworkSettings, namespace="reg.gs"):
            value = setting[INT](99)

        registry = SettingsRegistry()
        registry.register_schema(RegGS)

        val, _ = registry.resolve("reg.gs.value")
        assert val == 99

    def test_define_returns_setting_instance(self):
        """registry.define() returns a setting instance."""
        registry = SettingsRegistry()
        d = registry.define("prog.val", 42, type_=INT)
        assert isinstance(d, setting)
        assert d._default == 42

    def test_auto_define_creates_setting_instance(self):
        """JSON auto-define creates setting instances."""
        import json
        import tempfile
        import os

        registry = SettingsRegistry()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json.dumps({"auto": {"val": 123}}))
            path = f.name

        try:
            registry.load_from_json(path, tier="workspace")
            defn = registry.get_definition("auto.val")
            assert defn is not None
            assert isinstance(defn, setting)
            assert defn._default == 123
        finally:
            os.unlink(path)

    def test_auto_define_with_choices_speaks_choices_type(self):
        """A settings-file entry with 'choices' auto-defines as setting[CHOICES] —
        widget_key is SELECT_WIDGET and options land in widget_config."""
        import json
        import tempfile
        import os

        from haywire.barn.builtin import widget_keys

        registry = SettingsRegistry()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json.dumps({"custom": {"pick": {"value": "a", "choices": ["a", "b"], "type": "str"}}}))
            path = f.name

        try:
            registry.load_from_json(path, tier="workspace")
            defn = registry.get_definition("custom.pick")
            assert defn is not None
            assert defn.widget_key == widget_keys.SELECT_WIDGET
            assert defn.widget_config["properties"]["options"] == ["a", "b"]
        finally:
            os.unlink(path)

    def test_settings_decorator_sets_setting_keys(self):
        """@settings decorator sets _setting_key on all settings via _prop_fields()."""

        @settings(namespace="dec.ls")
        class DecLS(LibrarySettings):
            speed = setting[FLOAT](1.0)
            mode = setting[STRING]("fast")

        fields = DecLS._property_settings()
        assert fields["speed"]._setting_key == "dec.ls.speed"
        assert fields["mode"]._setting_key == "dec.ls.mode"

    def test_no_setting_descriptor_in_codebase(self):
        """SettingDescriptor no longer exists — importing it raises ImportError."""
        with pytest.raises(ImportError):
            from haywire.core.settings.descriptors import (  # type: ignore[import-untyped,import-not-found]  # noqa: F401
                SettingDescriptor,
            )
