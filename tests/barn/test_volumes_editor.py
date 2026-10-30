"""The ADMIN Volumes editor: rows per volume, writes through VolumeStore, errors shown not raised."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from haybale_studio.editors.volumes_editor import VolumesEditor
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.access import AccessTier
from haywire.core.volumes import VolumeStore, list_volumes, set_volume_store

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


@pytest.fixture
def store(tmp_path: Path) -> Iterator[VolumeStore]:
    s = VolumeStore(tmp_path / "volumes.toml")
    set_volume_store(s)
    yield s
    set_volume_store(None)


def _fresh(store: VolumeStore) -> dict[str, Path]:
    return VolumeStore(store.path).configured()


async def _open(user: User) -> None:
    @ui.page("/")
    def page() -> None:
        editor = VolumesEditor(MagicMock())
        editor.draw(MagicMock(), ui.column())

    await user.open("/")


async def _type(user: User, marker: str, text: str) -> None:
    el: ui.input = user.find(marker=marker).elements.pop()  # type: ignore[assignment]
    el.set_value(text)


def test_requires_admin() -> None:
    from haywire.core.access import required_tier

    assert VolumesEditor.class_identity.requires is AccessTier.ADMIN
    # The slot filter (`Slot._editor_accessible`) asks `can_access(required_tier(cls))`.
    required = required_tier(VolumesEditor)
    assert AccessTier.ADMIN.satisfies(required)
    assert not AccessTier.EDIT.satisfies(required)
    assert not AccessTier.VIEW.satisfies(required)


@pytest.mark.anyio
async def test_one_row_per_volume_with_source_and_missing_marker(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    store.set("models", tmp_path / "not-there-yet")
    await _open(user)
    for status in list_volumes():
        await user.should_see(status.name)
    await user.should_see(marker="volume-missing-models")
    await user.should_not_see(marker="volume-missing-home")
    await user.should_see("configured")


@pytest.mark.anyio
async def test_project_has_no_edit_control(user: User, store: VolumeStore) -> None:
    await _open(user)
    await user.should_see(marker="volume-location-home")
    await user.should_not_see(marker="volume-location-project")
    await user.should_not_see(marker="volume-set-project")


@pytest.mark.anyio
async def test_set_location_writes_through_the_store(user: User, store: VolumeStore, tmp_path: Path) -> None:
    await _open(user)
    target = tmp_path / "elsewhere"
    target.mkdir()
    await _type(user, "volume-location-home", str(target))
    user.find(marker="volume-set-home").click()
    assert _fresh(store) == {"home": target}


@pytest.mark.anyio
async def test_add_volume_adds_a_configured_row(user: User, store: VolumeStore, tmp_path: Path) -> None:
    await _open(user)
    await _type(user, "volume-add-name", "scans")
    await _type(user, "volume-add-location", str(tmp_path))
    user.find(marker="volume-add").click()
    assert _fresh(store) == {"scans": tmp_path}
    await user.should_see(marker="volume-location-scans")


@pytest.mark.anyio
async def test_remove_drops_the_configured_entry(user: User, store: VolumeStore, tmp_path: Path) -> None:
    store.set("scans", tmp_path)
    await _open(user)
    user.find(marker="volume-remove-scans").click()
    assert _fresh(store) == {}
    await user.should_not_see(marker="volume-location-scans")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "location", "message"),
    [("Bad Name", "/tmp", "Invalid volume name"), ("scans", "rel/dir", "must be absolute")],
)
async def test_invalid_input_shows_the_store_message_and_writes_nothing(
    user: User, store: VolumeStore, name: str, location: str, message: str
) -> None:
    await _open(user)
    await _type(user, "volume-add-name", name)
    await _type(user, "volume-add-location", location)
    user.find(marker="volume-add").click()
    await user.should_see(message)
    assert _fresh(store) == {}


@pytest.mark.anyio
async def test_malformed_file_shows_the_message_instead_of_crashing(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    store.path.write_text("[volumes\nbroken")
    await _open(user)
    await _type(user, "volume-add-name", "scans")
    await _type(user, "volume-add-location", str(tmp_path))
    user.find(marker="volume-add").click()
    # The TOML parser's position text ("... at line 1 col 8 ...") is the stable part of its message.
    await user.should_see("line 1")
    assert not _fresh(store)
