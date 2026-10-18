"""TextWidget's commit mode: the value is written on Enter or blur, never per keystroke.

The browser half (the real Enter and blur events) is in
``tests/ui/harness/test_list_widget.py``; these pin the server-side contract.
"""

from typing import Any, cast

import pytest
from nicegui import Client

from haywire.barn.builtin.types import STRING
from haywire.barn.builtin.widgets import TextWidget
from haywire.ui.panel.setting_widget_model import SettingWidgetModel
from haywire.ui.widget.converters import BindingMode

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _rendered(*, commit: bool):
    """A TextWidget on a STRING cell whose edits land in the cell and are recorded."""
    cell = STRING.create_field(default_override={"value": ""})
    edits: list = []

    def on_edit(value: Any) -> None:
        edits.append(value)
        cell.set_value(value)

    properties = {"commit": True} if commit else {}
    model = SettingWidgetModel(
        field_id="text", widget_config={"properties": properties}, cell=cell, on_edit=on_edit
    )
    widget = TextWidget(model)
    with Client(cast(Any, _noop_page), request=None):
        widget.render()
    return cast(Any, widget), cell, edits


def test_commit_mode_binds_one_way():
    widget, _, _ = _rendered(commit=True)
    assert widget._bindings[0].mode is BindingMode.ONE_WAY

    plain, _, _ = _rendered(commit=False)
    assert plain._bindings[0].mode is BindingMode.TWO_WAY


def test_commit_writes_the_typed_text_once():
    widget, cell, edits = _rendered(commit=True)

    widget._input.value = "abc"
    assert edits == []

    widget._commit()
    assert edits == ["abc"]
    assert cell.get_value() == "abc"

    widget._commit()
    assert edits == ["abc"], "a commit equal to the model's value writes nothing"


def test_commit_mode_still_shows_model_changes():
    widget, cell, _ = _rendered(commit=True)
    cell.set_value("zz")
    assert widget._input.value == "zz"
