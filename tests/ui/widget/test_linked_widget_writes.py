"""A widget on a linked inlet shows the linked value and refuses writes; the view snaps back."""

from typing import Any, cast

import pytest

from tests.ui.widget._sync_fixtures import _BaseDefaultFloatWidget, make_float_port

pytestmark = pytest.mark.unit


def _linked_widget():
    port = make_float_port()
    widget = _BaseDefaultFloatWidget(port)
    widget.render()
    port._linked_edges["e1"] = cast(Any, object())
    port.set_value(4.0, edge_id="e1")
    return port, widget


def test_the_view_shows_the_linked_value():
    _port, widget = _linked_widget()

    assert widget.el.value == 4.0


def test_a_view_edit_is_refused_and_the_view_snaps_back():
    port, widget = _linked_widget()
    widget.el.value = 9.0

    widget._bindings[0]._sync_to_model(9.0)

    assert port.data.get_own_value() == 0.0
    assert port.get_value() == 4.0
    assert widget.el.value == 4.0


def test_a_direct_widget_write_is_refused_while_linked():
    port, widget = _linked_widget()

    widget.set_value(9.0)

    assert port.data.get_own_value() == 0.0
    assert widget.el.value == 4.0


def test_an_unlinked_widget_still_writes_the_own_value():
    port = make_float_port()
    widget = _BaseDefaultFloatWidget(port)
    widget.render()

    widget._bindings[0]._sync_to_model(9.0)

    assert port.get_value() == 9.0
