"""Step 1 — the combined precondition gate."""

import subprocess
from pathlib import Path

import pytest

from haywire_studio.share_pipeline import PreconditionsError
from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True)


def _add_lib(repo: Path, name: str = "haybale-alpha") -> Path:
    lib = repo / "barn" / name
    (lib / name.replace("-", "_")).mkdir(parents=True)
    (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n')
    return lib


def _commit(repo: Path, message: str = "init") -> str:
    """Stage everything and commit, returning the new commit's sha."""
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _current_branch(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    """A local bare repo usable as `origin` — makes ls-remote real without a network."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)
    return remote


@pytest.fixture
def project(tmp_path: Path, bare_remote: Path) -> Path:
    """A shareable project: git repo, one barn library, origin pointing at a real bare repo."""
    repo = tmp_path / "project"
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


def test_healthy_project_passes(project: Path) -> None:
    report = SharePipeline(project).check_preconditions()
    assert report.ok is True
    assert report.failures == []
    assert report.remote_url is not None
    assert [p.name for p in report.barn_libraries] == ["haybale-alpha"]


def test_missing_barn_directory_fails(tmp_path: Path, bare_remote: Path) -> None:
    repo = tmp_path / "nobarn"
    _init_repo(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True, capture_output=True
    )
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("barn" in f.message for f in report.failures)


def test_barn_with_no_library_fails(tmp_path: Path, bare_remote: Path) -> None:
    repo = tmp_path / "emptybarn"
    _init_repo(repo)
    (repo / "barn").mkdir()
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True, capture_output=True
    )
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("pyproject.toml" in f.message for f in report.failures)


def test_missing_origin_fails_with_setup_instructions(tmp_path: Path) -> None:
    repo = tmp_path / "noremote"
    _init_repo(repo)
    _add_lib(repo)
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("remote add origin" in f.remedy for f in report.failures)
    assert report.remote_url is None


def test_unreachable_remote_fails(tmp_path: Path) -> None:
    """ls-remote exercises the exact credential path push uses, so auth
    failures surface here rather than after a commit and tag exist."""
    repo = tmp_path / "badremote"
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(tmp_path / "does-not-exist.git")],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("origin" in f.message or "origin" in f.remedy for f in report.failures)


def test_every_failure_is_reported_together(tmp_path: Path) -> None:
    """No barn AND no remote must both appear — fixing one shouldn't reveal the other."""
    repo = tmp_path / "broken"
    _init_repo(repo)
    report = SharePipeline(repo).check_preconditions()
    assert len(report.failures) >= 2
    assert any("barn" in f.message for f in report.failures)
    assert any("origin" in f.message or "origin" in f.remedy for f in report.failures)


def test_missing_git_binary_reports_install_instructions(project: Path, monkeypatch) -> None:
    from haywire_studio import gitcmd

    def _no_git(*_a, **_kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitcmd.subprocess, "run", _no_git)
    report = SharePipeline(project).check_preconditions()
    assert report.ok is False
    assert any("git-scm.com" in f.remedy for f in report.failures)


def test_require_preconditions_raises_with_all_failures(tmp_path: Path) -> None:
    repo = tmp_path / "broken2"
    _init_repo(repo)
    with pytest.raises(PreconditionsError) as excinfo:
        SharePipeline(repo).require_preconditions()
    assert len(excinfo.value.failures) >= 2


def test_require_preconditions_returns_report_when_ok(project: Path) -> None:
    report = SharePipeline(project).require_preconditions()
    assert report.ok is True


def test_successful_check_records_remote_url_on_the_pipeline(project: Path) -> None:
    pipeline = SharePipeline(project)
    assert pipeline.remote_url is None
    pipeline.check_preconditions()
    assert pipeline.remote_url is not None


def test_pipeline_starts_with_an_empty_write_set(project: Path) -> None:
    assert SharePipeline(project).written == []


def test_every_failure_has_a_non_empty_remedy(tmp_path: Path, bare_remote: Path, monkeypatch) -> None:
    """No `PreconditionFailure` returned under any failure scenario has an empty remedy.

    Covers every branch of ``check_preconditions``: missing git, missing barn/,
    empty barn/, missing origin, unreachable origin, and everything-broken.
    """
    from haywire_studio import gitcmd

    scenarios: list[Path] = []

    nobarn = tmp_path / "nobarn2"
    _init_repo(nobarn)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=nobarn, check=True, capture_output=True
    )
    scenarios.append(nobarn)

    emptybarn = tmp_path / "emptybarn2"
    _init_repo(emptybarn)
    (emptybarn / "barn").mkdir()
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)],
        cwd=emptybarn,
        check=True,
        capture_output=True,
    )
    scenarios.append(emptybarn)

    noremote = tmp_path / "noremote2"
    _init_repo(noremote)
    _add_lib(noremote)
    scenarios.append(noremote)

    badremote = tmp_path / "badremote2"
    _init_repo(badremote)
    _add_lib(badremote)
    subprocess.run(
        ["git", "remote", "add", "origin", str(tmp_path / "does-not-exist2.git")],
        cwd=badremote,
        check=True,
        capture_output=True,
    )
    scenarios.append(badremote)

    broken = tmp_path / "broken3"
    _init_repo(broken)
    scenarios.append(broken)

    for repo in scenarios:
        report = SharePipeline(repo).check_preconditions()
        assert report.ok is False
        for failure in report.failures:
            assert failure.remedy, f"{repo.name}: {failure.message!r} has no remedy"

    project_repo = tmp_path / "gitless"
    _init_repo(project_repo)
    _add_lib(project_repo)

    def _no_git(*_a, **_kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitcmd.subprocess, "run", _no_git)
    report = SharePipeline(project_repo).check_preconditions()
    assert report.ok is False
    for failure in report.failures:
        assert failure.remedy, f"missing-git: {failure.message!r} has no remedy"


