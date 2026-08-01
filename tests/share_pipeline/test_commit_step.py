"""Step 5 — marketstall rebuild, commit file-scoping, tag. Real git, no mocks."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from haywire_studio.share_pipeline import CommitError
from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Git repo with a bare origin, one barn library, one seeded commit."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    repo = tmp_path / "project"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.test")
    _git(repo, "config", "user.name", "T")
    _git(repo, "remote", "add", "origin", str(remote))

    lib = repo / "barn" / "haybale-alpha"
    (lib / "haybale_alpha").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.3.1"\n')
    (lib / "README.md").write_text("# alpha\n")
    (repo / "README.md").write_text("# root\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed")
    _git(repo, "push", "-u", "origin", "HEAD")
    return repo


def _ready(project: Path, version: str = "0.3.2") -> SharePipeline:
    """A pipeline as it looks after step 3: version set, one file written."""
    pipeline = SharePipeline(project)
    pipeline.version = version
    pyproject = project / "barn" / "haybale-alpha" / "pyproject.toml"
    pyproject.write_text(f'[project]\nname = "haybale-alpha"\nversion = "{version}"\n')
    pipeline._record([pyproject])
    return pipeline


# ── marketstall ──────────────────────────────────────────────────────────────


def test_apply_marketstall_records_what_it_wrote(project: Path) -> None:
    pipeline = _ready(project)
    result = pipeline.apply_marketstall()
    assert result.out_path.is_file()
    assert result.out_path in pipeline.written


# ── barn_dirty_files ─────────────────────────────────────────────────────────


def test_untracked_barn_file_is_surfaced(project: Path) -> None:
    """Uncommitted barn content is silently ABSENT for consumers — they install
    from a clone. It's the one working-tree state that corrupts a publish."""
    asset = project / "barn" / "haybale-alpha" / "haybale_alpha" / "icon.png"
    asset.write_bytes(b"\x89PNG")
    dirty = _ready(project).barn_dirty_files()
    assert [d.path.name for d in dirty] == ["icon.png"]
    assert dirty[0].untracked is True


def test_modified_tracked_barn_file_is_surfaced(project: Path) -> None:
    (project / "barn" / "haybale-alpha" / "README.md").write_text("# alpha edited\n")
    dirty = _ready(project).barn_dirty_files()
    assert [d.path.name for d in dirty] == ["README.md"]
    assert dirty[0].untracked is False


def test_pipeline_own_writes_are_not_listed_as_dirty(project: Path) -> None:
    """The bumped pyproject is already in the write set; listing it twice would
    ask the user to opt into a file the wizard is committing anyway."""
    pipeline = _ready(project)
    assert all(d.path.name != "pyproject.toml" for d in pipeline.barn_dirty_files())


def test_dirt_outside_barn_is_never_mentioned(project: Path) -> None:
    """It has no bearing on what consumers get, and warning about it would
    train users to ignore the warning that matters."""
    (project / "notes.txt").write_text("wip\n")
    (project / "README.md").write_text("# root edited\n")
    assert _ready(project).barn_dirty_files() == []


def test_gitignored_barn_files_are_not_listed(project: Path) -> None:
    """An ignored file is an expression of intent; `git add` would fail on it."""
    (project / ".gitignore").write_text("__pycache__/\n")
    cache = project / "barn" / "haybale-alpha" / "haybale_alpha" / "__pycache__"
    cache.mkdir()
    (cache / "x.pyc").write_bytes(b"\x00")
    dirty = _ready(project).barn_dirty_files()
    assert all("__pycache__" not in str(d.path) for d in dirty)


# ── plan_commit ──────────────────────────────────────────────────────────────


def test_plan_commit_defaults_the_message_to_the_version(project: Path) -> None:
    plan = _ready(project).plan_commit()
    assert plan.message == "chore: share v0.3.2"
    assert plan.tag == "v0.3.2"


def test_plan_commit_accepts_a_custom_message(project: Path) -> None:
    plan = _ready(project).plan_commit(message="release: alpha goes 0.3.2")
    assert plan.message == "release: alpha goes 0.3.2"
    assert plan.tag == "v0.3.2"  # the tag never follows the message


def test_plan_commit_lists_exactly_the_accumulated_writes(project: Path) -> None:
    pipeline = _ready(project)
    pipeline.apply_marketstall()
    plan = pipeline.plan_commit()
    assert set(plan.files) == set(pipeline.written)


def test_plan_commit_includes_a_diffstat(project: Path) -> None:
    plan = _ready(project).plan_commit()
    assert "pyproject.toml" in plan.diffstat


def test_plan_commit_without_a_version_raises(project: Path) -> None:
    from haywire_studio.share_pipeline import PipelineStateError

    pipeline = SharePipeline(project)
    with pytest.raises(PipelineStateError):
        pipeline.plan_commit()


# ── apply_commit ─────────────────────────────────────────────────────────────


