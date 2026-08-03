"""Framework update check: PyPI query, pin rewrite, startup mismatch notice."""

from __future__ import annotations

import textwrap
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest
import toml

pytestmark = pytest.mark.unit


def _root_pyproject(tmp_path: Path, pin: str = "~=0.0.34") -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        textwrap.dedent(f"""
            [project]
            name = "my-project"
            version = "0.1.0"
            dependencies = [
                "haywire-studio{pin}",
                "haybale-marketplace{pin}",
                "numpy>=1.0",
            ]
        """).lstrip()
    )
    return path


def test_update_available_when_pypi_is_ahead():
    from haywire.core.update.check import check_for_update

    with patch("haywire.core.update.check._installed_version", return_value="0.0.34"):
        with patch("haywire.core.update.check._latest_on_pypi", return_value="0.0.35"):
            status = check_for_update()

    assert status.available
    assert status.latest == "0.0.35"


def test_no_update_when_installed_matches_latest():
    from haywire.core.update.check import check_for_update

    with patch("haywire.core.update.check._installed_version", return_value="0.0.35"):
        with patch("haywire.core.update.check._latest_on_pypi", return_value="0.0.35"):
            status = check_for_update()

    assert not status.available
    assert status.reachable


def test_offline_is_reported_as_unreachable_not_as_up_to_date():
    """ "Couldn't reach PyPI" and "you're up to date" are different answers —
    collapsing them would tell the user a comforting lie."""
    from haywire.core.update.check import check_for_update

    with patch("haywire.core.update.check._installed_version", return_value="0.0.34"):
        with patch(
            "haywire.core.update.check._latest_on_pypi",
            side_effect=urllib.error.URLError("no route"),
        ):
            status = check_for_update()

    assert not status.reachable
    assert not status.available
    assert status.latest is None


def test_rewrite_pins_moves_every_lockstep_dist(tmp_path):
    from haywire.core.update.pin import rewrite_pins

    path = _root_pyproject(tmp_path)
    new_text = rewrite_pins(path, "0.0.35")
    deps = toml.loads(new_text)["project"]["dependencies"]

    assert "haywire-studio>=0.0.35" in deps
    assert "haybale-marketplace>=0.0.35" in deps
    assert "numpy>=1.0" in deps


def test_rewrite_pins_does_not_write_the_file(tmp_path):
    """The conflict check needs write-resolve-restore, so the rewrite must be a
    pure text transform the caller controls."""
    from haywire.core.update.pin import rewrite_pins

    path = _root_pyproject(tmp_path)
    before = path.read_text()
    rewrite_pins(path, "0.0.35")

    assert path.read_text() == before


def test_rewrite_pins_normalizes_lockstep_dists_to_a_floor(tmp_path):
    """Lockstep dists always land on ``>=``, whatever operator they carried.

    This used to preserve the declared operator, on the reasoning that an update
    moves the version and not the author's chosen policy. But on lockstep dists
    that operator is not the author's choice — it is whatever tool wrote the
    line — and preserving ``~=0.0.X`` kept a ceiling that blocks 0.1.0. See
    ``tests/update/test_update_pin.py`` for the full parametrized case.
    """
    from haywire.core.update.pin import rewrite_pins

    path = _root_pyproject(tmp_path, pin=">=0.0.34")
    deps = toml.loads(rewrite_pins(path, "0.0.35"))["project"]["dependencies"]

    assert "haywire-studio>=0.0.35" in deps


def test_startup_mismatch_fires_when_the_pin_is_ahead_of_the_installed(tmp_path):
    """Derived, not stored: pin-vs-installed IS the condition and is always
    current, whereas a stored marker goes stale on a hand-edited pin."""
    from haywire.core.update.pin import startup_mismatch

    path = _root_pyproject(tmp_path, pin=">=0.0.35")
    with patch("haywire.core.update.pin._installed_version", return_value="0.0.34"):
        notice = startup_mismatch(path)

    assert notice is not None
    assert "0.0.35" in notice
    assert "0.0.34" in notice
    assert "uv run haywire" in notice


def test_no_startup_mismatch_when_synced(tmp_path):
    from haywire.core.update.pin import startup_mismatch

    path = _root_pyproject(tmp_path, pin=">=0.0.34")
    with patch("haywire.core.update.pin._installed_version", return_value="0.0.34"):
        assert startup_mismatch(path) is None


def test_no_startup_mismatch_when_installed_is_ahead(tmp_path):
    """Installed > floor is the normal state, not a fault."""
    from haywire.core.update.pin import startup_mismatch

    path = _root_pyproject(tmp_path, pin=">=0.0.31")
    with patch("haywire.core.update.pin._installed_version", return_value="0.0.34"):
        assert startup_mismatch(path) is None