# ── 4a: malformed / invalid manifest ────────────────────────────────────────


def test_invalid_os_declaration_fails_with_remedy(project: Path) -> None:
    """[tool.haywire].os with 'other' (a runtime sentinel) is rejected (4a)."""
    lib = project / "barn" / "haybale-alpha"
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["macos", "other"]\n')

    report = SharePipeline(project).check_preconditions()

    assert report.ok is False
    matches = [f for f in report.failures if "pyproject.toml" in f.message]
    assert matches, report.failures
    for f in matches:
        assert f.remedy
        assert "macos" in f.remedy and "windows" in f.remedy and "linux" in f.remedy
        assert "other" in f.remedy


def test_malformed_toml_fails_with_remedy(project: Path) -> None:
    """A pyproject.toml the parser cannot read at all is reported by name (4a)."""
    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text("this is not [[[ valid toml")

    report = SharePipeline(project).check_preconditions()

    assert report.ok is False
    matches = [f for f in report.failures if "pyproject.toml" in f.message]
    assert matches, report.failures
    for f in matches:
        assert f.remedy


def test_malformed_manifest_is_two_faces_of_one_condition(project: Path) -> None:
    """The same malformed manifest is reported two ways by two callers:
    check_preconditions() surfaces it as a PreconditionFailure (report, don't raise —
    the wizard's first panel explains why sharing is blocked), while apply_marketstall()
    — a later step that assumes preconditions already passed — raises MarketstallError.
    """
    from haywire_studio.share_pipeline import MarketstallError

    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text("this is not [[[ valid toml")

    report = SharePipeline(project).check_preconditions()
    assert report.ok is False
    assert any("pyproject.toml" in f.message for f in report.failures)

    with pytest.raises(MarketstallError):
        SharePipeline(project).apply_marketstall()


# ── 4b: detached HEAD ────────────────────────────────────────────────────────


