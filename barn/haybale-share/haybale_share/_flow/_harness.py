"""Panel harness — render every Share screen in every state, without git.

    uv run python -m haybale_share._flow      # the runnable entry point (__main__.py)

Then open http://localhost:8091.

**Why fixtures rather than a real pipeline.** Each panel renders from flow
state: Preflight needs a ``PreconditionFailure`` of a specific ``kind``,
Review needs a ``DriftReport`` carrying all four finding kinds at once, and the
post-commit failure screen needs a ``commit_result`` plus a ``PushError``.
Driving a real ``SharePipeline`` gives you exactly one of those — whichever
state your repo happens to be in — and never the interesting ones. So every
scenario here hand-builds the state and calls the panel directly.

Nothing writes. The pipeline is pointed at a scratch directory and no step
method is ever called, so a scenario cannot touch the repo even by accident.

This is a development tool, not a test. The Playwright suite asserts
behaviour; this exists to be *looked at* — spacing, wrapping, whether a screen
with four finding sections is still readable, whether the failed-push screen
reads as calm rather than alarming.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from haywire.core.publishing.pipeline import (
    CommitResult,
    DepDrift,
    DriftReport,
    FrameworkOption,
    FrameworkPlan,
    LibraryVersion,
    PreconditionFailure,
    PreconditionsError,
    PushError,
    SharePipeline,
    VersionPlan,
)

from haywire.core.library.identity import LibraryReloadAction

from ._state import ShareFlow
from .panels import panel_done, panel_preflight, panel_publish, panel_review

_SCRATCH = Path(tempfile.gettempdir()) / "haybale-share-harness"

ALPHA = Path("barn/haybale-alpha")
BETA = Path("barn/haybale-beta")


def _flow() -> ShareFlow:
    """A flow pointed at a scratch dir. No scenario calls a step method."""
    _SCRATCH.mkdir(parents=True, exist_ok=True)
    return ShareFlow(pipeline=SharePipeline(_SCRATCH))


# ── Preflight ────────────────────────────────────────────────────────────────


def preflight_checking() -> ShareFlow:
    """The auto-start state: spinner, no failure yet."""
    return _flow()


def _failed(failure: PreconditionFailure) -> ShareFlow:
    flow = _flow()
    flow.fail(PreconditionsError([failure]))
    return flow


def preflight_dirty_tree() -> ShareFlow:
    """act-kind, takes input. The message is a multi-line file list — the case
    that made the old modal's single-line label useless."""
    return _failed(
        PreconditionFailure(
            message=(
                "Working tree is not clean:\n"
                "  barn/haybale-alpha/pyproject.toml\n"
                "  barn/haybale-alpha/haybale_alpha/nodes/thing.py\n"
                "  docs/reference/glossary.md"
            ),
            remedy=(
                "Commit or stash these changes before sharing. The publish pipeline "
                "reverts everything it writes on failure by resetting the whole working "
                "tree — anything already uncommitted here would be lost along with it."
            ),
            kind="act",
            fix_id="commit_dirty_tree",
            fix_label="Commit changes",
        )
    )


def preflight_no_origin() -> ShareFlow:
    """act-kind, takes input (a URL)."""
    return _failed(
        PreconditionFailure(
            message="No 'origin' remote is configured.",
            remedy="git remote add origin <your-repo-url>\ngit push -u origin <branch-name>",
            kind="act",
            fix_id="add_origin",
            fix_label="Add origin remote",
        )
    )


def preflight_invalid_os() -> ShareFlow:
    """act-kind, no input — the fix's subject rides on lib_dir."""
    return _failed(
        PreconditionFailure(
            message="Invalid manifest at barn/haybale-alpha/haybale_alpha/haybale.toml: "
            "'other' is not declarable",
            remedy=(
                "`haybale.toml`'s `os` may only declare `macos`, `windows`, `linux`. "
                "`other` is a runtime sentinel for platforms that don't map to one of "
                "those three — it is set at runtime and must never be declared."
            ),
            kind="act",
            fix_id="strip_os",
            fix_label="Remove `other` from the os list",
            lib_dir="barn/haybale-alpha",
        )
    )


