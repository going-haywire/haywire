"""ModelRefWidget: the card row (state icon, name, pin, edit) and the picker dialog (Current + four tabs)."""

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
from haywire.core.catalog import CatalogRegistry
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort
from haywire.core.undo.config import UndoConfig
from haywire.core.volumes import VolumeStore, location_of
from haywire.ui.widget.factory import WidgetFactory

from tests.conftest import edit_route, make_node

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
    catalog = CatalogRegistry()
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


async def _eventually(check: Callable[[], bool]) -> None:
    for _ in range(200):
        if check():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not met")


def _cache_file(
    state: Any, repo: str, commit: str, name: str, data: bytes = DATA, main: bool = False
) -> Path:
    """Add one file to the temp HF cache in HF's own layout (blob + snapshot symlink)."""
    folder = state.hf_cache / ("models--" + repo.replace("/", "--"))
    (folder / "blobs").mkdir(parents=True, exist_ok=True)
    blob = folder / "blobs" / hashlib.sha256(data).hexdigest()
    blob.write_bytes(data)
    link = folder / "snapshots" / commit / name
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(blob)
    if main:
        (folder / "refs").mkdir(exist_ok=True)
        (folder / "refs" / "main").write_text(commit)
    return link


# =============================================================================
# Helpers for the card and the dialog
# =============================================================================


def _widget_mod() -> Any:
    return _mod("haybale_models.widgets.model_ref_widget")


def _icon_classes(widget: Any) -> list[str]:
    return list(widget._icon.classes)


def _open_picker(user: User, tab: str | None = None) -> None:
    user.find(marker="model-ref-edit").click()
    if tab is not None:
        panels = cast(ui.tab_panels, user.find(marker="model-ref-tabs").elements.pop())
        panels.value = tab


def _rows(user: User, marker: str) -> list[ui.element]:
    try:
        return sorted(user.find(marker=marker).elements, key=lambda e: e.id)
    except AssertionError:  # nothing listed yet
        return []


def _row_labels(user: User, marker: str) -> list[str]:
    return [next(c.text for c in r.descendants() if isinstance(c, ui.label)) for r in _rows(user, marker)]


def _click_row(user: User, marker: str, label: str) -> None:
    for row in _rows(user, marker):
        if next(c.text for c in row.descendants() if isinstance(c, ui.label)) == label:
            for listener in list(row._event_listeners.values()):
                if listener.type == "click":
                    row._handle_event({"listener_id": listener.id, "args": {}})
            return
    raise AssertionError(f"no row {label!r}")


def _current_name(user: User) -> str:
    return cast(ui.label, user.find(marker="model-ref-current-name").elements.pop()).text


# =============================================================================
# The card
# =============================================================================


@pytest.mark.unit
@pytest.mark.anyio
async def test_card_without_a_model_is_red_and_says_no_model(user: User, state: Any) -> None:
    widget = await _open(user, _direct(_port(ModelRef())))

    assert widget._icon.props["name"] == "model_training"
    assert "hw-text-danger" in _icon_classes(widget)
    assert widget._name.text == "no model"
    assert not widget._pin.visible


@pytest.mark.unit
@pytest.mark.anyio
async def test_card_shows_a_local_catalog_entry_green_by_name(user: User, state: Any) -> None:
    _put(state, "lib/sharp.pth")
    widget = await _open(user, _direct(_port(ModelRef(catalog="haybale-beta:catalog:4x-Sharp"))))

    assert "hw-text-success" in _icon_classes(widget)
    assert widget._name.text == "Sharp"
    assert "Catalog: haybale-beta:catalog:4x-Sharp" in widget._name_tip.text
    assert "Here: pytorch-pth, 7 B (local)" in widget._name_tip.text


@pytest.mark.unit
@pytest.mark.anyio
async def test_card_shows_a_missing_model_amber(user: User, state: Any) -> None:
    widget = await _open(user, _direct(_port(ModelRef(catalog="haybale-alpha:catalog:4x-Soft"))))

    assert widget._icon.props["name"] == "model_training"
    assert "hw-text-warning" in _icon_classes(widget)
    assert widget._name.text == "Soft"


@pytest.mark.unit
@pytest.mark.anyio
async def test_card_shows_an_unpinned_address_with_its_pin(user: User, state: Any) -> None:
    _put(state, "dl/m.pth", source="https://example.invalid/m.pth")
    widget = await _open(user, _direct(_port(ModelRef(urls=("https://example.invalid/m.pth",)))))

    assert widget._icon.props["name"] == "online_prediction"
    assert "hw-text-warning" in _icon_classes(widget)
    assert widget._name.text == "m.pth"
    assert widget._pin.visible
    assert widget._pin.props["data-hw-requires"] == "edit"