def test_detached_head_fails_with_remedy(tmp_path: Path, bare_remote: Path) -> None:
    repo = tmp_path / "detached"
    _init_repo(repo)
    _add_lib(repo)
    sha = _commit(repo)
    subprocess.run(["git", "checkout", sha], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True, capture_output=True
    )

    report = SharePipeline(repo).check_preconditions()

    assert report.ok is False
    matches = [f for f in report.failures if "detached" in f.message.lower()]
    assert matches, report.failures
    for f in matches:
        assert f.remedy


def test_unborn_branch_is_not_mistaken_for_detached_head(project: Path) -> None:
    """A brand-new repo with zero commits is NOT detached HEAD.

    `git rev-parse --abbrev-ref HEAD` prints the same literal "HEAD" for both
    an unborn branch and a genuinely detached one, so the check must not use
    that string alone — otherwise a project nobody has committed to yet would
    be misreported as detached.
    """
    report = SharePipeline(project).check_preconditions()
    assert report.ok is True
    assert not any("detached" in f.message.lower() for f in report.failures)


# ── 4c: publishing from a non-default branch ────────────────────────────────


def _bare_remote_with_default_branch(tmp_path: Path, name: str) -> tuple[Path, str]:
    """A bare repo that HAS been pushed to (via clone, never `git push`).

    Returns (remote_path, default_branch_name). Distinct from the module-level
    `bare_remote` fixture, which is deliberately never pushed to (it backs the
    "nothing has ever been shared" tests, where a default branch must stay
    undeterminable).
    """
    source = tmp_path / f"{name}_source"
    _init_repo(source)
    (source / "f.txt").write_text("x")
    _commit(source)
    default_branch = _current_branch(source)

    remote = tmp_path / f"{name}.git"
    subprocess.run(["git", "clone", "--bare", str(source), str(remote)], check=True, capture_output=True)
    return remote, default_branch


def test_non_default_branch_fails_with_remedy(tmp_path: Path) -> None:
    remote, default_branch = _bare_remote_with_default_branch(tmp_path, "pushed_remote")

    repo = tmp_path / "feature_checkout"
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(["git", "checkout", "-b", "feature-x"], cwd=repo, check=True, capture_output=True)
    _commit(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True, capture_output=True
    )

    report = SharePipeline(repo).check_preconditions()

    assert report.default_branch == default_branch
    assert report.ok is False
    matches = [f for f in report.failures if "default branch" in f.message]
    assert matches, report.failures
    for f in matches:
        assert f.remedy
        assert "feature-x" in f.message
        assert f.remedy == (
            f"Switch to the default branch and publish from there: `git switch {default_branch}`."
        )


def test_default_branch_checkout_passes(tmp_path: Path) -> None:
    """The common, healthy case: local checkout on the SAME branch the remote
    was pushed to. Every existing 4c test either fails the check or uses the
    never-pushed `bare_remote` fixture (default_branch stays None, so the
    branch comparison never runs) — this is the one real projects live in.
    """
    remote, default_branch = _bare_remote_with_default_branch(tmp_path, "matching_remote")

    repo = tmp_path / "matching_checkout"
    _init_repo(repo)
    _add_lib(repo)
    _commit(repo)
    assert _current_branch(repo) == default_branch
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True, capture_output=True
    )

    report = SharePipeline(repo).check_preconditions()

    assert report.ok is True
    assert report.default_branch == default_branch


def test_unpushed_remote_leaves_default_branch_undetermined(project: Path) -> None:
    """The never-pushed `bare_remote` fixture must not be mistaken for a 4c failure.

    `git ls-remote --symref` on a bare repo with zero refs exits 0 with empty
    stdout — no `ref:` line to parse. That is "nothing has ever been shared",
    not a wrong branch, so `default_branch` stays None and no failure fires.
    """
    report = SharePipeline(project).check_preconditions()
    assert report.default_branch is None
    assert report.ok is True