def preflight_unknown_host() -> ShareFlow:
    """act-kind writing OUTSIDE the repo (~/.haywire/config.toml)."""
    return _failed(
        PreconditionFailure(
            message="Host 'git.example.org' is not recognized.",
            remedy=(
                "Add this to ~/.haywire/config.toml:\n\n"
                "[[hosts]]\n"
                'hostname = "git.example.org"\n'
                'provider = "gitlab"   # or "github"\n\n'
                "This only teaches haywire how to build browser-friendly URLs for this "
                "host — it has nothing to do with push access."
            ),
            kind="act",
            fix_id="add_host_config",
            fix_label="Add host to config.toml",
            lib_dir="git.example.org",
        )
    )


_DETACHED_BLOCKED = (
    "Publishing tags the commit it creates and pushes it to a branch, "
    "and a detached HEAD is on no branch — so there is nothing to push to."
)

_BRANCH_BLOCKED = (
    "Publishing always happens on the default branch, so the tag and the "
    "marketstall URLs point at a ref that will still exist later — a feature "
    "branch usually disappears when it merges."
)


def preflight_detached_safe() -> ShareFlow:
    """Detached, but the commit is already on a branch — switching loses nothing."""
    return _failed(
        PreconditionFailure(
            message="HEAD is detached — no branch is currently checked out.",
            remedy=(
                f"{_DETACHED_BLOCKED}\n\n"
                "This commit is already on `master`, so switching to it loses nothing — "
                "it only moves HEAD back onto the branch."
            ),
            kind="act",
            fix_id="switch_branch",
            fix_label="Switch to master",
            lib_dir="master",
        )
    )


def preflight_detached_orphan() -> ShareFlow:
    """Detached WITH commits no branch contains — no button, on purpose.

    ``git switch`` here would leave the work unreachable (recoverable via
    reflog, but the user would not know to look). The remedy says to save it
    first instead of offering a one-click way to lose it.
    """
    return _failed(
        PreconditionFailure(
            message="HEAD is detached, and this commit is not on any branch.",
            remedy=(
                f"{_DETACHED_BLOCKED}\n\n"
                "Switching away now would leave this commit unreachable. Put it on a "
                "branch first:\n\n"
                "  git switch -c my-branch\n\n"
                "then publish from there."
            ),
        )
    )


def preflight_wrong_branch_merged() -> ShareFlow:
    """On a branch with nothing unmerged — switching is safe, so it is offered."""
    return _failed(
        PreconditionFailure(
            message="Currently on `feature/share-rework`, but the repository publishes from `master`.",
            remedy=(
                f"{_BRANCH_BLOCKED}\n\n"
                "`feature/share-rework` has nothing that `master` does not already "
                "contain, so switching loses no work."
            ),
            kind="act",
            fix_id="switch_branch",
            fix_label="Switch to master",
            lib_dir="master",
        )
    )


def preflight_wrong_branch_unmerged() -> ShareFlow:
    """On a branch with unmerged commits — no button.

    Nothing would be destroyed (the branch keeps its commits), but moving a
    user off unmerged work is a decision they should make deliberately, not
    one a publish wizard makes for them.
    """
    return _failed(
        PreconditionFailure(
            message="Currently on `feature/share-rework`, but the repository publishes from `master`.",
            remedy=(
                f"{_BRANCH_BLOCKED}\n\n"
                "`feature/share-rework` has commits that `master` does not. Merge them "
                "first, or publish after this branch lands:\n\n"
                "  git switch master\n\n"
                "Nothing is lost either way — `feature/share-rework` keeps its commits."
            ),
        )
    )


def _unreachable(remote: str, hostname: str, detail: str) -> ShareFlow:
    """Built through the real failure builder, not a hand-written fixture.

    The whole point of these three scenarios is which docs link comes out, so
    faking it would show nothing.
    """
    from haywire.core.publishing.pipeline.steps.preconditions import _unreachable_failure

    return _failed(_unreachable_failure(remote, hostname, detail))


def preflight_unreachable_ssh() -> ShareFlow:
    """SSH transport on a known host — links the key docs."""
    return _unreachable(
        "git@github.com:someone/haywire.git",
        "github.com",
        "Permission denied (publickey).",
    )


def preflight_unreachable_https() -> ShareFlow:
    """HTTPS on the same host — a different failure and a different page."""
    return _unreachable(
        "https://gitlab.com/someone/haywire.git",
        "gitlab.com",
        "fatal: Authentication failed",
    )


def preflight_unreachable_unknown_host() -> ShareFlow:
    """No provider for this host, so the remedy falls back to the guide rather
    than inventing a docs URL from the hostname."""
    return _unreachable(
        "git@git.example.org:someone/haywire.git",
        "git.example.org",
        "Could not resolve hostname git.example.org",
    )


