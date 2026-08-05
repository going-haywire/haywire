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
    requires_haywire: str | None = None,
) -> int:
    """Dispatch to one of the two modes and return the process exit code."""
    pipeline = SharePipeline(repo_root)
    try:
        if yes:
            return _run_yes(pipeline, bump=bump, message=message, requires_haywire=requires_haywire)
        return _run_interactive(pipeline)
    except ShareError as exc:
        print(f"\n✗ {exc}")
        return EXIT_FAILED


# ── --yes ────────────────────────────────────────────────────────────────────


def _resolve_framework_answer(pipeline: SharePipeline, specifier: str | None) -> str | None:
    """Apply a supplied framework specifier, or leave the declaration alone.

    No flag means keep the declared floor. That default is INERT — it changes
    nothing and locks nobody out — which is exactly what --yes is for. Raising
    a floor, the consumer-excluding direction, always needs the explicit flag.

    Not applying is now genuinely harmless: the marketstall's ``require`` is
    derived from the pyproject floor at write time, so skipping this leaves the
    published entry stating the floor that is actually declared rather than
    stamping an empty one.
    """
    if specifier is None:
        return None
    pipeline.apply_framework(specifier)
    return specifier


def _detected_additions(drift: object) -> tuple[list[str], list[str]]:
    """The pyproject entries and decorator names --yes would declare.

    Declared with NO floor, matching the interactive screen's default: a floor
    is the oldest version that works, which nothing here can compute, and an
    unpinned declaration constrains no consumer. The report already names what
    is missing, so nothing is re-detected.
    """
    return (
        list(drift.pyproject_missing),  # type: ignore[attr-defined]
        list(drift.decorator_missing),  # type: ignore[attr-defined]
    )


def _run_yes(
    pipeline: SharePipeline,
    *,
    bump: str | None,
    message: str | None,
    requires_haywire: str | None = None,
) -> int:
    """Full non-interactive run. Every decision must arrive as a flag."""
    if not bump:
        print("--yes requires --bump (patch|minor|major|X.Y.Z): a non-interactive run")
        print("cannot guess which version you meant to publish.")
        return EXIT_FAILED

    pipeline.require_preconditions()
    print("✓ Preconditions OK")

    report = pipeline.check_drift()
    if report.needs_decision:
        # Declaring an import the source actually uses is unambiguously
        # correct, so --yes does it rather than refusing. Removals and floor
        # changes are NOT touched here: both are optional, and one is lossy.
        pyproject_entries: dict[Path, list[str]] = {}
        decorator_entries: dict[Path, list[str]] = {}
        for d in report.drifted:
            entries, names = _detected_additions(d)
            pyproject_entries[d.lib_dir] = entries
            decorator_entries[d.lib_dir] = names
            for dep in entries + names:
                print(f"  + {d.lib_dir.name}: {dep}")
        pipeline.apply_additions(pyproject_entries, decorator_entries)
        print("✓ Declared every detected import")
    else:
        print("✓ Every import is declared")

    answer = _resolve_framework_answer(pipeline, requires_haywire)
    if answer:
        print(f"✓ Framework requirement set to {answer}")
    else:
        print("✓ Framework requirement unchanged")

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


_DETECT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("pyproject_missing", "Undeclared imports — pyproject.toml does not declare these"),
    ("decorator_missing", "Undeclared in @library(dependencies) — hot-reload and enable gating"),
    ("unused_declarations", "Declared, not imported"),
    ("pyproject_version_lag", "Version floors below what is installed"),
    ("unresolved", "Unresolved imports — mapped to no installed distribution"),
)


def _print_detect_report(report: object) -> None:
    """Print the findings grouped by KIND, each instance naming its library.

    Grouping by library instead repeats the same explanation once per library
    and forces the reader to work out which name is the subject and which is
    the container. Mirrors the wizard's Detect screen so both surfaces read
    the same way.
    """
    libraries = report.libraries  # type: ignore[attr-defined]
    printed = False
    for field, heading in _DETECT_SECTIONS:
        rows: list[str] = []
        for drift in libraries:
            library = drift.lib_dir.name
            if field == "pyproject_version_lag":
                rows += [
                    f"{dist}  in {library} — declares {declared}, {installed} installed"
                    for dist, declared, installed in getattr(drift, field)
                ]
            else:
                rows += [f"{item}  in {library}" for item in getattr(drift, field)]
        if not rows:
            continue
        printed = True
        print(f"\n  {heading}:")
        for row in rows:
            print(f"    {row}")
    if not printed:
        print("  Nothing to report.")


