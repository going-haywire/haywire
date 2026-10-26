"""Tests for render_panels — separators between the order bands of a banded surface."""

from types import SimpleNamespace
from typing import Any, cast

import pytest

from haywire.ui.panel import host_rendering
from haywire.ui.panel.host_rendering import render_panels
from haywire.ui.panel.layout import PanelLayout


class _Container:
    """A container recording what is drawn into it, in order."""

    def __init__(self) -> None:
        self.default_slot = SimpleNamespace(children=[])

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _Separator:
    def __init__(self, container: _Container) -> None:
        self._container = container
        container.default_slot.children.append(self)

    def delete(self) -> None:
        self._container.default_slot.children.remove(self)


def _panel(name: str, order: int, *, draws: bool = True) -> type:
    return type(name, (), {"class_identity": SimpleNamespace(order=order), "draws": draws})


@pytest.fixture
def drawn(monkeypatch):
    container = _Container()

    def _render_panel(cls, _ctx, _layout, **_kw):
        if cls.draws:
            container.default_slot.children.append(cls.__name__)
        return True

    monkeypatch.setattr(host_rendering, "render_panel", _render_panel)
    monkeypatch.setattr(host_rendering.hui, "separator", lambda **_kw: _Separator(container))

    def _render(panels: list[type], *, banded: bool = True) -> list[str]:
        surface = cast(Any, SimpleNamespace(banded=banded))
        render_panels(surface, panels, [], cast(Any, None), PanelLayout(container))
        return ["---" if isinstance(c, _Separator) else c for c in container.default_slot.children]

    return _render


def test_a_separator_falls_between_bands(drawn):
    assert drawn([_panel("Copy", 100), _panel("Enter", 200), _panel("Group", 210)]) == [
        "Copy",
        "---",
        "Enter",
        "Group",
    ]


def test_a_band_that_draws_nothing_gets_no_separator(drawn):
    panels = [_panel("Copy", 100), _panel("Empty", 200, draws=False), _panel("Delete", 600)]

    assert drawn(panels) == ["Copy", "---", "Delete"]


def test_no_separator_at_the_top_when_the_first_band_draws_nothing(drawn):
    assert drawn([_panel("Errors", 0, draws=False), _panel("Copy", 100)]) == ["Copy"]


def test_panels_are_drawn_in_order(drawn):
    assert drawn([_panel("Delete", 600), _panel("Copy", 100)]) == ["Copy", "---", "Delete"]


def test_an_unbanded_surface_draws_no_separators(drawn):
    assert drawn([_panel("Copy", 100), _panel("Delete", 600)], banded=False) == ["Copy", "Delete"]
