"""dev/scripts/worktree_setup.py: the studio port, the core link and the recorded lead."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import worktree_setup
from scripts.worktree_setup import (
    DONE,
    FIRST_WORKTREE_PORT,
    LEAD,
    SETTINGS,
    choose_studio_port,
    core_link,
    read_lead,
    studio_port,
    with_studio_port,
    without_open_haystack,
    write_lead,
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


T3_LINK = "t3-thread://v2/337c3f3f/mcp:launch:49a6"


def test_the_lead_is_written_and_read_back(tmp_path):
    assert read_lead(tmp_path) is None
    write_lead(tmp_path, f"  {T3_LINK}\n")
    assert (tmp_path / LEAD).read_text() == f"{T3_LINK}\n"
    assert read_lead(tmp_path) == T3_LINK


def test_an_empty_lead_file_records_no_lead(tmp_path):
    (tmp_path / LEAD).write_text("\n")
    assert read_lead(tmp_path) is None


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_lead_on_a_set_up_worktree_only_records_the_lead(tmp_path, monkeypatch, capsys):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "commit", "-q", "--allow-empty", "-m", "x")
    _git(main, "worktree", "add", "-q", "-b", "feat/x", str(tmp_path / "work"))
    git_dir = Path(_git(tmp_path / "work", "rev-parse", "--path-format=absolute", "--git-dir"))
    (git_dir / DONE).write_text("")
    monkeypatch.chdir(tmp_path / "work")
    monkeypatch.setattr(worktree_setup, "build_environment", pytest.fail)
    assert worktree_setup.main(["--lead", "herdr-lead (t1)"]) == 0
    assert capsys.readouterr().out == "lead: herdr-lead (t1)\n"
    assert read_lead(git_dir) == "herdr-lead (t1)"


def _umbrella_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A worktree of a clone whose repository tracks no ``pyproject.toml``, and its git folder."""
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-q", "-b", "master")
    (seed / "README.md").write_text("umbrella\n")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-q", "-m", "x")
    _git(tmp_path, "clone", "-q", str(seed), "main")
    worktree = tmp_path / "work"
    _git(tmp_path / "main", "worktree", "add", "-q", "-b", "chore/x", str(worktree), "origin/master")
    git_dir = Path(_git(worktree, "rev-parse", "--path-format=absolute", "--git-dir"))
    return worktree, git_dir


@pytest.mark.parametrize("lead", [None, "herdr-lead (t1)"])
def test_a_checkout_without_pyproject_skips_the_environment(tmp_path, monkeypatch, capsys, lead):
    worktree, git_dir = _umbrella_worktree(tmp_path)
    monkeypatch.chdir(worktree)
    monkeypatch.setattr(worktree_setup.shutil, "which", lambda name: None)
    for step in ("core_link", "build_environment", "assign_studio_port"):
        monkeypatch.setattr(worktree_setup, step, pytest.fail)
    assert worktree_setup.main(["--lead", lead] if lead else []) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "environment: skipped (no pyproject.toml), and with it the studio port"
    assert out[-2] == "branch: up to date with origin/master"
    assert (git_dir / DONE).exists()
    assert read_lead(git_dir) == lead
    assert not (worktree / "haywire-repo").exists()
    assert not (worktree / SETTINGS).exists()
