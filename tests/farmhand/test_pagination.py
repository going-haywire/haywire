"""Unit tests for the Farmhand truncation-note helper."""

import pytest

from haywire.core.farmhand import truncation_note

pytestmark = pytest.mark.unit


def test_no_note_when_page_covers_everything():
    # First page holds the whole collection -> nothing hidden.
    assert truncation_note(shown=3, total=3, offset=0) == ""
    assert truncation_note(shown=0, total=0, offset=0) == ""
    # Asked for more than exists; still complete.
    assert truncation_note(shown=3, total=3, offset=0) == ""


def test_note_when_first_page_is_truncated():
    note = truncation_note(shown=100, total=200, offset=0)
    assert "showing 1-100 of 200" in note
    assert "limit/offset" in note


def test_note_when_offset_page_even_if_it_reaches_the_end():
    # A non-zero offset always warns: the caller is looking at a slice, and the
    # items before `offset` are not in this payload.
    note = truncation_note(shown=100, total=200, offset=100)
    assert "showing 101-200 of 200" in note


def test_note_for_middle_page():
    note = truncation_note(shown=50, total=200, offset=100)
    assert "showing 101-150 of 200" in note
