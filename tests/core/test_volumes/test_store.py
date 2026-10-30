import threading
from pathlib import Path

import pytest

from haywire.core.di import context
from haywire.core.volumes import (
    PROJECT_KEY,
    VolumeEntry,
    VolumeStore,
    ensure_volume,
    user_volume_key,
)

pytestmark = pytest.mark.unit

MODELS = "haybale-models:volume:models"


def _keys(store):
    return [e.key for e in store.entries()]


def test_missing_file_lists_only_project(volume_store):
    assert _keys(volume_store) == [PROJECT_KEY]


def test_add_is_seen_by_a_fresh_store(tmp_path, volume_store):
    volume_store.add(MODELS, label="Models", description="Weights", location=tmp_path / "m")
    fresh = VolumeStore(volume_store.path)
    assert fresh.entry(MODELS) == VolumeEntry(MODELS, "Models", "Weights", tmp_path / "m")


def test_entries_sorted_by_label_after_project(tmp_path, volume_store):
    volume_store.add("user:volume:b", label="beta", description="", location=tmp_path)
    volume_store.add("user:volume:a", label="Alpha", description="", location=tmp_path)
    assert _keys(volume_store) == [PROJECT_KEY, "user:volume:a", "user:volume:b"]


def test_update_changes_only_the_given_fields(tmp_path, volume_store):
    volume_store.add(MODELS, label="Models", description="Weights", location=tmp_path / "m")
    volume_store.update(MODELS, label="My models")
    assert volume_store.entry(MODELS) == VolumeEntry(MODELS, "My models", "Weights", tmp_path / "m")
    volume_store.update(MODELS, location=tmp_path / "n", description="")
    assert volume_store.entry(MODELS) == VolumeEntry(MODELS, "My models", "", tmp_path / "n")


@pytest.mark.parametrize("op", ["add", "update", "remove", "ensure"])
def test_project_cannot_be_written(tmp_path, volume_store, op):
    kwargs = {"label": "P", "description": "", "location": tmp_path}
    calls = {
        "add": lambda: volume_store.add(PROJECT_KEY, **kwargs),
        "update": lambda: volume_store.update(PROJECT_KEY, label="P"),
        "remove": lambda: volume_store.remove(PROJECT_KEY),
        "ensure": lambda: volume_store.ensure(PROJECT_KEY, **kwargs),
    }
    with pytest.raises(ValueError, match="project"):
        calls[op]()


@pytest.mark.parametrize("key", ["models", "Bad:volume:x", "lib:volumes:x", "lib:volume:X", "lib:volume:"])
def test_invalid_key_is_refused(tmp_path, volume_store, key):
    with pytest.raises(ValueError, match="key"):
        volume_store.add(key, label="x", description="", location=tmp_path)


def test_relative_location_is_refused(volume_store):
    with pytest.raises(ValueError, match="absolute"):
        volume_store.add(MODELS, label="M", description="", location=Path("rel"))
    volume_store.add(MODELS, label="M", description="", location=Path("/abs"))
    with pytest.raises(ValueError, match="absolute"):
        volume_store.update(MODELS, location=Path("rel"))


def test_duplicate_add_and_unknown_update_are_refused(tmp_path, volume_store):
    volume_store.add(MODELS, label="M", description="", location=tmp_path)
    with pytest.raises(ValueError, match="exists"):
        volume_store.add(MODELS, label="M", description="", location=tmp_path)
    with pytest.raises(ValueError, match="no volume"):
        volume_store.update("user:volume:nope", label="x")


def test_remove_reports_whether_it_existed(tmp_path, volume_store):
    volume_store.add(MODELS, label="M", description="", location=tmp_path)
    assert volume_store.remove(MODELS) is True
    assert volume_store.remove(MODELS) is False


def test_ensure_adds_once_and_never_overwrites(tmp_path, volume_store):
    assert volume_store.ensure(MODELS, label="Models", description="", location=tmp_path / "m") is True
    volume_store.update(MODELS, location=tmp_path / "elsewhere", label="Mine")
    assert volume_store.ensure(MODELS, label="Models", description="", location=tmp_path / "m") is False
    assert volume_store.entry(MODELS) == VolumeEntry(MODELS, "Mine", "", tmp_path / "elsewhere")


def test_remove_then_ensure_restores_the_suggestion(tmp_path, volume_store):
    ensure_volume(MODELS, label="Models", description="", location=tmp_path / "m")
    volume_store.update(MODELS, location=tmp_path / "elsewhere")
    volume_store.remove(MODELS)
    assert ensure_volume(MODELS, label="Models", description="", location=tmp_path / "m") is True
    assert volume_store.entry(MODELS).location == tmp_path / "m"


