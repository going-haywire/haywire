# tests/core/test_settings/test_tier_collapse.py
"""Tests for the P2 tier-collapse: OVERRIDE dropped, tiers are set-or-unset."""

from pathlib import Path

import pytest

from haywire.barn.builtin.types import INT
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.value import SettingValue


def _reg_with(name="exec.threads", default=4):
    reg = SettingsRegistry()
    reg.define(name, default, type_=INT)
    return reg, name


class TestSettingValueSetUnset:
    def test_unset_is_not_set(self):
        sv = SettingValue.unset()
        assert sv.is_set is False
        assert sv.value is None

    def test_of_is_set(self):
        sv = SettingValue.of(42)
        assert sv.is_set is True
        assert sv.value == 42

    def test_default_construction_is_unset(self):
        assert SettingValue().is_set is False

    def test_roundtrip_set(self):
        sv = SettingValue.of("#aabbcc")
        assert SettingValue.from_dict(sv.to_dict()) == sv

    def test_roundtrip_unset(self):
        sv = SettingValue.unset()
        assert sv.to_dict() == {}
        assert SettingValue.from_dict({}) == sv

    def test_no_mode_attribute(self):
        assert not hasattr(SettingValue.of(1), "mode")


class TestResolutionCollapse:
    def test_default_when_no_tier_set(self):
        reg, name = _reg_with()
        assert reg.resolve(name) == (4, "default")

    def test_global_set_beats_default(self):
        reg, name = _reg_with()
        reg.set_global(name, 8, tier="global")
        assert reg.resolve(name) == (8, "global")

    def test_workspace_set_beats_global_set(self):
        reg, name = _reg_with()
        reg.set_global(name, 8, tier="global")
        reg.set_global(name, 16, tier="workspace")
        assert reg.resolve(name) == (16, "workspace")

    def test_local_beats_workspace(self):
        reg, name = _reg_with()
        reg.set_global(name, 16, tier="workspace")
        assert reg.resolve(name, local=SettingValue.of(32)) == (32, "local")

    def test_unset_local_falls_through(self):
        reg, name = _reg_with()
        reg.set_global(name, 16, tier="workspace")
        assert reg.resolve(name, local=SettingValue.unset()) == (16, "workspace")

    def test_set_global_rejects_mode_kwarg(self):
        reg, name = _reg_with()
        with pytest.raises(TypeError):
            reg.set_global(name, 8, mode="anything")  # type: ignore[call-arg]

    def test_reset_global_returns_to_default(self):
        reg, name = _reg_with()
        reg.set_global(name, 8, tier="workspace")
        reg.reset_global(name, tier="workspace")
        assert reg.resolve(name) == (4, "default")


class TestJsonNoOverride:
    def test_save_writes_to_dict_value(self, tmp_path: Path):
        reg, name = _reg_with("exec.threads", 4)
        reg.set_global(name, 16, tier="workspace")
        out = tmp_path / "settings.json"
        reg.save_to_json(out)
        import json

        data = json.loads(out.read_text())
        # nested under exec.threads, IType to_dict form — never an {override,value} table
        assert data["exec"]["threads"] == {"value": 16}

    def test_load_ignores_override_key_as_plain_set(self, tmp_path: Path):
        # A legacy {override=true, value=…} table loads as a *set* value, not a forced one.
        import json

        out = tmp_path / "settings.json"
        out.write_text(json.dumps({"exec": {"threads": {"override": True, "value": 99}}}))
        reg, name = _reg_with("exec.threads", 4)
        reg.load_from_json(out, tier="workspace")
        # value comes through; no OVERRIDE semantics remain (it's just a workspace set)
        assert reg.resolve(name) == (99, "workspace")


class TestSettingModeRemoved:
    def test_settingmode_not_exported(self):
        import haywire.core.settings as s

        assert not hasattr(s, "SettingMode")

    def test_settingmode_enum_gone(self):
        with pytest.raises(ImportError):
            from haywire.core.settings.enums import SettingMode  # noqa: F401
