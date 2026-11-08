"""The owner-only steps are one list, rendered with the project's own values."""

import json
import re
import subprocess
from pathlib import Path

import pytest

from haywire.core.publishing.human_steps import HUMAN_ONLY_STEPS, checklist, github_owner_repo

pytestmark = pytest.mark.unit


def _repo(tmp_path: Path, *, remote: str | None) -> Path:
    root = tmp_path / "proj"
    lib = root / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.1.0"\n')
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    if remote:
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=root, check=True, capture_output=True)
    return root


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/maybites/my-repo.git", ("maybites", "my-repo")),
        ("git@github.com:maybites/my-repo.git", ("maybites", "my-repo")),
        ("https://github.com/maybites/my-repo", ("maybites", "my-repo")),
        ("https://gitlab.com/maybites/my-repo.git", None),
        ("/tmp/some/bare.git", None),
    ],
)
def test_github_owner_repo(url: str, expected: tuple[str, str] | None) -> None:
    assert github_owner_repo(url) == expected


def test_pending_publisher_checklist_uses_the_remote_and_every_library_name(tmp_path: Path) -> None:
    root = _repo(tmp_path, remote="git@github.com:maybites/my-repo.git")
    text = "\n".join(checklist(["pypi_pending_publisher", "github_pypi_environment"], root))
    assert "haybale-alpha" in text
    assert "Owner             : maybites" in text
    assert "Repository        : my-repo" in text
    assert "publish.yml" in text
    assert "`pypi`" in text


def test_pending_publisher_checklist_flags_a_non_github_remote(tmp_path: Path) -> None:
    root = _repo(tmp_path, remote="https://gitlab.com/o/r.git")
    assert "fill owner and repository by hand" in "\n".join(checklist(["pypi_pending_publisher"], root))


def test_create_repo_step_is_listed_without_a_remote(tmp_path: Path) -> None:
    root = _repo(tmp_path, remote=None)
    lines = checklist(["create_github_repo"], root, project_name="my-project")
    assert lines[0].startswith("1. Create the GitHub repository")
    assert any("my-project" in line for line in lines)


def test_create_repo_step_is_skipped_when_origin_answers(tmp_path: Path) -> None:
    bare = tmp_path / "bare.git"
    bare.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=bare, check=True, capture_output=True)
    root = _repo(tmp_path, remote=str(bare))
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    (root / "f").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=root, check=True, capture_output=True)
    assert checklist(["create_github_repo"], root) == []


def test_every_failure_step_id_is_registered() -> None:
    from haywire.core.publishing.pipeline.steps import preconditions

    source = Path(preconditions.__file__).read_text()
    used = set(re.findall(r'"(\w+)"', " ".join(re.findall(r"human_steps=\(([^)]*)\)", source))))
    assert used
    assert used <= set(HUMAN_ONLY_STEPS)


def test_share_stop_without_origin_prints_the_checklist(tmp_path: Path, capsys) -> None:
    from haywire_studio.packaging.share_cli import EXIT_HUMAN_NEEDED, run_share_cli

    root = _repo(tmp_path, remote=None)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=root, check=True, capture_output=True)

    code = run_share_cli(repo_root=root, bump="patch", message=None, json_output=True)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == EXIT_HUMAN_NEEDED
    assert payload["stop"]["checklist"][0].startswith("1. Create the GitHub repository")
    assert "do not attempt it yourself" in captured.err
