"""Step 1 — the combined precondition gate."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit


from haywire.core.marketstall.host_providers import resolve_host, ssh_to_https
from haywire_studio.packaging.share.git import git, git_remote
from haywire_studio.packaging.share.manifest.errors import InvalidOsDeclarationError, ManifestReadError
from haywire_studio.packaging.share.manifest.os_field import describe_os_fix, invalid_os_values
from haywire_studio.packaging.share.manifest.reader import read_manifest
from haywire_studio.packaging.share.pipeline.results import PreconditionFailure, PreconditionsReport

if TYPE_CHECKING:
    from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline

GIT_INSTALL_HINT = (
    "macOS (Homebrew):  brew install git\n"
    "Ubuntu/Debian:     sudo apt-get install git\n"
    "Windows:           https://git-scm.com/download/win"
)

_NO_REMOTE_HINT = "git remote add origin <your-repo-url>\ngit push -u origin <branch-name>"


def check(pipeline: "SharePipeline") -> PreconditionsReport:
    """Verify everything needed to publish. Stops at the FIRST failure.

    Reports rather than raises so the wizard's first panel can explain why
    a workspace cannot be shared. The menu item is always enabled — a
    disabled one cannot carry a tooltip, since the design guide's disabled
    state includes ``pointer-events: none`` (design-guide.md:725).

    Stop-at-first-failure (not collect-all): an earlier failure can make a
    later probe's result moot or misleading — a dirty working tree means
    nothing else matters until it's clean; an unreachable-because-nonexistent
    origin makes the reachability round-trip wasted; an unrecognized host
    makes the reachability probe against it wasted too. Each probe below
    returns immediately once it finds a problem, so ``PreconditionsReport``
    never carries more than one failure. The wizard exits to a remedy modal
    on any failure and the user restarts it after fixing what's reported —
    cheap enough that this costs nothing (see the Share Wizard Preflight
    Gate plan, 2026-08-05).

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
    """
    version = git(["--version"], cwd=pipeline.repo_root, timeout=10.0)
    if not version.ok:
        # Nothing else is checkable without git — every remaining probe
        # would report the same missing binary as a different symptom.
        return PreconditionsReport(
            failures=[PreconditionFailure(message="git is not installed.", remedy=GIT_INSTALL_HINT)],
            remote_url=None,
            barn_libraries=[],
        )

    # Whole repo, not scoped to barn/: if the tree is proven clean before the
    # wizard writes anything, any dirt found after a later-step failure is
    # provably this run's own writes, which is what makes a blanket revert
    # safe (see steps/rollback.py). git status --porcelain covers staged,
    # unstaged, and untracked files.
    dirty = git(["status", "--porcelain"], cwd=pipeline.repo_root, timeout=10.0)
    if dirty.ok and dirty.stdout.strip():
        dirty_files = [line[3:].strip() for line in dirty.stdout.splitlines() if line.strip()]
        listed = "\n".join(f"  {f}" for f in dirty_files)
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message=f"Working tree is not clean:\n{listed}",
                    remedy=(
                        "Commit or stash these changes before sharing. The publish pipeline "
                        "reverts everything it writes on failure by resetting the whole working "
                        "tree — anything already uncommitted here would be lost along with it, "
                        "so nothing may be dirty before the wizard starts."
                    ),
                    kind="act",
                    fix_id="commit_dirty_tree",
                    fix_label="Commit changes",
                )
            ],
            remote_url=None,
            barn_libraries=[],
        )

    barn = pipeline.repo_root / "barn"
    barn_libraries: list[Path] = []
    if not barn.is_dir():
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message=f"No barn/ directory at {pipeline.repo_root}. Is this a haywire project root?",
                    remedy=(
                        "Run this from your haywire project root (the directory containing "
                        "barn/), or run `haywire init <name>` to scaffold a new project."
                    ),
                )
            ],
            remote_url=None,
            barn_libraries=[],
        )

    barn_libraries = pipeline._barn_library_dirs()
    if not barn_libraries:
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message=f"No library with a pyproject.toml under {barn}. Nothing to publish.",
                    remedy=(
                        "Add a library under barn/, each with its own pyproject.toml — "
                        "see docs/haybale/haybale-package-canon.md for the expected layout."
                    ),
                )
            ],
            remote_url=None,
            barn_libraries=[],
        )

    for lib_dir in barn_libraries:
        pyproject_path = lib_dir / "pyproject.toml"
        try:
            rel_path = pyproject_path.relative_to(pipeline.repo_root)
        except ValueError:
            rel_path = pyproject_path
        try:
            rel_lib_dir = lib_dir.relative_to(pipeline.repo_root)
        except ValueError:
            rel_lib_dir = lib_dir
        try:
            read_manifest(lib_dir)
        except InvalidOsDeclarationError as exc:
            # invalid_os_values() re-reads the raw list to compute what
            # the fix would actually do — read_manifest() above already
            # proved the TOML parses (only validation failed), so this
            # read cannot legitimately raise ManifestReadError here.
            invalid_values = invalid_os_values(lib_dir)
            return PreconditionsReport(
                failures=[
                    PreconditionFailure(
                        message=f"Invalid manifest at {rel_path}: {exc}",
                        remedy=(
                            "[tool.haywire].os may only declare `macos`, `windows`, `linux`. "
                            "`other` is a runtime sentinel for platforms that don't map to one "
                            "of those three — it is set at runtime and must never be declared. "
                            "Remove it (or the whole invalid entry) from the list."
                        ),
                        kind="act",
                        fix_id="strip_os",
                        fix_label=describe_os_fix(invalid_values),
                        lib_dir=str(rel_lib_dir),
                    )
                ],
                remote_url=None,
                barn_libraries=barn_libraries,
            )
        except ManifestReadError as exc:
            return PreconditionsReport(
                failures=[
                    PreconditionFailure(
                        message=f"Could not read {rel_path}: {exc}",
                        remedy=f"Fix the TOML in {rel_path} so it parses, then try again.",
                    )
                ],
                remote_url=None,
                barn_libraries=barn_libraries,
            )

    # No framework-consistency check: the marketstall's `require` is derived
    # from each library's pyproject floor at write time, so the two carriers
    # cannot disagree. The invariant is asserted by a unit test over
    # write_marketstall rather than re-checked on every publish.

    remote = git(["remote", "get-url", "origin"], cwd=pipeline.repo_root, timeout=10.0)
    if not remote.ok or not remote.stdout.strip():
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message="No 'origin' remote is configured.",
                    remedy=_NO_REMOTE_HINT,
                    kind="act",
                    fix_id="add_origin",
                    fix_label="Add origin remote",
                )
            ],
            remote_url=None,
            barn_libraries=barn_libraries,
        )

    remote_url = remote.stdout.strip()

    # Host recognition applies only to remotes that NAME a network host.
    # `git remote get-url` legitimately returns a local filesystem path
    # (`/srv/git/foo.git`, a sibling clone, a test's bare repo), for which
    # urlsplit() yields an empty hostname. That is not-a-host, not an
    # unrecognized host: there is no config entry that would make it
    # recognizable and nothing for the marketstall to build a browser URL
    # from, so the probe has no opinion and skips. ssh_to_https() runs first
    # so the scp form (git@host:owner/repo) resolves to its real hostname
    # rather than falling into this same empty-hostname branch.
    https_url = ssh_to_https(remote_url).removesuffix(".git").rstrip("/")
    hostname = (urlsplit(https_url).hostname or "").lower()
    if hostname and resolve_host(hostname) is None:
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message=f"Host '{hostname}' is not recognized.",
                    remedy=(
                        f"Add this to ~/.haywire/config.toml:\n\n"
                        f"[[hosts]]\n"
                        f'hostname = "{hostname}"\n'
                        f'provider = "gitlab"   # or "github"\n\n'
                        f"This only teaches haywire how to build browser-friendly URLs for "
                        f"this host — it has nothing to do with push access."
                    ),
                    kind="act",
                    fix_id="add_host_config",
                    # lib_dir carries the fix's SUBJECT: the hostname here, a
                    # barn library directory for strip_os. Reused rather than
                    # adding a fourth near-identical field, and it keeps the
                    # act-modal from re-parsing `remedy` prose to recover it.
                    fix_label="Add host to config.toml",
                    lib_dir=hostname,
                )
            ],
            remote_url=remote_url,
            barn_libraries=barn_libraries,
        )

    reachable = git_remote(["ls-remote", "--symref", "origin", "HEAD"], cwd=pipeline.repo_root, timeout=60.0)
    if not reachable.ok:
        detail = (reachable.stderr or reachable.stdout).strip().splitlines()
        first = detail[0] if detail else f"exit {reachable.returncode}"
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message=f"Cannot reach origin ({remote_url}): {first}",
                    remedy="Check the URL and your credentials, then try again.",
                )
            ],
            remote_url=remote_url,
            barn_libraries=barn_libraries,
        )

    default_branch: str | None = None
    # Absent when the remote has never had anything pushed to it (an empty
    # repo has no HEAD to symref) — that is "nothing has ever been shared",
    # not a failure, so default_branch simply stays None and the
    # non-default-branch check below is skipped.
    for line in reachable.stdout.splitlines():
        left, sep, right = line.partition("\t")
        if sep and right.strip() == "HEAD" and left.startswith("ref: refs/heads/"):
            default_branch = left.removeprefix("ref: refs/heads/").strip()
            break

    symbolic = git(["symbolic-ref", "-q", "HEAD"], cwd=pipeline.repo_root, timeout=10.0)
    if not symbolic.ok:
        # Genuinely detached: HEAD points straight at a commit rather
        # than a branch ref. `current_branch() == "HEAD"` alone is NOT
        # this test — an unborn branch (a fresh repo before its first
        # commit) prints the same literal "HEAD" from `rev-parse
        # --abbrev-ref HEAD` while `symbolic-ref` still succeeds, so
        # relying on that string would misreport a brand-new project.
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message="HEAD is detached — no branch is currently checked out.",
                    remedy=_detached_head_remedy(pipeline),
                )
            ],
            remote_url=remote_url,
            barn_libraries=barn_libraries,
            default_branch=default_branch,
        )

    if default_branch is not None:
        # symbolic.ok already proved HEAD is not detached (above), so
        # current_branch() cannot legitimately return None here — but it
        # is a general-purpose query, not a private helper, so the None
        # case is still handled explicitly rather than assumed away.
        current = pipeline.current_branch()
        if current is None:
            return PreconditionsReport(
                failures=[
                    PreconditionFailure(
                        message="HEAD is detached — no branch is currently checked out.",
                        remedy=_detached_head_remedy(pipeline),
                    )
                ],
                remote_url=remote_url,
                barn_libraries=barn_libraries,
                default_branch=default_branch,
            )
        if current != default_branch:
            return PreconditionsReport(
                failures=[
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
                ],
                remote_url=remote_url,
                barn_libraries=barn_libraries,
                default_branch=default_branch,
            )

    pipeline.remote_url = remote_url
    return PreconditionsReport(
        failures=[],
        remote_url=remote_url,
        barn_libraries=barn_libraries,
        default_branch=default_branch,
    )


def _detached_head_remedy(pipeline: "SharePipeline") -> str:
    """Remedy text for a detached HEAD, computed from ``git branch --contains HEAD``.

    Each line is prefixed ``"* "`` (current) or ``"  "`` (other); a
    detached HEAD also shows a synthetic ``(HEAD detached at <sha>)`` /
    ``(HEAD detached from <sha>)`` line, which is not a real branch name
    and is filtered out. If no real branch remains — a dangling commit no
    branch was ever built from — the remedy falls back to naming a new
    one.
    """
    result = git(["branch", "--contains", "HEAD"], cwd=pipeline.repo_root, timeout=10.0)
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
