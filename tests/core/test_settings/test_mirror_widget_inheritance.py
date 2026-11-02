"""A ``shadow()`` / ``watch()`` mirror draws like its source: same widget, options and range."""

from __future__ import annotations

from haywire.barn.builtin.types import CHOICES, INT, STRING
from haywire.barn.builtin.widgets import SimpleLabelWidget
from haywire.core.settings.descriptor import setting, shadow, watch
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.core.settings.settings_node import NodeSettings


class _Source(FrameworkSettings, namespace="test.mirrorwidget"):
    mode = setting[CHOICES]("a", widget_config={"options": ["a", "b"], "new_value_mode": "add-unique"})
    level = setting[INT](5, min=1, max=9)
    note = setting[STRING]("", widget=SimpleLabelWidget.config())


def test_shadow_keeps_the_select_options() -> None:
    class _Bag(NodeSettings):
        mode = shadow(_Source.mode)

    props = _Bag.__dict__["mode"].widget_config["properties"]
    assert props["options"] == ["a", "b"]
    assert props["new_value_mode"] == "add-unique"


def test_shadow_keeps_the_range() -> None:
    class _Bag(NodeSettings):
        level = shadow(_Source.level)

    assert _Bag.__dict__["level"].widget_config["properties"] == {"min": 1, "max": 9}


def test_watch_keeps_an_explicit_widget() -> None:
    class _Bag(NodeSettings):
        note = watch(_Source.note)

    assert _Bag.__dict__["note"].widget_key == _Source.note.widget_key == SimpleLabelWidget.config()["key"]


def test_the_mirror_own_widget_config_wins() -> None:
    class _Bag(NodeSettings):
        mode = shadow(_Source.mode, widget_config={"options": ["b"]})

    assert _Bag.__dict__["mode"].widget_config["properties"]["options"] == ["b"]
