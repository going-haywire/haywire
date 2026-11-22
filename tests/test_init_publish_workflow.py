"""`haywire init` writes a publish workflow that is a no-op unless distribute = "pypi"."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from haywire_studio.publish_workflow import render_publish_plan, render_publish_workflow

pytestmark = pytest.mark.unit


def _project(root: Path, *, distribute: str | None, libs: dict[str, str], root_extra: str = "") -> Path:
    block = f'\n[tool.haywire.marketstall]\ndistribute = "{distribute}"\n' if distribute else ""
    (root / "pyproject.toml").write_text(
        '[project]\nname = "proj"\nversion = "0.1.0"\n' + root_extra + block
    )
    for name, version in libs.items():
        lib = root / "barn" / name
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n')
    (root / ".github").mkdir()
    (root / ".github" / "publish_plan.py").write_text(render_publish_plan())
    return root


def _plan(
    root: Path, *, ref_type: str = "tag", ref_name: str = "v0.1.0", extra_env: dict[str, str] | None = None
) -> tuple[int, dict[str, str], str]:
    output = root / "gh_output"
    # The planner reads these from the runner; a test must not inherit the real CI run's.
    env = {
        **{
            k: v
            for k, v in os.environ.items()
            if k not in ("GITHUB_EVENT_NAME", "DEFAULT_BRANCH", "BEFORE_SHA")
        },
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REF_TYPE": ref_type,
        "GITHUB_REF_NAME": ref_name,
        **(extra_env or {}),
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
    assert text.count("if: needs.guard.outputs.enabled == 'true'") == 3  # build, smoke, tag
    assert "needs: [guard, build, smoke, tag]" in text


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
        {"dist": "haybale-a", "version": "0.1.0", "path": "barn/haybale-a"},
        {"dist": "haybale-b", "version": "0.1.0", "path": "barn/haybale-b"},
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


def _standalone(root: Path) -> bool:
    _, out, _ = _plan(root)
    return out["standalone"] == "true"


def test_a_root_without_sources_is_standalone(tmp_path: Path) -> None:
    assert _standalone(_project(tmp_path, distribute="pypi", libs={"haybale-a": "0.1.0"}))


def test_a_root_whose_sources_stay_inside_the_checkout_is_standalone(tmp_path: Path) -> None:
    extra = (
        "\n[tool.uv.sources.haybale-a]\nworkspace = true\n"
        '\n[tool.uv.sources.vendored]\npath = "vendor/vendored"\n'
    )
    root = _project(tmp_path, distribute="pypi", libs={"haybale-a": "0.1.0"}, root_extra=extra)
    assert _standalone(root)


def test_a_relative_link_out_of_the_checkout_is_not_standalone(tmp_path: Path) -> None:
    extra = (
        '\n[tool.uv.sources.haywire-core]\npath = "../haywire-repo/packages/haywire-core"\neditable = true\n'
    )
    (tmp_path / "proj").mkdir()
    root = _project(tmp_path / "proj", distribute="pypi", libs={"haybale-a": "0.1.0"}, root_extra=extra)
    assert not _standalone(root)


def test_an_absolute_link_out_of_the_checkout_is_not_standalone(tmp_path: Path) -> None:
    extra = '\n[tool.uv.sources.haywire-core]\npath = "/home/dev/haywire/packages/haywire-core"\n'
    root = _project(tmp_path, distribute="pypi", libs={"haybale-a": "0.1.0"}, root_extra=extra)
    assert not _standalone(root)


def test_the_pyproject_of_a_dev_project_is_not_standalone(tmp_path: Path) -> None:
    from haywire_studio.init import _generate_project_pyproject

    generated = _generate_project_pyproject("proj", "haybale-proj", dev_repo="/home/dev/haywire")
    root = _project(tmp_path, distribute="pypi", libs={"haybale-proj": "0.1.0"})
    (root / "pyproject.toml").write_text(generated + '\n[tool.haywire.marketstall]\ndistribute = "pypi"\n')
    assert not _standalone(root)


def test_the_flag_is_reported_even_when_nothing_is_published(tmp_path: Path) -> None:
    root = _project(tmp_path, distribute=None, libs={"haybale-a": "0.1.0"})
    _, out, _ = _plan(root, ref_type="branch", ref_name="main")
    assert out["standalone"] == "true"


def test_each_library_is_built_from_its_own_directory() -> None:
    build = render_publish_workflow().split("\n  build:\n", 1)[1].split("\n  publish:\n", 1)[0]
    assert "working-directory: ${{ matrix.lib.path }}" in build
    assert 'uv build --out-dir "${GITHUB_WORKSPACE}/dist"' in build
    assert "--package" not in build


def test_the_root_is_only_synced_for_the_tests_of_a_standalone_project() -> None:
    build = render_publish_workflow().split("\n  build:\n", 1)[1].split("\n  publish:\n", 1)[0]
    assert build.count("uv sync") == 1
    tests = build.split("- name: Run tests\n", 1)[1].split("- name: Build", 1)[0]
    assert "needs.guard.outputs.standalone == 'true'" in tests
    assert "uv sync --frozen" in tests


def test_the_guard_passes_the_flag_on() -> None:
    assert "standalone: ${{ steps.plan.outputs.standalone }}" in render_publish_workflow()


def test_every_action_is_pinned_to_a_commit() -> None:
    uses = re.findall(r"uses: (\S+)(.*)", render_publish_workflow())
    assert len(uses) == 9
    for ref, comment in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), ref
        assert re.fullmatch(r" # v\d+\.\d+\.\d+", comment), ref


def test_init_writes_both_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    project = tmp_path / "my-project"
    assert (project / ".github" / "workflows" / "publish.yml").read_text() == render_publish_workflow()
    assert (project / ".github" / "publish_plan.py").read_text() == render_publish_plan()


# ── a push to the default branch: the merge of a release PR ─────────────────


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _merged(tmp_path: Path, *, bump: str | None = "0.2.0") -> tuple[Path, str]:
    """A project at 0.1.0 whose next commit bumps the library; returns it and the commit before."""
    root = _project(tmp_path, distribute="pypi", libs={"haybale-a": "0.1.0"})
    for args in (("init", "-b", "main"), ("config", "user.email", "t@t.test"), ("config", "user.name", "T")):
        _git(root, *args)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "seed")
    before = _git(root, "rev-parse", "HEAD")
    manifest = root / "barn" / "haybale-a" / "pyproject.toml"
    manifest.write_text(f'[project]\nname = "haybale-a"\nversion = "{bump or "0.1.0"}"\n# edit\n')
    _git(root, "commit", "-am", "release")
    return root, before


def _push_plan(root: Path, before: str, *, branch: str = "main") -> tuple[int, dict[str, str], str]:
    return _plan(
        root,
        ref_type="branch",
        ref_name=branch,
        extra_env={"GITHUB_EVENT_NAME": "push", "DEFAULT_BRANCH": "main", "BEFORE_SHA": before},
    )


def test_a_push_that_changes_the_version_asks_for_its_tag(tmp_path: Path) -> None:
    root, before = _merged(tmp_path)
    code, out, _ = _push_plan(root, before)
    assert (code, out["enabled"], out["tag"]) == (0, "true", "v0.2.0")
    assert [item["dist"] for item in json.loads(out["matrix"])] == ["haybale-a"]


def test_a_push_to_a_tagged_version_does_nothing(tmp_path: Path) -> None:
    root, before = _merged(tmp_path)
    _git(root, "tag", "v0.2.0")
    code, out, _ = _push_plan(root, before)
    assert (code, out["enabled"], out["tag"]) == (0, "false", "")


def test_a_push_that_keeps_the_version_does_nothing(tmp_path: Path) -> None:
    root, before = _merged(tmp_path, bump=None)
    code, out, _ = _push_plan(root, before)
    assert (code, out["enabled"]) == (0, "false")


def test_a_push_to_another_branch_does_nothing(tmp_path: Path) -> None:
    root, before = _merged(tmp_path)
    code, out, _ = _push_plan(root, before, branch="feature")
    assert (code, out["enabled"]) == (0, "false")


def test_a_new_branch_push_has_no_before_commit_and_does_nothing(tmp_path: Path) -> None:
    root, _ = _merged(tmp_path)
    code, out, _ = _push_plan(root, "0" * 40)
    assert (code, out["enabled"]) == (0, "false")


def test_the_tag_job_runs_between_build_and_publish() -> None:
    import yaml  # type: ignore[import-untyped]

    jobs = yaml.safe_load(render_publish_workflow())["jobs"]
    assert jobs["tag"]["needs"] == ["guard", "build", "smoke"]
    assert jobs["tag"]["permissions"] == {"contents": "write"}
    assert jobs["publish"]["needs"] == ["guard", "build", "smoke", "tag"]
    assert "needs.tag.result != 'failure'" in jobs["publish"]["if"]
    assert "needs.smoke.result == 'success'" in jobs["publish"]["if"]


def test_the_smoke_job_installs_every_wheel_in_one_clean_environment() -> None:
    import yaml

    smoke = yaml.safe_load(render_publish_workflow())["jobs"]["smoke"]
    assert smoke["needs"] == ["guard", "build"]
    download = smoke["steps"][0]
    assert download["with"] == {"pattern": "dist-*", "path": "dist/", "merge-multiple": True}
    install = next(step for step in smoke["steps"] if step.get("name") == "Install the wheels")
    assert "uv venv" in install["run"]
    assert "uv pip install dist/*.whl" in install["run"]
    assert "uv sync" not in install["run"]


def _load_script() -> str:
    import yaml

    steps = yaml.safe_load(render_publish_workflow())["jobs"]["smoke"]["steps"]
    run = next(step for step in steps if step.get("name") == "Load every library as the studio does")["run"]
    return run.split("<<'PY'\n", 1)[1].rsplit("PY\n", 1)[0]


def _run_load_script(dists: list[str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "MATRIX": json.dumps([{"dist": dist} for dist in dists])}
    return subprocess.run(
        [sys.executable, "-c", _load_script()], env=env, capture_output=True, text=True, timeout=120
    )


def test_the_smoke_job_loads_a_library_entry_point() -> None:
    result = _run_load_script(["haybale-core"])
    assert result.returncode == 0, result.stderr
    assert "haybale-core: loaded" in result.stdout


def test_the_smoke_job_fails_for_a_wheel_without_a_library_entry_point() -> None:
    result = _run_load_script(["pytest"])
    assert result.returncode != 0
    assert "pytest declares no haywire.libraries entry point" in result.stderr


def test_the_workflow_also_triggers_on_the_default_branches() -> None:
    import yaml

    triggers = yaml.safe_load(render_publish_workflow())[True]
    assert triggers["push"]["branches"] == ["main", "master"]
