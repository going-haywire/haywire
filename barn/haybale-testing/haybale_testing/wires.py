"""Test-only wire types."""

from haywire.api import (
    ARROW_HEAD_WIDGET,
    CHOICES,
    COLOR,
    FLOAT,
    NO_ARROW_HEAD,
    STRING,
    EdgeSettings,
    WireRole,
    WireType,
    dash_choices,
    setting,
)
from haywire.core.edge.arrow_heads import DEFAULT_HEAD_SIZE, head_size_choices


class TestVisualStyle(EdgeSettings):
    """The style of a test visual edge: every field the canvas draws."""

    color = setting[COLOR]("#8e8e8e", label="Colour")
    width = setting[FLOAT](2.0, label="Width", min=0.5, max=12.0)
    dash = setting[CHOICES]("solid", label="Dash", widget_config={"options": dash_choices})
    arrow_start = setting[STRING](NO_ARROW_HEAD, label="Start Head", widget={"key": ARROW_HEAD_WIDGET})
    arrow_start_size = setting[CHOICES](
        DEFAULT_HEAD_SIZE, label="Start Head Size", widget_config={"options": head_size_choices}
    )
    arrow_end = setting[STRING]("arrow", label="End Head", widget={"key": ARROW_HEAD_WIDGET})
    arrow_end_size = setting[CHOICES](
        DEFAULT_HEAD_SIZE, label="End Head Size", widget_config={"options": head_size_choices}
    )


class TestVisualWire(WireType):
    """A drawn-only wire for tests: saved and drawn, never executed, styled per edge."""

    role = WireRole.VISUAL
    propagation = ()
    pin_kind = "test_visual"
    style = TestVisualStyle
