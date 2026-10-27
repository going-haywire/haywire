"""What ``HaywireException.from_exception`` names as the failing item."""

import pytest

from haywire.core.errors import HaywireException

pytestmark = pytest.mark.unit


def _report_from(handler) -> HaywireException:
    try:
        handler()
    except ZeroDivisionError as exc:
        return HaywireException.from_exception(exc, "UI handler failed")
    raise AssertionError("handler did not raise")


def test_a_failing_lambda_is_named_not_its_enclosing_def():
    def draw():
        return lambda: 1 / 0

    report = _report_from(draw())
    assert report.highlighted_item == "<lambda>"
    assert f"Check the <lambda> on line {report.line_number}" in report.suggestions
    assert not any("'draw'" in s for s in report.suggestions)


def test_a_failing_def_is_still_named():
    def on_click():
        return 1 / 0

    report = _report_from(on_click)
    assert report.highlighted_item == "on_click"
    assert "Check the 'on_click' function definition" in report.suggestions
