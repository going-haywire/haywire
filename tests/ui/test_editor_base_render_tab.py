"""Tests for BaseEditor.draw_tab — the default tab/icon interior renderer."""

from types import SimpleNamespace

from haywire.ui.editor import base as base_mod
from haywire.ui.editor.base import BaseEditor


class _FakeUiElement:
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def tooltip(self, *a, **_k):
        self.tooltip_args = a
        return self

    def classes(self, *_a, **_k):
        return self

    def style(self, *_a, **_k):
        return self


def _install_base_ui_fakes(monkeypatch):
    """Record ui.icon / ui.label calls made on the base module."""
    created: list = []

    def _factory(kind):
        def _make(*a, **k):
            el = _FakeUiElement(*a, **k)
            created.append((kind, el))
            return el

        return _make

    monkeypatch.setattr(base_mod.ui, "icon", _factory("icon"), raising=False)
    monkeypatch.setattr(base_mod.ui, "label", _factory("label"), raising=False)
    return created


class _MinimalEditor(BaseEditor):
    class_identity = SimpleNamespace(
        registry_key="t:editor:1",
        label="My Editor",
        icon="account_tree",
        default_slot="main",
    )

    def draw(self, context, container) -> None:  # pragma: no cover - unused here
        pass


def _make_editor(label: str = "") -> _MinimalEditor:
    wrapper = SimpleNamespace(label=label)
    editor = _MinimalEditor(wrapper)
    return editor


def test_draw_tab_horizontal_default_draws_label_from_wrapper(monkeypatch):
    created = _install_base_ui_fakes(monkeypatch)
    editor = _make_editor(label="graph.hwg")

    editor.draw_tab(SimpleNamespace(), orientation="horizontal")

    labels = [el for kind, el in created if kind == "label"]
    assert any(el._args and el._args[0] == "graph.hwg" for el in labels)
    # Horizontal default draws no icon.
    assert not any(kind == "icon" for kind, _ in created)


def test_draw_tab_horizontal_falls_back_to_class_label(monkeypatch):
    created = _install_base_ui_fakes(monkeypatch)
    editor = _make_editor(label="")  # empty wrapper label

    editor.draw_tab(SimpleNamespace(), orientation="horizontal")

    labels = [el for kind, el in created if kind == "label"]
    assert any(el._args and el._args[0] == "My Editor" for el in labels)


def test_draw_tab_vertical_default_draws_icon_with_tooltip(monkeypatch):
    created = _install_base_ui_fakes(monkeypatch)
    editor = _make_editor(label="ignored-in-vertical")

    editor.draw_tab(SimpleNamespace(), orientation="vertical")

    icons = [el for kind, el in created if kind == "icon"]
    assert any(el._args and el._args[0] == "account_tree" for el in icons)
    # Tooltip carries the human-readable class label.
    assert any(getattr(el, "tooltip_args", None) == ("My Editor",) for el in icons)
    # Vertical default draws no text label.
    assert not any(kind == "label" for kind, _ in created)
