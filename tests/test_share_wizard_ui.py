"""The share wizard's state machine. UI rendering is smoke-tested only."""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline
from haywire_studio.packaging.share.pipeline.steps import detect as steps_detect
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
async def test_scan_advances_to_detect(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
    assert wizard.step == "detect"
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
    assert wizard.precondition_failure is not None
    from haywire_studio.packaging.share.pipeline import PreconditionFailure

    assert isinstance(wizard.precondition_failure, PreconditionFailure)


@pytest.mark.anyio
async def test_precondition_failure_does_not_auto_queue_a_modal(tmp_path: Path) -> None:
    """A step-1 failure sets `precondition_failure` (what the error banner's
    "Solve" button reads) but never populates `pending_modal` — that modal
    opens ONLY when Solve is clicked (`_open_precondition_modal`), never
    automatically. `pending_modal` is reserved for the mid-pipeline rollback
    case, which IS automatic (see
    `test_mid_pipeline_failure_reverts_the_working_tree_and_queues_a_rollback_modal`).
    """
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.packaging.share.pipeline import SharePipeline

    repo = tmp_path / "broken"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    wizard = ShareWizard(pipeline=SharePipeline(repo), popup=None)
    await wizard.advance_from_preconditions()

    assert wizard.step == "preconditions"
    assert wizard.precondition_failure is not None
    assert wizard.precondition_failure.kind == "inform"
    assert wizard.pending_modal is None


@pytest.mark.anyio
async def test_error_detail_offers_solve_instead_of_retry_when_a_failure_is_present(
    tmp_path: Path,
) -> None:
    """The preconditions step's error banner never falls back to the generic
    Retry button — every failure (inform or act) is resolved through its
    remedy modal, so _precondition_error_detail always returns a ('Solve',
    ...) override once a failure exists, and nothing (False) before one does.
    """
    from haybale_marketplace.editors._share_wizard.panels import _precondition_error_detail

    repo = tmp_path / "broken3"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    wizard = _wizard(repo)
    assert wizard.precondition_failure is None
    assert _precondition_error_detail(wizard, lambda: None) is False

    await wizard.advance_from_preconditions()
    assert wizard.precondition_failure is not None

    result = _precondition_error_detail(wizard, lambda: None)
    assert isinstance(result, tuple)
    label, _on_click = result
    assert label == "Solve"


@pytest.mark.anyio
async def test_solve_button_stays_available_across_repeated_renders(tmp_path: Path) -> None:
    """The Solve override survives multiple renders of the same failure
    (a redraw calling _precondition_error_detail again) — its state
    (`precondition_failure`) is a plain field, not a one-shot queue, so
    nothing about calling it once consumes or disables it for the next
    render. This is also what stops the modal itself from stacking: the
    modal is opened only from the button's own on_click, never as a side
    effect of this function being called during render."""
    from haybale_marketplace.editors._share_wizard.panels import _precondition_error_detail

    repo = tmp_path / "broken4"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    wizard = _wizard(repo)
    await wizard.advance_from_preconditions()
    assert wizard.precondition_failure is not None

    first = _precondition_error_detail(wizard, lambda: None)
    second = _precondition_error_detail(wizard, lambda: None)
    assert isinstance(first, tuple)
    assert isinstance(second, tuple)
    assert first[0] == second[0] == "Solve"


@pytest.mark.anyio
async def test_clean_drift_skips_straight_to_version(project: Path) -> None:
    """Nothing to decide means nothing to ask."""
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
    assert wizard.drift_report is not None
    assert wizard.drift_report.needs_decision is False


# ── step 2 → 3 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_detect_writes_nothing_and_advances(project: Path) -> None:
    """The report is read-only; the first write is the framework floor."""
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_drifty):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
    assert wizard.step == "framework"
    assert wizard.pipeline.written == []


@pytest.mark.anyio
async def test_declining_to_declare_records_the_acknowledgement(project: Path) -> None:
    """Publishing a knowingly-undeclared import is the one state worth flagging."""
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_drifty):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({}, skipped=True)
    assert wizard.step == "floors"
    assert wizard.pipeline.undeclared_acknowledged is True


