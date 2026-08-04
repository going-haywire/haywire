"""The share wizard's state machine. UI rendering is smoke-tested only."""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline
from haywire_studio.packaging.share.pipeline.steps import drift as steps_drift
from haywire_studio.packaging.share.pipeline.steps import push as steps_push
from haywire_studio.packaging.share.pipeline.steps import version as steps_version

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"


@pytest.fixture
def project(tmp_path: Path) -> Path:
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

    lib = repo / "barn" / "haybale-alpha"
    (lib / "haybale_alpha").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.3.1"\n')
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=repo, check=True, capture_output=True)
    return repo


def _wizard(project: Path):
    """A ShareWizard with no popup — the state machine under test."""
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.packaging.share.pipeline import SharePipeline

    return ShareWizard(pipeline=SharePipeline(project), popup=None)


def _no_drift(lib_dir: Path):
    from haywire_studio.packaging.share import DepDrift

    return DepDrift(lib_dir=lib_dir)


def _drifty(lib_dir: Path):
    from haywire_studio.packaging.share import DepDrift

    return DepDrift(lib_dir=lib_dir, pyproject_missing=["numpy"])


def _fake_docs():
    from haywire_studio.packaging.share.pipeline.results import DocsResult

    return patch.object(
        SharePipeline,
        "apply_docs",
        new=AsyncMock(return_value=DocsResult(coverage={"alpha": []}, written=[])),
    )


# ── step 1 → 2 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_wizard_starts_at_preconditions(project: Path) -> None:
    wizard = _wizard(project)
    assert wizard.step == "preconditions"
    assert wizard.error is None


@pytest.mark.anyio
async def test_healthy_project_reports_a_pass_before_scanning(project: Path) -> None:
    """Step 1 reports only on project health. The drift scan is step 2, so its
    multi-second cost isn't charged to a step labelled "Check the project"."""
    wizard = _wizard(project)
    await wizard.advance_from_preconditions()

    assert wizard.step == "checked"
    assert wizard.error is None
    assert wizard.preconditions_report is not None
    assert wizard.preconditions_report.ok
    # The scan has NOT run yet — that is the whole point of the split.
    assert wizard.drift_report is None


