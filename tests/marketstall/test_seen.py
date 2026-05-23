"""seen.toml tracker — spec §7.4 first-install scoping."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_is_seen_returns_false_when_file_missing(tmp_path: Path) -> None:
    from haywire.core.marketstall.seen import is_seen

    seen_path = tmp_path / "seen.toml"
    assert is_seen("haybale-foo", seen_path=seen_path) is False


@pytest.mark.unit
def test_mark_seen_creates_file(tmp_path: Path) -> None:
    from haywire.core.marketstall.seen import mark_seen, is_seen

    seen_path = tmp_path / "seen.toml"
    mark_seen("haybale-foo", seen_path=seen_path)

    assert seen_path.is_file()
    assert is_seen("haybale-foo", seen_path=seen_path) is True


@pytest.mark.unit
def test_mark_seen_is_idempotent(tmp_path: Path) -> None:
    from haywire.core.marketstall.seen import mark_seen

    seen_path = tmp_path / "seen.toml"
    mark_seen("haybale-foo", seen_path=seen_path)
    mark_seen("haybale-foo", seen_path=seen_path)
    mark_seen("haybale-foo", seen_path=seen_path)

    # No duplicates.
    import toml

    data = toml.loads(seen_path.read_text())
    assert data.get("seen", []).count("haybale-foo") == 1


@pytest.mark.unit
def test_is_seen_distinguishes_names(tmp_path: Path) -> None:
    from haywire.core.marketstall.seen import mark_seen, is_seen

    seen_path = tmp_path / "seen.toml"
    mark_seen("haybale-foo", seen_path=seen_path)

    assert is_seen("haybale-foo", seen_path=seen_path) is True
    assert is_seen("haybale-bar", seen_path=seen_path) is False


@pytest.mark.unit
def test_mark_seen_preserves_existing_entries(tmp_path: Path) -> None:
    from haywire.core.marketstall.seen import mark_seen, is_seen

    seen_path = tmp_path / "seen.toml"
    mark_seen("haybale-foo", seen_path=seen_path)
    mark_seen("haybale-bar", seen_path=seen_path)
    mark_seen("haybale-baz", seen_path=seen_path)

    assert is_seen("haybale-foo", seen_path=seen_path) is True
    assert is_seen("haybale-bar", seen_path=seen_path) is True
    assert is_seen("haybale-baz", seen_path=seen_path) is True


@pytest.mark.unit
def test_is_seen_returns_false_on_malformed_file(tmp_path: Path) -> None:
    """A corrupt seen.toml fails closed: returns False (rather than crashing).

    Rationale: showing the safety modal once extra is harmless; crashing
    Install is not.
    """
    from haywire.core.marketstall.seen import is_seen

    seen_path = tmp_path / "seen.toml"
    seen_path.write_text("this is = not valid TOML [[")

    assert is_seen("haybale-foo", seen_path=seen_path) is False
