"""``haywire share`` — a thin non-interactive runner over :class:`SharePipeline`.

One mode. Every decision arrives as a flag, or takes the inert default; the
command runs to completion or exits non-zero. The prompt-driven mode this used
to carry is gone: it re-implemented every judgement the Share editor makes,
divergently (its own copy of the finding vocabulary, its own registration
comprehension), and the terminal is a poor place to answer eleven questions
about dependency floors.

``--dry-run`` reports what a publish would do and writes nothing. That is what
the deleted ``--check`` mode was reaching for; ``--check`` failed on every PR
checkout because it enforced preconditions that a PR checkout cannot satisfy.
Here the branch state is *reported* rather than enforced, so the command is
useful exactly where the old one was not.

Returns exit codes; never calls ``sys.exit`` itself, so it stays testable.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from haywire.core.publishing.human_steps import checklist
from haywire.core.publishing.pipeline import (
    PreconditionFailure,
    PreconditionsError,
    ShareError,
    SharePipeline,
    TagCollisionError,
)
from haywire.core.publishing.pipeline.steps import release_state
from haywire.core.publishing.url import derive_share_url_only

from haywire_studio.playbook import State

#: Exit codes. Stable: callers branch on them. See the sharing guide.
EXIT_OK = 0  # released, or the requested read-only report succeeded
EXIT_ALREADY_RELEASED = 10  # nothing to do; do not retry
EXIT_REFUSED = 20  # refused; ``next`` names the repair
EXIT_HUMAN_NEEDED = 30  # only a person can proceed
EXIT_FAILED_REVERTED = 40  # failed mid-run; this run's writes were reverted
EXIT_FAILED_PARTIAL = 50  # failed after the release commit; resume or stop
EXIT_USAGE = 64  # bad command line

_SETTLED_CODES = {"already_released", "nothing_to_release"}

_STATES = {
    "already_released": State.RELEASED.value,
    "nothing_to_release": State.NOTHING_TO_RELEASE.value,
    "unpushed_release": State.UNPUSHED.value,
    "stale_marker": State.STALE_MARKER.value,
}

_STATUS_COMMAND = "uv run --frozen haywire share --status"
_FIRST_RELEASE_COMMAND = "uv run --frozen haywire share --first-release"
_RESUME_COMMAND = "uv run --frozen haywire share --resume"


@dataclass
class Outcome:
    """What one invocation concluded; ``--json`` prints it as one object."""

    state: str = State.UNKNOWN.value
    exit_code: int = EXIT_OK
    version: str | None = None
    tag: str | None = None
    next_command: str | None = None
    then_command: str | None = None
    stop_reason: str | None = None
    checklist: list[str] | None = None
    failure: dict[str, str] | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "state": self.state,
            "ok": self.exit_code in (EXIT_OK, EXIT_ALREADY_RELEASED),
            "exit_code": self.exit_code,
            "version": self.version,
            "tag": self.tag,
            "next": {"command": self.next_command} if self.next_command else None,
            "stop": {
                "reason": self.stop_reason,
                "checklist": self.checklist or [],
                "then": self.then_command,
            }
            if self.stop_reason
            else None,
            "failure": self.failure,
        }


def run_share_cli(
    *,
    repo_root: Path,
    bump: str | None,
    message: str | None,
    requires_haywire: str | None = None,
    dry_run: bool = False,
    status: bool = False,
    resume: bool = False,
    json_output: bool = False,
    first_release: bool = False,
) -> int:
    """Publish *repo_root*, or report what publishing it would do; return the exit code.

    With ``json_output`` the human text goes to stderr and stdout carries exactly one
    JSON object (:meth:`Outcome.as_json`).
    """
    pipeline = SharePipeline(repo_root)
    pipeline.first_release = first_release
    out = Outcome()

    def dispatch() -> None:
        try:
            if status:
                _run_status(pipeline, out)
            elif resume:
                _run_resume(pipeline, out)
            elif dry_run:
                _run_dry(pipeline, out)
            else:
                _run_publish(pipeline, out, bump=bump, message=message, requires_haywire=requires_haywire)
        except PreconditionsError as exc:
            _refuse(out, exc.failures[0], repo_root)
        except ShareError as exc:
            _fail(pipeline, out, exc, publishing=not (status or resume or dry_run))

    if json_output:
        with contextlib.redirect_stdout(sys.stderr):
            dispatch()
        print(json.dumps(out.as_json()))
    else:
        dispatch()
    return out.exit_code


def _classify(failure: PreconditionFailure) -> tuple[int, str]:
    """The exit code and state name for one precondition failure."""
    state = _STATES.get(failure.code)
    if failure.code in _SETTLED_CODES:
        return EXIT_ALREADY_RELEASED, state or State.RELEASED.value
    if failure.human_only:
        return EXIT_HUMAN_NEEDED, state or State.NEEDS_HUMAN.value
    return EXIT_REFUSED, state or State.BLOCKED.value


def _refuse(out: Outcome, failure: PreconditionFailure, repo_root: Path) -> None:
    """Print a refusal, ending in one DONE/STOP/NEXT line and a STATE line."""
    _print_failure(failure)
    out.exit_code, out.state = _classify(failure)
    out.failure = {"code": failure.code or "precondition", "message": failure.message}
    if out.exit_code == EXIT_ALREADY_RELEASED:
        print(
            "DONE: nothing to release."
            if failure.code == "nothing_to_release"
            else "DONE: already released."
        )
    elif out.exit_code == EXIT_HUMAN_NEEDED:
        out.stop_reason = failure.message.splitlines()[0]
        print(f"STOP: human needed — {out.stop_reason}")
        if failure.human_steps:
            out.checklist = checklist(failure.human_steps, repo_root)
            print("Give this to the owner, then wait; do not attempt it yourself:")
            for line in out.checklist:
                print(f"  {line}")
        if failure.next_command:
            out.then_command = failure.next_command
            print(f"THEN, once the owner confirms: {failure.next_command}")
    else:
        out.next_command = failure.next_command or _STATUS_COMMAND
        if failure.next_command:
            print(f"NEXT: {failure.next_command}")
        else:
            print(f"NEXT: fix the problem above, then run: {_STATUS_COMMAND}")
    print(f"STATE: {out.state}")


def _fail(pipeline: SharePipeline, out: Outcome, exc: ShareError, *, publishing: bool) -> None:
    """A step failed after preconditions passed: revert this run's writes, or point at resume."""
    print(f"\n✗ {exc}")
    out.failure = {"code": type(exc).__name__, "message": str(exc).splitlines()[0]}
    if release_state.detect(pipeline.repo_root).kind is release_state.ReleaseKind.UNPUSHED:
        out.exit_code, out.state, out.next_command = (
            EXIT_FAILED_PARTIAL,
            State.UNPUSHED.value,
            _RESUME_COMMAND,
        )
        print(f"NEXT: {_RESUME_COMMAND}")
    elif publishing:
        try:
            pipeline.rollback()
            print("✓ Reverted every change this run made.")
        except ShareError as rollback_exc:
            print(f"✗ Could not revert: {rollback_exc}")
        out.exit_code, out.state = EXIT_FAILED_REVERTED, State.FAILED.value
        out.next_command = _STATUS_COMMAND
        print(f"NEXT: read the error above, then run: {_STATUS_COMMAND}")
    else:
        out.exit_code, out.state, out.next_command = EXIT_REFUSED, State.BLOCKED.value, _STATUS_COMMAND
        print(f"NEXT: {_STATUS_COMMAND}")
    print(f"STATE: {out.state}")


