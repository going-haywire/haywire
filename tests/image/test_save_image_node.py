"""Save Image: if_exists placement, depth, per-format settings bags and their visibility."""

import importlib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from haywire.core.settings import UiState
from haywire.core.volumes import VolumePath, get_volume_store
from tests.conftest import make_node

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _save(graph: Any) -> Any:
    return _add(graph, "haybale_image.nodes.save_image", "SaveImageNode")


def _image(dtype: Any = np.uint8, *, noise: bool = False) -> Any:
    value_mod = importlib.import_module("haybale_image.value")
    rng = np.random.default_rng(0)
    f = rng.random((24, 32, 3)) if noise else np.tile(np.linspace(0, 1, 32), (24, 1))[..., None].repeat(3, 2)
    top = {np.uint8: 255, np.uint16: 65535}[dtype]
    return value_mod.ImageValue.from_array((f * top).astype(dtype))


def _read(path: Path) -> Any:
    return importlib.import_module("haybale_image.io.codecs").read_image(path)


def _run(
    node: Any, rel: str, image: Any = None, *, if_exists: str = "overwrite", depth: str = "source"
) -> str:
    return node.worker(
        MagicMock(),
        image=_image() if image is None else image,
        path=VolumePath(SCANS, rel),
        if_exists=if_exists,
        depth=depth,
    )


@pytest.fixture
def scans(tmp_path):
    get_volume_store().add(SCANS, label="Scans", description="", location=tmp_path)
    return tmp_path


def test_saves_png_and_reports_saved(graph_with_library_system, scans):
    node = _save(graph_with_library_system)
    assert _run(node, "out.png") == "next"
    assert _read(scans / "out.png").width == 32
    assert node.ports["saved"].get_value() == VolumePath(SCANS, "out.png")


def test_saving_bar_sweeps_while_encoding_and_writing(graph_with_library_system, scans, monkeypatch):
    from haywire.barn.builtin.types.progress import PROGRESS

    node = _save(graph_with_library_system)
    mod = importlib.import_module("haybale_image.nodes.save_image")
    seen: list[tuple[bool, Any, str]] = []

    def record(real: Any) -> Any:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            bar = node.progress.main
            seen.append((bar.active, bar.fraction, bar.label))
            return real(*args, **kwargs)

        return wrapped

    monkeypatch.setattr(mod, "encode_image", record(mod.encode_image))
    monkeypatch.setattr(mod, "atomic_write", record(mod.atomic_write))
    _run(node, "out.png")
    assert seen == [(True, None, "encoding"), (True, None, "writing")]
    assert node.progress.main == PROGRESS()


def test_skip_keeps_existing_and_reports_it(graph_with_library_system, scans):
    (scans / "out.png").write_bytes(b"keep")
    node = _save(graph_with_library_system)
    assert _run(node, "out.png", if_exists="skip") == "next"
    assert (scans / "out.png").read_bytes() == b"keep"
    assert node.ports["saved"].get_value() == VolumePath(SCANS, "out.png")


def test_unique_suffix_reports_suffixed_path(graph_with_library_system, scans):
    (scans / "sub").mkdir()
    (scans / "sub" / "out.png").write_bytes(b"keep")
    node = _save(graph_with_library_system)
    assert _run(node, "sub/out.png", if_exists="unique-suffix") == "next"
    assert (scans / "sub" / "out.png").read_bytes() == b"keep"
    assert _read(scans / "sub" / "out_1.png").width == 32
    assert node.ports["saved"].get_value() == VolumePath(SCANS, "sub/out_1.png")


def test_missing_folder_raises(graph_with_library_system, scans):
    node = _save(graph_with_library_system)
    with pytest.raises(FileNotFoundError, match="Create Folder"):
        _run(node, "nowhere/out.png")


def test_empty_image_raises(graph_with_library_system, scans):
    value_mod = importlib.import_module("haybale_image.value")
    node = _save(graph_with_library_system)
    with pytest.raises(ValueError, match="image is empty"):
        _run(node, "out.png", value_mod.ImageValue.empty(value_mod.Layout.RGB))
    assert not (scans / "out.png").exists()


