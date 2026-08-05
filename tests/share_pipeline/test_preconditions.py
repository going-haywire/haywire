"""Step 1 — the combined precondition gate."""

import subprocess
from pathlib import Path

import pytest

from haywire_studio.packaging.share.pipeline import PreconditionsError
from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline

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
    """A shareable project: git repo, one barn library, origin pointing at a real bare repo, clean tree."""
    repo = tmp_path / "project"
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    _commit(repo)
    return repo


def test_healthy_project_passes(project: Path) -> None:
    report = SharePipeline(project).check_preconditions()
    assert report.ok is True
    assert report.failures == []
    assert report.remote_url is not None
    assert [p.name for p in report.barn_libraries] == ["haybale-alpha"]


def test_dirty_working_tree_fails_first_and_lists_every_dirty_file(
    tmp_path: Path, bare_remote: Path
) -> None:
    """A dirty tree wins over every other probe, and names every offending
    file so the user can act without re-running `git status` themselves.

    The repo is otherwise healthy EXCEPT that it is also missing an origin —
    proving ordering, since stop-at-first-failure means only the earliest
    probe can show. Two dirty files, one modified and one untracked, cover
    both halves of `git status --porcelain` output.
    """
    repo = tmp_path / "dirty"
    _init_repo(repo)
    _add_lib(repo)
    _commit(repo)
    (repo / "barn" / "haybale-alpha" / "pyproject.toml").write_text('[project]\nname = "x"\n')
    (repo / "untracked.txt").write_text("scratch")

    report = SharePipeline(repo).check_preconditions()

    assert report.ok is False
    assert report.failure is not None
    assert "working tree" in report.failure.message.lower()
    assert "untracked.txt" in report.failure.message
    assert "pyproject.toml" in report.failure.message


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
    _commit(repo)
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert report.failure is not None
    assert report.failure.kind == "act"
    assert report.failure.fix_id == "add_origin"
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
    _commit(repo)
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("origin" in f.message or "origin" in f.remedy for f in report.failures)


def test_check_stops_at_the_first_failure(tmp_path: Path) -> None:
    """No barn/ AND no origin are both true here, but only the first-encountered
    problem (no barn/, which is probed before origin) is reported — an earlier
    failure can make a later probe's result moot, so check() does not run it."""
    repo = tmp_path / "broken"
    _init_repo(repo)
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert len(report.failures) == 1
    assert report.failure is not None
    assert "barn" in report.failure.message


def test_missing_git_binary_reports_install_instructions(project: Path, monkeypatch) -> None:
    from haywire_studio.packaging.share import git as gitcmd

    def _no_git(*_a, **_kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitcmd.subprocess, "run", _no_git)
    report = SharePipeline(project).check_preconditions()
    assert report.ok is False
    assert any("git-scm.com" in f.remedy for f in report.failures)


