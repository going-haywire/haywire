"""PathWidget: volume select, relative field, status line and folder browser."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.barn.builtin.types.path import FILE_PATH, FOLDER_PATH, PATH
from haywire.barn.builtin.widgets.path_widget import PathWidget
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort
from haywire.core.volumes import VolumePath, VolumeStore, set_volume_store
from haywire.core.volumes import volume as volume_mod


@pytest.fixture(autouse=True)
def volume_store(tmp_path: Path) -> Any:
    store = VolumeStore(tmp_path / "volumes.toml")
    set_volume_store(store)
    yield store
    set_volume_store(None)


@pytest.fixture(autouse=True)
def volume_registry() -> Any:
    snapshot = dict(volume_mod._VOLUME_BY_NAME)
    yield
    volume_mod._VOLUME_BY_NAME.clear()
    volume_mod._VOLUME_BY_NAME.update(snapshot)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _port(value: VolumePath, properties: dict | None = None, type_cls: Any = PATH) -> DataPort:
    port = DataPort(
        registry_id="path",
        registry_key=type_cls.class_identity.registry_key,
        label="Path",
        id="path",
        type_cls=type_cls,
        port_type=PortType.INLET,
        widget_config={"properties": properties} if properties is not None else {},
    )
    port.set_value(value)
    return port


def _scans(tmp_path: Path, store: VolumeStore) -> Path:
    root = tmp_path / "scans"
    (root / "day1").mkdir(parents=True)
    (root / "day1" / "a.png").write_text("x")
    (root / "day1" / "notes.txt").write_text("x")
    (root / "top.PNG").write_text("x")
    store.set("scans", root)
    return root


async def _open(user: User, port: DataPort) -> PathWidget:
    holder: dict[str, PathWidget] = {}

    @ui.page("/")
    def page() -> None:
        holder["w"] = PathWidget(port)
        holder["w"].render()

    await user.open("/")
    return holder["w"]


def _status(user: User) -> str:
    return cast(Any, user.find(marker="path-status").elements.pop()).text


def _tree(user: User) -> ui.tree:
    return cast(ui.tree, user.find(kind=ui.tree).elements.pop())


def _labels(nodes: list[dict]) -> list[str]:
    out: list[str] = []
    for node in nodes:
        out.append(node["label"])
        out.extend(_labels(node.get("children") or []))
    return out


@pytest.mark.unit
@pytest.mark.anyio
async def test_choosing_a_volume_keeps_relative(user: User, tmp_path: Path, volume_store) -> None:
    _scans(tmp_path, volume_store)
    port = _port(VolumePath("project", "sub/a.png"))
    await _open(user, port)

    select = cast(ui.select, user.find(marker="path-volume").elements.pop())
    assert cast(dict, select.options)["project"] == "Project"
    assert cast(dict, select.options)["scans"] == "scans"
    select.value = "scans"  # what a pick in the dropdown does server-side

    assert port.get_value() == VolumePath("scans", "sub/a.png")


@pytest.mark.unit
@pytest.mark.anyio
async def test_typing_relative_is_kept_verbatim(user: User) -> None:
    port = _port(VolumePath("project", ""))
    await _open(user, port)

    user.find(marker="path-relative").trigger("update:value", "sub\\odd/../x.png")

    assert port.get_value() == VolumePath("project", "sub\\odd/../x.png")


@pytest.mark.unit
@pytest.mark.anyio
async def test_status_names_an_undefined_volume(user: User) -> None:
    port = _port(VolumePath("scans", "a.png"))
    await _open(user, port)

    assert _status(user) == "volume 'scans' is not defined on this machine"


@pytest.mark.unit
@pytest.mark.anyio
async def test_status_names_a_missing_location(user: User, tmp_path: Path, volume_store) -> None:
    missing = tmp_path / "unplugged"
    volume_store.set("drive", missing)
    port = _port(VolumePath("drive", "a.png"))
    await _open(user, port)

    assert _status(user) == f"location missing: {missing}"


@pytest.mark.unit
@pytest.mark.anyio
async def test_status_shows_an_escape_without_raising(user: User, tmp_path: Path, volume_store) -> None:
    _scans(tmp_path, volume_store)
    port = _port(VolumePath("scans", "../outside.png"))
    await _open(user, port)

    assert "escapes its volume" in _status(user)


@pytest.mark.unit
@pytest.mark.anyio
async def test_status_follows_a_model_change(user: User, tmp_path: Path, volume_store) -> None:
    root = _scans(tmp_path, volume_store)
    port = _port(VolumePath("nowhere", ""))
    await _open(user, port)

    port.set_value(VolumePath("scans", "day1/a.png"))

    assert _status(user) == str((root / "day1" / "a.png").resolve())


@pytest.mark.unit
@pytest.mark.anyio
async def test_folder_mode_browses_folders_only(user: User, tmp_path: Path, volume_store) -> None:
    _scans(tmp_path, volume_store)
    port = _port(VolumePath("scans", ""), {"mode": "folder"})
    await _open(user, port)

    user.find(marker="path-browse").click()

    assert _labels(_tree(user).props["nodes"]) == ["day1"]


@pytest.mark.unit
@pytest.mark.anyio
async def test_folder_pick_sets_relative_on_confirm(user: User, tmp_path: Path, volume_store) -> None:
    root = _scans(tmp_path, volume_store)
    port = _port(VolumePath("scans", ""), {"mode": "folder"})
    await _open(user, port)

    user.find(marker="path-browse").click()
    user.find(kind=ui.tree).trigger("update:selected", str(root / "day1"))
    await user.should_see(marker="path-picked", content="scans:day1")
    user.find(kind=ui.button, content="Select").click()

    assert port.get_value() == VolumePath("scans", "day1")


@pytest.mark.unit
@pytest.mark.anyio
async def test_file_mode_hides_other_extensions(user: User, tmp_path: Path, volume_store) -> None:
    _scans(tmp_path, volume_store)
    port = _port(VolumePath("scans", ""), {"mode": "file", "extensions": [".png"]})
    await _open(user, port)

    user.find(marker="path-browse").click()

    assert _labels(_tree(user).props["nodes"]) == ["day1", "a.png", "top.PNG"]


@pytest.mark.unit
@pytest.mark.anyio
async def test_file_pick_sets_the_posix_relative(user: User, tmp_path: Path, volume_store) -> None:
    root = _scans(tmp_path, volume_store)
    port = _port(VolumePath("scans", ""), {"mode": "file"})
    await _open(user, port)

    user.find(marker="path-browse").click()
    user.find(kind=ui.tree).trigger("update:selected", str(root / "day1" / "a.png"))

    assert port.get_value() == VolumePath("scans", "day1/a.png")


@pytest.mark.unit
@pytest.mark.anyio
async def test_save_mode_joins_folder_and_name(user: User, tmp_path: Path, volume_store) -> None:
    root = _scans(tmp_path, volume_store)
    port = _port(VolumePath("scans", ""), {"mode": "save"})
    await _open(user, port)

    user.find(marker="path-browse").click()
    user.find(kind=ui.tree).trigger("update:selected", str(root / "day1"))
    cast(Any, user.find(marker="path-save-name").elements.pop()).value = "out.png"
    user.find(kind=ui.button, content="Select").click()

    assert port.get_value() == VolumePath("scans", "day1/out.png")


@pytest.mark.integration
@pytest.mark.parametrize(("type_cls", "mode"), [(FILE_PATH, "file"), (FOLDER_PATH, "folder")])
def test_a_typed_port_reaches_the_widget_with_its_mode(library_system, type_cls: Any, mode: str) -> None:
    registry = library_system.get_type_registry()
    for spec in (
        type_cls.as_inlet("p"),
        type_cls.as_inlet("p", widget_config={"properties": {"extensions": [".png"]}}),
    ):
        port = DataPort.from_spec(cast(Any, spec), registry, cast(Any, None), cast(Any, None))
        assert PathWidget(port)._mode == mode


@pytest.mark.integration
def test_an_explicit_port_mode_wins(library_system) -> None:
    spec = FILE_PATH.as_inlet("p", widget_config={"properties": {"mode": "save"}})
    port = DataPort.from_spec(
        cast(Any, spec), library_system.get_type_registry(), cast(Any, None), cast(Any, None)
    )
    assert PathWidget(port)._mode == "save"
