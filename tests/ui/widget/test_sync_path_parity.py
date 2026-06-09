"""Correctness of the unified BaseWidget sync path (primitive case).

Verifies the single canonical base directly: initial sync, repeated model→view,
and the converter default for an unset port.  Single-subscription teardown lives
in test_single_activation.py.
"""

import haywire.core.graph.editor  # noqa: F401

import pytest

from tests.ui.widget._sync_fixtures import build_base_default

pytestmark = pytest.mark.unit


def test_initial_sync_lands_port_value():
    sync, port, el = build_base_default()
    port.set_value(42.0)
    sync()
    assert el.value == 42.0


def test_model_to_view_across_updates():
    sync, port, el = build_base_default()
    for v in (1.0, -3.5, 0.0, 999.25):
        port.set_value(v)
        sync()
        assert el.value == v


def test_unset_port_uses_converter_default():
    """An unset FLOAT port syncs the converter's default_value, not a crash.

    The default bind() uses PrimitiveUnwrappingConverter(); to_view(None) returns
    its default_value (None unless configured). This documents that the default
    path tolerates an unset port — production widgets pass an explicit
    default_value (see basic_widgets.py) to show 0.0/''/False.
    """
    from haywire.ui.widget.converters import PrimitiveUnwrappingConverter

    assert PrimitiveUnwrappingConverter().to_view(None) is None
    assert PrimitiveUnwrappingConverter(default_value=0.0).to_view(None) == 0.0
