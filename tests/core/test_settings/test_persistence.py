import haywire.core.graph.editor  # noqa: F401

import json

from haywire.core.settings.persistence import SettingsFileStore


def test_read_flattens_dot_keys(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"ui": {"node": {"bg": {"value": "#fff"}}}}))
    store = SettingsFileStore()
    assert store.read(p) == {"ui.node.bg": {"value": "#fff"}}


def test_read_returns_none_on_garbage(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{not json")
    assert SettingsFileStore().read(p) is None


def test_write_nests_and_roundtrips(tmp_path):
    p = tmp_path / "out" / "settings.json"
    store = SettingsFileStore()
    store.write(p, {"ui.node.bg": {"value": "#fff"}, "exec.threads": 4})
    data = json.loads(p.read_text())
    assert data == {"ui": {"node": {"bg": {"value": "#fff"}}}, "exec": {"threads": 4}}
