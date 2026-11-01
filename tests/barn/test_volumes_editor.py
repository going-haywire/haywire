"""The ADMIN Volumes editor: compact rows, edit/view and add modals writing through VolumeStore."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from haybale_studio.editors.volumes_editor import VolumesEditor
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.access import AccessTier
from haywire.core.volumes import PROJECT_KEY, VolumeEntry, VolumeStore, set_volume_store
from haywire.ui import elements as hui

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


MODELS = "haybale-models:volume:models"
SCANS = "user:volume:scans"


def _fresh(store: VolumeStore) -> dict[str, VolumeEntry]:
    return {e.key: e for e in VolumeStore(store.path).entries() if e.key != PROJECT_KEY}


def _scans(store: VolumeStore, location: Path) -> None:
    store.add(SCANS, label="Scans", description="Scanner drive", location=location)


async def _open(user: User, *, can_admin: bool = True) -> None:
    @ui.page("/")
    def page() -> None:
        context = MagicMock()
        context.can_admin.return_value = can_admin
        editor = VolumesEditor(MagicMock())
        editor.draw(context, ui.column())

    await user.open("/")


async def _type(user: User, marker: str, text: str) -> None:
    el: ui.input = user.find(marker=marker).elements.pop()  # type: ignore[assignment]
    el.set_value(text)


def _one(user: User, marker: str) -> Any:
    elements = user.find(marker=marker).elements
    assert len(elements) == 1, f"{marker}: {len(elements)} elements"
    return next(iter(elements))


def _dialog_open(user: User) -> bool:
    return bool(_one(user, "volume-dialog").value)


def test_requires_admin() -> None:
    from haywire.core.access import required_tier

    assert VolumesEditor.class_identity.requires is AccessTier.ADMIN
    # The slot filter (`Slot._editor_accessible`) asks `can_access(required_tier(cls))`.
    required = required_tier(VolumesEditor)
    assert AccessTier.ADMIN.satisfies(required)
    assert not AccessTier.EDIT.satisfies(required)
    assert not AccessTier.VIEW.satisfies(required)


def test_has_its_own_icon() -> None:
    assert VolumesEditor.class_identity.icon == hui.icon.volumes
    assert hui.icon.volumes != hui.icon.haystack


@pytest.mark.anyio
async def test_header_carries_the_title_and_the_add_button(user: User, store: VolumeStore) -> None:
    await _open(user)
    await user.should_see("Volumes")
    await user.should_see(marker="volume-add")
    await user.should_not_see("Graphs refer to files as")
    await user.should_not_see(marker="volume-add-name")  # no inline add form


@pytest.mark.anyio
async def test_a_row_is_the_label_over_a_fitted_location_line(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    target = tmp_path / "not-there-yet"
    store.add(MODELS, label="Models", description="", location=target)
    await _open(user)
    await user.should_see("Models")
    await user.should_see("Project")
    line = _one(user, "volume-location-models")
    assert line.props["title"] == str(target)
    assert "hw-path-fit" in line.classes
    await user.should_see(marker="volume-missing-models")
    await user.should_not_see(MODELS)  # the key is a detail, not a row line
    for word in ("configured", "default", "fixed", "Source"):
        await user.should_not_see(word)
    await user.should_see(marker="volume-undefined-project")


@pytest.mark.anyio
async def test_the_row_button_edits_a_stored_volume_and_views_project(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    _scans(store, tmp_path)
    await _open(user)
    assert _one(user, "volume-open-scans").props["icon"] == hui.icon.edit
    assert _one(user, "volume-open-project").props["icon"] == hui.icon.view


@pytest.mark.anyio
async def test_without_write_access_every_row_only_views(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    _scans(store, tmp_path)
    await _open(user, can_admin=False)
    assert _one(user, "volume-open-scans").props["icon"] == hui.icon.view
    await user.should_not_see(marker="volume-add")
    user.find(marker="volume-open-scans").click()
    assert _dialog_open(user)
    await user.should_see("Scanner drive")
    for marker in (
        "volume-dialog-label",
        "volume-dialog-location",
        "volume-dialog-save",
        "volume-dialog-delete",
    ):
        await user.should_not_see(marker=marker)


@pytest.mark.anyio
async def test_the_project_modal_is_read_only_and_shows_the_key(user: User, store: VolumeStore) -> None:
    await _open(user)
    user.find(marker="volume-open-project").click()
    assert _dialog_open(user)
    await user.should_see(PROJECT_KEY)
    await user.should_see("The open project's folder")
    await user.should_not_see(marker="volume-dialog-location")
    await user.should_not_see(marker="volume-dialog-save")


@pytest.mark.anyio
async def test_save_updates_label_description_and_location_but_never_the_key(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    _scans(store, tmp_path / "a")
    await _open(user)
    user.find(marker="volume-open-scans").click()
    await user.should_see(SCANS)
    await user.should_not_see(marker="volume-dialog-suggested")  # a user volume has no library
    await user.should_not_see(marker="volume-dialog-reset")
    await _type(user, "volume-dialog-label", "Scans 2")
    await _type(user, "volume-dialog-description", "")
    await _type(user, "volume-dialog-location", str(tmp_path / "b"))
    user.find(marker="volume-dialog-save").click()
    assert _fresh(store) == {SCANS: VolumeEntry(SCANS, "Scans 2", "", tmp_path / "b")}
    assert not _dialog_open(user)
    assert _one(user, "volume-location-scans").props["title"] == str(tmp_path / "b")


@pytest.mark.anyio
async def test_a_store_error_shows_in_the_edit_modal_and_keeps_it_open(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    _scans(store, tmp_path)
    await _open(user)
    user.find(marker="volume-open-scans").click()
    await _type(user, "volume-dialog-location", "rel/dir")
    user.find(marker="volume-dialog-save").click()
    await user.should_see("must be absolute")
    assert _dialog_open(user)
    assert _fresh(store)[SCANS].location == tmp_path


@pytest.mark.anyio
async def test_delete_drops_the_volume(user: User, store: VolumeStore, tmp_path: Path) -> None:
    _scans(store, tmp_path)
    await _open(user)
    user.find(marker="volume-open-scans").click()
    user.find(marker="volume-dialog-delete").click()
    assert _fresh(store) == {}
    assert not _dialog_open(user)
    await user.should_not_see(marker="volume-row-scans")


@pytest.mark.anyio
async def test_a_library_volume_resets_instead_of_deleting(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    store.ensure(MODELS, label="Models", description="", location=tmp_path / "m")
    store.update(MODELS, location=tmp_path / "elsewhere", label="Mine")
    await _open(user)
    user.find(marker="volume-open-models").click()
    await user.should_see(f"Suggested location: {tmp_path / 'm'}")
    await user.should_not_see(marker="volume-dialog-delete")
    user.find(marker="volume-dialog-reset").click()
    assert _fresh(store) == {MODELS: VolumeEntry(MODELS, "Mine", "", tmp_path / "m", tmp_path / "m")}
    assert not _dialog_open(user)
    assert _one(user, "volume-location-models").props["title"] == str(tmp_path / "m")


@pytest.mark.anyio
async def test_a_library_volume_without_a_suggestion_has_no_reset(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    store.add(MODELS, label="Models", description="", location=tmp_path)
    await _open(user)
    user.find(marker="volume-open-models").click()
    await user.should_see("has not recorded a suggested location")
    await user.should_not_see(marker="volume-dialog-reset")
    await user.should_not_see(marker="volume-dialog-delete")


@pytest.mark.anyio
async def test_the_add_modal_adds_a_user_volume(user: User, store: VolumeStore, tmp_path: Path) -> None:
    await _open(user)
    user.find(marker="volume-add").click()
    await _type(user, "volume-add-name", "scans")
    await user.should_see("Key: user:volume:scans")
    await _type(user, "volume-add-label", "Scans")
    await _type(user, "volume-add-description", "Scanner drive")
    await _type(user, "volume-add-location", str(tmp_path))
    user.find(marker="volume-add-confirm").click()
    assert _fresh(store) == {SCANS: VolumeEntry(SCANS, "Scans", "Scanner drive", tmp_path)}
    assert not _dialog_open(user)
    await user.should_see(marker="volume-location-scans")


@pytest.mark.anyio
async def test_an_empty_label_in_the_add_modal_falls_back_to_the_name(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    await _open(user)
    user.find(marker="volume-add").click()
    await _type(user, "volume-add-name", "scans")
    await _type(user, "volume-add-location", str(tmp_path))
    user.find(marker="volume-add-confirm").click()
    assert _fresh(store)[SCANS].label == "scans"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "location", "message"),
    [("Bad Name", "/tmp", "Invalid volume name"), ("scans", "rel/dir", "must be absolute")],
)
async def test_invalid_input_in_the_add_modal_shows_the_store_message_and_writes_nothing(
    user: User, store: VolumeStore, name: str, location: str, message: str
) -> None:
    await _open(user)
    user.find(marker="volume-add").click()
    await _type(user, "volume-add-name", name)
    await _type(user, "volume-add-location", location)
    user.find(marker="volume-add-confirm").click()
    await user.should_see(message)
    assert _dialog_open(user)
    assert _fresh(store) == {}


@pytest.mark.anyio
async def test_adding_an_existing_name_shows_the_error(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    _scans(store, tmp_path)
    await _open(user)
    user.find(marker="volume-add").click()
    await _type(user, "volume-add-name", "scans")
    await _type(user, "volume-add-location", str(tmp_path / "other"))
    user.find(marker="volume-add-confirm").click()
    await user.should_see("already exists")
    assert _fresh(store)[SCANS].location == tmp_path


@pytest.mark.anyio
async def test_malformed_file_shows_the_message_in_the_modal_instead_of_crashing(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    store.path.write_text("[volumes\nbroken")
    await _open(user)
    user.find(marker="volume-add").click()
    await _type(user, "volume-add-name", "scans")
    await _type(user, "volume-add-location", str(tmp_path))
    user.find(marker="volume-add-confirm").click()
    await user.should_see("unreadable")
    assert _dialog_open(user)
    assert store.path.read_text() == "[volumes\nbroken"


@pytest.mark.anyio
async def test_a_session_demoted_after_draw_gets_the_error_in_the_modal(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    _scans(store, tmp_path)
    contexts: list[MagicMock] = []

    @ui.page("/")
    def page() -> None:
        context = MagicMock()
        context.can_admin.return_value = True
        contexts.append(context)
        VolumesEditor(MagicMock()).draw(context, ui.column())

    await user.open("/")
    user.find(marker="volume-open-scans").click()
    await _type(user, "volume-dialog-location", "/tmp")
    contexts[0].can_admin.return_value = False
    user.find(marker="volume-dialog-save").click()
    await user.should_see("needs admin access")
    assert _dialog_open(user)
    assert _fresh(store)[SCANS].location == tmp_path