@pytest.mark.anyio
async def test_keeping_everything_writes_only_the_framework_floor(project: Path) -> None:
    """Every dependency screen's default answer is inert."""
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_drifty):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
    assert wizard.step == "confirm"
    assert [p.name for p in wizard.pipeline.written] == ["pyproject.toml"]


@pytest.mark.anyio
async def test_version_plan_is_loaded_for_the_next_panel(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
    assert wizard.version_plan is not None
    assert wizard.version_plan.common_version == "0.3.1"


# ── step 3 → 4 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_version_bump_advances_to_docs(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
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
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
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
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
    await wizard.advance_from_version("patch")

    assert wizard.hot_swap_needs_restart is True


@pytest.mark.anyio
async def test_version_bump_without_manager_skips_hot_swap(project: Path) -> None:
    """No manager (e.g. the CLI, or a studio without a live registry) — the
    bump stays file-only, exactly as before Option B."""
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
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
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
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
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
    await wizard.advance_from_version("patch")

    assert wizard.step == "version"
    assert wizard.error is not None
    assert "v0.3.2" in wizard.error


@pytest.mark.anyio
async def test_lock_warning_surfaces_without_blocking(project: Path) -> None:
    (project / "uv.lock").write_text("")
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
    with patch.object(steps_version, "refresh_lockfile", return_value=(False, "uv lock failed: boom")):
        await wizard.advance_from_version("patch")

    assert wizard.step == "docs"
    assert wizard.warnings
    assert any("boom" in w for w in wizard.warnings)


# ── step 4 → 5 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_docs_step_advances_and_keeps_coverage(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
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
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
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
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
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
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()
    await wizard.advance_from_commit("chore: share v0.3.2")

    assert wizard.step == "push"
    assert wizard.commit_result is not None
    assert wizard.commit_result.tag == "v0.3.2"


@pytest.mark.anyio
async def test_commit_step_verifies_push_before_committing(project: Path) -> None:
    """Closes the race window since step 1 — and leaves nothing to undo."""
    from haywire_studio.packaging.share import git as gitcmd

    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
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
        await wizard.advance_from_commit("chore: share v0.3.2")

    assert wizard.step == "commit"
    assert wizard.error is not None
    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
        ).stdout
        == head_before
    )


# ── step 6 → done ────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_push_completes_the_wizard(project: Path) -> None:
    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()
    await wizard.advance_from_commit("chore: share v0.3.2")
    await wizard.advance_from_push()

    assert wizard.step == "done"
    assert wizard.push_result is not None


@pytest.mark.anyio
async def test_push_failure_is_retryable_in_place(project: Path) -> None:
    from haywire_studio.packaging.share.pipeline import PushError

    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()
        await wizard.advance_from_detect()
        await wizard.advance_from_framework(">=0.0.1")
        await wizard.advance_from_unused({})
        await wizard.advance_from_undeclared({})
        await wizard.advance_from_floors({})
        await wizard.advance_from_confirm()
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()
    await wizard.advance_from_commit("chore: share v0.3.2")

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
    """`project`, but with an invalid `[tool.haywire].os` declaration.

    Committed after the mutation: the clean-tree precondition runs before the
    manifest probe, so an uncommitted edit here would mask the very failure
    these tests are about.
    """
    pyproject = project / "barn" / "haybale-alpha" / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["macos", "other"]\n')
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "invalid os"], cwd=project, check=True, capture_output=True)
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
async def test_strip_os_fix_then_recheck_reaches_checked(os_project: Path) -> None:
    """The act-modal's contract, minus the dialog: take fix_id/lib_dir straight
    off the failure (no string-parsing), apply it, then Restart Wizard —
    which is retry() + advance_from_preconditions() — lands on 'checked'."""
    wizard = _wizard(os_project)
    await wizard.advance_from_preconditions()

    failure = wizard.precondition_failure
    assert failure is not None
    assert failure.fix_id == "strip_os"
    assert failure.kind == "act"
    assert failure.lib_dir is not None

    wizard.pipeline.apply_precondition_fix("strip_os", lib_dir=failure.lib_dir)
    subprocess.run(["git", "add", "-A"], cwd=os_project, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "strip invalid os"], cwd=os_project, check=True, capture_output=True
    )

    wizard.retry()
    await wizard.advance_from_preconditions()

    assert wizard.step == "checked"
    assert wizard.error is None
    assert wizard.precondition_failure is None


