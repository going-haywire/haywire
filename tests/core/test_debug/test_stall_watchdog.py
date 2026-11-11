"""The stall watchdog prints the stacks of a process that every thread is held up in."""

import logging
import time

import pytest
from haywire.core.debug.stall_watchdog import StallWatchdog, condense_dump


def _hold_the_interpreter() -> None:
    """Hold the interpreter lock for about half a second in one C call, which never releases it."""
    sum(range(60_000_000))


@pytest.mark.unit
def test_a_held_up_process_prints_the_stack_that_held_it(tmp_path, caplog):
    out = tmp_path / "stacks.txt"
    with out.open("w") as stream, caplog.at_level(logging.WARNING):
        watchdog = StallWatchdog(50, file=stream)
        watchdog.start()
        time.sleep(0.2)
        _hold_the_interpreter()
        time.sleep(0.2)
        watchdog.stop()
    text = out.read_text()
    assert "_hold_the_interpreter" in text, "the stack names the code that held the process"
    assert "Timeout (" not in text
    assert any("held up" in r.message and "_hold_the_interpreter" in r.message for r in caplog.records)


@pytest.mark.unit
def test_a_quiet_process_prints_nothing(tmp_path, caplog):
    out = tmp_path / "stacks.txt"
    with out.open("w") as stream, caplog.at_level(logging.WARNING):
        watchdog = StallWatchdog(200, file=stream)
        watchdog.start()
        time.sleep(0.6)
        watchdog.stop()
    assert out.read_text() == ""
    assert not [r for r in caplog.records if "held up" in r.message]


@pytest.mark.unit
def test_stop_ends_the_thread_and_start_is_idempotent(tmp_path):
    with (tmp_path / "s.txt").open("w") as stream:
        watchdog = StallWatchdog(100, file=stream)
        watchdog.start()
        watchdog.start()
        assert watchdog.running
        watchdog.stop()
        assert not watchdog.running


_DUMP = """Timeout (0:00:00.040000)!
Thread 0x0000000000000001 (most recent call first):
  File "/usr/lib/python3.12/threading.py", line 355 in wait
  File "/usr/lib/python3.12/queue.py", line 171 in get
  File "/app/site-packages/watchdog/observers/api.py", line 379 in dispatch_events

Thread 0x0000000000000002 (most recent call first):
  File "/app/.venv/lib/python3.12/site-packages/watchdog/observers/fsevents.py", line 308 in run

Thread 0x0000000000000003 (most recent call first):
  File "/app/gc_freeze.py", line 44 in unfreeze_after_run
  File "/app/interpreter.py", line 245 in stop_execution
"""


@pytest.mark.unit
def test_the_report_keeps_the_busy_thread_and_drops_the_parked_ones():
    stacks, omitted = condense_dump(_DUMP)
    assert omitted == 2
    assert "unfreeze_after_run" in stacks
    assert "stop_execution" in stacks
    assert "fsevents" not in stacks
    assert "queue.py" not in stacks
    assert "Timeout (" not in stacks


@pytest.mark.unit
def test_a_dump_of_only_parked_threads_condenses_to_nothing():
    stacks, omitted = condense_dump(
        'Thread 0x0000000000000001 (most recent call first):\n  File "/x/threading.py", line 355 in wait\n'
    )
    assert stacks == ""
    assert omitted == 1
