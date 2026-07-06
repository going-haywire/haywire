import haywire.core.graph.editor  # noqa: F401

import pytest
from typing import Any
from unittest.mock import MagicMock, patch

from haywire.barn.builtin.widgets.basic_widgets import SelectWidget
from haywire.core.types.port import DataPort
from haywire.core.types.enums import FlowType, PortType
from haywire.barn.builtin.types import STRING

pytestmark = pytest.mark.unit


def make_string_port_with_config(widget_config: dict[str, Any], port_id: str = "select_test") -> DataPort:
    """Create a STRING port with custom widget config.

    ``promoted=True``: several tests in this module deliberately exercise a
    LIVE CALLABLE in ``widget_config`` (dynamic-options resolution at build
    time). A plain (non-promoted) port now rejects a non-serializable
    widget_config at construction (ADR 0019/0018) — a promoted port is exempt
    because its widget_config is never serialized (it round-trips through the
    owning descriptor instead), which is exactly the "safe" case for a live
    callable this suite is testing.
    """
    port = DataPort(
        registry_id="string",
        registry_key="haybale_core:type:string",
        label="S",
        id=port_id,
        type_cls=STRING,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
        widget_config=widget_config,
        promoted=True,
    )
    return port


def test_select_widget_resolves_callable_options():
    """SelectWidget should resolve callable options at build time."""

    # Create a callable that returns a list of options
    def options_callable() -> list[str]:
        return ["a", "b", "c"]

    config = {"properties": {"options": options_callable}}

    port = make_string_port_with_config(config)
    widget = SelectWidget(port)

    # Mock ui.select to capture the options passed to it
    with patch("haywire.barn.builtin.widgets.basic_widgets.ui.select") as mock_select:
        mock_element = MagicMock()
        mock_select.return_value = mock_element
        mock_element.classes.return_value = mock_element

        # Call build() directly to test option resolution
        widget.build()

        # Verify that ui.select was called with resolved options
        mock_select.assert_called_once()
        call_kwargs = mock_select.call_args[1]
        assert call_kwargs["options"] == ["a", "b", "c"]


def test_select_widget_resolves_callable_options_dict():
    """SelectWidget should resolve callable that returns a dict of options."""

    def options_callable() -> dict[str, str]:
        return {"1": "One", "2": "Two", "3": "Three"}

    config = {"properties": {"options": options_callable}}

    port = make_string_port_with_config(config)
    widget = SelectWidget(port)

    with patch("haywire.barn.builtin.widgets.basic_widgets.ui.select") as mock_select:
        mock_element = MagicMock()
        mock_select.return_value = mock_element
        mock_element.classes.return_value = mock_element

        widget.build()

        call_kwargs = mock_select.call_args[1]
        assert call_kwargs["options"] == {"1": "One", "2": "Two", "3": "Three"}


def test_select_widget_handles_list_options():
    """SelectWidget should still work with static list options."""
    config = {"properties": {"options": ["Low", "Medium", "High"]}}

    port = make_string_port_with_config(config)
    widget = SelectWidget(port)

    with patch("haywire.barn.builtin.widgets.basic_widgets.ui.select") as mock_select:
        mock_element = MagicMock()
        mock_select.return_value = mock_element
        mock_element.classes.return_value = mock_element

        widget.build()

        call_kwargs = mock_select.call_args[1]
        assert call_kwargs["options"] == ["Low", "Medium", "High"]


def test_select_widget_handles_dict_options():
    """SelectWidget should still work with static dict options."""
    config = {"properties": {"options": {0: "Off", 1: "On"}}}

    port = make_string_port_with_config(config)
    widget = SelectWidget(port)

    with patch("haywire.barn.builtin.widgets.basic_widgets.ui.select") as mock_select:
        mock_element = MagicMock()
        mock_select.return_value = mock_element
        mock_element.classes.return_value = mock_element

        widget.build()

        call_kwargs = mock_select.call_args[1]
        assert call_kwargs["options"] == {0: "Off", 1: "On"}


def test_select_widget_empty_options():
    """SelectWidget should handle missing options gracefully."""
    config = {"properties": {}}

    port = make_string_port_with_config(config)
    widget = SelectWidget(port)

    with patch("haywire.barn.builtin.widgets.basic_widgets.ui.select") as mock_select:
        mock_element = MagicMock()
        mock_select.return_value = mock_element
        mock_element.classes.return_value = mock_element

        widget.build()

        call_kwargs = mock_select.call_args[1]
        assert call_kwargs["options"] == []


def test_select_widget_callable_invoked_at_build_time():
    """Verify that callable options are invoked at build time, not at config time."""
    call_count = 0

    def options_callable() -> list[str]:
        nonlocal call_count
        call_count += 1
        return ["option1", "option2"]

    config = {"properties": {"options": options_callable}}

    port = make_string_port_with_config(config)
    widget = SelectWidget(port)

    # At this point the callable has not been invoked yet
    assert call_count == 0

    with patch("haywire.barn.builtin.widgets.basic_widgets.ui.select") as mock_select:
        mock_element = MagicMock()
        mock_select.return_value = mock_element
        mock_element.classes.return_value = mock_element

        # build() should invoke the callable
        widget.build()
        assert call_count == 1

        # The options passed to ui.select should be the result of the call
        call_kwargs = mock_select.call_args[1]
        assert call_kwargs["options"] == ["option1", "option2"]
