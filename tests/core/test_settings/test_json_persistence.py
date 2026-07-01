# tests/core/test_settings/test_json_persistence.py
"""P3: settings persist as JSON; complex ITypes round-trip via to_dict/from_dict."""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard, per CLAUDE.md)

from pathlib import Path

from haywire.barn.builtin.types import COLOR, INT, VEC2I
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.settings.types import Vec2i


class TestJsonableSeam:
    def test_scalar_passthrough(self):
        reg = SettingsRegistry()
        reg.define("ui.threads", 4, type_=INT)
        # INT serializes through its to_dict shape; round-trips back to the int.
        raw = reg._value_to_jsonable("ui.threads", 8)
        assert reg._value_from_jsonable("ui.threads", raw) == 8

    def test_color_roundtrip(self):
        reg = SettingsRegistry()
        reg.define("ui.tint", "#ffffff", type_=COLOR)
        raw = reg._value_to_jsonable("ui.tint", "#abcdef")
        assert reg._value_from_jsonable("ui.tint", raw) == "#abcdef"

    def test_vec_roundtrip(self):
        reg = SettingsRegistry()
        reg.define("ui.offset", Vec2i([0, 0]), type_=VEC2I)
        raw = reg._value_to_jsonable("ui.offset", Vec2i([3, 4]))
        restored = reg._value_from_jsonable("ui.offset", raw)
        assert list(restored) == [3, 4]

    def test_unknown_key_passthrough(self):
        reg = SettingsRegistry()
        # No definition → value passes through untouched (auto-defined TOML keys).
        assert reg._value_to_jsonable("not.defined", 7) == 7
        assert reg._value_from_jsonable("not.defined", 7) == 7


class TestSaveJson:
    def test_save_writes_nested_json(self, tmp_path: Path):
        reg = SettingsRegistry()
        reg.define("exec.threads", 4, type_=INT)
        reg.set_global("exec.threads", 16, tier="workspace")
        out = tmp_path / "settings.json"
        reg.save_to_json(out)

        import json

        data = json.loads(out.read_text())
        # INT to_dict shape, nested under exec.threads
        assert data["exec"]["threads"] == {"value": 16}

    def test_save_writes_color_to_dict(self, tmp_path: Path):
        reg = SettingsRegistry()
        reg.define("ui.tint", "#ffffff", type_=COLOR)
        reg.set_global("ui.tint", "#abcdef", tier="workspace")
        out = tmp_path / "settings.json"
        reg.save_to_json(out)

        import json

        data = json.loads(out.read_text())
        assert data["ui"]["tint"] == {"value": "#abcdef"}


class TestLoadJson:
    def test_roundtrip_color_through_disk(self, tmp_path: Path):
        out = tmp_path / "settings.json"

        reg1 = SettingsRegistry()
        reg1.define("ui.tint", "#ffffff", type_=COLOR)
        reg1.set_global("ui.tint", "#abcdef", tier="workspace")
        reg1.save_to_json(out)

        reg2 = SettingsRegistry()
        reg2.define("ui.tint", "#ffffff", type_=COLOR)
        reg2.load_from_json(out, tier="workspace")
        assert reg2.resolve("ui.tint") == ("#abcdef", "workspace")

    def test_roundtrip_vec_through_disk(self, tmp_path: Path):
        out = tmp_path / "settings.json"

        reg1 = SettingsRegistry()
        reg1.define("ui.offset", Vec2i([0, 0]), type_=VEC2I)
        reg1.set_global("ui.offset", Vec2i([3, 4]), tier="workspace")
        reg1.save_to_json(out)

        reg2 = SettingsRegistry()
        reg2.define("ui.offset", Vec2i([0, 0]), type_=VEC2I)
        reg2.load_from_json(out, tier="workspace")
        value, source = reg2.resolve("ui.offset")
        assert list(value) == [3, 4]
        assert source == "workspace"
