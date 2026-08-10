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
from pathlib import Path

from haywire.core.publishing.marketstall import read_pypi_marketplace_url
from haywire.core.publishing.pipeline import ShareError, SharePipeline
from haywire.core.publishing.url import derive_share_url_only

EXIT_OK = 0
EXIT_FAILED = 1


def run_share_cli(
    *,
    repo_root: Path,
    bump: str | None,
    message: str | None,
    requires_haywire: str | None = None,
    dry_run: bool = False,
) -> int:
    """Publish *repo_root*, or report what publishing it would do."""
    pipeline = SharePipeline(repo_root)
    try:
        if dry_run:
            return _run_dry(pipeline)
        return _run_publish(pipeline, bump=bump, message=message, requires_haywire=requires_haywire)
    except ShareError as exc:
        print(f"\n✗ {exc}")
        return EXIT_FAILED


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


def _run_dry(pipeline: SharePipeline) -> int:
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
    return EXIT_OK if report.ok else EXIT_FAILED


def _run_publish(
    pipeline: SharePipeline,
    *,
    bump: str | None,
    message: str | None,
    requires_haywire: str | None,
) -> int:
    """The full run. Every decision arrives as a flag or takes its inert default."""
    if not bump:
        print("share requires --bump (patch|minor|major|X.Y.Z): a non-interactive run")
        print("cannot guess which version you meant to publish.")
        print("Run `haywire share --dry-run` to see what is available.")
        return EXIT_FAILED

    pipeline.require_preconditions()
    print("✓ Preconditions OK")

    report = pipeline.check_drift()

    registrations = report.decorator_registrations
    if registrations:
        for lib_dir, names in registrations.items():
            for name in names:
                print(f"  + {lib_dir.name}: haybale.toml linked_libraries {name}")
        pipeline.apply_decorator_registrations(registrations)
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

    # Step 7, after the push, matching the wizard. No registry to reload here —
    # the CLI holds no live library system — so this only refreshes the
    # environment for the next process.
    synced, sync_warning = pipeline.apply_sync()
    if synced:
        print("✓ Refreshed installed versions (uv sync)")
    elif sync_warning:
        print(f"⚠ {sync_warning}")

    pypi_url = read_pypi_marketplace_url(pipeline.repo_root)
    if pypi_url:
        print(f"\n✓ Released packages (recommended):\n  {pypi_url}")

    tag = f"v{pipeline.version}" if pipeline.version else None
    url = derive_share_url_only(pipeline.repo_root, tag=tag)
    if url.share_url:
        print(f"\n✓ Share this URL:\n  {url.share_url}")
        if url.tagged_url:
            print(f"\n  Frozen to this version:\n  {url.tagged_url}")
    elif url.warning:
        print(f"\n⚠ {url.warning}")
    return EXIT_OK