@pytest.mark.anyio
async def test_scan_advances_to_drift(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
    assert wizard.step == "drift"
    assert wizard.error is None
    assert wizard.drift_report is not None


@pytest.mark.anyio
async def test_failed_preconditions_stay_put_with_an_error(tmp_path: Path) -> None:
    """The menu item is always enabled; this step explains why a workspace
    can't be shared. A disabled item can't carry a tooltip — the design guide's
    disabled state includes pointer-events: none (design-guide.md:725)."""
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.packaging.share.pipeline import SharePipeline

    repo = tmp_path / "broken"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    wizard = ShareWizard(pipeline=SharePipeline(repo), popup=None)
    await wizard.advance_from_preconditions()

    assert wizard.step == "preconditions"
    assert wizard.error is not None
    assert "barn" in wizard.error
    assert wizard.precondition_failures
    from haywire_studio.packaging.share.pipeline import PreconditionFailure

    assert all(isinstance(f, PreconditionFailure) for f in wizard.precondition_failures)


@pytest.mark.anyio
async def test_clean_drift_skips_straight_to_version(project: Path) -> None:
    """Nothing to decide means nothing to ask."""
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
    assert wizard.drift_report is not None
    assert wizard.drift_report.needs_decision is False


# ── step 2 → 3 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_drift_union_advances(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_drifty):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        with patch.object(steps_drift, "apply_drift_fix"):
            await wizard.advance_from_drift("union")
    assert wizard.step == "framework"


@pytest.mark.anyio
async def test_drift_skip_records_the_acknowledgement(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_drifty):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
    assert wizard.step == "framework"
    assert wizard.pipeline.drift_acknowledged is True


@pytest.mark.anyio
async def test_version_plan_is_loaded_for_the_next_panel(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    assert wizard.version_plan is not None
    assert wizard.version_plan.common_version == "0.3.1"


# ── step 3 → 4 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_version_bump_advances_to_docs(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")
    assert wizard.step == "docs"
    assert wizard.pipeline.version == "0.3.2"


class _FakeIdentity:
    def __init__(self, needs_restart: bool) -> None:
        self.needs_restart = needs_restart


class _FakeRegistry:
    """Just enough of LibraryRegistry's surface for _hot_swap_bumped_libraries."""

    def __init__(self, dist_to_lib_id: dict[str, str], needs_restart: dict[str, bool]) -> None:
        self._dist_to_lib_id = dist_to_lib_id
        self._needs_restart = needs_restart
        self.removed: list[str] = []
        self.scanned = False
        self.enabled_all = False

    def find_library_by_distribution_name(self, dist_name: str) -> str | None:
        return self._dist_to_lib_id.get(dist_name)

    def get_library_identity(self, lib_id: str) -> _FakeIdentity:
        return _FakeIdentity(self._needs_restart.get(lib_id, False))

    def remove_library(self, lib_id: str) -> bool:
        self.removed.append(lib_id)
        return True

    def scan_for_libraries(self) -> None:
        self.scanned = True

    def enable_all_libraries(self) -> None:
        self.enabled_all = True


class _FakeManager:
    def __init__(self, registry: _FakeRegistry) -> None:
        self.registry = registry


@pytest.mark.anyio
async def test_version_bump_hot_swaps_live_library_when_manager_present(project: Path) -> None:
    """Option B: a bumped barn library still loaded in the running process is
    evicted (registry.remove_library) and rescanned in place, mirroring
    update_library_identity()'s metadata-edit path — so a restart is not
    needed for the common case of a plain version bump."""
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.packaging.share.pipeline import SharePipeline

    registry = _FakeRegistry(
        dist_to_lib_id={"haybale-alpha": "alpha"},
        needs_restart={"alpha": False},
    )
    wizard = ShareWizard(
        pipeline=SharePipeline(project),
        popup=None,
        manager=_FakeManager(registry),  # type: ignore[arg-type]
    )
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")

    assert registry.removed == ["alpha"]
    assert registry.scanned
    assert registry.enabled_all
    assert wizard.hot_swapped_libraries == ["alpha"]
    assert wizard.hot_swap_needs_restart is False


@pytest.mark.anyio
async def test_version_bump_hot_swap_ors_needs_restart_across_libraries(project: Path) -> None:
    registry = _FakeRegistry(
        dist_to_lib_id={"haybale-alpha": "alpha"},
        needs_restart={"alpha": True},
    )
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.packaging.share.pipeline import SharePipeline

    wizard = ShareWizard(
        pipeline=SharePipeline(project),
        popup=None,
        manager=_FakeManager(registry),  # type: ignore[arg-type]
    )
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")

    assert wizard.hot_swap_needs_restart is True


@pytest.mark.anyio
async def test_version_bump_without_manager_skips_hot_swap(project: Path) -> None:
    """No manager (e.g. the CLI, or a studio without a live registry) — the
    bump stays file-only, exactly as before Option B."""
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")

    assert wizard.hot_swapped_libraries == []
    assert wizard.hot_swap_needs_restart is False


@pytest.mark.anyio
async def test_version_bump_skips_library_not_found_live(project: Path) -> None:
    """A dist name the live registry has never heard of (not yet enabled, or
    this manager tracks a different set) is skipped, not an error — the bump
    itself already succeeded on disk and is not rolled back."""
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.packaging.share.pipeline import SharePipeline

    registry = _FakeRegistry(dist_to_lib_id={}, needs_restart={})
    wizard = ShareWizard(
        pipeline=SharePipeline(project),
        popup=None,
        manager=_FakeManager(registry),  # type: ignore[arg-type]
    )
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")

    assert registry.removed == []
    assert not registry.scanned
    assert wizard.hot_swapped_libraries == []
    assert wizard.step == "docs"


@pytest.mark.anyio
async def test_tag_collision_keeps_the_user_on_the_version_step(project: Path) -> None:
    """Where the fix is cheapest — 'pick 0.3.2 instead' costs nothing here."""
    subprocess.run(["git", "tag", "v0.3.2"], cwd=project, check=True, capture_output=True)
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")

    assert wizard.step == "version"
    assert wizard.error is not None
    assert "v0.3.2" in wizard.error


@pytest.mark.anyio
async def test_lock_warning_surfaces_without_blocking(project: Path) -> None:
    (project / "uv.lock").write_text("")
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    with patch.object(steps_version, "refresh_lockfile", return_value=(False, "uv lock failed: boom")):
        await wizard.advance_from_version("patch")

    assert wizard.step == "docs"
    assert wizard.warnings
    assert any("boom" in w for w in wizard.warnings)


# ── step 4 → 5 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_docs_step_advances_and_keeps_coverage(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()

    assert wizard.step == "commit"
    assert wizard.docs_result is not None
    assert wizard.commit_plan is not None


@pytest.mark.anyio
async def test_docs_failure_stays_on_the_docs_step(project: Path) -> None:
    from haywire_studio.packaging.share.pipeline import DocsGenerationError

    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")

    with patch.object(
        SharePipeline,
        "apply_docs",
        new=AsyncMock(side_effect=DocsGenerationError("boom", output="traceback")),
    ):
        await wizard.advance_from_docs()

    assert wizard.step == "docs"
    assert wizard.error is not None


@pytest.mark.anyio
async def test_docs_output_is_captured_for_the_log(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")

    async def _streamy(self, on_output=None):
        from haywire_studio.packaging.share.pipeline.results import DocsResult

        if on_output:
            on_output("loading libraries…")
        return DocsResult(coverage={}, written=[])

    with patch.object(SharePipeline, "apply_docs", new=_streamy):
        await wizard.advance_from_docs()

    assert "loading libraries…" in wizard.log_lines


# ── step 5 → 6 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_commit_advances_to_push(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()
    await wizard.advance_from_commit("chore: share v0.3.2", [])

    assert wizard.step == "push"
    assert wizard.commit_result is not None
    assert wizard.commit_result.tag == "v0.3.2"


@pytest.mark.anyio
async def test_commit_step_verifies_push_before_committing(project: Path) -> None:
    """Closes the race window since step 1 — and leaves nothing to undo."""
    from haywire_studio.packaging.share import git as gitcmd

    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()

    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
    ).stdout

    def _rejected(args, **_kw):
        if "--dry-run" in args:
            return gitcmd.GitResult(ok=False, stdout="", stderr="! [rejected]", returncode=1)
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch.object(steps_push, "git_remote", side_effect=_rejected):
        await wizard.advance_from_commit("chore: share v0.3.2", [])

    assert wizard.step == "commit"
    assert wizard.error is not None
    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
        ).stdout
        == head_before
    )


