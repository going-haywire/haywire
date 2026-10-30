"""The ADMIN Volumes editor: compact rows, edit/view and add modals writing through VolumeStore."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from haybale_studio.editors.volumes_editor import VolumesEditor
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.access import AccessTier
from haywire.core.volumes import VolumeStore, list_volumes, set_volume_store
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


def _fresh(store: VolumeStore) -> dict[str, Path]:
    return VolumeStore(store.path).configured()


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
async def test_a_row_is_the_name_over_a_fitted_location_line(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    target = tmp_path / "not-there-yet"
    store.set("models", target)
    await _open(user)
    for status in list_volumes():
        await user.should_see(status.name)
    line = _one(user, "volume-location-models")
    assert line.props["title"] == str(target)
    assert "hw-path-fit" in line.classes
    assert [child.text for child in line.default_slot.children][0] == str(target)
    await user.should_see(marker="volume-missing-models")
    await user.should_not_see(marker="volume-missing-home")
    await user.should_not_see("configured")  # no source column
    await user.should_not_see(marker="volume-location-project")
    await user.should_see(marker="volume-undefined-project")
    await user.should_see("not defined on this machine")


@pytest.mark.anyio
async def test_the_row_button_edits_a_configurable_volume_and_views_project(
    user: User, store: VolumeStore
) -> None:
    await _open(user)
    assert _one(user, "volume-open-home").props["icon"] == hui.icon.edit
    assert _one(user, "volume-open-project").props["icon"] == hui.icon.view


@pytest.mark.anyio
async def test_without_write_access_every_row_only_views(user: User, store: VolumeStore) -> None:
    await _open(user, can_admin=False)
    assert _one(user, "volume-open-home").props["icon"] == hui.icon.view
    await user.should_not_see(marker="volume-add")


@pytest.mark.anyio
async def test_the_view_modal_shows_details_without_controls(user: User, store: VolumeStore) -> None:
    await _open(user)
    user.find(marker="volume-open-project").click()
    assert _dialog_open(user)
    await user.should_see("The current project's workspace root.")
    await user.should_see("undefined")
    await user.should_not_see(marker="volume-dialog-location")
    await user.should_not_see(marker="volume-dialog-save")


@pytest.mark.anyio
async def test_save_in_the_edit_modal_writes_closes_and_redraws(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    await _open(user)
    target = tmp_path / "elsewhere"
    target.mkdir()
    user.find(marker="volume-open-home").click()
    await user.should_not_see(marker="volume-dialog-remove")  # home is not configured yet
    await _type(user, "volume-dialog-location", str(target))
    user.find(marker="volume-dialog-save").click()
    assert _fresh(store) == {"home": target}
    assert not _dialog_open(user)
    assert _one(user, "volume-location-home").props["title"] == str(target)


@pytest.mark.anyio
async def test_a_store_error_shows_in_the_edit_modal_and_keeps_it_open(
    user: User, store: VolumeStore
) -> None:
    await _open(user)
    user.find(marker="volume-open-home").click()
    await _type(user, "volume-dialog-location", "rel/dir")
    user.find(marker="volume-dialog-save").click()
    await user.should_see("must be absolute")
    assert _dialog_open(user)
    assert _fresh(store) == {}


@pytest.mark.anyio
async def test_remove_in_the_edit_modal_drops_the_configured_entry(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    store.set("scans", tmp_path)
    await _open(user)
    user.find(marker="volume-open-scans").click()
    user.find(marker="volume-dialog-remove").click()
    assert _fresh(store) == {}
    assert not _dialog_open(user)
    await user.should_not_see(marker="volume-row-scans")


@pytest.mark.anyio
async def test_the_add_modal_adds_a_configured_row(user: User, store: VolumeStore, tmp_path: Path) -> None:
    await _open(user)
    user.find(marker="volume-add").click()
    await _type(user, "volume-add-name", "scans")
    await _type(user, "volume-add-location", str(tmp_path))
    user.find(marker="volume-add-confirm").click()
    assert _fresh(store) == {"scans": tmp_path}
    assert not _dialog_open(user)
    await user.should_see(marker="volume-location-scans")


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
async def test_malformed_file_shows_the_message_in_the_modal_instead_of_crashing(
    user: User, store: VolumeStore, tmp_path: Path
) -> None:
    store.path.write_text("[volumes\nbroken")
    await _open(user)
    user.find(marker="volume-add").click()
    await _type(user, "volume-add-name", "scans")
    await _type(user, "volume-add-location", str(tmp_path))
    user.find(marker="volume-add-confirm").click()
    # The TOML parser's position text ("... at line 1 col 8 ...") is the stable part of its message.
    await user.should_see("line 1")
    assert _dialog_open(user)
    assert not _fresh(store)


@pytest.mark.anyio
async def test_a_configurable_volume_without_write_access_is_view_only(
    user: User, store: VolumeStore
) -> None:
    await _open(user, can_admin=False)
    user.find(marker="volume-open-home").click()
    assert _dialog_open(user)
    await user.should_not_see(marker="volume-dialog-location")
    await user.should_not_see(marker="volume-dialog-save")
    await user.should_not_see(marker="volume-dialog-remove")


@pytest.mark.anyio
async def test_a_session_demoted_after_draw_gets_the_error_in_the_modal(
    user: User, store: VolumeStore
) -> None:
    contexts: list[MagicMock] = []

    @ui.page("/")
    def page() -> None:
        context = MagicMock()
        context.can_admin.return_value = True
        contexts.append(context)
        VolumesEditor(MagicMock()).draw(context, ui.column())

    await user.open("/")
    user.find(marker="volume-open-home").click()
    await _type(user, "volume-dialog-location", "/tmp")
    contexts[0].can_admin.return_value = False
    user.find(marker="volume-dialog-save").click()
    await user.should_see("needs admin access")
    assert _dialog_open(user)
    assert _fresh(store) == {}


@pytest.mark.anyio
async def test_remove_is_absent_for_a_default_source_volume(user: User, store: VolumeStore) -> None:
    await _open(user)
    user.find(marker="volume-open-home").click()
    assert _dialog_open(user)
    await user.should_not_see(marker="volume-dialog-remove")


def _texts(user: User, text: str) -> list[Any]:
    return [el for el in user.find(kind=ui.label).elements if getattr(el, "text", None) == text]


@pytest.mark.anyio
@pytest.mark.parametrize(("name", "label"), [("project", "Project"), ("home", "Home")])
async def test_a_label_that_only_recases_the_name_is_not_shown_again(
    user: User, store: VolumeStore, name: str, label: str
) -> None:
    await _open(user)
    user.find(marker=f"volume-open-{name}").click()
    assert _dialog_open(user)
    assert _texts(user, label) == []
    assert _texts(user, name)  # the name itself is shown once, as the heading


def test_a_label_differing_from_the_name_is_shown(store: VolumeStore) -> None:
    from haybale_studio.editors.volumes_editor import _distinct_label

    status = next(s for s in list_volumes() if s.name == "project")
    assert _distinct_label(status) is None
    assert _distinct_label(replace(status, label="Workspace")) == "Workspace"
    assert _distinct_label(replace(status, label="")) is None
