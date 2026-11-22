"""A widget's cleanup is tied to its own element, not to the page.

A card redraw renders new widgets and cleans up the old ones; a page-level
``client.on_delete`` entry per render was never removed, so every redraw kept
the old widgets alive until the tab closed.
"""

from __future__ import annotations

import pytest

from haywire.barn.builtin.widgets.annotation_text_widget import AnnotationTextWidget
from tests.ui.widget.test_annotation_text_widget import _model

pytestmark = pytest.mark.unit


def test_rendering_a_widget_adds_nothing_to_the_page(nicegui_slot_context) -> None:
    first = AnnotationTextWidget(_model("Hello", lambda _value: None))
    client = first.render().client
    before = len(client.delete_handlers)

    for _ in range(5):
        widget = AnnotationTextWidget(_model("Hello", lambda _value: None))
        widget.render()
        widget.cleanup()

    assert len(client.delete_handlers) == before


def test_removing_the_widget_element_cleans_the_widget_up(nicegui_slot_context) -> None:
    widget = AnnotationTextWidget(_model("Hello", lambda _value: None))
    root = widget.render()

    root.delete()

    assert widget._cleaned_up
