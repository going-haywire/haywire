"""BlockPump: pacing, end of source, stop, errors."""

import threading
import time

import pytest

from haybale_audio.emitter import BlockPump
from haybale_audio.value import AudioBlock

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


def test_delivers_numbered_blocks_at_the_block_rate():
    left = [_BLOCK] * 20
    pump, seen, ended, _ = _run(lambda: left.pop() if left else None)
    assert ended.wait(2)
    pump.stop()
    assert [n for n, _ in seen] == list(range(20))
    assert seen[0][1] < 0.005, "the first block goes out at once"
    assert seen[-1][1] == pytest.approx(0.19, abs=0.05), "19 blocks of 10 ms after the first"


def test_stop_interrupts_the_wait_and_reports_end():
    pump, seen, ended, result = _run(lambda: _BLOCK)
    time.sleep(0.05)
    started = time.monotonic()
    pump.stop()
    assert time.monotonic() - started < 0.1
    assert ended.wait(1)
    assert result["error"] is None
    assert not pump.running


def test_error_from_produce_is_reported():
    def produce():
        raise RuntimeError("disk gone")

    _, _, ended, result = _run(produce)
    assert ended.wait(1)
    assert str(result["error"]) == "disk gone"