# ── Review ───────────────────────────────────────────────────────────────────


def _reviewable(report: DriftReport, *, versions_agree: bool = True) -> ShareFlow:
    flow = _flow()
    flow.step = "review"
    flow.drift_report = report
    flow.framework_plan = FrameworkPlan(
        installed="0.0.38",
        declared=">=0.0.31",
        options=[
            FrameworkOption(
                specifier=">=0.0.31",
                label="keep the current declaration",
                consequence="Usable by projects on Haywire 0.0.31 and newer. No consumer has to upgrade.",
                recommended=True,
            ),
            FrameworkOption(
                specifier=">=0.0.38",
                label="require the version you built against",
                consequence="Consumers on 0.0.31–0.0.37 must update their project before they can install.",
            ),
            FrameworkOption(
                specifier="~=0.0.31",
                label="compatible release",
                consequence="Also excludes Haywire 0.1.0 and newer.",
            ),
        ],
    )
    current = [
        LibraryVersion(lib_dir=ALPHA, name="haybale-alpha", version="0.3.1"),
        LibraryVersion(lib_dir=BETA, name="haybale-beta", version="0.3.1" if versions_agree else "0.2.7"),
    ]
    flow.version_plan = VersionPlan(
        current=current,
        common_version="0.3.1" if versions_agree else None,
        suggestions={"patch": "0.3.2", "minor": "0.4.0", "major": "1.0.0"} if versions_agree else {},
    )
    return flow


def review_clean() -> ShareFlow:
    """The common case for a repeat publisher.

    Every finding category collapses to a ✓ line. The predecessor gave each of
    these its own screen with its own Continue button — six screens of good
    news, six clicks, no decisions.
    """
    return _reviewable(DriftReport(drifted=[], findings_only=[]))


def review_one_undeclared() -> ShareFlow:
    """The single most common real finding."""
    return _reviewable(
        DriftReport(
            drifted=[DepDrift(lib_dir=ALPHA, pyproject_missing=["numpy"])],
            findings_only=[],
        )
    )


def review_everything() -> ShareFlow:
    """All four finding kinds at once, across two libraries — the density test.

    This is the layout most likely to be unreadable, and the one a real repo
    almost never produces on demand.
    """
    return _reviewable(
        DriftReport(
            drifted=[
                DepDrift(
                    lib_dir=ALPHA,
                    pyproject_missing=["numpy", "opencv-python"],
                    linked_missing=["haybale_studio"],
                    unused_declarations=["requests"],
                    pyproject_version_lag=[("toml", ">=0.10.0", "0.10.2")],
                    unresolved=["cv2.legacy"],
                ),
                DepDrift(lib_dir=BETA, pyproject_missing=["pillow"]),
            ],
            findings_only=[
                DepDrift(
                    lib_dir=BETA,
                    unused_declarations=["click", "urllib3"],
                    pyproject_version_lag=[("attrs", ">=22.0", "23.1.0")],
                )
            ],
        )
    )


def review_versions_disagree() -> ShareFlow:
    """No arithmetic to offer, so the bump control becomes a free-text field."""
    return _reviewable(DriftReport(drifted=[], findings_only=[]), versions_agree=False)


# ── Publish ──────────────────────────────────────────────────────────────────


def publish_ready() -> ShareFlow:
    flow = _flow()
    flow.step = "publish"
    flow.pipeline.version = "0.3.2"
    return flow


def publish_running() -> ShareFlow:
    """Mid-run, with streamed subprocess output in the log."""
    flow = publish_ready()
    for line in (
        "Generating docs for haybale-alpha…",
        "  wrote barn/haybale-alpha/OVERVIEW.md",
        "  wrote barn/haybale-alpha/QUICKREF.md",
        "  wrote barn/haybale-alpha/docs/ThingNode.md",
        "Generating docs for haybale-beta…",
        "  wrote barn/haybale-beta/OVERVIEW.md",
        "2 libraries, 14 files, 0 coverage gaps",
    ):
        flow.push_log(line)
    return flow


def publish_committed_unpushed() -> ShareFlow:
    """The state the predecessor lied about.

    A commit and tag exist and were NOT reverted — the working-tree revert
    cannot reach committed history. The old wizard ran it anyway and reported
    "every change this run made has been reverted — nothing was left behind".
    """
    flow = publish_ready()
    flow.commit_result = CommitResult(sha="4a3f1e9c2b", tag="v0.3.2", files=[])
    flow.fail(
        PushError(
            stderr=(
                "! [rejected]        master -> master (fetch first)\n"
                "error: failed to push some refs to 'github.com:someone/haywire.git'"
            ),
            manual_command="git push origin master --tags",
        )
    )
    return flow


