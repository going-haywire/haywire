"""``haywire share`` — a thin runner over :class:`SharePipeline`.

Two modes:

* **interactive** (default) — prompts through the same steps as the wizard.
* **``--yes``** — non-interactive full run with flag-supplied answers, for
  tag-triggered release automation and for the test suite (testing a
  seven-step git-mutating pipeline through a prompt loop is otherwise
  miserable).

Returns exit codes; never calls ``sys.exit`` itself, so it stays testable.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from haywire_studio.packaging.share.pipeline import (
    ShareError,
    SharePipeline,
)
from haywire_studio.packaging.share.url import derive_share_url_only

EXIT_OK = 0
EXIT_FAILED = 1


def run_share_cli(
    *,
    repo_root: Path,
    yes: bool,
    bump: str | None,
    message: str | None,
) -> int:
    """Dispatch to one of the two modes and return the process exit code."""
    pipeline = SharePipeline(repo_root)
    try:
        if yes:
            return _run_yes(pipeline, bump=bump, message=message)
        return _run_interactive(pipeline)
    except ShareError as exc:
        print(f"\n✗ {exc}")
        return EXIT_FAILED


# ── --yes ────────────────────────────────────────────────────────────────────


def _run_yes(
    pipeline: SharePipeline,
    *,
    bump: str | None,
    message: str | None,
) -> int:
    """Full non-interactive run. Every decision must arrive as a flag."""
    if not bump:
        print("--yes requires --bump (patch|minor|major|X.Y.Z): a non-interactive run")
        print("cannot guess which version you meant to publish.")
        return EXIT_FAILED

    pipeline.require_preconditions()
    print("✓ Preconditions OK")

    drift = pipeline.check_drift()
    if drift.needs_decision:
        # Union is additive and safe, but Replace destructively removes declared
        # deps — that decision is never made on the user's behalf.
        print("✗ Dependency drift found. Resolve it interactively with `haywire share`:")
        for d in drift.drifted:
            print(f"  - {d.lib_dir.name}")
        return EXIT_FAILED
    print("✓ No dependency drift")

    bump_result = pipeline.apply_bump(bump)
    print(f"✓ Bumped every barn library to {bump_result.version}")
    if bump_result.lock_warning:
        print(f"⚠ {bump_result.lock_warning}")

    docs = asyncio.run(pipeline.apply_docs(on_output=lambda line: print(f"  {line}")))
    gaps = docs.total_gaps
    print(f"✓ Regenerated docs ({gaps} coverage gap(s))")

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

    url = derive_share_url_only(pipeline.repo_root)
    if url.share_url:
        print(f"\n✓ Share this URL:\n  {url.share_url}")
    elif url.warning:
        print(f"\n⚠ {url.warning}")
    return EXIT_OK


# ── interactive ──────────────────────────────────────────────────────────────


def _ask(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def _confirm(prompt: str) -> bool:
    return _ask(f"{prompt} (y/N)", default="n").lower().startswith("y")


def _run_interactive(pipeline: SharePipeline) -> int:
    """Prompt through the same six steps the wizard walks."""
    print("── 1. Preconditions ──")
    pipeline.require_preconditions()
    print("✓ git, barn/, and origin all OK")

    print("\n── 2. Dependency drift ──")
    drift = pipeline.check_drift()
    if drift.needs_decision:
        for d in drift.drifted:
            print(f"  {d.lib_dir.name}:")
            for dep in d.pyproject_missing:
                print(f"    + pyproject.toml: {dep}")
            for dep in d.decorator_missing:
                print(f"    + @library(dependencies): {dep}")
        choice = _ask("Union (add missing) / Replace (overwrite) / Skip", default="Union").lower()
        if choice.startswith("u"):
            pipeline.apply_drift_union(drift)
            print("✓ Merged detected dependencies")
        elif choice.startswith("r"):
            print("Replace removes declarations the source no longer imports.")
            if not _confirm("Really replace?"):
                return EXIT_FAILED
            pipeline.apply_drift_replace(drift)
            print("✓ Replaced declared dependencies")
        else:
            pipeline.acknowledge_drift()
            print("⚠ Continuing with unresolved drift")
    else:
        print("✓ No drift")

    print("\n── 3. Version ──")
    version_plan = pipeline.plan_version()
    for lib in version_plan.current:
        print(f"  {lib.name}: {lib.version or '(none)'}")
    if version_plan.versions_agree:
        for keyword, resolved in version_plan.suggestions.items():
            print(f"  {keyword}: {resolved}")
        spec = _ask("Bump (patch|minor|major|X.Y.Z)", default="patch")
    else:
        print("⚠ Versions disagree — every barn library will be set to the version you name.")
        spec = _ask("Target version (X.Y.Z)")
    bump_result = pipeline.apply_bump(spec)
    print(f"✓ All barn libraries now {bump_result.version}")
    if bump_result.lock_warning:
        print(f"⚠ {bump_result.lock_warning}")

    print("\n── 4. Docs ──")
    docs = asyncio.run(pipeline.apply_docs(on_output=lambda line: print(f"  {line}")))
    print(f"✓ Docs regenerated ({docs.total_gaps} coverage gap(s))")

    print("\n── 5. Marketstall, commit, tag ──")
    stall = pipeline.apply_marketstall()
    print(f"✓ Wrote {stall.out_path}")
    if stall.warning:
        print(f"⚠ {stall.warning}")

    plan = pipeline.plan_commit()
    print("\nFiles to commit:")
    for path in plan.files:
        print(f"  {path.relative_to(pipeline.repo_root)}")

    include_barn: list[Path] = []
    if plan.barn_dirty:
        print("\nUncommitted content under barn/ — consumers install from a clone,")
        print("so anything left out is silently MISSING for them:")
        for entry in plan.barn_dirty:
            marker = "new" if entry.untracked else "modified"
            print(f"  ({marker}) {entry.path.relative_to(pipeline.repo_root)}")
        if _confirm("Include these in this commit?"):
            include_barn = [entry.path for entry in plan.barn_dirty]

    message = _ask("Commit message", default=plan.message)
    plan = pipeline.plan_commit(message=message)

    pipeline.verify_push_allowed()
    print("✓ Remote will accept the push")

    if not _confirm(f"Commit and tag {plan.tag}?"):
        print("Aborted before committing. Nothing was committed or tagged.")
        return EXIT_FAILED

    result = pipeline.apply_commit(plan, include_barn=include_barn)
    print(f"✓ Committed {result.sha[:8]} and tagged {result.tag}")

    print("\n── 6. Push ──")
    if not _confirm(f"Push {result.tag} to origin?"):
        print(f"Not pushed. Run this when ready:\n  git {' '.join(pipeline.push_command())}")
        return EXIT_OK

    push = asyncio.run(pipeline.apply_push(on_output=lambda line: print(f"  {line}")))
    print(f"✓ Pushed to {push.remote} ({push.branch}, {push.tag})")

    url = derive_share_url_only(pipeline.repo_root)
    if url.share_url:
        print(f"\n✓ Share this URL:\n  {url.share_url}")
    elif url.warning:
        print(f"\n⚠ {url.warning}")
    return EXIT_OK