def _print_findings(pipeline: SharePipeline) -> None:
    """Every library's findings, one line each, naming its library.

    Deliberately terse and ungrouped: the editor groups by finding kind because
    it has room and controls to attach; a CLI that reproduced that layout would
    be a second copy of the vocabulary to keep in sync — which is exactly what
    the old interactive mode was.
    """
    report = pipeline.check_drift()
    for drift in report.libraries:
        name = drift.lib_dir.name
        for dep in drift.pyproject_missing:
            print(f"  ! {name}: {dep} imported but not declared")
        for dep in drift.unused_declarations:
            print(f"  · {name}: {dep} declared but not imported")
        for dist, declared, installed in drift.pyproject_version_lag:
            print(f"  · {name}: {dist} declares {declared}, {installed} installed")
        for dep in drift.unresolved:
            print(f"  · {name}: {dep} resolved to no distribution")
    if not report.libraries:
        print("  Nothing to report.")


def _print_failure(failure: PreconditionFailure) -> None:
    print(f"✗ {failure.message}")
    for line in failure.remedy.splitlines():
        print(f"    {line}")
    if failure.doc_url:
        print(f"    {failure.doc_label or 'Docs'}: {failure.doc_url}")


def _run_status(pipeline: SharePipeline, out: Outcome) -> None:
    """Read-only. The last line is ``STATE: <name>``, stable for callers to match."""
    report = pipeline.check_preconditions()
    if not report.ok:
        _refuse(out, report.failures[0], pipeline.repo_root)
        return
    print("✓ Ready to release.")
    out.state, out.exit_code, out.next_command = (
        State.READY.value,
        EXIT_OK,
        "uv run --frozen haywire share --bump patch",
    )
    print(f"NEXT: {out.next_command}")
    print("STATE: READY")


