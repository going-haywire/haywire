"""IMAGE types and the layout adapters, resolved through the adapter factory."""

import importlib
from typing import Any

import numpy as np
import pytest

from haywire.core.types.enums import StoreStrategy

pytestmark = pytest.mark.integration


def _types() -> Any:
    return importlib.import_module("haybale_image.types.image")


def _value() -> Any:
    return importlib.import_module("haybale_image.value")


def _img(layout: Any, channels: int = 0) -> Any:
    shape = (2, 3) if channels == 0 else (2, 3, channels)
    return _value().ImageValue.from_array(np.full(shape, 200, dtype=np.uint8))


def _chain(library_system: Any, src: Any, dst: Any) -> Any:
    first, error = library_system.get_adapter_factory().create_chain(src, dst, "edge-test")
    assert error is None, error
    return first


def _named(adapter: Any) -> list[str]:
    """Class names along the chain, terminal ReturnAdapter dropped."""
    names = []
    while adapter is not None and type(adapter).__name__ != "ReturnAdapter":
        names.append(type(adapter).__name__)
        adapter = getattr(adapter, "child", None)
    return names


def test_defaults_are_empty_of_their_layout(graph_with_library_system):
    t, v = _types(), _value()
    for cls, layout in (
        (t.IMAGE, v.Layout.GRAY),
        (t.IMAGE_GRAY, v.Layout.GRAY),
        (t.IMAGE_RGB, v.Layout.RGB),
        (t.IMAGE_RGBA, v.Layout.RGBA),
    ):
        value = cls()._value
        assert value.layout is layout
        assert value.is_empty
        assert cls.create_field()._default.layout is layout


def test_to_dict_is_descriptive_and_from_dict_is_empty(graph_with_library_system):
    t, v = _types(), _value()
    assert t.IMAGE_RGB().to_dict() == {"value": {"width": 0, "height": 0, "layout": v.Layout.RGB.value}}
    restored = t.IMAGE_RGBA.from_dict({"value": {}})
    assert restored.is_empty
    assert restored.layout is v.Layout.RGBA
    assert t.IMAGE.from_dict({}).layout is v.Layout.GRAY


@pytest.mark.parametrize("name", ["IMAGE", "IMAGE_GRAY", "IMAGE_RGB", "IMAGE_RGBA"])
def test_image_never_stored(graph_with_library_system, name):
    assert getattr(_types(), name).class_identity.store_strategy is StoreStrategy.NEVER


def test_derived_to_image_is_passthrough(graph_with_library_system, library_system):
    t = _types()
    assert _named(_chain(library_system, t.IMAGE_RGB, t.IMAGE)) == []


def test_gray_to_rgb_chains_via_image(graph_with_library_system, library_system):
    t, v = _types(), _value()
    adapter = _chain(library_system, t.IMAGE_GRAY, t.IMAGE_RGB)
    assert _named(adapter) == ["ImageToRgbAdapter"]
    assert adapter.convert(_img(v.Layout.GRAY)).layout is v.Layout.RGB


def test_rgba_to_rgb_drops_alpha(graph_with_library_system, library_system):
    t, v = _types(), _value()
    adapter = _chain(library_system, t.IMAGE_RGBA, t.IMAGE_RGB)
    out = adapter.convert(_img(v.Layout.RGBA, 4))
    assert out.layout is v.Layout.RGB
    assert out.array(np.uint8).shape == (2, 3, 3)


def test_image_to_gray_and_rgba(graph_with_library_system, library_system):
    t, v = _types(), _value()
    gray = _chain(library_system, t.IMAGE, t.IMAGE_GRAY).convert(_img(v.Layout.RGB, 3))
    rgba = _chain(library_system, t.IMAGE, t.IMAGE_RGBA).convert(_img(v.Layout.RGB, 3))
    assert gray.layout is v.Layout.GRAY
    assert rgba.layout is v.Layout.RGBA
