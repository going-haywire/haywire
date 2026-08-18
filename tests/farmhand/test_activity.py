"""Farmhand activity tracking — the record store, and what the presence row reads off it."""

from unittest.mock import MagicMock

import pytest

from haywire.core.access import AccessTier
from haywire_studio.farmhand.activity import HISTORY_LIMIT, ActivityTracker

pytestmark = pytest.mark.unit


@pytest.fixture
def tracker():
    return ActivityTracker()


# -- store mechanics ---------------------------------------------------------


def test_a_started_call_is_current_for_its_principal(tracker):
    tracker.start("builder", "graph_editor_add_node")
    current = tracker.current("builder")
    assert current is not None
    assert current.tool == "graph_editor_add_node"
    assert current.running is True


def test_a_finished_call_stops_being_current_and_becomes_last(tracker):
    token = tracker.start("builder", "graph_editor_add_node")
    tracker.finish(token)

    assert tracker.current("builder") is None
    last = tracker.last("builder")
    assert last is not None
    assert last.tool == "graph_editor_add_node"
    assert last.ok is True
    assert last.running is False


def test_a_failed_call_records_its_error(tracker):
    token = tracker.start("builder", "haystack_save_graph")
    tracker.finish(token, ok=False, error="[save_failed] disk full")

    last = tracker.last("builder")
    assert last is not None
    assert last.ok is False
    assert last.error == "[save_failed] disk full"


def test_principals_do_not_see_each_others_activity(tracker):
    tracker.start("builder", "graph_editor_add_node")
    tracker.start("reader", "graph_editor_query_graph")

    assert tracker.current("builder").tool == "graph_editor_add_node"
    assert tracker.current("reader").tool == "graph_editor_query_graph"


def test_concurrent_calls_by_one_principal_report_the_newest_as_current(tracker):
    # MCP permits several requests in flight at once, so the tracker keys by
    # token; a one-line chip can only honestly show the most recent.
    tracker.start("builder", "first")
    tracker.start("builder", "second")

    assert tracker.current("builder").tool == "second"


def test_finishing_one_of_two_concurrent_calls_leaves_the_other_running(tracker):
    first = tracker.start("builder", "first")
    tracker.start("builder", "second")
    tracker.finish(first)

    current = tracker.current("builder")
    assert current is not None
    assert current.tool == "second"


def test_finish_with_an_unknown_token_is_ignored(tracker):
    # Called from an `except` block that is about to re-raise the real error —
    # a bookkeeping slip must not become a second exception.
    tracker.finish(9999)
    assert tracker.recent() == []


def test_finish_if_running_closes_an_open_call_and_reports_that_it_did(tracker):
    token = tracker.start("builder", "studio_verify_component")

    assert tracker.finish_if_running(token) is True
    last = tracker.last("builder")
    assert last is not None
    assert last.ok is False
    assert last.error == "cancelled"


def test_finish_if_running_is_a_no_op_once_the_call_already_finished(tracker):
    # The host calls it from a `finally` that also runs after the success path.
    token = tracker.start("builder", "graph_editor_add_node")
    tracker.finish(token, ok=True)

    assert tracker.finish_if_running(token) is False
    assert tracker.last("builder").ok is True
    assert len(tracker.recent()) == 1


def test_history_is_capped_and_newest_first(tracker):
    for index in range(HISTORY_LIMIT + 10):
        tracker.finish(tracker.start("builder", f"tool_{index}"))

    recent = tracker.recent()
    assert len(recent) == HISTORY_LIMIT
    assert recent[0].tool == f"tool_{HISTORY_LIMIT + 9}"


def test_elapsed_of_a_finished_call_is_fixed(tracker):
    token = tracker.start("builder", "tool")
    tracker.finish(token)
    last = tracker.last("builder")

    assert last.elapsed() == last.elapsed()  # not creeping with wall clock


def test_auth_off_records_under_the_none_principal(tracker):
    # principal is None when authentication is disabled; the tracker must not
    # collapse that into "some agent" or drop it.
    tracker.start(None, "graph_editor_add_node")
    assert tracker.current(None).tool == "graph_editor_add_node"
    assert tracker.current("builder") is None


# -- what the presence row surfaces -----------------------------------------


