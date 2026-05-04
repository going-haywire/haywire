# tests/ui/panel/test_panel_error_boundary.py
"""Panel error boundary catches exceptions, wraps as HaywireException, returns error info."""

from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui.panel.error_boundary import safe_call_panel_method


def test_safe_call_returns_value_on_success():
    def fn():
        return 42

    result, error = safe_call_panel_method(fn, panel_name="MyPanel", method_name="poll")
    assert result == 42
    assert error is None


def test_safe_call_catches_exceptions_and_wraps():
    def fn():
        raise ValueError("boom")

    result, error = safe_call_panel_method(fn, panel_name="MyPanel", method_name="poll")
    assert result is None
    assert isinstance(error, HaywireException)
    assert "MyPanel" in str(error)
    assert "poll" in str(error)


def test_safe_call_passes_through_haywire_exception():
    """If the function raises HaywireException, don't double-wrap."""
    inner = HaywireException("inner failure")

    def fn():
        raise inner

    result, error = safe_call_panel_method(fn, panel_name="MyPanel", method_name="draw")
    assert error is inner
