"""Tests for StdoutTee (formerly ConsoleBridge)."""

from typing import Any, cast

import sys

from haywire.ui.console_bridge import StdoutTee, console_print


class FakeStream:
    """A minimal file-like object standing in for the real sys.stdout."""

    def __init__(self):
        self.data: list[str] = []

    def write(self, s: str) -> int:
        self.data.append(s)
        return len(s)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        return -1

    @property
    def encoding(self) -> str:
        return "utf-8"


def test_split_writes_reassemble_into_one_line():
    fake = FakeStream()
    tee = StdoutTee(cast(Any, fake))
    received: list[str] = []
    tee.add_sink(received.append)

    tee.write("hello ")
    tee.write("world")
    tee.write("\n")

    assert received == ["hello world"]


def test_trailing_partial_line_held_back():
    fake = FakeStream()
    tee = StdoutTee(cast(Any, fake))
    received: list[str] = []
    tee.add_sink(received.append)

    tee.write("no newline yet")
    assert received == []

    tee.write("\n")
    assert received == ["no newline yet"]


def test_real_stream_receives_every_byte_unmodified():
    fake = FakeStream()
    tee = StdoutTee(cast(Any, fake))
    tee.add_sink(lambda line: None)

    tee.write("partial")
    tee.write(" more\n")

    assert "".join(fake.data) == "partial more\n"


def test_broken_sink_does_not_break_write_or_drop_later_sinks():
    fake = FakeStream()
    tee = StdoutTee(cast(Any, fake))
    received: list[str] = []

    def bad_sink(line: str) -> None:
        raise RuntimeError("boom")

    tee.add_sink(bad_sink)
    tee.add_sink(received.append)

    tee.write("still works\n")

    assert received == ["still works"]


def test_sink_that_prints_does_not_recurse():
    fake = FakeStream()
    tee = StdoutTee(cast(Any, fake))
    calls: list[str] = []

    def printing_sink(line: str) -> None:
        calls.append(line)
        tee.write("from sink\n")  # would recurse forever without the guard

    tee.add_sink(printing_sink)
    tee.write("outer\n")

    assert calls == ["outer"]
    assert "".join(fake.data) == "outer\nfrom sink\n"


def test_install_twice_leaves_exactly_one_wrapper(monkeypatch):
    fake = FakeStream()
    monkeypatch.setattr(sys, "stdout", fake)
    tee = StdoutTee(cast(Any, fake))

    tee.install()
    first = sys.stdout
    tee.install()

    assert sys.stdout is first
    assert isinstance(sys.stdout, StdoutTee)


def test_detach_unregisters_sink():
    fake = FakeStream()
    tee = StdoutTee(cast(Any, fake))
    received: list[str] = []
    detach = tee.add_sink(received.append)

    tee.write("one\n")
    detach()
    tee.write("two\n")

    assert received == ["one"]


def test_history_is_capped_at_max_history():
    fake = FakeStream()
    tee = StdoutTee(cast(Any, fake))
    tee.max_history = 3

    for i in range(5):
        tee.write(f"line{i}\n")

    assert tee.get_history_text().splitlines() == ["line2", "line3", "line4"]


def test_shrinking_max_history_trims_existing_history_immediately():
    fake = FakeStream()
    tee = StdoutTee(cast(Any, fake))
    for i in range(5):
        tee.write(f"line{i}\n")

    tee.max_history = 2

    assert tee.get_history_text().splitlines() == ["line3", "line4"]


def test_max_history_clamps_to_at_least_one():
    """min= on the setting is UI-only, so a hand-edited 0 must not blank the panel."""
    fake = FakeStream()
    tee = StdoutTee(cast(Any, fake))
    tee.max_history = 0

    assert tee.max_history == 1
    tee.write("kept\n")
    assert tee.get_history_text().splitlines() == ["kept"]


def test_console_print_routes_through_real_print(monkeypatch, capsys):
    fake = StdoutTee(sys.stdout)
    monkeypatch.setattr(sys, "stdout", fake)
    received: list[str] = []
    fake.add_sink(received.append)

    console_print("hello", "world")

    assert received == ["hello world"]