def test_depth_source_16_png_stays_16(graph_with_library_system, scans):
    node = _save(graph_with_library_system)
    _run(node, "deep.png", _image(np.uint16))
    assert _read(scans / "deep.png").source_depth == 16


def test_depth_16_jpeg_defuses_to_8(graph_with_library_system, scans):
    node = _save(graph_with_library_system)
    assert _run(node, "deep.jpg", _image(np.uint16), depth="16") == "next"
    assert _read(scans / "deep.jpg").source_depth == 8


def test_node_quality_overrides_library_default(graph_with_library_system, scans):
    node = _save(graph_with_library_system)
    noisy = _image(noise=True)
    _run(node, "hi.jpg", noisy)
    node.jpeg.quality = 20
    _run(node, "lo.jpg", noisy)
    assert (scans / "lo.jpg").stat().st_size < (scans / "hi.jpg").stat().st_size


def test_library_default_reaches_node(graph_with_library_system):
    image_settings = importlib.import_module("haybale_image.settings.image_settings").ImageSettings()
    node = _save(graph_with_library_system)
    assert node.jpeg.quality == 95
    image_settings.jpeg_quality = 40
    try:
        assert node.jpeg.quality == 40
    finally:
        image_settings.jpeg_quality = 95


_BAGS = ("png", "jpeg", "webp", "tiff", "avif")


def _states(node: Any) -> dict[str, set[UiState]]:
    return {
        name: {
            getattr(node, name)._effective_ui_state(f)
            for f in type(getattr(node, name))._settings_descriptors()
        }
        for name in _BAGS
    }


def test_only_current_format_bag_visible(graph_with_library_system):
    node = _save(graph_with_library_system)
    node.hb_refresh_format_bags(VolumePath(SCANS, "a/b.JPG"))
    states = _states(node)
    assert states.pop("jpeg") == {UiState.NORMAL}
    assert all(s == {UiState.HIDDEN} for s in states.values())


def test_all_bags_visible_without_path_extension(graph_with_library_system):
    node = _save(graph_with_library_system)
    node.hb_refresh_format_bags(VolumePath(SCANS, "b.jpg"))
    node.hb_refresh_format_bags(VolumePath(SCANS, "b"))
    assert all(s == {UiState.NORMAL} for s in _states(node).values())
    node.hb_refresh_format_bags(VolumePath(SCANS, "b.jpg"))
    node.hb_refresh_format_bags(None)
    assert all(s == {UiState.NORMAL} for s in _states(node).values())


def test_path_edit_refreshes_bag_visibility(graph_with_library_system):
    node = _save(graph_with_library_system)
    node.ports["path"].set_value(VolumePath(SCANS, "x.tiff"))
    assert _states(node)["tiff"] == {UiState.NORMAL}
    assert _states(node)["jpeg"] == {UiState.HIDDEN}


def test_worker_refreshes_bag_visibility(graph_with_library_system, scans):
    node = _save(graph_with_library_system)
    _run(node, "out.webp")
    assert _states(node)["webp"] == {UiState.NORMAL}
    assert _states(node)["png"] == {UiState.HIDDEN}


def test_load_outlet_wires_into_save(graph_with_library_system):
    graph = graph_with_library_system
    load = _add(graph, "haybale_image.nodes.load_image", "LoadImageNode")
    save = _save(graph)
    edge = graph.create_edge_wrapper(load.node_id, "image", save.node_id, "image")
    assert edge is not None
    assert save.ports["image"].data.has_linked_value()


def _bundle_stamps(image: Any) -> Any:
    from haywire.barn.builtin.types import FLOAT, INT, VEC3F
    from haywire.core.settings import Vec3f

    return (
        image.stamped("camera_timestamp", 1.5, FLOAT)
        .stamped("camera_frame_number", 7, INT)
        .stamped("offset", Vec3f([1.0, 2.0, 3.0]), VEC3F)
    )