@pytest.mark.anyio
async def test_add_origin_fix_then_recheck_against_reachable_remote_reaches_checked(
    noremote_project: Path,
) -> None:
    """Same shape with add_origin: a good URL (a real bare repo) clears the
    missing-origin failure AND passes reachability, landing on 'checked'."""
    wizard = _wizard(noremote_project)
    await wizard.advance_from_preconditions()

    failure = wizard.precondition_failure
    assert failure is not None
    assert failure.fix_id == "add_origin"

    other_remote = noremote_project.parent / "other_remote.git"
    other_remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=other_remote, check=True, capture_output=True)
    subprocess.run(
        ["git", "push", str(other_remote), "HEAD:refs/heads/main"],
        cwd=noremote_project,
        check=True,
        capture_output=True,
    )

    wizard.pipeline.apply_precondition_fix("add_origin", url=str(other_remote))

    wizard.retry()
    await wizard.advance_from_preconditions()

    assert wizard.step == "checked"
    assert wizard.error is None


@pytest.mark.anyio
async def test_add_origin_fix_with_bad_url_swaps_in_the_reachability_failure(
    noremote_project: Path,
) -> None:
    """A bad-but-recognized-host URL: after the fix + re-check, the failure is
    now the reachability one (kind == 'inform'), not the missing-origin one.

    The host must be one `resolve_host()` recognizes (github.com here) —
    otherwise the new host-recognition probe (Task 4) would catch it first
    and this would exercise a different failure than the one under test.
    """
    wizard = _wizard(noremote_project)
    await wizard.advance_from_preconditions()
    assert wizard.precondition_failure is not None
    assert wizard.precondition_failure.fix_id == "add_origin"

    wizard.pipeline.apply_precondition_fix(
        "add_origin", url="https://github.com/haywire-nonexistent-org/nowhere.git"
    )

    wizard.retry()
    await wizard.advance_from_preconditions()

    assert wizard.step == "preconditions"
    assert wizard.error is not None
    failure = wizard.precondition_failure
    assert failure is not None
    assert failure.kind == "inform"
    assert "No 'origin' remote is configured" not in failure.message
    assert "Cannot reach origin" in failure.message
    assert failure.remedy


@pytest.mark.anyio
async def test_fix_success_never_advances_past_checked(os_project: Path) -> None:
    """The user still has to click Scan — a fix+recheck stops exactly where a
    normal successful Check would, never at 'drift' or beyond."""
    wizard = _wizard(os_project)
    await wizard.advance_from_preconditions()
    failure = wizard.precondition_failure
    assert failure is not None
    assert failure.fix_id == "strip_os"

    wizard.pipeline.apply_precondition_fix("strip_os", lib_dir=failure.lib_dir)
    subprocess.run(["git", "add", "-A"], cwd=os_project, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "strip invalid os"], cwd=os_project, check=True, capture_output=True
    )

    wizard.retry()
    await wizard.advance_from_preconditions()

    assert wizard.step == "checked"
    assert wizard.drift_report is None