@pytest.mark.anyio
async def test_opted_in_barn_files_reach_the_commit(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")
    asset = project / "barn" / "haybale-alpha" / "haybale_alpha" / "icon.png"
    asset.write_bytes(b"\x89PNG")
    with _fake_docs():
        await wizard.advance_from_docs()

    await wizard.advance_from_commit("chore: share v0.3.2", [asset])

    committed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert "barn/haybale-alpha/haybale_alpha/icon.png" in committed


# ── step 6 → done ────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_push_completes_the_wizard(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()
    await wizard.advance_from_commit("chore: share v0.3.2", [])
    await wizard.advance_from_push()

    assert wizard.step == "done"
    assert wizard.push_result is not None


@pytest.mark.anyio
async def test_push_failure_is_retryable_in_place(project: Path) -> None:
    from haywire_studio.packaging.share.pipeline import PushError

    wizard = _wizard(project)
    with patch.object(steps_drift, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_drift("skip")
        await wizard.advance_from_framework(">=0.0.1")
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()
    await wizard.advance_from_commit("chore: share v0.3.2", [])

    with patch.object(
        SharePipeline,
        "apply_push",
        new=AsyncMock(side_effect=PushError(stderr="timeout", manual_command="git p ush ...")),
    ):
        await wizard.advance_from_push()

    assert wizard.step == "push"
    assert wizard.error is not None
    assert wizard.manual_command is not None

    # Retrying the same step works — the failed step is retryable in place.
    wizard.retry()
    assert wizard.error is None
    await wizard.advance_from_push()
    assert wizard.step == "done"


@pytest.mark.anyio
async def test_retry_clears_only_the_error(project: Path) -> None:
    wizard = _wizard(project)
    wizard.error = "boom"
    wizard.warnings = ["keep me"]
    wizard.retry()
    assert wizard.error is None
    assert wizard.warnings == ["keep me"]


# ── precondition fixes (side step) ──────────────────────────────────────────


@pytest.fixture
def os_project(project: Path) -> Path:
    """`project`, but with an invalid `[tool.haywire].os` declaration."""
    pyproject = project / "barn" / "haybale-alpha" / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["macos", "other"]\n')
    return project


@pytest.fixture
def noremote_project(tmp_path: Path) -> Path:
    """A shareable project with NO origin configured at all."""
    repo = tmp_path / "noremote"
    repo.mkdir()
    for args in (
        ["init"],
        ["config", "user.email", "t@t.test"],
        ["config", "user.name", "T"],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    lib = repo / "barn" / "haybale-alpha"
    (lib / "haybale_alpha").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.3.1"\n')
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.mark.anyio
async def test_strip_os_fix_reaches_checked_with_no_error(os_project: Path) -> None:
    """The wizard's whole point: take fix_id/lib_dir straight off the failure
    object (no string-parsing) and land on the same step a clean Check would."""
    wizard = _wizard(os_project)
    await wizard.advance_from_preconditions()

    assert wizard.step == "preconditions"
    assert wizard.precondition_failures
    matches = [f for f in wizard.precondition_failures if f.fix_id == "strip_os"]
    assert matches, wizard.precondition_failures
    failure = matches[0]
    assert failure.lib_dir is not None

    await wizard.advance_from_preconditions_fix(failure.fix_id, lib_dir=failure.lib_dir)

    assert wizard.step == "checked"
    assert wizard.error is None
    assert wizard.precondition_failures is None


@pytest.mark.anyio
async def test_add_origin_fix_against_reachable_remote_reaches_checked(noremote_project: Path) -> None:
    """A good URL (pointed at a real bare repo) clears the missing-origin
    failure AND passes reachability, landing on 'checked'."""
    wizard = _wizard(noremote_project)
    await wizard.advance_from_preconditions()

    assert wizard.step == "preconditions"
    matches = [f for f in (wizard.precondition_failures or []) if f.fix_id == "add_origin"]
    assert matches, wizard.precondition_failures

    other_remote = noremote_project.parent / "other_remote.git"
    other_remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=other_remote, check=True, capture_output=True)
    subprocess.run(
        ["git", "push", str(other_remote), "HEAD:refs/heads/main"],
        cwd=noremote_project,
        check=True,
        capture_output=True,
    )

    await wizard.advance_from_preconditions_fix("add_origin", url=str(other_remote))

    assert wizard.step == "checked"
    assert wizard.error is None


@pytest.mark.anyio
async def test_add_origin_fix_with_bad_url_swaps_in_the_reachability_failure(
    noremote_project: Path,
) -> None:
    """A bad URL: the reachability failure replaces the missing-remote one,
    with its own remedy. The wizard stays on 'preconditions', not 'checked'."""
    wizard = _wizard(noremote_project)
    await wizard.advance_from_preconditions()
    assert any(f.fix_id == "add_origin" for f in wizard.precondition_failures or [])

    await wizard.advance_from_preconditions_fix(
        "add_origin", url="https://example.invalid/nowhere/nothing.git"
    )

    assert wizard.step == "preconditions"
    assert wizard.error is not None
    failures = wizard.precondition_failures or []
    assert not any("No 'origin' remote is configured" in f.message for f in failures)
    assert any("Cannot reach origin" in f.message for f in failures)
    reach_failure = next(f for f in failures if "Cannot reach origin" in f.message)
    assert reach_failure.remedy


@pytest.mark.anyio
async def test_fix_success_never_advances_past_checked(os_project: Path) -> None:
    """The user still has to click Scan — a fix+recheck stops exactly where a
    normal successful Check would, never at 'drift' or beyond."""
    wizard = _wizard(os_project)
    await wizard.advance_from_preconditions()
    failure = next(f for f in wizard.precondition_failures if f.fix_id == "strip_os")

    await wizard.advance_from_preconditions_fix(failure.fix_id, lib_dir=failure.lib_dir)

    assert wizard.step == "checked"
    assert wizard.drift_report is None


@pytest.mark.anyio
async def test_failing_fix_is_caught_and_rendered_without_crashing(project: Path) -> None:
    """add_origin against a project that already has an origin raises
    PreconditionsError from a completely different call path than step 1's
    batch check — it must still land in the existing _fail()/error rendering
    without crashing, and the wizard must stay on 'preconditions'."""
    wizard = _wizard(project)
    await wizard.advance_from_preconditions()
    assert wizard.step == "checked"  # `project` fixture already has an origin

    # Force the wizard back to the preconditions step to exercise the fix
    # path the way the UI would (the button only ever appears there).
    wizard.step = "preconditions"

    await wizard.advance_from_preconditions_fix("add_origin", url="git@example.com:foo/bar.git")

    assert wizard.step == "preconditions"
    assert wizard.error is not None
    assert "already exists" in wizard.error
    # This is a single synthesized failure, not a step-1 batch report — the
    # existing _fail() still renders it as one failure row without crashing.
    assert wizard.precondition_failures is not None
    assert len(wizard.precondition_failures) == 1
    assert wizard.precondition_failures[0].fix_id is None


def test_every_drift_choice_is_explained() -> None:
    """The three words can't carry the semantics on their own: the choice that
    sounds safest (Replace) deletes, and the neutral-sounding one (Skip) ships
    libraries whose deps are undeclared. Each option must state its effect."""
    from haybale_marketplace.editors._share_wizard import _DRIFT_EXPLANATIONS, _DRIFT_OPTIONS

    assert set(_DRIFT_OPTIONS) == {"union", "replace", "skip"}
    assert set(_DRIFT_EXPLANATIONS) == set(_DRIFT_OPTIONS)

    # Replace is the destructive one and must say so.
    assert "REMOVED" in _DRIFT_EXPLANATIONS["replace"][0]
    assert _DRIFT_EXPLANATIONS["replace"][1] == "--hw-danger"
    # Union is additive and must promise that nothing is lost.
    assert "Nothing is removed" in _DRIFT_EXPLANATIONS["union"][0]
    assert _DRIFT_EXPLANATIONS["union"][1] == "--hw-positive"
    # Skip must name the consequence for consumers, not just "does nothing".
    assert "unresolved" in _DRIFT_EXPLANATIONS["skip"][0]


def test_every_wizard_select_is_marked_in_popup() -> None:
    """The wizard renders inside a Popup, so every select it builds must carry
    in_popup=True. A QMenu defaults to z-6000 and the Popup card is z-7001, so
    an unlifted dropdown opens BEHIND the popup and looks empty.
    See .insights/feedback_nicegui_nested_menu_flyouts.md (#2)."""
    import re
    from pathlib import Path as _Path

    wizard_dir = _Path("barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard")
    source = "\n".join(path.read_text() for path in sorted(wizard_dir.glob("*.py")))
    selects = len(re.findall(r"\bui\.select\(|\bselect_field\(", source))
    marked = source.count("in_popup=True")
    assert selects, "expected at least one select in the wizard"
    assert marked == selects, (
        f"{selects} select(s) but {marked} marked in_popup — one opens behind the popup"
    )


def test_render_functions_import_and_reference_only_tokens() -> None:
    """No hardcoded colours — the design guide forbids them, and a literal hex
    breaks every theme but the one it was picked in."""
    import re
    from pathlib import Path as _Path

    wizard_dir = _Path("barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard")
    for path in sorted(wizard_dir.glob("*.py")):
        source = path.read_text()
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source), f"hardcoded colour found in {path.name}"
        assert "box-shadow" not in source, f"no box-shadow on chrome (design guide) in {path.name}"
        assert "ui.card()" not in source, f"use Popup / hui.dialog_card(), not a bare card, in {path.name}"
