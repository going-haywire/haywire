import pytest

from haywire.core.di import context
from haywire.core.volumes import VolumeStore, set_volume_store


@pytest.fixture(autouse=True)
def volume_store(tmp_path):
    store = VolumeStore(tmp_path / "volumes.toml")
    set_volume_store(store)
    yield store
    set_volume_store(None)


@pytest.fixture
def workspace_root_restore():
    previous = context._workspace_root
    yield
    context._workspace_root = previous
