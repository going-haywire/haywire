"""Farmhand activity tracking — the record store, and what the presence row reads off it."""

import json
from unittest.mock import MagicMock

import pytest

from haywire.core.access import AccessTier
from haywire.core.farmhand.activity import HISTORY_LIMIT, PAYLOAD_CHAR_CAP, ActivityTracker

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
    from haywire.core.farmhand.activity import activity_tracker

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


# -- arguments/result capture (2026-08-18 expansion) --------------------------


def test_a_running_call_carries_its_serialized_arguments(tracker):
    tracker.start("builder", "graph_editor_add_node", {"binding_id": "g1", "registry_key": "core:node:echo"})

    record = tracker.current("builder")
    assert json.loads(record.arguments) == {"binding_id": "g1", "registry_key": "core:node:echo"}


def test_start_with_no_arguments_stores_an_empty_object(tracker):
    tracker.start("builder", "studio_status")

    assert tracker.current("builder").arguments == "{}"


def test_a_finished_call_carries_its_serialized_result(tracker):
    token = tracker.start("builder", "echo", {"text": "hi"})
    tracker.finish(token, result={"echo": "hi"})

    last = tracker.last("builder")
    assert json.loads(last.arguments) == {"text": "hi"}
    assert json.loads(last.result) == {"echo": "hi"}


def test_a_finished_call_with_no_result_leaves_result_none(tracker):
    token = tracker.start("builder", "studio_status")
    tracker.finish(token, ok=False, error="[boom] nope")

    assert tracker.last("builder").result is None


def test_a_non_serializable_result_degrades_to_a_repr_not_a_crash(tracker):
    class Unserializable:
        def __repr__(self):
            return "<Unserializable thing>"

    token = tracker.start("builder", "weird_tool")
    tracker.finish(token, result={"payload": Unserializable()})

    assert "Unserializable thing" in tracker.last("builder").result


def test_long_arguments_are_truncated_to_the_char_cap(tracker):
    tracker.start("builder", "big_tool", {"blob": "a" * (PAYLOAD_CHAR_CAP * 2)})

    arguments = tracker.current("builder").arguments
    assert len(arguments) == PAYLOAD_CHAR_CAP + len("...[truncated]")
    assert arguments.endswith("...[truncated]")


def test_long_results_are_truncated_to_the_char_cap(tracker):
    token = tracker.start("builder", "big_tool")
    tracker.finish(token, result={"blob": "a" * (PAYLOAD_CHAR_CAP * 2)})

    result = tracker.last("builder").result
    assert len(result) == PAYLOAD_CHAR_CAP + len("...[truncated]")


def test_short_arguments_are_not_truncated(tracker):
    tracker.start("builder", "small_tool", {"x": 1})

    assert not tracker.current("builder").arguments.endswith("...[truncated]")


# -- clear_history vs clear (UI Clear button scope) ---------------------------


def test_clear_history_drops_finished_calls_but_not_running_ones(tracker):
    still_running = tracker.start("builder", "still_going")
    tracker.finish(tracker.start("builder", "done"))

    tracker.clear_history()

    assert tracker.recent() == []
    assert tracker.current("builder") is not None
    assert tracker.current("builder").tool == "still_going"
    # The running call can still be finished normally after a history clear.
    tracker.finish(still_running)
    assert tracker.last("builder").tool == "still_going"


def test_clear_wipes_running_calls_too_unlike_clear_history(tracker):
    tracker.start("builder", "still_going")
    tracker.clear()
    assert tracker.current("builder") is None


# -- resize_history (ActivitySettings.history_size) ---------------------------


def test_resize_history_keeps_the_most_recent_entries(tracker):
    for index in range(5):
        tracker.finish(tracker.start("builder", f"tool_{index}"))

    tracker.resize_history(2)

    recent = tracker.recent()
    assert [r.tool for r in recent] == ["tool_4", "tool_3"]


def test_resize_history_to_a_larger_cap_keeps_everything(tracker):
    for index in range(3):
        tracker.finish(tracker.start("builder", f"tool_{index}"))

    tracker.resize_history(100)

    assert len(tracker.recent()) == 3


