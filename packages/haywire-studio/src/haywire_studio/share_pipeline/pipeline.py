"""``SharePipeline`` — the stateful engine behind every share caller.

Later steps consume earlier steps' outputs: drift resolution precedes docs, the
bumped version feeds both the docs render and the marketstall entry, and the
final commit's file list is the union of every step's writes. A stateful object
keeps that sequencing in one place instead of re-derived by each caller, and
maps onto the wizard's linear resumable stepper.

Each step is a check/plan call that mutates nothing plus an apply call that
does.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Callable

import toml

from haywire.core.library.decorator_io import _set_decorator_list_field
from haywire.core.library.dep_detect import (
    EntryPointLibrarySource,
    detect_deps,
    find_module_dir,
    set_pyproject_dependencies,
)
from haywire_studio.share import (
    InvalidOsDeclarationError,
    ManifestReadError,
    MarketstallWriteResult,
    NoBarnError,
    apply_drift_fix,
    detect_share_drift,
    read_manifest,
    write_marketstall,
)
from haywire_studio.share_pipeline.errors import (
    CommitError,
    DocsGenerationError,
    ManifestError,
    MarketstallError,
    PipelineStateError,
    PreconditionsError,
    PushError,
    TagCollisionError,
    VersionError,
)
from haywire_studio.share_pipeline.gitcmd import git, git_remote, git_remote_streaming, run_streaming
from haywire_studio.share_pipeline.results import (
    BarnDirtyFile,
    BumpResult,
    CommitPlan,
    CommitResult,
    DocsResult,
    DriftReport,
    PreconditionFailure,
    PreconditionsReport,
    PushResult,
    VersionPlan,
)
from haywire_studio.share_pipeline.versions import (
    next_version,
    plan_versions,
    refresh_lockfile,
    write_barn_versions,
)

GIT_INSTALL_HINT = (
    "macOS (Homebrew):  brew install git\n"
    "Ubuntu/Debian:     sudo apt-get install git\n"
    "Windows:           https://git-scm.com/download/win"
)

_NO_REMOTE_HINT = "git remote add origin <your-repo-url>\ngit push -u origin <branch-name>"

# Shared by every step that reads/writes a library manifest (pyproject.toml,
# and the __init__.py decorator kept in sync with it): a malformed file or an
# I/O failure must translate to a ShareError subclass before it can reach a
# wizard step handler's `except ShareError`, never surface as the raw
# exception type.
_MANIFEST_FAILURE_TYPES = (ManifestReadError, toml.TomlDecodeError, OSError)


class SharePipeline:
    """Drives one project's publish, one step at a time.

    Args:
        repo_root: The project root — the uv workspace root holding ``barn/``,
            ``marketstall.toml``, and the git repo.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        # Accumulated write set. Every apply step appends the files it wrote;
        # step 5 stages exactly this list (plus any barn files the user opted
        # in) and never uses `git add -A`.
        self.written: list[Path] = []
        self.remote_url: str | None = None
        # Set when the user chose to continue past unresolved drift rather than
        # fix it. Step 5 records it in nothing — it exists so a caller can tell
        # "clean" from "acknowledged" without re-running detection.
        self.drift_acknowledged = False
        self.version: str | None = None

    # ── Step 1: preconditions ────────────────────────────────────────────────

    def check_preconditions(self) -> PreconditionsReport:
        """Verify everything needed to publish, collecting ALL failures.

        Reports rather than raises so the wizard's first panel can explain why
        a workspace cannot be shared. The menu item is always enabled — a
        disabled one cannot carry a tooltip, since the design guide's disabled
        state includes ``pointer-events: none`` (design-guide.md:725).

        The remote reachability check is ``git ls-remote --symref origin
        HEAD``: it exercises the exact credential path ``git push`` uses, so
        an auth failure surfaces here rather than after a commit and tag
        already exist. ``--symref`` narrows the round-trip to one ref instead
        of every ref, and its output additionally names the remote's default
        branch (``ref: refs/heads/<name>\\tHEAD``), which the non-default-
        branch check below needs. ``git symbolic-ref refs/remotes/origin/HEAD``
        is NOT a usable local substitute for that — it is unset in this very
        repo (nothing populates it without an explicit ``git remote set-head``)
        — so the remote round-trip is the only reliable source.

        Every ``barn/*`` library's ``pyproject.toml`` is parsed with
        :func:`read_manifest`; a malformed file or an invalid ``os``
        declaration is reported here rather than surfacing later as a crash
        mid-docs-generation or a silently wrong marketstall entry.

        The detached-HEAD and non-default-branch checks below always run —
        there is no way to bypass them.
        """
        failures: list[PreconditionFailure] = []
        remote_url: str | None = None
        default_branch: str | None = None

        version = git(["--version"], cwd=self.repo_root, timeout=10.0)
        if not version.ok:
            # Nothing else is checkable without git — every remaining probe
            # would report the same missing binary as a different symptom.
            return PreconditionsReport(
                failures=[PreconditionFailure(message="git is not installed.", remedy=GIT_INSTALL_HINT)],
                remote_url=None,
                barn_libraries=[],
            )

        barn = self.repo_root / "barn"
        barn_libraries: list[Path] = []
        if not barn.is_dir():
            failures.append(
                PreconditionFailure(
                    message=f"No barn/ directory at {self.repo_root}. Is this a haywire project root?",
                    remedy=(
                        "Run this from your haywire project root (the directory containing "
                        "barn/), or run `haywire init <name>` to scaffold a new project."
                    ),
                )
            )
        else:
            barn_libraries = sorted(
                d for d in barn.iterdir() if d.is_dir() and (d / "pyproject.toml").is_file()
            )
            if not barn_libraries:
                failures.append(
                    PreconditionFailure(
                        message=f"No library with a pyproject.toml under {barn}. Nothing to publish.",
                        remedy=(
                            "Add a library under barn/, each with its own pyproject.toml — "
                            "see docs/haybale/haybale-package-canon.md for the expected layout."
                        ),
                    )
                )

        for lib_dir in barn_libraries:
            pyproject_path = lib_dir / "pyproject.toml"
            try:
                rel_path = pyproject_path.relative_to(self.repo_root)
            except ValueError:
                rel_path = pyproject_path
            try:
                read_manifest(lib_dir)
            except InvalidOsDeclarationError as exc:
                failures.append(
                    PreconditionFailure(
                        message=f"Invalid manifest at {rel_path}: {exc}",
                        remedy=(
                            "[tool.haywire].os may only declare `macos`, `windows`, `linux`. "
                            "`other` is a runtime sentinel for platforms that don't map to one "
                            "of those three — it is set at runtime and must never be declared. "
                            "Remove it (or the whole invalid entry) from the list."
                        ),
                    )
                )
            except ManifestReadError as exc:
                failures.append(
                    PreconditionFailure(
                        message=f"Could not read {rel_path}: {exc}",
                        remedy=f"Fix the TOML in {rel_path} so it parses, then try again.",
                    )
                )

        remote = git(["remote", "get-url", "origin"], cwd=self.repo_root, timeout=10.0)
        if not remote.ok or not remote.stdout.strip():
            failures.append(
                PreconditionFailure(message="No 'origin' remote is configured.", remedy=_NO_REMOTE_HINT)
            )
        else:
            remote_url = remote.stdout.strip()
            reachable = git_remote(
                ["ls-remote", "--symref", "origin", "HEAD"], cwd=self.repo_root, timeout=60.0
            )
            if not reachable.ok:
                detail = (reachable.stderr or reachable.stdout).strip().splitlines()
                first = detail[0] if detail else f"exit {reachable.returncode}"
                failures.append(
                    PreconditionFailure(
                        message=f"Cannot reach origin ({remote_url}): {first}",
                        remedy="Check the URL and your credentials, then try again.",
                    )
                )
            else:
                # Absent when the remote has never had anything pushed to it
                # (an empty repo has no HEAD to symref) — that is "nothing has
                # ever been shared", not a failure, so default_branch simply
                # stays None and the non-default-branch check below is skipped.
                for line in reachable.stdout.splitlines():
                    left, sep, right = line.partition("\t")
                    if sep and right.strip() == "HEAD" and left.startswith("ref: refs/heads/"):
                        default_branch = left.removeprefix("ref: refs/heads/").strip()
                        break

        symbolic = git(["symbolic-ref", "-q", "HEAD"], cwd=self.repo_root, timeout=10.0)
        if not symbolic.ok:
            # Genuinely detached: HEAD points straight at a commit rather
            # than a branch ref. `current_branch() == "HEAD"` alone is NOT
            # this test — an unborn branch (a fresh repo before its first
            # commit) prints the same literal "HEAD" from `rev-parse
            # --abbrev-ref HEAD` while `symbolic-ref` still succeeds, so
            # relying on that string would misreport a brand-new project.
            failures.append(
                PreconditionFailure(
                    message="HEAD is detached — no branch is currently checked out.",
                    remedy=self._detached_head_remedy(),
                )
            )
        elif default_branch is not None:
            current = self.current_branch()
            if current != default_branch:
                failures.append(
                    PreconditionFailure(
                        message=(
                            f"Currently on `{current}`, but the repository's default branch "
                            f"is `{default_branch}`."
                        ),
                        remedy=(
                            f"Switch to the default branch and publish from there: "
                            f"`git switch {default_branch}`."
                        ),
                    )
                )

        if not failures:
            self.remote_url = remote_url

        return PreconditionsReport(
            failures=failures,
            remote_url=remote_url,
            barn_libraries=barn_libraries,
            default_branch=default_branch,
        )

    def _detached_head_remedy(self) -> str:
        """Remedy text for a detached HEAD, computed from ``git branch --contains HEAD``.

        Each line is prefixed ``"* "`` (current) or ``"  "`` (other); a
        detached HEAD also shows a synthetic ``(HEAD detached at <sha>)`` /
        ``(HEAD detached from <sha>)`` line, which is not a real branch name
        and is filtered out. If no real branch remains — a dangling commit no
        branch was ever built from — the remedy falls back to naming a new
        one.
        """
        result = git(["branch", "--contains", "HEAD"], cwd=self.repo_root, timeout=10.0)
        names = []
        for line in result.stdout.splitlines():
            name = line[2:].strip() if len(line) >= 2 else line.strip()
            if not name or name.startswith("(HEAD detached"):
                continue
            names.append(name)

        if names:
            quoted = ", ".join(f"`{n}`" for n in names)
            return f"This commit is on {quoted} — run `git switch {names[0]}`."
        return (
            "This commit is not on any branch — run `git switch -c my-branch` to create one, "
            "then publish from there."
        )

    def require_preconditions(self) -> PreconditionsReport:
        """:meth:`check_preconditions`, raising :class:`PreconditionsError` on failure."""
        report = self.check_preconditions()
        if not report.ok:
            raise PreconditionsError(report.failures)
        return report

    def _record(self, paths: list[Path]) -> list[Path]:
        """Append *paths* to the accumulated write set, de-duplicated, and return them.

        Step 5 stages exactly ``self.written``, so a duplicate would make the
        commit preview lie about how many files changed.
        """
        for path in paths:
            if path not in self.written:
                self.written.append(path)
        return paths

    # ── Step 2: dependency drift ─────────────────────────────────────────────

    def check_drift(self) -> DriftReport:
        """Run the drift gate against every barn library.

        Splits findings into actionable drift (a decision) and unresolved-only
        (informational). Reuses the same ``detect_share_drift`` the Edit
        dialog's "Detect dependencies" flow uses, so the wizard's diff modal
        shows what users already recognise.
        """
        drifted: list[object] = []
        unresolved_only: list[object] = []
        for lib_dir in self._barn_library_dirs():
            drift = detect_share_drift(lib_dir)
            if drift.has_drift:
                drifted.append(drift)
            elif drift.unresolved:
                unresolved_only.append(drift)
        return DriftReport(drifted=drifted, unresolved_only=unresolved_only)

    def apply_drift_union(self, report: DriftReport) -> list[Path]:
        """Merge detected deps into what's declared. Additive — removes nothing."""
        written: list[Path] = []
        for drift in report.drifted:
            try:
                apply_drift_fix(drift)
            except _MANIFEST_FAILURE_TYPES as exc:
                raise ManifestError(str(exc)) from exc
            written.extend(self._drift_written_paths(drift.lib_dir))
        return self._record(written)

    def apply_drift_replace(self, report: DriftReport) -> list[Path]:
        """Overwrite declared deps with exactly what was detected.

        Destructive by design: a declaration the source no longer imports is
        removed. That is why step 2 is a decision and not an auto-fix.
        """
        written: list[Path] = []
        libraries = EntryPointLibrarySource()
        for drift in report.drifted:
            lib_dir = drift.lib_dir
            detected = detect_deps(lib_dir, libraries=libraries)

            try:
                set_pyproject_dependencies(lib_dir, sorted(detected.pyproject))
                written.append(lib_dir / "pyproject.toml")

                module_dir = find_module_dir(lib_dir)
                if module_dir is not None:
                    init_file = module_dir / "__init__.py"
                    if init_file.is_file():
                        content = _set_decorator_list_field(
                            init_file.read_text(),
                            "dependencies",
                            sorted(detected.library_decorator),
                        )
                        init_file.write_text(content)
                        written.append(init_file)
            except _MANIFEST_FAILURE_TYPES as exc:
                raise ManifestError(str(exc)) from exc
        return self._record(written)

    def acknowledge_drift(self) -> None:
        """Record that the user chose to publish without resolving drift."""
        self.drift_acknowledged = True

    def _drift_written_paths(self, lib_dir: Path) -> list[Path]:
        """The files ``apply_drift_fix`` may have touched for one library.

        ``apply_drift_fix`` returns nothing, so the paths are reconstructed
        here. Both are included unconditionally: a path already identical on
        disk is a no-op for ``git add``, whereas a missed path would silently
        leave a fix out of the commit.
        """
        paths = [lib_dir / "pyproject.toml"]
        module_dir = find_module_dir(lib_dir)
        if module_dir is not None and (module_dir / "__init__.py").is_file():
            paths.append(module_dir / "__init__.py")
        return paths

    def _barn_library_dirs(self) -> list[Path]:
        """Every ``barn/*`` directory holding a pyproject.toml, sorted."""
        barn = self.repo_root / "barn"
        if not barn.is_dir():
            return []
        return sorted(d for d in barn.iterdir() if d.is_dir() and (d / "pyproject.toml").is_file())

    # ── Step 3: version bump (lockstep) ──────────────────────────────────────

    def plan_version(self) -> VersionPlan:
        """The current lockstep state plus the bumps available from it."""
        return plan_versions(self.repo_root)

    def check_tag_available(self, version: str) -> None:
        """Raise :class:`TagCollisionError` if ``v<version>`` already exists.

        Checked here, before anything is written, because this is where the fix
        is cheapest — "pick 0.3.2 instead" costs nothing, whereas discovering
        the collision at tag time leaves a commit already made.

        An unreachable remote is NOT treated as a collision: that is step 1's
        job to report, and inferring "taken" from "could not ask" would block a
        legitimate publish.
        """
        tag = f"v{version}"

        local = git(["rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=self.repo_root)
        remote_probe = git_remote(["ls-remote", "--tags", "origin", tag], cwd=self.repo_root)
        remote_hit = remote_probe.ok and f"refs/tags/{tag}" in remote_probe.stdout

        if local.ok or remote_hit:
            raise TagCollisionError(tag=tag, local=local.ok, remote=remote_hit)

    def apply_bump(self, spec: str) -> BumpResult:
        """Resolve *spec*, verify the tag is free, then bump every barn library.

        *spec* is ``"patch"``/``"minor"``/``"major"`` or an explicit ``X.Y.Z``.
        A keyword against libraries whose versions disagree raises
        :class:`VersionError`: there is no honest arithmetic to apply, and
        picking one sibling's version would downgrade the others.

        ``uv lock`` is always attempted (the lockfile records member versions
        and drifts a release behind otherwise) but never blocks — a failure
        comes back as ``lock_warning``.
        """
        plan = self.plan_version()
        if spec not in ("patch", "minor", "major"):
            version = next_version(spec, None)
        elif plan.common_version is None:
            versions = ", ".join(f"{v.name} {v.version or '(none)'}" for v in plan.current)
            raise VersionError(
                f"Barn library versions disagree ({versions}), so a '{spec}' bump is ambiguous. "
                "Supply an explicit X.Y.Z target."
            )
        else:
            version = next_version(spec, plan.common_version)

        self.check_tag_available(version)

        written = write_barn_versions(self.repo_root, version)
        self._record(written)

        lock_refreshed, lock_warning = refresh_lockfile(self.repo_root)
        if lock_refreshed:
            self._record([self.repo_root / "uv.lock"])

        self.version = version
        return BumpResult(
            version=version,
            written=written,
            lock_refreshed=lock_refreshed,
            lock_warning=lock_warning,
        )

    # ── Step 4: regenerate docs ──────────────────────────────────────────────

    def docs_command(self, json_path: Path | None = None) -> list[str]:
        """The argv for docs generation. ``--all``, always a subprocess.

        A subprocess because ``generate_docs()`` builds a SECOND library system
        whose ``initialize()`` calls ``set_global_injector()``, which in-studio
        repoints the live app's globals at a throwaway system (DI context is
        module-level globals, not ContextVar). ``extract_library`` also
        instantiates every node in a throwaway graph to read ports, which
        in-process would construct hardware-touching nodes inside the live app.
        See ``.insights/project_docs_gen_reentrancy.md``.

        ``--all`` rather than N per-library runs: one library-system load for
        the whole barn, and its root-relative filter naturally excludes
        site-packages installs and ``--dev`` mode's out-of-tree dev-repo
        libraries.
        """
        target = str(json_path) if json_path is not None else "<json-path>"
        # Bare "haywire": the console script installed by haywire-studio's
        # [project.scripts] entry point, resolved via PATH. The venv's bin/ is
        # on PATH whenever the studio itself is runnable, so this stays on the
        # same interpreter/virtualenv as the caller without hardcoding a path.
        return ["haywire", "docs", "--all", "--json", target]

    async def apply_docs(self, on_output: Callable[[str], None] | None = None) -> DocsResult:
        """Regenerate every barn library's docs. Always runs — no yes/no gate.

        Must run AFTER the version bump: ``render_quickref`` embeds
        ``v{doc.version}``, so generating first would publish a QUICKREF
        stating the previous version.

        Coverage gaps are read-only feedback and never fail the step; only a
        non-zero exit (a crash) raises :class:`DocsGenerationError`.
        """
        sink = on_output or (lambda _line: None)
        tmp_dir = Path(tempfile.mkdtemp(prefix="hw-share-docs-"))
        json_path = tmp_dir / "coverage.json"
        try:
            result = await run_streaming(
                self.docs_command(json_path),
                cwd=self.repo_root,
                on_output=sink,
            )
            if not result.ok:
                raise DocsGenerationError(
                    f"Docs generation failed (exit {result.returncode}). The output above shows what broke.",
                    output=result.stdout or result.stderr,
                )

            coverage: dict[str, list[str]] = {}
            if json_path.is_file():
                try:
                    coverage = json.loads(json_path.read_text())
                except json.JSONDecodeError as exc:
                    raise DocsGenerationError(
                        f"Docs generation wrote an unreadable coverage report: {exc}",
                        output=result.stdout,
                    ) from exc
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        written = self.docs_write_set()
        self._record(written)
        return DocsResult(coverage=coverage, written=written, output=result.stdout)

    def docs_write_set(self) -> list[Path]:
        """Doc files under ``barn/`` that now differ from HEAD.

        Read from ``git status --porcelain`` rather than predicted, because the
        generator's file set is data-dependent: it writes OVERVIEW/QUICKREF/
        README plus one file per component, and DELETES orphaned per-component
        docs when a component is renamed (generate.py:87). A deletion left out
        of the commit ships a stale doc.

        Scoped to ``barn/`` — only barn content reaches consumers, and sweeping
        up unrelated dirt is what makes a wizard commit untrustworthy.
        """
        status = git(["status", "--porcelain", "--", "barn"], cwd=self.repo_root)
        if not status.ok:
            return []

        out: list[Path] = []
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            path_part = line[3:].strip()
            # Renames print "old -> new"; the new path is what to stage.
            if " -> " in path_part:
                path_part = path_part.split(" -> ", 1)[1]
            path_part = path_part.strip('"')
            path = self.repo_root / path_part
            if path.suffix.lower() == ".md":
                out.append(path)
        return sorted(set(out))

    # ── Step 5: marketstall + commit + tag ───────────────────────────────────

    def apply_marketstall(self) -> MarketstallWriteResult:
        """Rebuild ``marketstall.toml`` from every ``barn/*`` library.

        Always a FULL rebuild: the feed's contract is "every haybale this repo
        offers", so rebuilding from disk is what keeps it true. A partial
        rebuild deletes the entries of libraries not in this run.

        Also rewrites the ``<!-- marketstall:share-url -->`` marker block in the
        root README and every ``barn/*/README.md``.
        """
        try:
            result = write_marketstall(self.repo_root)
        except (NoBarnError, *_MANIFEST_FAILURE_TYPES) as exc:
            raise MarketstallError(str(exc)) from exc
        self._record(result.written)
        return result

    def barn_dirty_files(self) -> list[BarnDirtyFile]:
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
            cwd=self.repo_root,
        )
        if not status.ok:
            return []

        own = set(self.written)
        out: list[BarnDirtyFile] = []
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            code, path_part = line[:2], line[3:].strip()
            if " -> " in path_part:
                path_part = path_part.split(" -> ", 1)[1]
            path = self.repo_root / path_part.strip('"')
            if path in own:
                continue
            out.append(BarnDirtyFile(path=path, untracked=code == "??"))
        return sorted(out, key=lambda d: d.path)

    def plan_commit(self, *, message: str | None = None) -> CommitPlan:
        """Preview exactly what would be staged, committed, and tagged.

        The write set spans the repo — every ``barn/*/pyproject.toml``, the root
        ``uv.lock``, each library's OVERVIEW/QUICKREF/``docs/*.md`` (including
        deletions for renamed components) and README, the root
        ``marketstall.toml``, and the share-url marker block in the root README
        and every ``barn/*/README.md``. Showing it is the point: a user must be
        able to see why a sibling library's README is in their commit.
        """
        if self.version is None:
            raise PipelineStateError("plan_commit() needs a version — run apply_bump() (step 3) first.")
        files = list(self.written)
        return CommitPlan(
            files=files,
            barn_dirty=self.barn_dirty_files(),
            message=message or f"chore: share v{self.version}",
            tag=f"v{self.version}",
            diffstat=self._diffstat(files),
        )

    def _diffstat(self, files: list[Path]) -> str:
        """``git diff --stat`` limited to *files*, including untracked ones.

        Untracked files have no diff to show, so they are appended as
        "(new file)" lines instead. Purely cosmetic — the commit stages from
        ``files``, never from this string, so a failed ``git diff`` degrades to
        an empty summary rather than an error. That also covers a repo with no
        commits yet, where ``HEAD`` does not resolve.
        """
        if not files:
            return ""
        rel = [str(p.relative_to(self.repo_root)) for p in files if p.is_relative_to(self.repo_root)]
        if not rel:
            return ""
        tracked_diff = git(["diff", "--stat", "HEAD", "--", *rel], cwd=self.repo_root)
        stdout = tracked_diff.stdout if tracked_diff.ok else ""
        lines = stdout.strip().splitlines() if stdout.strip() else []
        for path_str in rel:
            if path_str not in stdout:
                lines.append(f" {path_str} (new file)")
        return "\n".join(lines)

    def current_branch(self) -> str:
        """The current branch name, or ``"HEAD"`` when detached."""
        result = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo_root)
        return result.stdout.strip() or "HEAD"

    def push_command(self) -> list[str]:
        """The push argv, also shown verbatim in error panels for manual retry."""
        tag = f"v{self.version}" if self.version else ""
        args = ["push", "origin", f"HEAD:{self.current_branch()}"]
        if tag:
            args.append(tag)
        return args

    def verify_push_allowed(self) -> None:
        """``git push --dry-run`` — verify the remote will accept this push.

        Run immediately BEFORE the commit, closing the race window opened at
        step 1: someone else may have pushed meanwhile, and discovering that
        after a commit and tag exist means the user has to clean up.

        Mirrors the marketplace's ``dry_run()`` → ``install()`` pairing
        (library_manager.py:273): pre-flight verification over post-failure
        recovery, because nothing needs undoing if nothing was mutated.
        """
        branch = self.current_branch()
        probe = git_remote(
            ["push", "--dry-run", "origin", f"HEAD:{branch}"],
            cwd=self.repo_root,
            timeout=120.0,
        )
        if not probe.ok:
            raise PushError(
                stderr=(probe.stderr or probe.stdout).strip(),
                manual_command="git " + " ".join(self.push_command()),
            )

    def apply_commit(
        self,
        plan: CommitPlan,
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
        to_stage = [*plan.files, *(include_barn or [])]
        if not to_stage:
            raise CommitError("Nothing to commit — no files were written.")

        rel = [
            str(p.relative_to(self.repo_root)) if p.is_relative_to(self.repo_root) else str(p)
            for p in to_stage
        ]
        # `git add -A -- <paths>` stages deletions as well as modifications
        # within the given paths only; without -A a deleted file is skipped and
        # the stale version ships. The paths keep the scope explicit.
        staged = git(["add", "-A", "--", *rel], cwd=self.repo_root)
        if not staged.ok:
            raise CommitError(f"Could not stage files: {staged.stderr.strip()}", stderr=staged.stderr)

        # -m takes the message as an argv element, so shell metacharacters in a
        # user-supplied message are literal text.
        commit = git(["commit", "-m", plan.message], cwd=self.repo_root, timeout=60.0)
        if not commit.ok:
            raise CommitError(
                f"Commit failed: {(commit.stderr or commit.stdout).strip()}",
                stderr=commit.stderr or commit.stdout,
            )

        sha = git(["rev-parse", "HEAD"], cwd=self.repo_root).stdout.strip()

        tagged = git(["tag", plan.tag], cwd=self.repo_root)
        if not tagged.ok:
            raise CommitError(
                f"Committed {sha[:8]} but could not create tag {plan.tag}: {tagged.stderr.strip()}\n"
                f"Create it yourself with: git tag {plan.tag}",
                stderr=tagged.stderr,
            )

        return CommitResult(sha=sha, tag=plan.tag, files=to_stage)

    # ── Step 6: push ─────────────────────────────────────────────────────────

    async def apply_push(self, on_output: Callable[[str], None] | None = None) -> PushResult:
        """Push the commit and tag to ``origin``, for all callers.

        Env-hardened via :func:`git_remote_streaming`, so a missing credential
        becomes a clean error rather than an indefinite hang with no TTY. On
        failure the raised :class:`PushError` carries the exact command to run
        by hand, and the step is retryable in place — nothing here mutates
        pipeline state.
        """
        if self.version is None:
            raise PipelineStateError("apply_push() needs a version — run apply_bump() (step 3) first.")

        sink = on_output or (lambda _line: None)
        branch = self.current_branch()
        args = self.push_command()

        result = await git_remote_streaming(
            args,
            cwd=self.repo_root,
            on_output=sink,
            timeout=600.0,
        )
        if not result.ok:
            raise PushError(
                stderr=(result.stderr or result.stdout).strip(),
                manual_command="git " + " ".join(args),
            )
        return PushResult(
            remote="origin",
            branch=branch,
            tag=f"v{self.version}",
            output=result.stdout,
        )