def test_require_preconditions_raises_with_the_first_failure(tmp_path: Path) -> None:
    repo = tmp_path / "broken2"
    _init_repo(repo)
    with pytest.raises(PreconditionsError) as excinfo:
        SharePipeline(repo).require_preconditions()
    assert len(excinfo.value.failures) == 1


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

    Covers several branches of ``check_preconditions``: missing git, missing
    barn/, empty barn/, missing origin, unreachable origin. Since check()
    stops at the first failure, each scenario below yields exactly one.
    """
    from haywire_studio.packaging.share import git as gitcmd

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
        assert len(report.failures) == 1
        for failure in report.failures:
            assert failure.remedy, f"{repo.name}: {failure.message!r} has no remedy"

    project_repo = tmp_path / "gitless"
    _init_repo(project_repo)
    _add_lib(project_repo)
    _commit(project_repo)

    def _no_git(*_a, **_kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitcmd.subprocess, "run", _no_git)
    report = SharePipeline(project_repo).check_preconditions()
    assert report.ok is False
    assert len(report.failures) == 1
    for failure in report.failures:
        assert failure.remedy, f"missing-git: {failure.message!r} has no remedy"


# ── 4a: malformed / invalid manifest ────────────────────────────────────────


def test_invalid_os_declaration_fails_with_remedy(project: Path) -> None:
    """[tool.haywire].os with 'other' (a runtime sentinel) is rejected (4a)."""
    lib = project / "barn" / "haybale-alpha"
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["macos", "other"]\n')
    _commit(project, "add invalid os")

    report = SharePipeline(project).check_preconditions()

    assert report.ok is False
    matches = [f for f in report.failures if "pyproject.toml" in f.message]
    assert matches, report.failures
    for f in matches:
        assert f.remedy
        assert "macos" in f.remedy
        assert "windows" in f.remedy
        assert "linux" in f.remedy
        assert "other" in f.remedy


def test_invalid_os_declaration_carries_strip_os_fix_id(project: Path) -> None:
    """The os fault is the ONE remediable precondition in Task 2's scope: it
    offers fix_id='strip_os' with a label describing what will happen."""
    lib = project / "barn" / "haybale-alpha"
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["macos", "other"]\n')
    _commit(project, "add invalid os")

    report = SharePipeline(project).check_preconditions()

    assert report.ok is False
    matches = [f for f in report.failures if "pyproject.toml" in f.message]
    assert matches, report.failures
    for f in matches:
        assert f.kind == "act"
        assert f.fix_id == "strip_os"
        assert f.fix_label == "Remove invalid values"


def test_invalid_os_declaration_fix_label_states_correction_when_unambiguous(project: Path) -> None:
    """When every bad value maps cleanly to the same target, the label says so."""
    lib = project / "barn" / "haybale-alpha"
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["osx"]\n')
    _commit(project, "add correctable os")

    report = SharePipeline(project).check_preconditions()

    matches = [f for f in report.failures if "pyproject.toml" in f.message]
    assert matches, report.failures
    for f in matches:
        assert f.fix_id == "strip_os"
        assert f.fix_label == "Correct to macos"


def test_malformed_toml_fails_with_remedy(project: Path) -> None:
    """A pyproject.toml the parser cannot read at all is reported by name (4a).

    The underlying `toml` parser error — quoting line/column and embedded in
    `message` via `ManifestReadError` — is asserted verbatim below rather than
    just checking non-emptiness, so a regression that drops the parser's own
    line/column info (or the file path) would be caught here.
    """
    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text("this is not [[[ valid toml")
    _commit(project, "corrupt toml")

    report = SharePipeline(project).check_preconditions()

    assert report.ok is False
    matches = [f for f in report.failures if "pyproject.toml" in f.message]
    assert matches, report.failures
    for f in matches:
        assert f.remedy
        # message must name the file AND quote the parser's line/column info —
        # verified against the toml library's actual output for this exact
        # malformed string (see the module docstring in share.py's
        # read_manifest()): "... (line 1 column 6 char 5)".
        assert "pyproject.toml" in f.message
        assert "line 1 column 6 char 5" in f.message


def test_malformed_toml_carries_no_fix_id(project: Path) -> None:
    """A TOML parse failure (ManifestReadError) has no mechanical repair —
    fix_id must stay None, unlike the InvalidOsDeclarationError branch."""
    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text("this is not [[[ valid toml")
    _commit(project, "corrupt toml")

    report = SharePipeline(project).check_preconditions()

    assert report.ok is False
    matches = [f for f in report.failures if "pyproject.toml" in f.message]
    assert matches, report.failures
    for f in matches:
        assert f.fix_id is None
        assert f.fix_label == ""


def test_malformed_manifest_is_two_faces_of_one_condition(project: Path) -> None:
    """The same malformed manifest is reported two ways by two callers:
    check_preconditions() surfaces it as a PreconditionFailure (report, don't raise —
    the wizard's first panel explains why sharing is blocked), while apply_marketstall()
    — a later step that assumes preconditions already passed — raises MarketstallError.
    """
    from haywire_studio.packaging.share.pipeline import MarketstallError

    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text("this is not [[[ valid toml")
    _commit(project, "corrupt toml")

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
    branch = _current_branch(repo)
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
        # The commit IS on `branch` (the checkout above only moved HEAD off
        # of it), so the remedy must name that branch and the concrete
        # `git switch` command — not just generic prose.
        assert f"`{branch}`" in f.remedy
        assert f"git switch {branch}" in f.remedy


def test_detached_head_with_no_branch_suggests_switch_dash_c(tmp_path: Path, bare_remote: Path) -> None:
    """A dangling commit no branch was ever built from: `git branch --contains
    HEAD` returns nothing real, so the remedy must fall back to `git switch -c`
    guidance rather than naming a nonexistent branch."""
    repo = tmp_path / "detached_no_branch"
    _init_repo(repo)
    _add_lib(repo)
    sha = _commit(repo)
    branch = _current_branch(repo)
    (repo / "barn" / "haybale-alpha" / "extra.txt").write_text("more")
    second_sha = _commit(repo, message="second")
    # Detach onto second_sha FIRST — a checked-out branch can't be force-moved.
    subprocess.run(["git", "checkout", second_sha], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-f", branch, sha], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True, capture_output=True
    )

    report = SharePipeline(repo).check_preconditions()

    assert report.ok is False
    matches = [f for f in report.failures if "detached" in f.message.lower()]
    assert matches, report.failures
    for f in matches:
        assert f.remedy == (
            "This commit is not on any branch — run `git switch -c my-branch` to create one, "
            "then publish from there."
        )


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


# ── apply_precondition_fix dispatch ─────────────────────────────────────────


def test_apply_precondition_fix_raises_for_unknown_fix_id(project: Path) -> None:
    """An unregistered fix_id must raise PipelineStateError, not silently no-op.

    Task 2/3 register real handlers (e.g. "strip_os", "add_origin") into the
    module-level dispatch dict elsewhere; this dict starts empty here, so any
    fix_id is currently "unknown".
    """
    from haywire_studio.packaging.share.pipeline import PipelineStateError

    with pytest.raises(PipelineStateError):
        SharePipeline(project).apply_precondition_fix("nonexistent_fix_id")


def test_apply_precondition_fix_strip_os_repairs_the_named_library(project: Path) -> None:
    """apply_precondition_fix('strip_os', lib_dir=...) rewrites the right
    library's pyproject.toml so a re-run of check_preconditions passes.

    Committed after the mutation and again after the fix: the clean-tree
    probe runs before every other probe, so each edit must be committed
    before the next check_preconditions() call can reach the probe it
    means to exercise — matching what "Restart Wizard" actually re-checks."""
    lib = project / "barn" / "haybale-alpha"
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["macos", "other"]\n')
    _commit(project, "add invalid os")

    report = SharePipeline(project).check_preconditions()
    assert report.ok is False

    pipeline = SharePipeline(project)
    pipeline.apply_precondition_fix("strip_os", lib_dir="barn/haybale-alpha")
    _commit(project, "strip invalid os")

    text = pyproject.read_text()
    assert 'os = ["macos"]' in text

    report2 = pipeline.check_preconditions()
    assert report2.ok is True


def test_apply_precondition_fix_strip_os_dedups_reversed_near_miss_order(project: Path) -> None:
    """Regression: a near-miss listed BEFORE the already-declarable value it
    maps to (e.g. ["osx", "macos"]) must not produce a duplicate entry once
    strip_os has rewritten the manifest — check_preconditions must then pass,
    and the rewritten os list must contain no duplicates."""
    import toml

    lib = project / "barn" / "haybale-alpha"
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["osx", "macos"]\n')
    _commit(project, "add near-miss os")

    pipeline = SharePipeline(project)
    pipeline.apply_precondition_fix("strip_os", lib_dir="barn/haybale-alpha")
    _commit(project, "strip near-miss os")

    data = toml.loads(pyproject.read_text())
    os_values = data["tool"]["haywire"]["os"]
    assert os_values == ["macos"]
    assert len(os_values) == len(set(os_values))

    report = pipeline.check_preconditions()
    assert report.ok is True


def test_failure_lib_dir_round_trips_through_apply_precondition_fix(project: Path) -> None:
    """The wizard's whole point: it must be able to take `failure.lib_dir`
    straight from the report and pass it to apply_precondition_fix without
    any string-parsing of `message`. This test proves the round-trip using
    ONLY data taken from the PreconditionFailure itself — no hardcoded path."""
    lib = project / "barn" / "haybale-alpha"
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["macos", "other"]\n')
    _commit(project, "add invalid os")

    report = SharePipeline(project).check_preconditions()
    assert report.ok is False
    matches = [f for f in report.failures if f.fix_id == "strip_os"]
    assert matches, report.failures
    failure = matches[0]
    assert failure.lib_dir is not None

    pipeline = SharePipeline(project)
    pipeline.apply_precondition_fix("strip_os", lib_dir=failure.lib_dir)
    _commit(project, "strip invalid os")

    assert 'os = ["macos"]' in pyproject.read_text()
    assert pipeline.check_preconditions().ok is True


def test_apply_precondition_fix_strip_os_translates_manifest_failures(project: Path) -> None:
    """A pyproject that no longer parses at fix-time surfaces as ManifestError,
    the same translation convention apply_drift_union follows."""
    from haywire_studio.packaging.share.pipeline import ManifestError

    lib = project / "barn" / "haybale-alpha"
    (lib / "pyproject.toml").write_text("this is not [[[ valid toml")

    pipeline = SharePipeline(project)
    with pytest.raises(ManifestError):
        pipeline.apply_precondition_fix("strip_os", lib_dir="barn/haybale-alpha")


# ── apply_precondition_fix("add_origin") ────────────────────────────────────


def _get_remote_url(repo: Path) -> str:
    return subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_missing_origin_carries_add_origin_fix_id(tmp_path: Path) -> None:
    """check_preconditions() wires fix_id/fix_label onto the missing-origin failure."""
    repo = tmp_path / "noremote_fixid"
    _init_repo(repo)
    _add_lib(repo)
    _commit(repo)

    report = SharePipeline(repo).check_preconditions()

    assert report.ok is False
    matches = [f for f in report.failures if "No 'origin' remote" in f.message]
    assert matches, report.failures
    for f in matches:
        assert f.fix_id == "add_origin"
        assert f.fix_label


def test_apply_precondition_fix_add_origin_writes_url_verbatim(tmp_path: Path) -> None:
    """The remote is stored exactly as typed — an SSH-style URL is not rewritten
    to HTTPS. `_ssh_to_https` handles that at derivation time; rewriting what
    the user typed would make `git remote -v` disagree with their input."""
    repo = tmp_path / "add_origin_verbatim"
    _init_repo(repo)
    _add_lib(repo)

    url = "git@example.com:foo/bar.git"
    SharePipeline(repo).apply_precondition_fix("add_origin", url=url)

    assert _get_remote_url(repo) == url


def test_apply_precondition_fix_add_origin_ssh_url_not_rewritten(tmp_path: Path) -> None:
    """Same guarantee, phrased explicitly against SSH→HTTPS rewriting."""
    repo = tmp_path / "add_origin_ssh"
    _init_repo(repo)
    _add_lib(repo)

    ssh_url = "git@gitlab.com:someuser/somerepo.git"
    SharePipeline(repo).apply_precondition_fix("add_origin", url=ssh_url)

    stored = _get_remote_url(repo)
    assert stored == ssh_url
    assert not stored.startswith("https://")


def test_apply_precondition_fix_add_origin_raises_when_origin_already_exists(
    tmp_path: Path, bare_remote: Path
) -> None:
    """A pre-existing origin (a race, or a stale report) must fail cleanly with
    a typed exception, not a raw GitResult/subprocess failure leaking through."""
    from haywire_studio.packaging.share.pipeline import PreconditionsError

    repo = tmp_path / "add_origin_exists"
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True, capture_output=True
    )

    with pytest.raises(PreconditionsError):
        SharePipeline(repo).apply_precondition_fix("add_origin", url="git@example.com:foo/bar.git")

    # The pre-existing remote must be untouched by the failed attempt.
    assert _get_remote_url(repo) == str(bare_remote)


def test_apply_precondition_fix_add_origin_accepts_unknown_host(tmp_path: Path) -> None:
    """resolve_host() governs share-URL derivation, not pushability — an
    unrecognized host (not github.com/gitlab.com, no self-hosted config entry)
    must still be accepted for `git remote add`."""
    from haywire.core.marketstall.host_providers import resolve_host

    unknown_host = "git.example-selfhosted.internal"
    assert resolve_host(unknown_host) is None

    repo = tmp_path / "add_origin_unknown_host"
    _init_repo(repo)
    _add_lib(repo)

    url = f"git@{unknown_host}:foo/bar.git"
    SharePipeline(repo).apply_precondition_fix("add_origin", url=url)

    assert _get_remote_url(repo) == url


def test_add_origin_round_trip_clears_the_missing_origin_failure(tmp_path: Path, bare_remote: Path) -> None:
    """End-to-end: missing-origin repo -> check_preconditions() finds the
    add_origin failure -> apply the fix -> re-run check_preconditions() and
    confirm that SPECIFIC failure is gone.

    The origin URL is the local ``bare_remote`` path, not a fake host. Once a
    remote exists, check_preconditions() runs a real ``git ls-remote`` against
    it; an unroutable URL like ``git@example.com:...`` does not fail fast, it
    blocks until the 60s timeout. That put a minute of network wait into the
    fast suite for a test whose subject is the missing-remote failure clearing.
    """
    repo = tmp_path / "add_origin_e2e"
    _init_repo(repo)
    _add_lib(repo)
    _commit(repo)

    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    matches = [f for f in report.failures if f.fix_id == "add_origin"]
    assert matches, report.failures

    pipeline = SharePipeline(repo)
    pipeline.apply_precondition_fix("add_origin", url=str(bare_remote))

    report2 = pipeline.check_preconditions()
    assert not any("No 'origin' remote is configured" in f.message for f in report2.failures)
