"""ModelRefWidget: filtered catalog select, Other… address and browse, status line, Pin digest."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
from collections.abc import AsyncGenerator, Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.library.identity import LibraryIdentity
from haywire.core.models import ModelCatalogRegistry
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort
from haywire.core.undo.config import UndoConfig
from haywire.core.volumes import VolumeStore, location_of
from haywire.ui.widget.factory import WidgetFactory

from tests.conftest import edit_route, make_node

OTHER = "__other__"
DATA = b"weights"
SHA = hashlib.sha256(DATA).hexdigest()


def _mod(name: str) -> Any:
    return importlib.import_module(name)


def ModelRef(**kwargs: Any) -> Any:  # noqa: N802 - the class, looked up after any reload
    return _mod("haybale_models.value.model_ref").ModelRef(**kwargs)


def _entry(name: str, architecture: str, sha: str, precision: str | None = None) -> dict[str, Any]:
    resource: dict[str, Any] = {
        "platform": "pytorch",
        "type": "pth",
        "size": 2_400_000,
        "sha256": sha,
        "urls": [f"https://example.invalid/{name}.pth"],
    }
    if precision:
        resource["precision"] = precision
    return {
        "name": name,
        "author": "a",
        "license": "MIT",
        "architecture": architecture,
        "scale": 4,
        "tags": [],
        "description": "",
        "resources": [resource],
    }


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


@pytest.fixture
def state(models_env: VolumeStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A ModelsState stand-in: temp volumes, a fresh index and a two-library catalog."""
    keys = _mod("haybale_models.keys")
    consumer = _mod("haybale_models.consumer")
    location_of(keys.MODELS_VOLUME).mkdir(parents=True, exist_ok=True)
    location_of(keys.HF_VOLUME).mkdir(parents=True, exist_ok=True)
    catalog = ModelCatalogRegistry()
    for label, name, entries in (
        ("Beta", "haybale-beta", {"4x-Sharp": _entry("Sharp", "esrgan", SHA)}),
        (
            "Alpha",
            "haybale-alpha",
            {"4x-Soft": _entry("Soft", "esrgan", "b" * 64), "1x-Fast": _entry("Fast", "compact", "c" * 64)},
        ),
    ):
        folder = tmp_path / "catalogs" / name
        folder.mkdir(parents=True)
        for stem, doc in entries.items():
            (folder / f"{stem}.json").write_text(json.dumps(doc))
        catalog.add_folder(
            str(folder), LibraryIdentity(label=label, name=name, folder_path=str(folder), module_name=name)
        )
    fake = SimpleNamespace(
        index=_mod("haybale_models.store.index").ModelIndex(),
        catalog=catalog,
        hf_cache=location_of(keys.HF_VOLUME),
    )
    monkeypatch.setattr(consumer, "models_state", lambda: fake)
    return fake


def _put(state: Any, relative: str, data: bytes = DATA, source: str | None = None) -> Path:
    path = location_of(_mod("haybale_models.keys").MODELS_VOLUME) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    state.index.add(path, hashlib.sha256(data).hexdigest(), source)
    return path


def _port(value: Any, properties: dict | None = None) -> DataPort:
    model_ref = _mod("haybale_models.types.model_ref").MODEL_REF
    port = DataPort(
        registry_id="model",
        registry_key=model_ref.class_identity.registry_key,
        label="Model",
        id="model",
        type_cls=model_ref,
        port_type=PortType.INLET,
        widget_config={"properties": properties} if properties is not None else {},
    )
    port.set_value(value)
    return port


async def _open(user: User, build: Callable[[], Any]) -> Any:
    holder: dict[str, Any] = {}

    @ui.page("/")
    def page() -> None:
        holder["w"] = build()

    await user.open("/")
    return holder["w"]


def _direct(port: DataPort) -> Callable[[], Any]:
    def build() -> Any:
        widget = _mod("haybale_models.widgets.model_ref_widget").ModelRefWidget(port)
        widget.render()
        return widget

    return build


def _select(user: User) -> ui.select:
    return cast(ui.select, user.find(marker="model-ref-select").elements.pop())


def _status(user: User) -> str:
    return cast(ui.label, user.find(marker="model-ref-status").elements.pop()).text


