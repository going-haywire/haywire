"""Step 4 — docs regeneration via a subprocess, never in-process."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from haywire_studio.packaging.share.pipeline import DocsGenerationError
from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, capture_output=True)
    lib = repo / "barn" / "haybale-alpha" / "haybale_alpha"
    lib.mkdir(parents=True)
    (repo / "barn" / "haybale-alpha" / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\n'
    )
    (lib / "OVERVIEW.md").write_text("old overview\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    return repo


def test_docs_command_shells_out_with_all_and_json(project: Path) -> None:
    """In-process generation would repoint the live app's global injector and
    instantiate every node (hardware grabs) — see
    .insights/project_docs_gen_reentrancy.md."""
    cmd = SharePipeline(project).docs_command()
    assert cmd[:2] == ["haywire", "docs"] or cmd[:4] == ["uv", "run", "haywire", "docs"]
    assert "--all" in cmd
    assert "--json" in cmd


def test_docs_command_never_names_a_single_library(project: Path) -> None:
    """--all is one library-system load for the whole barn, and its
    root-relative filter excludes site-packages and --dev out-of-tree libs."""
    cmd = SharePipeline(project).docs_command()
    assert "haybale-alpha" not in " ".join(cmd)


@pytest.mark.anyio
async def test_apply_docs_parses_the_coverage_report(project: Path) -> None:
    from haywire_studio.packaging.share import git as gitcmd

    async def _fake_stream(cmd, *, cwd, on_output, timeout=None):
        # The real subprocess writes the report; emulate that side effect.
        json_path = Path(cmd[cmd.index("--json") + 1])
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps({"alpha": ["node Foo: no docstring"], "beta": []}))
        on_output("Generated docs for 2 libraries.")
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    pipeline = SharePipeline(project)
    with patch("haywire_studio.packaging.share.pipeline.steps.docs.run_streaming", side_effect=_fake_stream):
        result = await pipeline.apply_docs()

    assert result.coverage == {"alpha": ["node Foo: no docstring"], "beta": []}
    assert result.total_gaps == 1


@pytest.mark.anyio
async def test_apply_docs_streams_every_line(project: Path) -> None:
    from haywire_studio.packaging.share import git as gitcmd

    async def _fake_stream(cmd, *, cwd, on_output, timeout=None):
        Path(cmd[cmd.index("--json") + 1]).write_text("{}")
        for line in ("loading libraries…", "  • alpha: clean"):
            on_output(line)
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    lines: list[str] = []
    with patch("haywire_studio.packaging.share.pipeline.steps.docs.run_streaming", side_effect=_fake_stream):
        await SharePipeline(project).apply_docs(on_output=lines.append)

    assert lines == ["loading libraries…", "  • alpha: clean"]


@pytest.mark.anyio
async def test_apply_docs_raises_on_a_crash(project: Path) -> None:
    from haywire_studio.packaging.share import git as gitcmd

    async def _crash(cmd, *, cwd, on_output, timeout=None):
        on_output("Traceback (most recent call last):")
        return gitcmd.GitResult(ok=False, stdout="boom", stderr="boom", returncode=1)

    with patch("haywire_studio.packaging.share.pipeline.steps.docs.run_streaming", side_effect=_crash):
        with pytest.raises(DocsGenerationError) as excinfo:
            await SharePipeline(project).apply_docs()

    assert "boom" in excinfo.value.output or "boom" in str(excinfo.value)


@pytest.mark.anyio
async def test_apply_docs_records_modified_and_deleted_docs(project: Path) -> None:
    """Renamed components leave orphan docs that the generator DELETES
    (generate.py:87). A deletion must reach the commit, or the stale file ships."""
    from haywire_studio.packaging.share import git as gitcmd

    module = project / "barn" / "haybale-alpha" / "haybale_alpha"

    async def _fake_stream(cmd, *, cwd, on_output, timeout=None):
        Path(cmd[cmd.index("--json") + 1]).write_text("{}")
        (module / "OVERVIEW.md").write_text("new overview\n")  # modified
        (module / "QUICKREF.md").write_text("quickref\n")  # added
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    # Commit a doc that generation will remove, so a deletion is in the diff.
    docs = module / "docs"
    docs.mkdir()
    (docs / "old-node.md").write_text("stale\n")
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "stale doc"], cwd=project, check=True, capture_output=True)
    (docs / "old-node.md").unlink()

    pipeline = SharePipeline(project)
    with patch("haywire_studio.packaging.share.pipeline.steps.docs.run_streaming", side_effect=_fake_stream):
        result = await pipeline.apply_docs()

    names = {p.name for p in result.written}
    assert "OVERVIEW.md" in names
    assert "QUICKREF.md" in names
    assert "old-node.md" in names  # the deletion
    for path in result.written:
        assert path in pipeline.written


@pytest.mark.anyio
async def test_apply_docs_ignores_changes_outside_barn(project: Path) -> None:
    """Only barn content ships to consumers; unrelated dirt is not the wizard's business."""
    from haywire_studio.packaging.share import git as gitcmd

    async def _fake_stream(cmd, *, cwd, on_output, timeout=None):
        Path(cmd[cmd.index("--json") + 1]).write_text("{}")
        (project / "scratch.md").write_text("unrelated\n")
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch("haywire_studio.packaging.share.pipeline.steps.docs.run_streaming", side_effect=_fake_stream):
        result = await SharePipeline(project).apply_docs()

    assert all("scratch.md" != p.name for p in result.written)


@pytest.mark.anyio
async def test_apply_docs_cleans_up_its_temp_json(project: Path) -> None:
    from haywire_studio.packaging.share import git as gitcmd

    captured: dict[str, Path] = {}

    async def _fake_stream(cmd, *, cwd, on_output, timeout=None):
        path = Path(cmd[cmd.index("--json") + 1])
        captured["path"] = path
        path.write_text("{}")
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch("haywire_studio.packaging.share.pipeline.steps.docs.run_streaming", side_effect=_fake_stream):
        await SharePipeline(project).apply_docs()

    assert not captured["path"].exists()
