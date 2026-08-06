"""Step 1 — the combined precondition gate."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit


from haywire.core.marketstall.host_providers import resolve_host, ssh_to_https
from haywire.core.publishing.git import git, git_remote
from haywire.core.publishing.manifest.errors import InvalidOsDeclarationError, ManifestReadError
from haywire.core.publishing.manifest.os_field import describe_os_fix, invalid_os_values
from haywire.core.publishing.manifest.reader import read_manifest
from haywire.core.publishing.pipeline.results import PreconditionFailure, PreconditionsReport

if TYPE_CHECKING:
    from haywire.core.publishing.pipeline.pipeline import SharePipeline

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
            failures=[_unreachable_failure(remote_url, hostname, first)],
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
            failures=[_detached_head_failure(pipeline)],
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
                failures=[_detached_head_failure(pipeline)],
                remote_url=remote_url,
                barn_libraries=barn_libraries,
                default_branch=default_branch,
            )
        if current != default_branch:
            return PreconditionsReport(
                failures=[_wrong_branch_failure(pipeline, current=current, default=default_branch)],
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


def _branches_containing_head(pipeline: "SharePipeline") -> list[str]:
    """Branch names that already contain the current commit.

    ``git branch --contains HEAD`` prefixes each line ``"* "`` (current) or
    ``"  "`` (other); a detached HEAD also emits a synthetic
    ``(HEAD detached at <sha>)`` line, which is not a branch name and is
    filtered out.
    """
    result = git(["branch", "--contains", "HEAD"], cwd=pipeline.repo_root, timeout=10.0)
    names = []
    for line in result.stdout.splitlines():
        name = line[2:].strip() if len(line) >= 2 else line.strip()
        if not name or name.startswith("(HEAD detached"):
            continue
        names.append(name)
    return names


def _detached_head_failure(pipeline: "SharePipeline") -> PreconditionFailure:
    """The detached-HEAD failure, offering an in-place switch when it is safe.

    Two situations wear the same name and need opposite advice:

    * **Nothing to lose** — HEAD is already contained in a branch (you checked
      out a tag or a commit and did not commit on top). Switching just moves
      HEAD, so the fix is offered as a button.
    * **Work would be orphaned** — commits were made while detached and no
      branch contains them. ``git switch`` would leave them unreachable, so no
      button is offered and the remedy says to save the work first.

    Stating WHY publishing is blocked matters as much as stating the command:
    "HEAD is detached" plus a bare ``git switch`` told the user what to type
    without telling them what was wrong or what they risked.
    """
    names = _branches_containing_head(pipeline)
    blocked = (
        "Publishing tags the commit it creates and pushes it to a branch, "
        "and a detached HEAD is on no branch — so there is nothing to push to."
    )

    if names:
        target = names[0]
        others = f" (also on {', '.join(f'`{n}`' for n in names[1:])})" if len(names) > 1 else ""
        return PreconditionFailure(
            message="HEAD is detached — no branch is currently checked out.",
            remedy=(
                f"{blocked}\n\n"
                f"This commit is already on `{target}`{others}, so switching to it loses "
                f"nothing — it only moves HEAD back onto the branch."
            ),
            kind="act",
            fix_id="switch_branch",
            fix_label=f"Switch to {target}",
            lib_dir=target,
        )

    return PreconditionFailure(
        message="HEAD is detached, and this commit is not on any branch.",
        remedy=(
            f"{blocked}\n\n"
            "Switching away now would leave this commit unreachable. Put it on a "
            "branch first:\n\n"
            "  git switch -c my-branch\n\n"
            "then publish from there."
        ),
    )


def _wrong_branch_failure(pipeline: "SharePipeline", *, current: str, default: str) -> PreconditionFailure:
    """On a branch that is not the remote's default. Same shape as detached HEAD.

    Publishing is default-branch-only (see the arch doc's §5), and the safe
    condition for repairing it is identical: switching is lossless exactly
    when the current branch's commits are already contained in the default
    branch — i.e. the branch has nothing unmerged on it.

    A branch with unmerged work is the interesting case, and it must NOT offer
    a button. Nothing is destroyed by switching (the branch still holds the
    commits), but the user almost certainly wants to merge or abandon that work
    deliberately rather than have a publish wizard silently move them off it.
    """
    contained = git(["merge-base", "--is-ancestor", "HEAD", default], cwd=pipeline.repo_root, timeout=10.0)
    blocked = (
        "Publishing always happens on the default branch, so the tag and the "
        "marketstall URLs point at a ref that will still exist later — a feature "
        "branch usually disappears when it merges."
    )

    if contained.ok:
        return PreconditionFailure(
            message=f"Currently on `{current}`, but the repository publishes from `{default}`.",
            remedy=(
                f"{blocked}\n\n"
                f"`{current}` has nothing that `{default}` does not already contain, so "
                f"switching loses no work."
            ),
            kind="act",
            fix_id="switch_branch",
            fix_label=f"Switch to {default}",
            lib_dir=default,
        )

    return PreconditionFailure(
        message=f"Currently on `{current}`, but the repository publishes from `{default}`.",
        remedy=(
            f"{blocked}\n\n"
            f"`{current}` has commits that `{default}` does not. Merge them first, or "
            f"publish after this branch lands:\n\n"
            f"  git switch {default}\n\n"
            f"Nothing is lost either way — `{current}` keeps its commits."
        ),
    )


#: Where the sharing guide explains git remote requirements — the fallback for
#: a host with no auth docs of its own (a self-hosted Gitea, a filesystem
#: remote). The published site, not a repo path, so it is useful from an
#: installed copy that has no docs/ directory.
#:
#: The origin is ``site_url`` in mkdocs.yml. Restated here rather than read
#: from it because this runs in an INSTALLED venv, where that file does not
#: exist — ``tests/share_pipeline/test_unreachable_remedy.py`` fails if the
#: two ever diverge, the same guard LOCKSTEP_DISTS uses for the release config.
SHARING_GUIDE_URL = (
    "https://going-haywire.github.io/haywire/docs/guides/sharing-libraries/#44-git-remote-requirements"
)


def _unreachable_failure(remote_url: str, hostname: str, detail: str) -> PreconditionFailure:
    """The unreachable-origin failure, pointed at the RIGHT docs page.

    Two things are knowable here, and each narrows the advice:

    * **The transport.** ``git@host:owner/repo`` authenticates with an SSH
      key; ``https://host/owner/repo`` with a token or a credential helper.
      They fail differently and their docs pages are different, so naming the
      wrong one sends the reader somewhere that cannot help.
    * **The host.** ``resolve_host()`` already ran above and honours
      ``[[hosts]]`` config, so a self-hosted GitLab resolves to the GitLab
      provider and gets GitLab's docs rather than a generic shrug.

    Falls back to the sharing guide when the host is unrecognized or ships no
    auth docs. Never guesses a URL from the hostname: a wrong link is worse
    than no link, because it looks authoritative.

    The URL travels on ``doc_url``, not inside ``remedy`` — see
    :class:`PreconditionFailure`, where a URL buried in prose renders as dead
    text the user has to select and copy.
    """
    ssh = remote_url.startswith("git@") or remote_url.startswith("ssh://")
    transport = "ssh" if ssh else "https"
    how = (
        "This is an SSH remote, so it authenticates with an SSH key — check that "
        "the key is registered with the host and that ssh-agent is running."
        if ssh
        else "This is an HTTPS remote, so it authenticates with a token or a git "
        "credential helper — check that a credential is cached for this host."
    )

    provider = resolve_host(hostname) if hostname else None
    docs = getattr(provider, "auth_docs", {}).get(transport) if provider is not None else None

    if docs and provider is not None:
        # `label`, not name.title(): "github".title() is "Github", which is not
        # how the brand is written.
        brand = getattr(provider, "label", provider.name)
        doc_url, doc_label = docs, f"{brand}'s authentication guide"
    else:
        doc_url, doc_label = SHARING_GUIDE_URL, "Setting up a git remote"

    return PreconditionFailure(
        message=f"Cannot reach origin ({remote_url}): {detail}",
        remedy=(
            "The check exercises the same credential path a publish uses, so "
            f"this is what publishing would hit.\n\n{how}"
        ),
        doc_url=doc_url,
        doc_label=doc_label,
    )
