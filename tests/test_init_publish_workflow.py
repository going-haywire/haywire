"""`haywire init` writes a publish workflow that is a no-op unless distribute = "pypi"."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from haywire_studio.publish_workflow import render_publish_plan, render_publish_workflow

pytestmark = pytest.mark.unit


def _project(root: Path, *, distribute: str | None, libs: dict[str, str]) -> Path:
    block = f'\n[tool.haywire.marketstall]\ndistribute = "{distribute}"\n' if distribute else ""
    (root / "pyproject.toml").write_text('[project]\nname = "proj"\nversion = "0.1.0"\n' + block)
    for name, version in libs.items():
        lib = root / "barn" / name
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n')
    (root / ".github").mkdir()
    (root / ".github" / "publish_plan.py").write_text(render_publish_plan())
    return root


def _plan(root: Path, *, ref_type: str = "tag", ref_name: str = "v0.1.0") -> tuple[int, dict[str, str], str]:
    output = root / "gh_output"
    env = {
        **os.environ,
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REF_TYPE": ref_type,
        "GITHUB_REF_NAME": ref_name,
    }
    run = subprocess.run(
        [sys.executable, "-I", ".github/publish_plan.py"], cwd=root, env=env, capture_output=True, text=True
    )
    pairs = dict(line.split("=", 1) for line in output.read_text().splitlines()) if output.exists() else {}
    return run.returncode, pairs, run.stdout


def test_workflow_triggers_on_version_tags_and_manual_dispatch() -> None:
    text = render_publish_workflow()
    assert "tags:\n      - 'v*.*.*'" in text
    assert "workflow_dispatch:" in text
    for job in ("  guard:", "  build:", "  publish:"):
        assert job in text


def test_publish_job_uses_the_trusted_publishing_identity() -> None:
    publish = render_publish_workflow().split("\n  publish:\n", 1)[1]
    assert "name: pypi" in publish
    assert "id-token: write" in publish
    assert "${{ fromJSON(needs.guard.outputs.matrix) }}" in publish
    assert "password" not in publish


def test_build_and_publish_wait_for_the_guard() -> None:
    text = render_publish_workflow()
    assert text.count("if: needs.guard.outputs.enabled == 'true'") == 2


def test_git_distribution_is_a_green_no_op(tmp_path: Path) -> None:
    root = _project(tmp_path, distribute=None, libs={"haybale-a": "0.1.0"})
    code, out, _ = _plan(root, ref_type="branch", ref_name="main")
    assert (code, out["enabled"], json.loads(out["matrix"])) == (0, "false", [])


def test_pypi_distribution_lists_every_library(tmp_path: Path) -> None:
    root = _project(tmp_path, distribute="pypi", libs={"haybale-a": "0.1.0", "haybale-b": "0.1.0"})
    code, out, _ = _plan(root)
    assert code == 0
    assert out["enabled"] == "true"
    assert json.loads(out["matrix"]) == [
        {"dist": "haybale-a", "version": "0.1.0"},
        {"dist": "haybale-b", "version": "0.1.0"},
    ]


def test_a_tag_that_does_not_match_the_version_uploads_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path, distribute="pypi", libs={"haybale-a": "0.1.0"})
    code, out, stdout = _plan(root, ref_name="v0.2.0")
    assert code == 1
    assert "enabled" not in out
    assert "does not match" in stdout


def test_a_branch_run_does_not_publish(tmp_path: Path) -> None:
    root = _project(tmp_path, distribute="pypi", libs={"haybale-a": "0.1.0"})
    code, _, stdout = _plan(root, ref_type="branch", ref_name="main")
    assert code == 1
    assert "version tag only" in stdout


def test_symlinked_libraries_are_not_published(tmp_path: Path) -> None:
    root = _project(tmp_path, distribute="pypi", libs={"haybale-a": "0.1.0"})
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "pyproject.toml").write_text('[project]\nname = "linked"\nversion = "9.9.9"\n')
    (root / "barn" / "haybale-linked").symlink_to(elsewhere)
    _, out, _ = _plan(root)
    assert [item["dist"] for item in json.loads(out["matrix"])] == ["haybale-a"]


def test_init_writes_both_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    project = tmp_path / "my-project"
    assert (project / ".github" / "workflows" / "publish.yml").read_text() == render_publish_workflow()
    assert (project / ".github" / "publish_plan.py").read_text() == render_publish_plan()