def test_ensure_never_creates_the_folder(tmp_path, volume_store):
    volume_store.ensure(MODELS, label="M", description="", location=tmp_path / "later")
    assert not (tmp_path / "later").exists()


def test_project_follows_the_workspace_root(tmp_path, volume_store, workspace_root_restore):
    context.set_workspace_root(tmp_path / "a")
    assert volume_store.entry(PROJECT_KEY).location == tmp_path / "a"
    context.set_workspace_root(tmp_path / "b")
    assert volume_store.entry(PROJECT_KEY).location == tmp_path / "b"
    context._workspace_root = None
    assert volume_store.entry(PROJECT_KEY).location is None


def test_hand_written_project_entry_is_ignored(tmp_path, volume_store, workspace_root_restore):
    context.set_workspace_root(tmp_path)
    volume_store.path.write_text(f'[volumes."{PROJECT_KEY}"]\nlabel = "x"\nlocation = "/x"\n')
    assert volume_store.entry(PROJECT_KEY).location == tmp_path


def test_legacy_entries_read_as_user_volumes_and_survive_a_write(tmp_path, volume_store):
    volume_store.path.write_text('[volumes]\nassets = "/x/assets"\n')
    key = user_volume_key("assets")
    assert volume_store.entry(key) == VolumeEntry(key, "assets", "", Path("/x/assets"))
    volume_store.add(MODELS, label="M", description="", location=tmp_path)
    fresh = VolumeStore(volume_store.path)
    assert fresh.entry(key) == VolumeEntry(key, "assets", "", Path("/x/assets"))
    assert fresh.entry(MODELS) is not None
    assert "assets = " not in volume_store.path.read_text()


def test_bad_entries_are_skipped_with_a_warning(volume_store, caplog):
    volume_store.path.write_text(
        '[volumes]\nBad = "/x"\nrel = "x"\nok = "/y"\n'
        '[volumes."lib:volume:noloc"]\nlabel = "n"\n'
        '[volumes."not-a-key"]\nlocation = "/z"\n'
    )
    assert _keys(volume_store) == [PROJECT_KEY, user_volume_key("ok")]
    assert caplog.text.count("Ignoring") == 4


def test_unreadable_file_lists_only_project_and_refuses_writes(tmp_path, volume_store, caplog):
    volume_store.path.write_text("this is [not toml")
    assert _keys(volume_store) == [PROJECT_KEY]
    assert "unreadable" in caplog.text
    with pytest.raises(ValueError, match="unreadable"):
        volume_store.add(MODELS, label="M", description="", location=tmp_path)
    assert volume_store.path.read_text() == "this is [not toml"


def test_ensure_on_an_unreadable_file_logs_and_adds_nothing(tmp_path, volume_store, caplog):
    volume_store.path.write_text("this is [not toml")
    assert ensure_volume(MODELS, label="M", description="", location=tmp_path) is False
    assert "not added" in caplog.text
    assert volume_store.path.read_text() == "this is [not toml"


def test_label_defaults_to_the_name_part(tmp_path, volume_store):
    volume_store.path.write_text(f'[volumes."{MODELS}"]\nlocation = "{tmp_path}"\n')
    assert volume_store.entry(MODELS).label == "models"


def test_on_disk_edit_is_picked_up(tmp_path, volume_store):
    import os

    volume_store.add(MODELS, label="M", description="", location=tmp_path / "a")
    assert volume_store.entry(MODELS).location == tmp_path / "a"
    volume_store.path.write_text(f'[volumes."{MODELS}"]\nlocation = "{tmp_path / "bb"}"\n')
    os.utime(volume_store.path, ns=(1, 1))
    assert volume_store.entry(MODELS).location == tmp_path / "bb"


def test_concurrent_ensure_loses_nothing(tmp_path, volume_store):
    keys = [f"lib{i}:volume:v" for i in range(8)]
    barrier = threading.Barrier(len(keys))

    def worker(key):
        store = VolumeStore(volume_store.path)
        barrier.wait()
        store.ensure(key, label=key, description="", location=tmp_path)

    threads = [threading.Thread(target=worker, args=(k,)) for k in keys]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    fresh = VolumeStore(volume_store.path)
    assert sorted(_keys(fresh)[1:]) == sorted(keys)


def test_write_leaves_no_temp_file(tmp_path, volume_store):
    volume_store.add(MODELS, label="M", description="", location=tmp_path)
    assert sorted(p.name for p in volume_store.path.parent.iterdir() if p.name.startswith("volumes")) == [
        "volumes.toml"
    ]


def test_user_volume_key():
    assert user_volume_key("scans") == "user:volume:scans"
    with pytest.raises(ValueError, match="Invalid volume name"):
        user_volume_key("Bad Name")
