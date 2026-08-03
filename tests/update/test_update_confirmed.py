"""One update-confirmed flag drives BOTH the terminal banner and the exit code.

They are not the same mechanism — the banner is for the human at the terminal,
the exit code is for a future supervisor — but they must never disagree. A
single source means an exit WITHOUT an update (cancel, crash, ordinary quit)
cannot print "Haywire updated".
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_flag():
    from haywire.core.update import confirmed

    confirmed.reset_for_tests()
    yield
    confirmed.reset_for_tests()


def test_an_ordinary_exit_reports_no_update():
    from haywire.core.update import confirmed

    assert confirmed.update_confirmed() is None
    assert confirmed.exit_code() == 0


def test_confirming_sets_both_outputs_from_one_call():
    from haywire.core.update import confirmed

    confirmed.confirm_update("0.0.34", "0.0.35")

    assert confirmed.update_confirmed() == ("0.0.34", "0.0.35")
    assert confirmed.exit_code() == confirmed.UPDATE_EXIT_CODE


def test_the_sentinel_is_distinct_from_a_normal_exit():
    from haywire.core.update import confirmed

    assert confirmed.UPDATE_EXIT_CODE != 0


def test_the_banner_names_both_versions_and_the_relaunch_command():
    from haywire.core.update import confirmed

    text = confirmed.banner_text("0.0.34", "0.0.35")

    assert "0.0.34" in text
    assert "0.0.35" in text
    assert "uv run haywire" in text


def test_confirming_twice_registers_one_banner():
    """atexit handlers are additive; a double-confirm must not print twice."""
    from haywire.core.update import confirmed

    registered: list[object] = []
    confirmed._register = registered.append  # type: ignore[assignment]

    confirmed.confirm_update("0.0.34", "0.0.35")
    confirmed.confirm_update("0.0.34", "0.0.35")

    assert len(registered) == 1