@pytest.mark.anyio
async def test_commit_dirty_tree_fix_then_recheck_reaches_checked(project: Path) -> None:
    """Same shape as strip_os/add_origin: an 'act' failure, a fix applied
    straight off the failure's fix_id, then Restart Wizard (retry() +
    advance_from_preconditions()) lands on 'checked'."""
    (project / "untracked.txt").write_text("scratch")

    wizard = _wizard(project)
    await wizard.advance_from_preconditions()

    failure = wizard.precondition_failure
    assert failure is not None
    assert failure.fix_id == "commit_dirty_tree"
    assert failure.kind == "act"

    wizard.pipeline.apply_precondition_fix("commit_dirty_tree", message="wip")

    wizard.retry()
    await wizard.advance_from_preconditions()

    assert wizard.step == "checked"
    assert wizard.error is None
    assert wizard.precondition_failure is None


def test_failing_fix_raises_preconditions_error(project: Path) -> None:
    """add_origin against a project that already has an origin raises
    PreconditionsError from a completely different call path than step 1's
    batch check. The act-modal (remedy_modal.py) catches this at the call
    site and shows it inline in the dialog — there is no wizard method to
    "render without crashing" any more, so this test asserts the raise
    directly rather than driving it through the (now-deleted)
    advance_from_preconditions_fix."""
    from haywire_studio.packaging.share.pipeline import PreconditionsError

    wizard = _wizard(project)

    with pytest.raises(PreconditionsError, match="already exists"):
        wizard.pipeline.apply_precondition_fix("add_origin", url="git@example.com:foo/bar.git")


def test_append_host_config_writes_a_hosts_entry(tmp_path: Path, monkeypatch) -> None:
    """The add_host_config fix writes a [[hosts]] entry the resolver then honors.

    Asserted through load_self_hosted_hosts() rather than by string-matching
    the file: what matters is that resolve_host() will now recognize the host,
    not the exact bytes written.
    """
    from haywire.core.marketstall.host_providers import config as host_config
    from haybale_marketplace.editors._share_wizard.remedy_modal import append_host_config

    cfg = tmp_path / ".haywire" / "config.toml"
    monkeypatch.setattr(host_config, "_user_config_path", lambda: cfg)

    append_host_config("git.example-corp.internal")

    assert host_config.load_self_hosted_hosts(cfg) == {"git.example-corp.internal": "gitlab"}


@pytest.mark.anyio
async def test_mid_pipeline_failure_reverts_the_working_tree_and_queues_a_rollback_modal(
    project: Path,
) -> None:
    """A failure past step 1 leaves no trace: the tree is reverted BEFORE the
    error is reported, so the modal describes an already-cleaned state. Unlike
    a step-1 failure, this one DOES queue `pending_modal` — the rollback
    modal reports something that already happened (nothing to "solve"), so
    it opens automatically rather than waiting on a click."""
    from haywire_studio.packaging.share.pipeline import DocsGenerationError

    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()

    # A write this run made, standing in for whatever a real step would leave.
    stray = project / "generated_by_a_failed_run.md"
    stray.write_text("partial output")

    with patch.object(
        SharePipeline, "apply_docs", new=AsyncMock(side_effect=DocsGenerationError("docs blew up"))
    ):
        await wizard.advance_from_docs()

    assert wizard.error is not None
    assert "docs blew up" in wizard.error
    assert not stray.exists()
    assert wizard.pending_modal is not None
    assert isinstance(wizard.pending_modal, str)


@pytest.mark.anyio
async def test_precondition_failure_does_not_trigger_a_rollback(tmp_path: Path) -> None:
    """Step 1 never mutates, so it must not pay for a revert — and a stray
    file there must survive, proving no blanket clean ran."""
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.packaging.share.pipeline import SharePipeline as _SharePipeline

    repo = tmp_path / "broken3"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    stray = repo / "untouched.txt"
    stray.write_text("mine")

    wizard = ShareWizard(pipeline=_SharePipeline(repo), popup=None)
    await wizard.advance_from_preconditions()

    assert wizard.error is not None
    assert stray.exists()


