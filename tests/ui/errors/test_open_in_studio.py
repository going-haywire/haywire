"""render_error_details exposes an in-studio open hook."""

import inspect

import pytest

pytestmark = pytest.mark.unit


def test_render_error_details_accepts_on_open_in_studio():
    from haywire.ui.errors.haywire_exception import render_error_details

    sig = inspect.signature(render_error_details)
    assert "on_open_in_studio" in sig.parameters
    # Optional with a None default — existing callers keep working.
    assert sig.parameters["on_open_in_studio"].default is None
