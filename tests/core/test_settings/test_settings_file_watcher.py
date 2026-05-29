# tests/core/test_settings/test_file_watcher.py
"""Tests for SettingsRegistry file watching robustness.

Regression coverage for a Linux-only crash: starting the watcher against a
settings path whose parent directory does not exist raised FileNotFoundError
under the inotify backend (macOS FSEvents tolerated it, so it only bit in CI).
See internals/follow-ups/2026-05-29-settings-watcher-missing-dir.md.
"""

from pathlib import Path

import pytest

from haywire.core.settings.registry import SettingsRegistry


@pytest.mark.unit
def test_watch_missing_parent_dir_does_not_raise(tmp_path: Path) -> None:
    """load_from_toml(watch=True) against a path in a non-existent directory
    must not raise — the watcher should create the dir (or degrade) gracefully."""
    registry = SettingsRegistry()
    missing = tmp_path / "does-not-exist-yet" / "settings.toml"
    assert not missing.parent.exists()

    # Should not raise even though the file and its parent are absent.
    registry.load_from_toml(missing, tier="global", watch=True)

    # The watcher ensures its target directory exists before scheduling.
    assert missing.parent.exists()

    registry.stop_watching()


@pytest.mark.unit
def test_watch_missing_file_existing_dir_does_not_raise(tmp_path: Path) -> None:
    """The common first-run case: the directory exists but the file does not
    ('will create on save'). Watching must still succeed."""
    registry = SettingsRegistry()
    settings_path = tmp_path / "settings.toml"  # parent (tmp_path) exists
    assert not settings_path.exists()

    registry.load_from_toml(settings_path, tier="global", watch=True)

    registry.stop_watching()
