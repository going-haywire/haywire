import pytest

from haywire.core.di import context
from haywire.core.volumes import VolumeStore, set_volume_store
from haywire.core.volumes import volume as volume_mod


@pytest.fixture(autouse=True)
def volume_store(tmp_path):
    store = VolumeStore(tmp_path / "volumes.toml")
    set_volume_store(store)
    yield store
    set_volume_store(None)


@pytest.fixture(autouse=True)
def volume_registry():
    snapshot = dict(volume_mod._VOLUME_BY_NAME)
    yield
    volume_mod._VOLUME_BY_NAME.clear()
    volume_mod._VOLUME_BY_NAME.update(snapshot)


@pytest.fixture
def workspace_root_restore():
    previous = context._workspace_root
    yield
    context._workspace_root = previous