@pytest.mark.unit
@pytest.mark.anyio
async def test_card_names_an_hf_reference_by_its_repo(user: User, state: Any) -> None:
    ref = ModelRef(urls=("hf://org/my-repo/sub/m.pth",), sha256=SHA, size=7, label="m.pth")
    widget = await _open(user, _direct(_port(ref)))

    assert widget._name.text == "my-repo"
    assert "Address: hf://org/my-repo/sub/m.pth" in widget._name_tip.text


@pytest.mark.unit
@pytest.mark.anyio
async def test_card_uses_the_nodes_model_preference(user: User, state: Any, tmp_path: Path) -> None:
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
    root = location_of(_mod("haybale_models.keys").MODELS_VOLUME)
    _put(state, "a/fp32.pth", b"one")
    _put(state, "a/fp16.pth", b"two")
    state.index.add(root / "a/fp32.pth", "d" * 64, None)
    state.index.add(root / "a/fp16.pth", "e" * 64, None)
    port = _port(ModelRef(catalog="haybale-gamma:catalog:4x-Dual"), {"prefer": [{"precision": "fp32"}]})
    node = SimpleNamespace(
        model_preference=lambda _pid: [{"precision": "fp16"}, {}], model_filter=lambda _pid: {}
    )
    port._wrapper = SimpleNamespace(node=node, is_cleaned_up=False)  # type: ignore[assignment]
    widget = await _open(user, _direct(port))

    assert "fp16" in widget._name_tip.text


