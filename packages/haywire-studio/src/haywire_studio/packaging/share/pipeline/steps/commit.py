"""Step 5 — marketstall rebuild, commit file-scoping, tag."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from haywire_studio.packaging.share.git import git
from haywire_studio.packaging.share.marketstall import MarketstallWriteResult, NoBarnError, write_marketstall
from haywire_studio.packaging.share.pipeline.errors import CommitError, MarketstallError, PipelineStateError
from haywire_studio.packaging.share.pipeline.fixes import _MANIFEST_FAILURE_TYPES
from haywire_studio.packaging.share.pipeline.results import BarnDirtyFile, CommitPlan, CommitResult

if TYPE_CHECKING:
    from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline


def apply_marketstall(pipeline: "SharePipeline") -> MarketstallWriteResult:
    """Rebuild ``marketstall.toml`` from every ``barn/*`` library.

    Always a FULL rebuild: the feed's contract is "every haybale this repo
    offers", so rebuilding from disk is what keeps it true. A partial
    rebuild deletes the entries of libraries not in this run.

    Pins every entry's install_spec/docs_url/examples_url/tests_url to
    ``v<pipeline.version>`` — the tag :func:`apply` (later in this same
    step) will create once the commit succeeds. The version is already
    resolved and tag-collision-checked by step 3's ``apply_bump()`` before
    this ever runs, so the tag name is known and reserved even though the
    tag itself doesn't exist in git yet.

    Also rewrites the ``<!-- marketstall:share-url -->`` marker block in the
    root README and every ``barn/*/README.md``.
    """
    tag = f"v{pipeline.version}" if pipeline.version else None
    try:
        result = write_marketstall(
            pipeline.repo_root, tag=tag, requires_haywire=pipeline.requires_haywire or ""
        )
    except (NoBarnError, *_MANIFEST_FAILURE_TYPES) as exc:
        raise MarketstallError(str(exc)) from exc
    pipeline.record(result.written)
    return result


def barn_dirty_files(pipeline: "SharePipeline") -> list[BarnDirtyFile]:
    """Uncommitted content under ``barn/`` that the pipeline did not write.

    Offered as opt-in extras in step 5. Uncommitted barn content is
    silently ABSENT for consumers (they install from a clone), which is the
    one working-tree state that corrupts a publish.

    Dirt outside ``barn/`` is deliberately not reported: it has no bearing
    on what consumers get, and mentioning it would train users to dismiss
    the warning that matters. Ignored files never appear —
    ``git status --porcelain`` excludes them by default, and staging one
    would fail anyway.

    ``--untracked-files=all``: without it, an untracked directory (e.g. a
    brand-new component with no tracked sibling inside it yet) collapses
    to one line naming the directory instead of the file within it, which
    would surface as ``BarnDirtyFile(path=.../haybale_alpha/)`` rather than
    the actual new file.
    """
    status = git(
        ["status", "--porcelain", "--untracked-files=all", "--", "barn"],
        cwd=pipeline.repo_root,
    )
    if not status.ok:
        return []

    own = set(pipeline.written)
    out: list[BarnDirtyFile] = []
    for line in status.stdout.splitlines():
        if len(line) < 4:
            continue
        code, path_part = line[:2], line[3:].strip()
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        path = pipeline.repo_root / path_part.strip('"')
        if path in own:
            continue
        out.append(BarnDirtyFile(path=path, untracked=code == "??"))
    return sorted(out, key=lambda d: d.path)


def plan(pipeline: "SharePipeline", *, message: str | None = None) -> CommitPlan:
    """Preview exactly what would be staged, committed, and tagged.

    The write set spans the repo — every ``barn/*/pyproject.toml``, the root
    ``uv.lock``, each library's OVERVIEW/QUICKREF/``docs/*.md`` (including
    deletions for renamed components) and README, the root
    ``marketstall.toml``, and the share-url marker block in the root README
    and every ``barn/*/README.md``. Showing it is the point: a user must be
    able to see why a sibling library's README is in their commit.
    """
    if pipeline.version is None:
        raise PipelineStateError("plan_commit() needs a version — run apply_bump() (step 3) first.")
    files = list(pipeline.written)
    return CommitPlan(
        files=files,
        barn_dirty=barn_dirty_files(pipeline),
        message=message or f"chore: share v{pipeline.version}",
        tag=f"v{pipeline.version}",
        diffstat=_diffstat(pipeline, files),
    )


def _diffstat(pipeline: "SharePipeline", files: list[Path]) -> str:
    """``git diff --stat`` limited to *files*, plus new/deleted-path labels.

    ``git diff --stat HEAD`` only ever shows tracked, modified content —
    it says nothing about an untracked path (nothing to diff against) or a
    path that no longer exists on disk (a rename-orphan doc the docs
    generator deleted; see :func:`write_set`). Those two cases are
    classified per-path via ``git status --porcelain``, using the same
    two-character index/worktree code convention as
    :func:`barn_dirty_files`:

    - ``??`` (untracked)                    → "(new file)"
    - index or worktree char is ``D``        → "(deleted)"
    - anything else (tracked, modified)      → omitted; already present
      in the ``git diff --stat`` block above, so appending it again would
      duplicate the line.

    Purely cosmetic — the commit stages from ``files`` via
    ``git add -A -- <paths>``, never from this string, so a failed
    ``git diff``/``git status`` degrades to an empty or partial summary
    rather than an error. That also covers a repo with no commits yet,
    where ``HEAD`` does not resolve.
    """
    if not files:
        return ""
    rel = [str(p.relative_to(pipeline.repo_root)) for p in files if p.is_relative_to(pipeline.repo_root)]
    if not rel:
        return ""
    tracked_diff = git(["diff", "--stat", "HEAD", "--", *rel], cwd=pipeline.repo_root)
    stdout = tracked_diff.stdout if tracked_diff.ok else ""
    lines = stdout.strip().splitlines() if stdout.strip() else []

    status = git(["status", "--porcelain", "--", *rel], cwd=pipeline.repo_root)
    codes: dict[str, str] = {}
    if status.ok:
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            code, path_part = line[:2], line[3:].strip()
            if " -> " in path_part:
                path_part = path_part.split(" -> ", 1)[1]
            codes[path_part.strip('"')] = code

    for path_str in rel:
        code = codes.get(path_str, "")
        if code == "??":
            lines.append(f" {path_str} (new file)")
        elif "D" in code:
            lines.append(f" {path_str} (deleted)")
    return "\n".join(lines)


def apply(
    pipeline: "SharePipeline",
    commit_plan: CommitPlan,
    *,
    include_barn: list[Path] | None = None,
) -> CommitResult:
    """Stage exactly ``plan.files`` plus ``include_barn``, commit, then tag.

    Never ``-a``/``-A``. Staging is an explicit path list so a user's
    unrelated work-in-progress cannot land in a wizard-authored commit.
    There is no checkpoint commit either: the pre-wizard ``HEAD`` is already
    the rollback anchor, and the wizard authors exactly one commit.

    The tag is created only after the commit succeeds — a tag on the wrong
    commit is worse than no tag.
    """
    to_stage = [*commit_plan.files, *(include_barn or [])]
    if not to_stage:
        raise CommitError("Nothing to commit — no files were written.")

    rel = [
        str(p.relative_to(pipeline.repo_root)) if p.is_relative_to(pipeline.repo_root) else str(p)
        for p in to_stage
    ]
    # `git add -A -- <paths>` stages deletions as well as modifications
    # within the given paths only; without -A a deleted file is skipped and
    # the stale version ships. The paths keep the scope explicit.
    staged = git(["add", "-A", "--", *rel], cwd=pipeline.repo_root)
    if not staged.ok:
        raise CommitError(f"Could not stage files: {staged.stderr.strip()}", stderr=staged.stderr)

    # -m takes the message as an argv element, so shell metacharacters in a
    # user-supplied message are literal text.
    commit = git(["commit", "-m", commit_plan.message], cwd=pipeline.repo_root, timeout=60.0)
    if not commit.ok:
        raise CommitError(
            f"Commit failed: {(commit.stderr or commit.stdout).strip()}",
            stderr=commit.stderr or commit.stdout,
        )

    sha = git(["rev-parse", "HEAD"], cwd=pipeline.repo_root).stdout.strip()

    tagged = git(["tag", commit_plan.tag], cwd=pipeline.repo_root)
    if not tagged.ok:
        raise CommitError(
            f"Committed {sha[:8]} but could not create tag {commit_plan.tag}: {tagged.stderr.strip()}\n"
            f"Create it yourself with: git tag {commit_plan.tag}",
            stderr=tagged.stderr,
        )

    return CommitResult(sha=sha, tag=commit_plan.tag, files=to_stage)