def test_apply_commit_stages_only_the_planned_files(project: Path) -> None:
    """Never -a/-A: a checkpoint-style sweep would drag the user's unrelated
    work-in-progress into a wizard-authored commit."""
    pipeline = _ready(project)
    (project / "unrelated.txt").write_text("wip\n")
    (project / "barn" / "haybale-alpha" / "stray.py").write_text("# stray\n")

    plan = pipeline.plan_commit()
    pipeline.apply_commit(plan)

    committed = _git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert "unrelated.txt" not in committed
    assert "barn/haybale-alpha/stray.py" not in committed
    assert "barn/haybale-alpha/pyproject.toml" in committed


def test_apply_commit_creates_the_tag_on_that_commit(project: Path) -> None:
    pipeline = _ready(project)
    plan = pipeline.plan_commit()
    result = pipeline.apply_commit(plan)

    tagged = _git(project, "rev-list", "-n", "1", "v0.3.2").strip()
    head = _git(project, "rev-parse", "HEAD").strip()
    assert tagged == head == result.sha
    assert result.tag == "v0.3.2"


def test_apply_commit_includes_opted_in_barn_files(project: Path) -> None:
    pipeline = _ready(project)
    asset = project / "barn" / "haybale-alpha" / "haybale_alpha" / "icon.png"
    asset.write_bytes(b"\x89PNG")

    plan = pipeline.plan_commit()
    pipeline.apply_commit(plan, include_barn=[asset])

    committed = _git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert "barn/haybale-alpha/haybale_alpha/icon.png" in committed


def test_apply_commit_excludes_barn_files_not_opted_in(project: Path) -> None:
    pipeline = _ready(project)
    asset = project / "barn" / "haybale-alpha" / "haybale_alpha" / "icon.png"
    asset.write_bytes(b"\x89PNG")

    plan = pipeline.plan_commit()
    pipeline.apply_commit(plan, include_barn=[])

    committed = _git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert "barn/haybale-alpha/haybale_alpha/icon.png" not in committed


def test_apply_commit_stages_deletions(project: Path) -> None:
    """Renamed components leave orphan docs the generator deletes; a deletion
    left unstaged ships the stale file."""
    pipeline = _ready(project)
    doomed = project / "barn" / "haybale-alpha" / "haybale_alpha" / "docs" / "old.md"
    doomed.parent.mkdir(parents=True)
    doomed.write_text("stale\n")
    _git(project, "add", "-A")
    _git(project, "commit", "-m", "add doc")

    doomed.unlink()
    pipeline._record([doomed])

    plan = pipeline.plan_commit()
    pipeline.apply_commit(plan)

    committed = _git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert "barn/haybale-alpha/haybale_alpha/docs/old.md" in committed
    assert not doomed.exists()


def test_apply_commit_authors_exactly_one_commit(project: Path) -> None:
    """No checkpoint commit — the pre-wizard HEAD is already the rollback anchor."""
    before = int(_git(project, "rev-list", "--count", "HEAD").strip())
    pipeline = _ready(project)
    pipeline.apply_commit(pipeline.plan_commit())
    after = int(_git(project, "rev-list", "--count", "HEAD").strip())
    assert after == before + 1


def test_apply_commit_with_nothing_to_commit_raises(project: Path) -> None:
    """An empty commit would be tagged and pushed as a release that changed nothing."""
    pipeline = SharePipeline(project)
    pipeline.version = "0.3.2"
    plan = pipeline.plan_commit()
    with pytest.raises(CommitError):
        pipeline.apply_commit(plan)


def test_apply_commit_leaves_no_tag_when_the_commit_fails(project: Path) -> None:
    pipeline = SharePipeline(project)
    pipeline.version = "0.3.2"
    plan = pipeline.plan_commit()
    with pytest.raises(CommitError):
        pipeline.apply_commit(plan)
    tags = _git(project, "tag", "--list").split()
    assert "v0.3.2" not in tags


def test_apply_commit_message_with_shell_metacharacters_is_literal(project: Path) -> None:
    pipeline = _ready(project)
    nasty = "chore: share v0.3.2 $(echo pwned) `whoami` && rm -rf /"
    plan = pipeline.plan_commit(message=nasty)
    pipeline.apply_commit(plan)
    assert _git(project, "log", "-1", "--format=%s").strip() == nasty


# ── verify_push_allowed ──────────────────────────────────────────────────────


def test_verify_push_allowed_passes_against_a_reachable_remote(project: Path) -> None:
    _ready(project).verify_push_allowed()  # must not raise


def test_verify_push_allowed_rejects_a_diverged_remote(project: Path, tmp_path: Path) -> None:
    """Closes the race window since step 1 — someone may have pushed meanwhile."""
    from haywire_studio.share_pipeline import PushError, gitcmd

    def _rejected(args, **_kw):
        if "--dry-run" in args:
            return gitcmd.GitResult(
                ok=False,
                stdout="",
                stderr="! [rejected] master -> master (fetch first)",
                returncode=1,
            )
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch("haywire_studio.share_pipeline.pipeline.git_remote", side_effect=_rejected):
        with pytest.raises(PushError) as excinfo:
            _ready(project).verify_push_allowed()

    assert "rejected" in excinfo.value.stderr
    assert excinfo.value.manual_command


def test_current_branch_is_reported(project: Path) -> None:
    branch = SharePipeline(project).current_branch()
    assert branch in {"main", "master"}