@pytest.mark.unit
@pytest.mark.anyio
async def test_card_pin_hashes_a_file_of_unknown_digest(
    user: User, state: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = state.hf_cache / "models--org--repo" / "snapshots" / "abc" / "cfg.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(DATA)
    monkeypatch.setattr(_mod("huggingface_hub"), "try_to_load_from_cache", lambda *a, **k: str(snapshot))
    unpinned = ModelRef(urls=("hf://org/repo/cfg.json",))
    port = _port(unpinned)
    widget = await _open(user, _direct(port))
    assert widget._pin.visible

    user.find(marker="model-ref-pin").click()

    await _eventually(lambda: port.get_value() == unpinned.pinned(SHA, 7))
    assert "hw-text-success" in _icon_classes(widget)


# =============================================================================
# The picker dialog
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize(
    ("ref", "tab"),
    [
        ({}, "catalog"),
        ({"catalog": "haybale-beta:catalog:4x-Sharp"}, "catalog"),
        ({"urls": ["hf://org/repo/m.pth"]}, "hf"),
        ({"urls": ["https://example.invalid/m.pth"]}, "address"),
        ({"sha256": "a" * 64, "size": 1, "label": "x.pth"}, "files"),
    ],
)
def test_picker_opens_on_the_tab_of_the_reference(ref: dict, tab: str) -> None:
    model_ref = _mod("haybale_models.value.model_ref").ModelRef
    assert _widget_mod()._tab_for(model_ref.from_dict(ref)) == tab


@pytest.mark.unit
@pytest.mark.anyio
async def test_catalog_tab_lists_only_filtered_entries_by_library(user: User, state: Any) -> None:
    _put(state, "lib/sharp.pth")
    await _open(user, _direct(_port(ModelRef(), {"filter": {"architecture": ["esrgan"]}})))
    _open_picker(user)

    # Grouped by library label (Alpha before Beta), then by name.
    assert _row_labels(user, "model-ref-catalog-pick") == ["Soft", "Sharp"]
    texts = [lbl.text for lbl in user.find(kind=ui.label).elements]
    assert "pytorch-pth · local · 7 B" in texts
    assert "pytorch-pth · not downloaded · 2.4 MB" in texts


@pytest.mark.unit
@pytest.mark.anyio
async def test_catalog_search_narrows_the_list(user: User, state: Any) -> None:
    await _open(user, _direct(_port(ModelRef())))
    _open_picker(user)

    cast(ui.input, user.find(marker="model-ref-catalog-search").elements.pop()).value = "fas"

    await _eventually(lambda: _row_labels(user, "model-ref-catalog-pick") == ["Fast"])


@pytest.mark.unit
@pytest.mark.anyio
async def test_choosing_shows_the_choice_and_use_writes_it(user: User, state: Any) -> None:
    _put(state, "lib/sharp.pth")
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _open_picker(user)

    _click_row(user, "model-ref-catalog-pick", "Sharp")

    assert _current_name(user) == "Sharp"
    assert port.get_value() == ModelRef()  # nothing stored before Use
    user.find(marker="model-ref-use").click()
    await _eventually(lambda: port.get_value() == ModelRef(catalog="haybale-beta:catalog:4x-Sharp"))


@pytest.mark.unit
@pytest.mark.anyio
async def test_cancel_stores_nothing(user: User, state: Any) -> None:
    port = _port(ModelRef(catalog="haybale-beta:catalog:4x-Sharp"))
    await _open(user, _direct(port))
    _open_picker(user)

    _click_row(user, "model-ref-catalog-pick", "Soft")
    user.find(marker="model-ref-cancel").click()
    await asyncio.sleep(0.05)

    assert port.get_value() == ModelRef(catalog="haybale-beta:catalog:4x-Sharp")


@pytest.mark.unit
@pytest.mark.anyio
async def test_clear_then_use_stores_no_model(user: User, state: Any) -> None:
    port = _port(ModelRef(catalog="haybale-beta:catalog:4x-Sharp"))
    await _open(user, _direct(port))
    _open_picker(user)

    user.find(marker="model-ref-clear").click()
    assert _current_name(user) == "no model"
    user.find(marker="model-ref-use").click()

    await _eventually(lambda: port.get_value().is_empty)


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_models_folder_file_is_hashed_then_chosen(user: User, state: Any) -> None:
    keys = _mod("haybale_models.keys")
    path = location_of(keys.MODELS_VOLUME) / "mine" / "x.pth"
    path.parent.mkdir(parents=True)
    path.write_bytes(DATA)
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _open_picker(user, "files")
    await _eventually(lambda: bool(_rows(user, "model-ref-file-pick")))

    assert _row_labels(user, "model-ref-file-pick") == ["mine/x.pth"]
    _click_row(user, "model-ref-file-pick", "mine/x.pth")
    await _eventually(lambda: _current_name(user) == "x.pth")
    user.find(marker="model-ref-use").click()

    await _eventually(lambda: port.get_value() == ModelRef(sha256=SHA, size=7, label="x.pth"))
    assert state.index.sha256_at(path) == SHA


@pytest.mark.unit
@pytest.mark.anyio
async def test_models_folder_tab_leaves_out_catalog_variants(user: User, state: Any) -> None:
    keys = _mod("haybale_models.keys")
    root = location_of(keys.MODELS_VOLUME)
    for name, data in (("catalog/sharp.pth", DATA), ("mine/own.pth", b"own weights")):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
        state.index.add(root / name, hashlib.sha256(data).hexdigest(), None)
    await _open(user, _direct(_port(ModelRef())))
    _open_picker(user, "files")
    await _eventually(lambda: bool(_rows(user, "model-ref-file-pick")))

    assert _row_labels(user, "model-ref-file-pick") == ["mine/own.pth"]


@pytest.mark.unit
@pytest.mark.anyio
async def test_hf_tab_lists_only_model_files_as_org_repo_path(user: User, state: Any) -> None:
    _cache_file(state, "org/repo", "c0ffee", "m.pth", main=True)
    _cache_file(state, "org/repo", "c0ffee", "sub/W.SafeTensors", main=True)
    _cache_file(state, "org/repo", "c0ffee", "config.json", b"{}", main=True)
    _cache_file(state, "other/tok", "beef", "tokenizer.model", b"t")
    await _open(user, _direct(_port(ModelRef())))
    _open_picker(user, "hf")
    await _eventually(lambda: bool(_rows(user, "model-ref-hf-pick")))

    assert sorted(_row_labels(user, "model-ref-hf-pick")) == ["org/repo/m.pth", "org/repo/sub/W.SafeTensors"]
    for label in user.find(kind=ui.label).elements:
        assert "models--" not in label.text
        assert "snapshots" not in label.text


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_hf_file_is_chosen_pinned_by_its_address(user: User, state: Any) -> None:
    _cache_file(state, "org/repo", "c0ffee", "m.pth")
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _open_picker(user, "hf")
    await _eventually(lambda: bool(_rows(user, "model-ref-hf-pick")))

    _click_row(user, "model-ref-hf-pick", "org/repo/m.pth")
    assert _current_name(user) == "repo"
    user.find(marker="model-ref-use").click()

    await _eventually(
        lambda: port.get_value()
        == ModelRef(urls=("hf://org/repo/m.pth@c0ffee",), sha256=SHA, size=7, label="m.pth")
    )


@pytest.mark.unit
def test_hf_rows_take_main_else_the_newest_revision(state: Any) -> None:
    import os

    old = _cache_file(state, "org/a", "old", "m.pth", b"1")
    _cache_file(state, "org/a", "new", "m.pth", b"2")
    os.utime(old.resolve(), (1, 1))
    pinned = _cache_file(state, "org/b", "c1", "m.pth", b"3", main=True)
    os.utime(pinned.resolve(), (1, 1))
    _cache_file(state, "org/b", "c2", "m.pth", b"4")

    uris = {r.label: r.uri for r in _widget_mod()._hf_model_rows(state.hf_cache)}

    assert uris == {"org/a/m.pth": "hf://org/a/m.pth@new", "org/b/m.pth": "hf://org/b/m.pth"}


def _enter_address(user: User, text: str) -> None:
    cast(ui.input, user.find(marker="model-ref-uri").elements.pop()).value = text
    user.find(marker="model-ref-uri").trigger("keydown.enter")


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_https_address_on_this_machine_is_pinned_on_use(user: User, state: Any) -> None:
    _put(state, "dl/m.pth", source="https://example.invalid/m.pth")
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _open_picker(user, "address")

    _enter_address(user, "https://example.invalid/m.pth")
    await _eventually(lambda: _current_name(user) == "m.pth")
    user.find(marker="model-ref-use").click()

    await _eventually(
        lambda: port.get_value() == ModelRef(urls=("https://example.invalid/m.pth",)).pinned(SHA, 7)
    )


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_https_address_not_here_is_stored_unpinned(user: User, state: Any) -> None:
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _open_picker(user, "address")

    _enter_address(user, "https://example.invalid/far.pth")
    await _eventually(lambda: _current_name(user) == "far.pth")
    user.find(marker="model-ref-use").click()

    await _eventually(lambda: port.get_value() == ModelRef(urls=("https://example.invalid/far.pth",)))


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_hf_address_is_pinned_when_the_hub_answers(
    user: User, state: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []

    def remote(uri: str) -> tuple[str, int]:
        asked.append(uri)
        return SHA, 7

    monkeypatch.setattr(_mod("haybale_models.hf"), "remote_sha256", remote)
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _open_picker(user, "address")

    _enter_address(user, "hf://org/repo/m.pth")
    pinned = ModelRef(urls=("hf://org/repo/m.pth",), sha256=SHA, size=7)
    await _eventually(
        lambda: cast(ui.label, user.find(marker="model-ref-uri-note").elements.pop()).text
        == "Pinned from the Hub."
    )
    user.find(marker="model-ref-use").click()

    await _eventually(lambda: port.get_value() == pinned)
    assert asked == ["hf://org/repo/m.pth"]


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_address_without_scheme_is_not_taken(user: User, state: Any) -> None:
    port = _port(ModelRef())
    await _open(user, _direct(port))
    _open_picker(user, "address")

    _enter_address(user, "example.invalid/m.pth")
    await asyncio.sleep(0.05)

    note = cast(ui.label, user.find(marker="model-ref-uri-note").elements.pop())
    assert note.text == "An address starts with hf:// or https://"
    assert _current_name(user) == "no model"


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
async def test_card_pin_is_an_undoable_edit(
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
    assert editor.can_undo() is True
    editor.undo()
    assert port.get_value().sha256 is None
    assert editor.can_undo() is False
    assert widget._pin.visible


@pytest.mark.integration
@pytest.mark.anyio
async def test_use_is_an_undoable_edit(
    user: User, state: Any, library_system, held_graph: BaseGraph, editor: Editor
) -> None:
    _put(state, "lib/sharp.pth")
    port, build = _routed(library_system, held_graph, editor, LevelMode.EDIT, ModelRef())
    await _open(user, build)
    _open_picker(user)

    _click_row(user, "model-ref-catalog-pick", "Sharp")
    user.find(marker="model-ref-use").click()

    await _eventually(lambda: port.get_value() == ModelRef(catalog="haybale-beta:catalog:4x-Sharp"))
    assert editor.can_undo() is True
    editor.undo()
    assert port.get_value().is_empty


@pytest.mark.integration
@pytest.mark.anyio
async def test_view_mode_stores_nothing(
    user: User, state: Any, library_system, held_graph: BaseGraph, editor: Editor
) -> None:
    _put(state, "dl/m.pth", source="https://example.invalid/m.pth")
    unpinned = ModelRef(urls=("https://example.invalid/m.pth",))
    port, build = _routed(library_system, held_graph, editor, LevelMode.VIEW, unpinned)
    await _open(user, build)

    user.find(marker="model-ref-pin").click()
    _open_picker(user)
    _click_row(user, "model-ref-catalog-pick", "Sharp")
    user.find(marker="model-ref-use").click()
    await asyncio.sleep(0.05)

    assert port.get_value() == unpinned
    assert editor.can_undo() is False


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


@pytest.mark.unit
@pytest.mark.anyio
async def test_the_edit_button_is_unavailable_while_the_port_says_so(user: User, state: Any) -> None:
    await _open(
        user, _direct(_port(ModelRef(), {"unavailable": "Connect the Model outlet to choose a model"}))
    )

    edit = cast(ui.button, user.find(marker="model-ref-edit").elements.pop())
    assert edit.enabled is False
