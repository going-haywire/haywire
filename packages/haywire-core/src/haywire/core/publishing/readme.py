"""README share-URL marker blocks.

``haywire share`` rewrites the block between the marketstall markers in the
repo README and each barn library's README; ``haywire docs`` regenerates
those files but preserves the blocks verbatim.
"""

from __future__ import annotations

import re
from pathlib import Path

_README_MARKER_START = "<!-- marketstall:share-url:start -->"
_README_MARKER_END = "<!-- marketstall:share-url:end -->"
_README_NAMES = ("README.md", "Readme.md", "readme.md")  # case-insensitive search


def _update_readme_markers(
    content: str,
    share_url: str,
    *,
    tagged_url: str | None = None,
) -> str:
    """Rewrite every <!-- marketstall:share-url:start --> ... :end --> block.

    The block lists two subscription URLs:

    1. ``share_url`` — branch-live, always the current state of the repo.
    2. ``tagged_url`` — the same file pinned to the version it was published
       at, so a reader who copies it freezes to that release.

    A project that publishes to PyPI declares
    ``[tool.haywire.marketstall].distribute = "pypi"``, which makes the file at
    these URLs *be* the PyPI feed. There is no third, separately-deployed URL
    to advertise — the earlier ``pypi_marketplace_url`` existed only because
    this file was always git-flavoured.

    Files without the marker pair are returned unchanged.
    """
    pattern = re.compile(
        re.escape(_README_MARKER_START) + r"\n.*?\n" + re.escape(_README_MARKER_END),
        re.DOTALL,
    )
    lines: list[str] = []
    lines += ["# Always the latest (tracks the current branch):", share_url]
    if tagged_url is not None:
        lines += ["", "# Frozen to this version:", tagged_url]
    replacement = f"{_README_MARKER_START}\n```sh\n" + "\n".join(lines) + f"\n```\n{_README_MARKER_END}"
    return pattern.sub(replacement, content)


def _find_readme(directory: Path) -> Path | None:
    """Find README.md (case-insensitive variants) in directory. None if absent.

    Searches in order: README.md, Readme.md, readme.md. First hit wins.
    """
    for name in _README_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _update_repo_readmes(
    repo_root: Path,
    share_url: str,
    *,
    tagged_url: str | None = None,
) -> list[Path]:
    """Update marker blocks in the root README and each barn/*/README.md.

    Returns the list of README paths that were updated (had markers AND were rewritten).
    """
    updated: list[Path] = []
    candidates: list[Path] = []

    root_readme = _find_readme(repo_root)
    if root_readme is not None:
        candidates.append(root_readme)

    barn = repo_root / "barn"
    if barn.is_dir():
        for lib_dir in sorted(barn.iterdir()):
            if not lib_dir.is_dir():
                continue
            lib_readme = _find_readme(lib_dir)
            if lib_readme is not None:
                candidates.append(lib_readme)

    for readme in candidates:
        old = readme.read_text(encoding="utf-8")
        new = _update_readme_markers(old, share_url, tagged_url=tagged_url)
        if new != old:
            readme.write_text(new, encoding="utf-8")
            updated.append(readme)
    return updated