def _load_back(graph: Any, rel: str) -> tuple[Any, Any]:
    load = _add(graph, "haybale_image.nodes.load_image", "LoadImageNode")
    load.worker(MagicMock(), path=VolumePath(SCANS, rel))
    return load.ports["image"].get_value(), load


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16])
def test_write_fields_round_trips_through_a_png(graph_with_library_system, scans, dtype):
    node = _save(graph_with_library_system)
    node.png.write_fields = True
    _run(node, "out.png", _bundle_stamps(_image(dtype)))
    back, load = _load_back(graph_with_library_system, "out.png")
    assert back.fields["camera_timestamp"].value == 1.5
    assert back.fields["camera_frame_number"].value == 7
    assert back.fields["offset"].value == [1.0, 2.0, 3.0]
    assert back.source_depth == {np.uint8: 8, np.uint16: 16}[dtype]
    assert load.wrapper.state.warnings == []


def test_fields_are_not_written_by_default(graph_with_library_system, scans):
    _run(_save(graph_with_library_system), "out.png", _bundle_stamps(_image()))
    back, _ = _load_back(graph_with_library_system, "out.png")
    assert dict(back.fields) == {}


def test_write_fields_applies_to_png_only(graph_with_library_system, scans):
    node = _save(graph_with_library_system)
    node.png.write_fields = True
    _run(node, "out.jpg", _bundle_stamps(_image()))
    back, _ = _load_back(graph_with_library_system, "out.jpg")
    assert dict(back.fields) == {}


def test_an_unstorable_field_fails_loudly_and_writes_no_file(graph_with_library_system, scans):
    from haybale_image.types.image import IMAGE_RGB

    node = _save(graph_with_library_system)
    node.png.write_fields = True
    image = _bundle_stamps(_image()).stamped("preview", _image(), IMAGE_RGB)
    with pytest.raises(ValueError, match=r"preview \(IMAGE_RGB, this type is not saved\)"):
        _run(node, "out.png", image, if_exists="unique-suffix")
    assert list(scans.glob("out*")) == []


def test_write_fields_keeps_the_icc_profile(graph_with_library_system, scans):
    value_mod = importlib.import_module("haybale_image.value")
    node = _save(graph_with_library_system)
    node.png.write_fields = True
    image = _bundle_stamps(_image().with_metadata(value_mod.ImageMetadata(icc=b"profile")))
    _run(node, "out.png", image)
    back, _ = _load_back(graph_with_library_system, "out.png")
    assert back.metadata.icc == b"profile"
    assert back.fields["camera_frame_number"].value == 7


def test_a_field_whose_type_is_gone_loads_the_image_and_warns(graph_with_library_system, scans):
    import json

    from haybale_image.io.png_text import FIELDS_KEYWORD, with_text_chunk

    codecs = importlib.import_module("haybale_image.io.codecs")
    options = codecs.EncodeOptions()
    fmt = importlib.import_module("haybale_image.io.formats").Format.PNG
    doc = {
        "version": 1,
        "fields": {
            "kept": {"type": "haywire-core:type:INT", "data": {"value": 4}},
            "lost": {"type": "nolib:type:GONE", "data": {"value": 1}},
        },
    }
    (scans / "out.png").write_bytes(
        with_text_chunk(codecs.encode_image(_image(), fmt, options), FIELDS_KEYWORD, json.dumps(doc))
    )
    back, load = _load_back(graph_with_library_system, "out.png")
    assert not back.is_empty
    assert set(back.fields) == {"kept"}
    warnings = load.wrapper.state.warnings
    assert len(warnings) == 1
    assert "lost" in warnings[0].message
    assert "nolib:type:GONE" in warnings[0].message

    (scans / "out.png").write_bytes(codecs.encode_image(_image(), fmt, options))
    load.worker(MagicMock(), path=VolumePath(SCANS, "out.png"))
    assert load.wrapper.state.warnings == []
