"""Share-URL derivation: git remote/ref probes plus host-provider blob URLs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from haywire.core.marketstall.host_providers import resolve_host, ssh_to_https
from haywire_studio.packaging.share.barn import current_ref
from haywire_studio.packaging.share.git import git


def _find_git_root(start: Path) -> Path | None:
    """Walk up from *start* to find the nearest .git directory."""
    current = start.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def _get_remote_url(git_root: Path) -> str | None:
    """Get the origin remote URL, or None if unavailable."""
    result = git(["remote", "get-url", "origin"], cwd=git_root, timeout=10.0)
    if not result.ok:
        return None
    return result.stdout.strip()


def _get_current_ref(git_root: Path) -> str | None:
    """Return current branch name, or None if detached HEAD or git failure.

    Thin alias over :func:`haywire_studio.packaging.share.barn.current_ref` — kept as a
    module-level name here (rather than inlining the import at each call
    site) because tests patch ``haywire_studio.packaging.share.url._get_current_ref``.
    """
    return current_ref(git_root)


def _unknown_host_warning(hostname: str) -> str:
    return (
        f"Host '{hostname}' is not recognized. To enable, add this to\n"
        f"  ~/.haywire/config.toml:\n\n"
        f"    [[hosts]]\n"
        f'    hostname = "{hostname}"\n'
        f'    provider = "gitlab"   # or one of: github, gitlab\n\n'
        f"  Then re-run `haywire share` (without `--save`) to get the share URL."
    )


@dataclass(frozen=True)
class ShareSaveResult:
    """Output of _derive_url. share_url is None if URL derivation failed."""

    out_path: Path
    share_url: str | None
    warning: str | None  # User-facing warning when share_url is None


def _derive_url(
    repo_root: Path,
    out_path: Path,
) -> ShareSaveResult:
    """Derive the canonical blob URL for an existing marketstall.toml.

    Used by write_marketstall (after writing the file) and
    derive_share_url_only (no file write). Returns a ShareSaveResult
    with share_url=None and a user-facing warning when derivation fails.
    """
    remote_url = _get_remote_url(repo_root)
    if remote_url is None:
        return ShareSaveResult(
            out_path=out_path,
            share_url=None,
            warning=(
                "No git remote found. Push this repo to a supported host first, "
                "then re-run `haywire share` (without `--save`) to get the share URL."
            ),
        )

    https_url = ssh_to_https(remote_url).removesuffix(".git").rstrip("/")
    parts = urlsplit(https_url)
    hostname = (parts.hostname or "").lower()

    provider = resolve_host(hostname)
    if provider is None:
        return ShareSaveResult(
            out_path=out_path,
            share_url=None,
            warning=_unknown_host_warning(hostname),
        )

    # Parse owner + repo from the URL path.
    path = parts.path.strip("/")
    if "/" not in path:
        return ShareSaveResult(
            out_path=out_path,
            share_url=None,
            warning=f"Could not parse owner/repo from URL: {https_url}",
        )
    owner, _, repo = path.rpartition("/")

    # Share URLs are always branch-live off the current branch.
    ref_value = _get_current_ref(repo_root)
    if ref_value is None:
        return ShareSaveResult(
            out_path=out_path,
            share_url=None,
            warning="Detached HEAD; share URL not constructed. The file has been written.",
        )

    share_url = provider.blob_url(owner, repo, ref_value, "marketstall.toml")
    return ShareSaveResult(out_path=out_path, share_url=share_url, warning=None)


def derive_share_url_only(repo_root: Path) -> ShareSaveResult:
    """Re-derive the share URL for an existing marketstall.toml.

    Does NOT write any file. Returns a ShareSaveResult with the URL derivation
    outcome; callers can format it consistently across different entry points.
    """
    out_path = repo_root / "marketstall.toml"
    if not out_path.is_file():
        return ShareSaveResult(
            out_path=out_path,
            share_url=None,
            warning=(
                f"No marketstall.toml found at {out_path}. Run `haywire share --save` first to produce it."
            ),
        )
    return _derive_url(repo_root, out_path)
