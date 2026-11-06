"""Browser regression for the assisted download's drop zone: a real browser, a real upload."""

import hashlib
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.ui.harness.nav import goto_ready

pytestmark = pytest.mark.ui

_DATA = b"weights-" * 40_000
_SHA = hashlib.sha256(_DATA).hexdigest()


def _file(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _open(page: Page, harness: str, sha: str = _SHA, size: int | None = len(_DATA)) -> None:
    query = f"?sha={sha}" + (f"&size={size}" if size is not None else "")
    goto_ready(page, f"{harness}/assisted-upload{query}")
    expect(page.get_by_text("Download in browser")).to_be_visible()


def _drop(page: Page, path: Path) -> None:
    page.locator("input[type=file]").set_input_files(str(path))


def test_drop_stores_the_file_under_its_name(page: Page, harness: str, tmp_path: Path) -> None:
    """The real file name survives, as the raw body reached our route, not NiceGUI's multipart one."""
    _open(page, harness)
    _drop(page, _file(tmp_path, "mère #1.pth", _DATA))
    expect(page.get_by_text("✓ stored as mère #1.pth")).to_be_visible()


def test_wrong_file_is_refused_then_right_file_succeeds(page: Page, harness: str, tmp_path: Path) -> None:
    """A refused file does not block the slot; the message says what was expected."""
    _open(page, harness, size=None)
    _drop(page, _file(tmp_path, "wrong.pth", b"not the model"))
    expect(page.get_by_text(f"expected {_SHA}", exact=False).last).to_be_visible()
    _drop(page, _file(tmp_path, "right.pth", _DATA))
    expect(page.get_by_text("✓ stored as right.pth")).to_be_visible()


def test_wrong_size_is_refused_before_the_body(page: Page, harness: str, tmp_path: Path) -> None:
    _open(page, harness)
    _drop(page, _file(tmp_path, "short.pth", b"short"))
    expect(page.get_by_text(f"size mismatch: got 5 bytes, expected {len(_DATA)}")).to_be_visible()


def test_no_digest_shows_the_notice_and_accepts(page: Page, harness: str, tmp_path: Path) -> None:
    _open(page, harness, sha="", size=None)
    expect(page.get_by_text("this file can't be verified")).to_be_visible()
    _drop(page, _file(tmp_path, "any.pth", b"any bytes"))
    expect(page.get_by_text("✓ stored as any.pth")).to_be_visible()


def test_close_with_nothing_running_closes_at_once(page: Page, harness: str) -> None:
    _open(page, harness)
    page.get_by_role("button", name="Close").click()
    expect(page.locator("input[type=file]")).to_have_count(0)