def _run_resume(pipeline: SharePipeline, out: Outcome) -> None:
    push = asyncio.run(pipeline.resume_release(on_output=lambda line: print(f"  {line}")))
    out.state, out.exit_code, out.tag = State.RELEASED.value, EXIT_OK, push.tag
    out.version = push.tag.removeprefix("v")
    print(f"✓ Pushed to {push.remote} ({push.branch}, {push.tag})")
    print("STATE: RELEASED")


def _run_dry(pipeline: SharePipeline, out: Outcome) -> None:
    """Report; write nothing. Preconditions are REPORTED, not enforced."""
    report = pipeline.check_preconditions()
    if report.ok:
        print("✓ Preconditions OK")
    else:
        for failure in report.failures:
            print(f"✗ {failure.message}")
            if failure.remedy:
                for line in failure.remedy.splitlines():
                    print(f"    {line}")
            if failure.doc_url:
                print(f"    {failure.doc_label or 'Docs'}: {failure.doc_url}")

    print("\nFindings:")
    _print_findings(pipeline)

    plan = pipeline.plan_version()
    print("\nVersions:")
    for lib in plan.current:
        print(f"  {lib.name}: {lib.version or '(none)'}")
    if plan.versions_agree:
        for keyword, resolved in plan.suggestions.items():
            print(f"  --bump {keyword} → {resolved}")
    else:
        print("  ⚠ Versions disagree — --bump needs an explicit X.Y.Z.")

    print("\nNothing was written.")
    if report.ok:
        out.state, out.exit_code = State.READY.value, EXIT_OK
    else:
        out.exit_code, out.state = _classify(report.failures[0])
        out.failure = {
            "code": report.failures[0].code or "precondition",
            "message": report.failures[0].message,
        }