def test_every_pin_choice_is_explained() -> None:
    """The labels can't carry the semantics on their own.

    "Skip" sounds like the neutral option and is the only one that ships a
    library consumers cannot import, so each choice must state its effect.
    """
    from haybale_marketplace.editors._share_wizard.copy import PIN_EXPLANATIONS, PIN_OPTIONS

    assert set(PIN_OPTIONS) == {"none", "installed", "custom", "skip"}
    assert set(PIN_EXPLANATIONS) == set(PIN_OPTIONS)

    # Skip is the one that breaks consumers and must say so.
    assert "fail to import" in PIN_EXPLANATIONS["skip"][0]
    assert PIN_EXPLANATIONS["skip"][1] == "--hw-danger"
    # No-pin is the safe default and must promise it constrains nobody.
    assert "constrain" in PIN_EXPLANATIONS["none"][0].lower()
    assert PIN_EXPLANATIONS["none"][1] == "--hw-positive"
    # Floor-at-installed is legitimate but exclusionary; it must name that.
    assert "lock out" in PIN_EXPLANATIONS["installed"][0]


def test_floor_options_lead_with_keeping_the_declaration() -> None:
    """The inert answer must be first, and must exist.

    A floor states the OLDEST version that works. Nothing in the wizard can
    compute that, so "keep" has to be available and has to be the default.
    """
    from haybale_marketplace.editors._share_wizard.copy import FLOOR_OPTIONS

    assert next(iter(FLOOR_OPTIONS)) == "keep"
    assert set(FLOOR_OPTIONS) == {"keep", "sync", "custom"}


def test_detect_sections_cover_every_dep_drift_finding() -> None:
    """A finding with no copy renders as a blank section the author cannot act on."""
    import dataclasses

    from haybale_marketplace.editors._share_wizard.copy import DETECT_SECTIONS
    from haywire_studio.packaging.share import DepDrift

    reportable = {f.name for f in dataclasses.fields(DepDrift)} - {"lib_dir"}
    assert set(DETECT_SECTIONS) == reportable


def test_findings_copy_is_descriptive_not_imperative() -> None:
    """The Findings screen reports; its only button is Continue, which resolves
    nothing. An instruction here ("Add these to the list") reads as a promise
    that Continue will carry it out, and the author walks past a decision they
    were never actually offered."""
    from haybale_marketplace.editors._share_wizard.copy import DETECT_SECTIONS

    # Sentence-initial imperatives — a blurb opening with one is giving orders.
    banned = ("add ", "remove ", "declare ", "fix ", "update ", "run ", "set ")
    for field, (_title, blurb, _token) in DETECT_SECTIONS.items():
        opening = blurb.lower()
        assert not opening.startswith(banned), (
            f"{field}'s blurb opens with an instruction: {blurb!r}. "
            "Findings describes what IS; the later screens do the acting."
        )


def test_findings_step_is_named_for_what_it_shows() -> None:
    """Every other step title is a noun phrase. A verb implies the screen acts."""
    from haybale_marketplace.editors._share_wizard.copy import STEP_TITLES

    assert STEP_TITLES["detect"] == "Findings"


def test_writing_screens_say_apply_not_continue() -> None:
    """The button label is the honest signal for whether a screen writes.

    "Continue" on a screen that rewrites pyproject.toml understates it; the
    author reads it as paging forward. Each screen that can write says Apply,
    the confirm screen says Confirm, and the read-only ones keep Continue —
    including a writing screen's EMPTY state, where there is nothing to apply.
    """
    from pathlib import Path as _Path

    source = _Path(
        "barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/panels.py"
    ).read_text()

    # One Apply per writing screen: framework, unused, undeclared, floors.
    assert source.count('"Apply"') == 4
    assert source.count('"Confirm"') == 1


def test_framework_panel_does_not_repeat_its_own_step_title() -> None:
    """The stepper already titles the screen; a section label saying the same
    thing costs a line and adds nothing."""
    from pathlib import Path as _Path

    from haybale_marketplace.editors._share_wizard.copy import STEP_TITLES

    source = _Path(
        "barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/panels.py"
    ).read_text()

    assert f'hui.section_label("{STEP_TITLES["framework"]}")' not in source


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
