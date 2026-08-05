"""Step 6 — pushing the commit and tag to origin."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from haywire.core.publishing.pipeline import PipelineStateError, PushError
from haywire.core.publishing.pipeline.pipeline import SharePipeline
from haywire.core.publishing.pipeline.steps import push as steps_push

pytestmark = pytest.mark.unit


@pytest.fixture
def pushable(tmp_path: Path) -> Path:
    """A repo with a bare origin, one commit, and a v0.3.2 tag ready to push."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    repo = tmp_path / "project"
    repo.mkdir()
    for args in (
        ["init"],
        ["config", "user.email", "t@t.test"],
        ["config", "user.name", "T"],
        ["remote", "add", "origin", str(remote)],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    (repo / "a.txt").write_text("a\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "tag", "v0.3.2"], cwd=repo, check=True, capture_output=True)
    return repo


def _ready(repo: Path) -> SharePipeline:
    pipeline = SharePipeline(repo)
    pipeline.version = "0.3.2"
    return pipeline


@pytest.mark.anyio
async def test_push_sends_commit_and_tag(pushable: Path, tmp_path: Path) -> None:
    result = await _ready(pushable).apply_push()

    remote = tmp_path / "remote.git"
    tags = subprocess.run(
        ["git", "tag", "--list"], cwd=remote, capture_output=True, text=True, check=True
    ).stdout.split()
    assert "v0.3.2" in tags
    assert result.tag == "v0.3.2"
    assert result.remote == "origin"
    assert result.branch in {"main", "master"}


@pytest.mark.anyio
async def test_push_streams_output(pushable: Path) -> None:
    lines: list[str] = []
    await _ready(pushable).apply_push(on_output=lines.append)
    assert lines  # git writes transfer progress to the merged stream


@pytest.mark.anyio
async def test_push_uses_the_hardened_env(pushable: Path) -> None:
    """A missing credential must be a clean error, not an indefinite hang —
    there is no TTY behind a NiceGUI event handler."""
    from haywire.core.publishing import git as gitcmd

    seen: dict = {}

    async def _capture(args, *, cwd, on_output, timeout=None):
        seen["args"] = args
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch.object(steps_push, "git_remote_streaming", side_effect=_capture):
        await _ready(pushable).apply_push()

    # apply_push must route through git_remote_streaming (which applies the
    # hardened env), never through a bare create_subprocess_exec.
    assert seen["args"][0] == "push"


@pytest.mark.anyio
async def test_push_failure_raises_with_the_manual_command(pushable: Path) -> None:
    from haywire.core.publishing import git as gitcmd

    async def _fail(args, *, cwd, on_output, timeout=None):
        on_output("remote: Permission denied")
        return gitcmd.GitResult(ok=False, stdout="denied", stderr="denied", returncode=128)

    with patch.object(steps_push, "git_remote_streaming", side_effect=_fail):
        with pytest.raises(PushError) as excinfo:
            await _ready(pushable).apply_push()

    assert "push origin" in excinfo.value.manual_command
    assert "v0.3.2" in excinfo.value.manual_command


@pytest.mark.anyio
async def test_push_is_retryable_in_place(pushable: Path) -> None:
    """A transient network failure must not poison the pipeline — the same step
    can be run again without re-running earlier steps."""
    from haywire.core.publishing import git as gitcmd

    calls = {"n": 0}

    async def _flaky(args, *, cwd, on_output, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return gitcmd.GitResult(ok=False, stdout="", stderr="timed out", returncode=128)
        return gitcmd.GitResult(ok=True, stdout="ok", stderr="", returncode=0)

    pipeline = _ready(pushable)
    with patch.object(steps_push, "git_remote_streaming", side_effect=_flaky):
        with pytest.raises(PushError):
            await pipeline.apply_push()
        result = await pipeline.apply_push()

    assert result.tag == "v0.3.2"


@pytest.mark.anyio
async def test_push_without_a_version_raises(pushable: Path) -> None:
    with pytest.raises(PipelineStateError):
        await SharePipeline(pushable).apply_push()


@pytest.mark.anyio
async def test_push_raises_on_detached_head(pushable: Path) -> None:
    """Defensive: check_preconditions() already rejects detached HEAD before any
    caller reaches apply_push(), but the guard here must fail loud rather than
    silently push a `HEAD:None`-shaped refspec if it's ever reached anyway."""
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=pushable, check=True, capture_output=True, text=True
    ).stdout.strip()
    subprocess.run(["git", "checkout", sha], cwd=pushable, check=True, capture_output=True)

    with pytest.raises(PipelineStateError):
        await _ready(pushable).apply_push()