async def _eventually(check: Callable[[], bool]) -> None:
    for _ in range(200):
        if check():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not met")


@pytest.mark.unit
@pytest.mark.anyio
async def test_select_lists_only_filtered_entries(user: User, state: Any) -> None:
    _put(state, "lib/sharp.pth")
    port = _port(ModelRef(), {"filter": {"architecture": ["esrgan"]}})
    await _open(user, _direct(port))

    user.find(marker="model-ref-select").trigger("popupShow")
    options = cast(dict, _select(user).options)

    # Grouped by library label (Alpha before Beta), then by name; Other… last.
    assert list(options) == ["haybale-alpha:model:4x-Soft", "haybale-beta:model:4x-Sharp", OTHER]
    assert options["haybale-alpha:model:4x-Soft"] == "Soft — not downloaded, 2.4 MB"
    assert options["haybale-beta:model:4x-Sharp"] == "Sharp — local, 7 B"
    assert options[OTHER] == "Other…"
    assert _status(user) == "no model chosen"


@pytest.mark.unit
@pytest.mark.anyio
async def test_model_change_resolves_once_and_popup_resolves_the_catalog(
    user: User, state: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _mod("haybale_models.widgets.model_ref_widget")
    real = module.resolve
    calls: list[Any] = []

    def counting(*args: Any, **kwargs: Any) -> Any:
        calls.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(module, "resolve", counting)
    port = _port(ModelRef())
    await _open(user, _direct(port))
    assert calls == []

    port.set_value(ModelRef(catalog="haybale-beta:model:4x-Sharp"))
    assert len(calls) <= 1

    calls.clear()
    user.find(marker="model-ref-select").trigger("popupShow")
    assert len(calls) == 3


@pytest.mark.unit
@pytest.mark.anyio
async def test_status_uses_the_nodes_model_preference(user: User, state: Any, tmp_path: Path) -> None:
    doc = _entry("Dual", "esrgan", "d" * 64)
    doc["resources"] = [
        {**doc["resources"][0], "precision": "fp32", "sha256": "d" * 64},
        {**doc["resources"][0], "precision": "fp16", "sha256": "e" * 64},
    ]
    folder = tmp_path / "catalogs" / "haybale-gamma"
    folder.mkdir(parents=True)
    (folder / "4x-Dual.json").write_text(json.dumps(doc))
    state.catalog.add_folder(
        str(folder),
        LibraryIdentity(
            label="Gamma", name="haybale-gamma", folder_path=str(folder), module_name="haybale-gamma"
        ),
    )
    _put(state, "a/fp32.pth", b"one")
    _put(state, "a/fp16.pth", b"two")
    # Both are local only if the index knows them by digest; index by the entries' digests.
    state.index.add(location_of(_mod("haybale_models.keys").MODELS_VOLUME) / "a/fp32.pth", "d" * 64, None)
    state.index.add(location_of(_mod("haybale_models.keys").MODELS_VOLUME) / "a/fp16.pth", "e" * 64, None)
    port = _port(ModelRef(catalog="haybale-gamma:model:4x-Dual"), {"prefer": [{"precision": "fp32"}]})
    node = SimpleNamespace(model_preference=lambda _pid: [{"precision": "fp16"}, {}])
    port._wrapper = SimpleNamespace(node=node, is_cleaned_up=False)  # type: ignore[assignment]
    await _open(user, _direct(port))

    assert "fp16" in _status(user)


@pytest.mark.unit
@pytest.mark.anyio
async def test_picking_an_entry_writes_a_catalog_ref(user: User, state: Any) -> None:
    _put(state, "lib/sharp.pth")
    port = _port(ModelRef())
    await _open(user, _direct(port))

    _select(user).value = "haybale-beta:model:4x-Sharp"

    assert port.get_value() == ModelRef(catalog="haybale-beta:model:4x-Sharp")
    assert _status(user) == "resolved: pytorch-pth, 7 B"


@pytest.mark.unit
@pytest.mark.anyio
async def test_other_uri_writes_file_ref(user: User, state: Any) -> None:
    port = _port(ModelRef())
    await _open(user, _direct(port))

    _select(user).value = OTHER
    assert port.get_value() == ModelRef()
    uri = cast(ui.input, user.find(marker="model-ref-uri").elements.pop())
    assert uri.visible
    uri.value = "https://example.invalid/m.pth"
    user.find(marker="model-ref-uri").trigger("keydown.enter")

    await _eventually(lambda: port.get_value() == ModelRef(urls=("https://example.invalid/m.pth",)))
    assert _status(user) == "missing — Show in Models"


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_address_without_scheme_is_not_written(user: User, state: Any) -> None:
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _select(user).value = OTHER

    cast(ui.input, user.find(marker="model-ref-uri").elements.pop()).value = "example.invalid/m.pth"
    user.find(marker="model-ref-uri").trigger("keydown.enter")
    await asyncio.sleep(0.05)

    assert port.get_value() == ModelRef()
    assert _status(user) == "an address starts with hf:// or https://"


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_hf_address_is_pinned_when_the_hub_answers(
    user: User, state: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    hf = _mod("haybale_models.hf")
    asked: list[str] = []

    def remote(uri: str) -> tuple[str, int]:
        asked.append(uri)
        return SHA, 7

    monkeypatch.setattr(hf, "remote_sha256", remote)
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _select(user).value = OTHER

    cast(ui.input, user.find(marker="model-ref-uri").elements.pop()).value = "hf://org/repo/m.pth"
    user.find(marker="model-ref-uri").trigger("keydown.enter")

    pinned = ModelRef(urls=("hf://org/repo/m.pth",), sha256=SHA, size=7)
    await _eventually(lambda: port.get_value() == pinned)
    user.find(marker="model-ref-uri").trigger("blur")
    await asyncio.sleep(0.05)
    assert asked == ["hf://org/repo/m.pth"]


@pytest.mark.unit
@pytest.mark.anyio
async def test_status_says_not_pinned_and_shows_pin(user: User, state: Any) -> None:
    _put(state, "dl/m.pth", source="https://example.invalid/m.pth")
    port = _port(ModelRef(urls=("https://example.invalid/m.pth",)))
    await _open(user, _direct(port))

    assert _status(user) == "not pinned — Pin digest"
    pin = user.find(marker="model-ref-pin").elements.pop()
    assert pin.visible
    assert pin.props["data-hw-requires"] == "edit"


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_picked_unindexed_file_is_hashed_then_written(user: User, state: Any) -> None:
    keys = _mod("haybale_models.keys")
    path = location_of(keys.MODELS_VOLUME) / "mine" / "x.pth"
    path.parent.mkdir(parents=True)
    path.write_bytes(DATA)
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _select(user).value = OTHER

    user.find(marker="model-ref-browse").click()
    user.find(marker="model-ref-tree-models").trigger("update:selected", str(path))

    await _eventually(lambda: port.get_value() == ModelRef(sha256=SHA, size=7, label="x.pth"))
    assert state.index.sha256_at(path) == SHA
    assert _status(user) == "resolved: x.pth, 7 B"


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_picked_hf_snapshot_file_writes_its_hf_address(user: User, state: Any) -> None:
    repo = state.hf_cache / "models--org--repo"
    (repo / "blobs").mkdir(parents=True)
    (repo / "blobs" / SHA).write_bytes(DATA)
    snapshot = repo / "snapshots" / "c0ffee" / "m.pth"
    snapshot.parent.mkdir(parents=True)
    snapshot.symlink_to(repo / "blobs" / SHA)
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _select(user).value = OTHER

    user.find(marker="model-ref-browse").click()
    user.find(marker="model-ref-tree-hugging").trigger("update:selected", str(snapshot))

    await _eventually(
        lambda: port.get_value()
        == ModelRef(urls=("hf://org/repo/m.pth@c0ffee",), sha256=SHA, size=7, label="m.pth")
    )


# =============================================================================
# Through the edit route
# =============================================================================


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


@pytest.fixture
def editor(held_graph: BaseGraph, library_system) -> Editor:
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=False)
    return Editor(held_graph, library_system.get_node_factory(), undo_config=config)


def _routed(library_system, held_graph: BaseGraph, editor: Editor, mode: LevelMode, value: Any) -> tuple:
    cls = _mod("haybale_models.nodes.resolve_model").ResolveModelNode
    wrapper = make_node(held_graph, cls.class_identity.registry_key)
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    port = wrapper.node.ports["model"]
    port.set_value(value)
    factory = library_system.injector.get(WidgetFactory)
    route = edit_route(editor, mode)

    def build() -> Any:
        widget, _element = factory.render_widget(
            "haybale-models:widget:ModelRefWidget",
            port,
            wrapper.node_id,
            route=route,
            minimum=LevelMode.OPERATE,
        )
        return widget

    return port, build


@pytest.mark.integration
@pytest.mark.anyio
async def test_pin_digest_is_an_undoable_edit(
    user: User, state: Any, library_system, held_graph: BaseGraph, editor: Editor
) -> None:
    _put(state, "dl/m.pth", source="https://example.invalid/m.pth")
    unpinned = ModelRef(urls=("https://example.invalid/m.pth",))
    port, build = _routed(library_system, held_graph, editor, LevelMode.EDIT, unpinned)
    widget = await _open(user, build)
    assert type(widget).__name__ == "ModelRefWidget"
    assert editor.can_undo() is False

    user.find(marker="model-ref-pin").click()

    await _eventually(lambda: port.get_value() == unpinned.pinned(SHA, 7))
    assert _status(user) == "resolved: m.pth, 7 B"
    assert editor.can_undo() is True
    editor.undo()
    assert port.get_value().sha256 is None
    assert editor.can_undo() is False
    assert _status(user) == "not pinned — Pin digest"


@pytest.mark.integration
@pytest.mark.anyio
async def test_view_mode_widget_is_read_only(
    user: User, state: Any, library_system, held_graph: BaseGraph, editor: Editor
) -> None:
    _put(state, "dl/m.pth", source="https://example.invalid/m.pth")
    unpinned = ModelRef(urls=("https://example.invalid/m.pth",))
    port, build = _routed(library_system, held_graph, editor, LevelMode.VIEW, unpinned)
    await _open(user, build)

    _select(user).value = "haybale-beta:model:4x-Sharp"
    user.find(marker="model-ref-pin").click()
    await asyncio.sleep(0.05)

    assert port.get_value() == unpinned
    assert _select(user).value == OTHER
    assert editor.can_undo() is False


@pytest.mark.unit
@pytest.mark.anyio
async def test_pin_hashes_a_file_of_unknown_digest(
    user: User, state: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = state.hf_cache / "models--org--repo" / "snapshots" / "abc" / "cfg.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(DATA)
    monkeypatch.setattr(_mod("huggingface_hub"), "try_to_load_from_cache", lambda *a, **k: str(snapshot))
    unpinned = ModelRef(urls=("hf://org/repo/cfg.json",))
    port = _port(unpinned)
    await _open(user, _direct(port))
    assert _status(user) == "not pinned — Pin digest"

    user.find(marker="model-ref-pin").click()

    await _eventually(lambda: port.get_value() == unpinned.pinned(SHA, 7))
    assert _status(user) == "resolved: cfg.json, 7 B"


class _DeadWrapper:
    """A wrapper whose node is gone: ``.node`` raises as ``NodeWrapper.node`` does after cleanup."""

    is_cleaned_up = False

    @property
    def node(self) -> Any:
        raise RuntimeError("NodeWrapper has no node instance (not built or already cleaned up).")


@pytest.mark.unit
@pytest.mark.anyio
async def test_preference_falls_back_when_the_wrapper_has_no_node(user: User, state: Any) -> None:
    port = _port(ModelRef(), {"prefer": [{"precision": "fp16"}]})
    port._wrapper = _DeadWrapper()  # type: ignore[assignment]
    widget = await _open(user, _direct(port))
    assert widget._preference() == [{"precision": "fp16"}]


@pytest.mark.unit
@pytest.mark.anyio
async def test_preference_falls_back_when_the_wrapper_is_cleaned_up(user: User, state: Any) -> None:
    port = _port(ModelRef(), {"prefer": [{"precision": "fp16"}]})
    node = SimpleNamespace(model_preference=lambda _pid: [{"precision": "fp32"}])
    port._wrapper = SimpleNamespace(node=node, is_cleaned_up=True)  # type: ignore[assignment]
    widget = await _open(user, _direct(port))
    assert widget._preference() == [{"precision": "fp16"}]