def _ask(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def _confirm(prompt: str) -> bool:
    return _ask(f"{prompt} (y/N)", default="n").lower().startswith("y")


def _run_interactive(pipeline: SharePipeline) -> int:
    """Prompt through the same screens the wizard walks."""
    print("── 1. Preconditions ──")
    pipeline.require_preconditions()
    print("✓ git, barn/, and origin all OK")

    print("\n── 2. Detect ──")
    report = pipeline.check_drift()
    _print_detect_report(report)

    print("\n── 3. Framework requirement ──")
    fw = pipeline.plan_framework()
    print(f"  haywire-core, installed: {fw.installed or '(unknown)'}")
    for index, option in enumerate(fw.options, start=1):
        mark = "  [recommended]" if option.recommended else ""
        print(f"  {index}. {option.specifier}   {option.label}{mark}")
        if option.consequence:
            print(f"       {option.consequence}")
    print(f"  {len(fw.options) + 1}. custom …   any valid PEP 440 specifier")
    choice = _ask("Choose", default="1")
    if choice.strip() == str(len(fw.options) + 1):
        specifier = _ask("Specifier (e.g. >=0.0.31)")
    else:
        try:
            specifier = fw.options[int(choice) - 1].specifier
        except (ValueError, IndexError):
            print("✗ Not one of the offered options.")
            return EXIT_FAILED
    pipeline.apply_framework(specifier)
    print(f"✓ Framework requirement set to haywire-core{specifier}")

    print("\n── 4. Unused declarations ──")
    unused = {d.lib_dir: list(d.unused_declarations) for d in report.libraries if d.unused_declarations}
    if not unused:
        print("  None.")
    else:
        for lib_dir, names in unused.items():
            print(f"  {lib_dir.name}: {', '.join(names)}")
        print("  Removing is irreversible here and a dynamic import looks identical")
        print("  to an unused declaration.")
        if _confirm("Remove them?"):
            pipeline.apply_removals(unused)
            print("✓ Removed")
        else:
            print("· Kept")

    print("\n── 5. Undeclared imports ──")
    if not report.needs_decision:
        print("  None.")
    else:
        pyproject_entries: dict[Path, list[str]] = {}
        decorator_entries: dict[Path, list[str]] = {}
        for d in report.drifted:
            entries, names = _detected_additions(d)
            for dep in entries + names:
                print(f"  {d.lib_dir.name}: {dep}")
            pyproject_entries[d.lib_dir] = entries
            decorator_entries[d.lib_dir] = names
        if _confirm("Declare them?"):
            pipeline.apply_additions(pyproject_entries, decorator_entries)
            print("✓ Declared")
        else:
            pipeline.acknowledge_undeclared()
            print("⚠ Publishing with imports left undeclared — consumers may fail to install")

    print("\n── 6. Version floors ──")
    lagging = {d.lib_dir: list(d.pyproject_version_lag) for d in report.libraries if d.pyproject_version_lag}
    if not lagging:
        print("  Every declared floor is at or above what is installed.")
    else:
        for lib_dir, rows in lagging.items():
            for dist, declared, installed in rows:
                print(f"  {lib_dir.name}: {dist} declares {declared}, {installed} installed")
        print("  A floor states the OLDEST version that works, which nothing here can")
        print("  compute — installed being newer is not evidence the floor is wrong.")
        if _confirm("Sync these floors to the installed versions?"):
            floors = {
                lib_dir: [f"{dist}>={installed}" for dist, _declared, installed in rows]
                for lib_dir, rows in lagging.items()
            }
            pipeline.apply_floors(floors)
            print("✓ Synced")
        else:
            print("· Kept")

    print("\n── 7. Version ──")
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

    print("\n── 8. Docs ──")
    docs = asyncio.run(pipeline.apply_docs(on_output=lambda line: print(f"  {line}")))
    print(f"✓ Docs regenerated ({docs.total_gaps} coverage gap(s))")

    print("\n── 9. Marketstall, commit, tag ──")
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

    print("\n── 10. Push ──")
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
