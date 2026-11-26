"""The pure parts of dev/scripts/worktree_setup.py: the studio port and the core link."""

from __future__ import annotations

from pathlib import Path

from scripts.worktree_setup import (
    FIRST_WORKTREE_PORT,
    choose_studio_port,
    core_link,
    studio_port,
    with_studio_port,
    without_open_haystack,
)


def test_first_free_port_above_the_main_studio():
    assert choose_studio_port(claimed=set(), busy=lambda port: False) == FIRST_WORKTREE_PORT
    assert FIRST_WORKTREE_PORT == 8125


def test_skips_ports_other_worktrees_claimed_or_something_listens_on():
    port = choose_studio_port(claimed={8125, 8127}, busy=lambda port: port == 8126)
    assert port == 8128


def test_port_is_written_beside_the_existing_settings():
    settings: dict = {
        "network": {"allowed_remote_ranges": {"value": "10.0.0.0/8"}},
        "ui": {"theme": {"value": "dark"}},
    }
    updated = with_studio_port(settings, 8126)
    assert studio_port(updated) == 8126
    assert updated["network"]["allowed_remote_ranges"] == {"value": "10.0.0.0/8"}
    assert updated["ui"] == {"theme": {"value": "dark"}}
    assert "port" not in settings["network"]


def test_no_port_in_empty_or_partial_settings():
    assert studio_port({}) is None
    assert studio_port({"network": {}}) is None
    assert studio_port(with_studio_port({}, 8125)) == 8125


def test_the_copy_leaves_out_the_haystack_the_main_studio_reopens():
    settings: dict = {
        "haystack": {"last_haystack_name": {"value": "Single"}, "new_counter": {"value": 49}},
        "ui": {"theme": {"value": "dark"}},
    }
    copied = without_open_haystack(settings)
    assert copied == {"haystack": {"new_counter": {"value": 49}}, "ui": {"theme": {"value": "dark"}}}
    assert settings["haystack"]["last_haystack_name"] == {"value": "Single"}
    assert without_open_haystack({"haystack": {"last_haystack_name": {"value": "x"}}}) == {}
    assert without_open_haystack({}) == {}


def _repo(path: Path, *, core: bool = False) -> Path:
    path.mkdir(parents=True)
    if core:
        (path / "dev" / "scripts").mkdir(parents=True)
        (path / "dev" / "scripts" / "worktree_setup.py").write_text("")
    return path


def test_a_library_worktree_away_from_core_gets_core_linked_beside_it(tmp_path):
    _repo(tmp_path / "work" / "haywire-repo", core=True)
    main = _repo(tmp_path / "work" / "haybale-x")
    worktree = _repo(tmp_path / "t3" / "haybale-x" / "feat")
    assert core_link(worktree, main) == (
        tmp_path / "t3" / "haybale-x" / "haywire-repo",
        tmp_path / "work" / "haywire-repo",
    )


def test_a_library_worktree_beside_core_needs_no_link(tmp_path):
    _repo(tmp_path / "work" / "haywire-repo", core=True)
    main = _repo(tmp_path / "work" / "haybale-x")
    worktree = _repo(tmp_path / "work" / "haybale-x-feat")
    assert core_link(worktree, main) is None


def test_a_core_worktree_needs_no_link(tmp_path):
    main = _repo(tmp_path / "work" / "haywire-repo", core=True)
    worktree = _repo(tmp_path / "t3" / "haywire-repo" / "feat", core=True)
    assert core_link(worktree, main) is None


def test_no_link_when_the_main_folder_has_no_core_beside_it(tmp_path):
    main = _repo(tmp_path / "work" / "haybale-x")
    worktree = _repo(tmp_path / "t3" / "haybale-x" / "feat")
    assert core_link(worktree, main) is None