def test_finish_picks_up_a_live_history_size_setting_change(tracker, monkeypatch):
    """The process-wide tracker syncs its cap from ActivitySettings on every finish()."""
    from haywire.core.farmhand import settings as settings_mod

    class _Fake:
        history_size = 2

    monkeypatch.setattr(settings_mod, "ActivitySettings", _Fake)

    for index in range(5):
        tracker.finish(tracker.start("builder", f"tool_{index}"))

    assert len(tracker.recent()) == 2
    assert [r.tool for r in tracker.recent()] == ["tool_4", "tool_3"]


# -- persisted audit log (opt-in, per-project JSONL) --------------------------


@pytest.fixture
def workspace_root(tmp_path):
    """Snapshot/restore the ambient workspace_root global around a test."""
    import haywire.core.di.context as ctx_mod

    original = ctx_mod._workspace_root
    ctx_mod.set_workspace_root(tmp_path)
    yield tmp_path
    ctx_mod._workspace_root = original


@pytest.fixture
def activity_settings():
    """A fresh ActivitySettings for each test — log_path defaults to off."""
    from haywire.core.farmhand.settings import ActivitySettings

    settings = ActivitySettings()
    settings.log_path = ""
    yield settings
    settings.log_path = ""


def test_no_log_path_configured_writes_nothing(tracker, workspace_root, activity_settings):
    tracker.finish(tracker.start("builder", "echo", {"text": "hi"}))

    assert list(workspace_root.iterdir()) == []


def test_configuring_a_log_path_writes_one_jsonl_line_per_finished_call(
    tracker, workspace_root, activity_settings
):
    activity_settings.log_path = ".haywire/activity.jsonl"

    tracker.finish(tracker.start("builder", "echo", {"text": "hi"}), result={"echo": "hi"})

    log_file = workspace_root / ".haywire" / "activity.jsonl"
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["principal"] == "builder"
    assert entry["tool"] == "echo"
    assert entry["ok"] is True
    assert json.loads(entry["arguments"]) == {"text": "hi"}
    assert json.loads(entry["result"]) == {"echo": "hi"}


def test_the_log_file_is_append_only_in_finish_order(tracker, workspace_root, activity_settings):
    activity_settings.log_path = "activity.jsonl"

    tracker.finish(tracker.start("builder", "first"))
    tracker.finish(tracker.start("builder", "second"))

    lines = (workspace_root / "activity.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["tool"] == "first"
    assert json.loads(lines[1])["tool"] == "second"


def test_clearing_history_does_not_touch_the_persisted_log(tracker, workspace_root, activity_settings):
    activity_settings.log_path = "activity.jsonl"

    tracker.finish(tracker.start("builder", "echo"))
    tracker.clear_history()

    log_file = workspace_root / "activity.jsonl"
    assert len(log_file.read_text(encoding="utf-8").splitlines()) == 1
    assert tracker.recent() == []


def test_clearing_history_after_disabling_the_log_leaves_the_old_file_alone(
    tracker, workspace_root, activity_settings
):
    activity_settings.log_path = "activity.jsonl"
    tracker.finish(tracker.start("builder", "echo"))

    activity_settings.log_path = ""  # turn logging off
    tracker.finish(tracker.start("builder", "second"))

    log_file = workspace_root / "activity.jsonl"
    # Only the first call was logged; turning logging off mid-session doesn't
    # retroactively touch what's already on disk, and stops future writes.
    assert len(log_file.read_text(encoding="utf-8").splitlines()) == 1


def test_a_failed_persisted_write_does_not_raise_or_break_finish(tracker, workspace_root, activity_settings):
    # Point the log at a path that can't be created (a file where a directory
    # needs to go) — the write must be swallowed, not raised.
    blocker = workspace_root / "blocked"
    blocker.write_text("not a directory")
    activity_settings.log_path = "blocked/activity.jsonl"

    token = tracker.start("builder", "echo")
    tracker.finish(token, result={"ok": True})  # must not raise

    assert tracker.last("builder").tool == "echo"