def publish_warnings() -> ShareFlow:
    """Warnings render in the shared chrome, above the panel body."""
    flow = publish_ready()
    flow.warnings.append("uv lock failed: could not resolve haybale-beta. The lockfile may be stale.")
    return flow


# ── Done ─────────────────────────────────────────────────────────────────────


def _published() -> ShareFlow:
    from haywire.core.publishing.pipeline import PushResult

    flow = _flow()
    flow.step = "done"
    flow.pipeline.version = "0.3.2"
    flow.push_result = PushResult(remote="origin", branch="master", tag="v0.3.2")
    return flow


def done_hot_swapped() -> ShareFlow:
    """Registry refreshed in place — no restart affordance."""
    flow = _published()
    flow.hot_swapped_libraries = ["alpha", "beta"]
    flow.hot_swap_on_reload = LibraryReloadAction.NONE
    return flow


def done_needs_refresh() -> ShareFlow:
    """A swapped library declared on_reload="refresh" — reloaded, tab still stale."""
    flow = _published()
    flow.hot_swapped_libraries = ["alpha", "beta"]
    flow.hot_swap_on_reload = LibraryReloadAction.REFRESH
    return flow


def done_needs_restart() -> ShareFlow:
    """Reloaded fine, but a library declares on_reload="restart".

    The registry is NOT stale here — the restart is that library's own
    requirement (C-extension modules, import-time global mutation), which is a
    different sentence from the one below.
    """
    flow = _published()
    flow.hot_swapped_libraries = ["alpha"]
    flow.hot_swap_on_reload = LibraryReloadAction.RESTART
    return flow


def done_nothing_swapped() -> ShareFlow:
    """No library was live to reload, so what's loaded really does predate the bump."""
    flow = _published()
    flow.hot_swapped_libraries = []
    flow.hot_swap_on_reload = LibraryReloadAction.NONE
    return flow


# ── Registry ─────────────────────────────────────────────────────────────────

Panel = Callable[[ShareFlow, Callable[[], None]], None]

SCENARIOS: dict[str, list[tuple[str, Callable[[], ShareFlow], Panel]]] = {
    "1 · Preflight": [
        ("Checking (auto-start)", preflight_checking, panel_preflight),
        ("Dirty tree — fix takes a message", preflight_dirty_tree, panel_preflight),
        ("No origin — fix takes a URL", preflight_no_origin, panel_preflight),
        ("Invalid os — fix takes nothing", preflight_invalid_os, panel_preflight),
        ("Unknown host — writes outside the repo", preflight_unknown_host, panel_preflight),
        ("Detached HEAD — safe to switch", preflight_detached_safe, panel_preflight),
        ("Detached HEAD — would orphan work", preflight_detached_orphan, panel_preflight),
        ("Wrong branch — nothing unmerged", preflight_wrong_branch_merged, panel_preflight),
        ("Wrong branch — has unmerged work", preflight_wrong_branch_unmerged, panel_preflight),
        ("Unreachable — SSH, known host", preflight_unreachable_ssh, panel_preflight),
        ("Unreachable — HTTPS, known host", preflight_unreachable_https, panel_preflight),
        ("Unreachable — unknown host", preflight_unreachable_unknown_host, panel_preflight),
    ],
    "2 · Review": [
        ("Clean repo — all ✓ lines", review_clean, panel_review),
        ("One undeclared import", review_one_undeclared, panel_review),
        ("Everything at once (density)", review_everything, panel_review),
        ("Versions disagree", review_versions_disagree, panel_review),
    ],
    "3 · Publish": [
        ("Ready", publish_ready, panel_publish),
        ("Running, with log output", publish_running, panel_publish),
        ("Warnings in chrome", publish_warnings, panel_publish),
        ("Committed but push failed", publish_committed_unpushed, panel_publish),
    ],
    "4 · Done": [
        ("Hot-swapped, no restart", done_hot_swapped, panel_done),
        ("Page reload needed", done_needs_refresh, panel_done),
        ("Restart needed (library asked)", done_needs_restart, panel_done),
        ("Restart needed (nothing swapped)", done_nothing_swapped, panel_done),
    ],
}