STRONG = "Correct-Horse9"


@pytest.fixture
def roster_path(tmp_path):
    from haywire_studio.auth.operations import add_agent, add_user, enable_auth

    target = tmp_path / "auth.json"
    add_user("alice", STRONG, AccessTier.ADMIN, path=target)
    enable_auth("alice", STRONG, path=target)
    add_agent("builder", AccessTier.EDIT, path=target)
    return target


@pytest.fixture
def seen_builder():
    """Put 'builder' in the gate's last_seen window, and clean up after."""
    import time

    from haywire_studio.auth import gate

    gate.last_seen().clear()
    gate.last_seen()["builder"] = time.monotonic()
    yield
    gate.last_seen().clear()


@pytest.fixture
def clean_tracker():
    """The presence row reads the process-wide tracker; isolate it per test."""
    from haywire_studio.farmhand.activity import activity_tracker

    activity_tracker().clear()
    yield activity_tracker()
    activity_tracker().clear()


def _empty_manager():
    manager = MagicMock()
    manager.active_sessions = {}
    return manager


def _agent_entry(roster_path):
    from haywire_studio.auth.live import RosterCache
    from haywire_studio.auth.presence import collect_presence

    entries = collect_presence(_empty_manager(), RosterCache(roster_path))
    return next(e for e in entries if e.name == "builder")


def test_idle_agent_shows_no_running_tool(roster_path, seen_builder, clean_tracker):
    entry = _agent_entry(roster_path)
    assert entry.running_tool == ""
    assert entry.last_tool == ""


def test_agent_mid_call_shows_the_running_tool(roster_path, seen_builder, clean_tracker):
    clean_tracker.start("builder", "graph_editor_add_node")

    entry = _agent_entry(roster_path)
    assert entry.running_tool == "graph_editor_add_node"


def test_agent_after_a_call_shows_it_as_last_not_running(roster_path, seen_builder, clean_tracker):
    clean_tracker.finish(clean_tracker.start("builder", "graph_editor_add_node"))

    entry = _agent_entry(roster_path)
    assert entry.running_tool == ""
    assert entry.last_tool == "graph_editor_add_node"
    assert entry.last_ok is True


def test_agent_after_a_failed_call_reports_it_failed(roster_path, seen_builder, clean_tracker):
    token = clean_tracker.start("builder", "haystack_save_graph")
    clean_tracker.finish(token, ok=False, error="[save_failed] nope")

    entry = _agent_entry(roster_path)
    assert entry.last_tool == "haystack_save_graph"
    assert entry.last_ok is False


def test_user_entries_never_carry_activity(roster_path, clean_tracker):
    from haywire_studio.auth.live import RosterCache
    from haywire_studio.auth.presence import collect_presence

    clean_tracker.start("alice", "graph_editor_add_node")
    manager = MagicMock()
    session = MagicMock()
    session.context.principal = "alice"
    manager.active_sessions = {"s0": session}

    entries = collect_presence(manager, RosterCache(roster_path))
    alice = next(e for e in entries if e.name == "alice")
    # A browser principal's actions are already visible on screen; the chip
    # stays a plain identity chip.
    assert alice.running_tool == ""
    assert alice.last_tool == ""


# -- running_calls (what the activity editor lists) --------------------------


def test_running_calls_lists_every_in_flight_call_newest_first(tracker):
    tracker.start("builder", "first")
    tracker.start("other", "second")

    running = tracker.running_calls()
    assert [r.tool for r in running] == ["second", "first"]


def test_running_calls_spans_principals_unlike_current(tracker):
    # `current` answers a per-chip question; the editor lists everyone's.
    tracker.start("builder", "a")
    tracker.start("other", "b")

    assert len(tracker.running_calls()) == 2
    assert tracker.current("builder").tool == "a"


def test_running_calls_drops_finished_calls(tracker):
    token = tracker.start("builder", "done")
    tracker.start("builder", "still_going")
    tracker.finish(token)

    assert [r.tool for r in tracker.running_calls()] == ["still_going"]


def test_running_calls_is_empty_when_idle(tracker):
    tracker.finish(tracker.start("builder", "done"))
    assert tracker.running_calls() == []
