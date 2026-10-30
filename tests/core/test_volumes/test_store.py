import logging
import os
from pathlib import Path

import pytest

from haywire.core.volumes import VolumeStore

pytestmark = pytest.mark.unit


def test_missing_file_is_empty(volume_store):
    assert volume_store.configured() == {}


def test_set_persists_across_instances(volume_store, tmp_path):
    volume_store.set("models", tmp_path / "m")
    assert VolumeStore(volume_store.path).configured() == {"models": tmp_path / "m"}


def test_set_rejects_bad_input(volume_store):
    with pytest.raises(ValueError, match="not configurable"):
        volume_store.set("project", Path("/x"))
    with pytest.raises(ValueError, match="Invalid"):
        volume_store.set("Bad", Path("/x"))
    with pytest.raises(ValueError, match="absolute"):
        volume_store.set("x", Path("rel"))


def test_remove(volume_store, tmp_path):
    volume_store.set("models", tmp_path / "m")
    assert volume_store.remove("models") is True
    assert volume_store.remove("models") is False
    assert volume_store.configured() == {}


def test_external_edit_is_picked_up(volume_store, tmp_path):
    volume_store.set("models", tmp_path / "m")
    assert volume_store.configured() == {"models": tmp_path / "m"}
    volume_store.path.write_text(f'[volumes]\nmodels = "{tmp_path / "other"}"\n', encoding="utf-8")
    st = volume_store.path.stat()
    os.utime(volume_store.path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert volume_store.configured() == {"models": tmp_path / "other"}


def test_bad_entries_ignored_with_warning(volume_store, caplog):
    volume_store.path.write_text('[volumes]\nBad = "/x"\nrel = "x"\nok = "/y"\n', encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert volume_store.configured() == {"ok": Path("/y")}
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 2


def test_invalid_toml_logs_error(volume_store, caplog):
    volume_store.path.write_text("[volumes\nnope", encoding="utf-8")
    with caplog.at_level(logging.ERROR):
        assert volume_store.configured() == {}
    assert any(r.levelno == logging.ERROR for r in caplog.records)