def _run_publish(
    pipeline: SharePipeline,
    out: Outcome,
    *,
    bump: str | None,
    message: str | None,
    requires_haywire: str | None,
) -> None:
    """The full run. Every decision arrives as a flag or takes its inert default."""
    if not bump and not pipeline.first_release:
        print("share requires --bump (patch|minor|major|X.Y.Z): a non-interactive run")
        print("cannot guess which version you meant to publish.")
        print("Run `haywire share --dry-run` to see what is available.")
        out.state, out.exit_code, out.next_command = State.USAGE.value, EXIT_USAGE, _STATUS_COMMAND
        out.failure = {"code": "usage", "message": "share requires --bump"}
        print("STATE: USAGE")
        return

    pipeline.require_preconditions()
    print("✓ Preconditions OK")

    if not bump:
        # --first-release without --bump publishes the version already declared.
        current = pipeline.plan_version().common_version
        if current is None:
            print("The libraries declare different versions: add --bump X.Y.Z.")
            out.state, out.exit_code, out.next_command = State.USAGE.value, EXIT_USAGE, _STATUS_COMMAND
            out.failure = {"code": "usage", "message": "versions disagree"}
            print("STATE: USAGE")
            return
        try:
            pipeline.check_tag_available(current)
        except TagCollisionError as exc:
            _refuse(
                out,
                PreconditionFailure(
                    message=str(exc),
                    remedy="That version is already tagged, so a first release needs a new one.",
                    code="first_release_tag_exists",
                    next_command=f"{_FIRST_RELEASE_COMMAND} --bump patch",
                ),
                pipeline.repo_root,
            )
            return
        bump = current

    report = pipeline.check_drift()

    registrations = report.linked_registrations
    if registrations:
        for lib_dir, names in registrations.items():
            for name in names:
                print(f"  + {lib_dir.name}: haybale.toml linked_libraries {name}")
        pipeline.apply_linked_registrations(registrations)
        print("✓ Registered imported libraries in haybale.toml linked_libraries")

    if report.needs_decision:
        # Declaring an import the source actually uses is unambiguously
        # correct, so this does it rather than refusing. Declared with no
        # floor: nothing here can compute the oldest version that works.
        # Removals and floor changes are NOT touched — optional, and one is
        # lossy.
        additions: dict[Path, list[str]] = {d.lib_dir: list(d.pyproject_missing) for d in report.drifted}
        for lib_dir, entries in additions.items():
            for dep in entries:
                print(f"  + {lib_dir.name}: {dep}")
        pipeline.apply_additions(additions)
        print("✓ Declared every detected import")
    else:
        print("✓ Every import is declared")

    # No flag means keep the declared floor — INERT, changing nothing and
    # locking nobody out. Raising a floor is the consumer-excluding direction
    # and always needs the explicit flag.
    if requires_haywire is not None:
        pipeline.apply_framework(requires_haywire)
        print(f"✓ Framework requirement set to {requires_haywire}")
    else:
        print("✓ Framework requirement unchanged")

    bump_result = pipeline.apply_bump(bump)
    print(f"✓ Bumped every barn library to {bump_result.version}")
    if bump_result.lock_warning:
        print(f"⚠ {bump_result.lock_warning}")

    docs = asyncio.run(pipeline.apply_docs(on_output=lambda line: print(f"  {line}")))
    print(f"✓ Regenerated docs ({docs.total_gaps} coverage gap(s))")

    stall = pipeline.apply_marketstall()
    print(f"✓ Wrote {stall.out_path}")
    if stall.warning:
        print(f"⚠ {stall.warning}")

    pipeline.verify_push_allowed()
    print("✓ Remote will accept the push")

    plan = pipeline.plan_commit(message=message)
    result = pipeline.apply_commit(plan)
    print(f"✓ Committed {result.sha[:8]} and tagged {result.tag}")

    push = asyncio.run(pipeline.apply_push(on_output=lambda line: print(f"  {line}")))
    print(f"✓ Pushed to {push.remote} ({push.branch}, {push.tag})")

    tag = f"v{pipeline.version}" if pipeline.version else None
    out.state, out.exit_code, out.version, out.tag = State.RELEASED.value, EXIT_OK, pipeline.version, tag
    url = derive_share_url_only(pipeline.repo_root, tag=tag)
    if url.share_url:
        print(f"\n✓ Share this URL:\n  {url.share_url}")
        if url.tagged_url:
            print(f"\n  Frozen to this version:\n  {url.tagged_url}")
    elif url.warning:
        print(f"\n⚠ {url.warning}")
    if pipeline.first_release:
        print(
            "\nFirst release: the tag push started publish.yml, which creates the PyPI project(s). "
            "Check the Actions tab, then https://pypi.org/project/<name>/."
        )
    print("STATE: RELEASED")
