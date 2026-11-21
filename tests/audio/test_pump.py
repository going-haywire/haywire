"""BlockPump: pacing, end of source, stop, errors."""

import threading
import pytest

from haybale_audio.emitter import BlockPump
from haybale_audio.value import AudioBlock

from tests.wait import wait_until

pytestmark = pytest.mark.unit

_BLOCK = AudioBlock.silence(1, 480, 48000)  # 10 ms


def _run(produce, **kwargs):
    seen, ended = [], threading.Event()
    result = {}

    def on_end(error):
        result["error"] = error
        ended.set()

    pump = BlockPump(produce, lambda block, number, seconds: seen.append((number, seconds)), on_end)
    pump.start()
    return pump, seen, ended, result


class _RecordingStop(threading.Event):
    """The pump's stop event, logging each timed wait the pump asks for into *log*."""

    def __init__(self, log: list) -> None:
        super().__init__()
        self._log = log

    def wait(self, timeout=None):
        self._log.append(("wait", timeout))
        return super().wait(timeout)


def test_delivers_numbered_blocks_at_the_block_rate():
    left = [_BLOCK] * 20
    log, seen, ended = [], [], threading.Event()

    def deliver(block, number, seconds):
        log.append(("deliver", number))
        seen.append((number, seconds))

    pump = BlockPump(lambda: left.pop() if left else None, deliver, lambda error: ended.set())
    pump._stop = _RecordingStop(log)
    pump.start()
    assert ended.wait(10)
    pump.stop()
    assert [n for n, _ in seen] == list(range(20))
    assert log[0] == ("deliver", 0), "the first block goes out at once, not after a wait"
    waits = [t for kind, t in log if kind == "wait"]
    assert all(0 < t <= _BLOCK.duration + 1e-9 for t in waits), "the pump never sleeps past a block"
    # Only the lower bound is exact: a busy machine can deliver any block late.
    early = [(n, at) for n, at in seen if at < n * 0.01 - 0.001]
    assert not early, f"no block goes out before its time: {early}"


def test_stop_interrupts_the_wait_and_reports_end():
    long_block = AudioBlock.silence(1, 480_000, 48000)  # 10 s: the pump sleeps 10 s before the second
    pump, seen, ended, result = _run(lambda: long_block)
    assert wait_until(lambda: seen)  # the first block is out, so the pump is at (or near) its wait
    pump.stop()
    assert ended.wait(5), "stop() interrupts the 10 s wait; an uninterrupted pump ends only after it"
    assert result["error"] is None
    assert not pump.running


def test_error_from_produce_is_reported():
    def produce():
        raise RuntimeError("disk gone")

    _, _, ended, result = _run(produce)
    assert ended.wait(10)
    assert str(result["error"]) == "disk gone"
