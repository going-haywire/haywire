"""Fail a pull request that changes a package version unless it is a release PR.

A version is bumped only by a release (``/haywire-release``, whose PR is titled
``chore: release vX.Y.Z``). A feature PR that changes one has misread an
instruction, and the mismatch surfaces later as a half-released package.

Compares ``HEAD`` with the merge base of ``origin/$GITHUB_BASE_REF`` and looks at
the ``version = "..."`` lines of every existing ``pyproject.toml`` and
``haybale.toml``. A file the PR adds (a new package) may declare its first version.

Environment: ``GITHUB_BASE_REF`` (the PR's base branch), ``PR_TITLE``.
Standard library only, so it runs before anything is installed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

RELEASE_TITLE = "chore: release"
_VERSION_LINE = re.compile(r'^[+-]version\s*=\s*"')


def changed_version_files(base: str) -> list[str]:
    """Return the modified ``pyproject.toml``/``haybale.toml`` files whose ``version`` line changed."""
    diff = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=M",
            "-U0",
            f"{base}...HEAD",
            "--",
            "*pyproject.toml",
            "*haybale.toml",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    changed: list[str] = []
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[len("+++ b/") :]
        elif _VERSION_LINE.match(line) and current and current not in changed:
            changed.append(current)
    return changed


def main() -> int:
    title = os.environ.get("PR_TITLE", "")
    base = f"origin/{os.environ.get('GITHUB_BASE_REF', 'master')}"
    changed = changed_version_files(base)
    if not changed:
        print("No package version changed.")
        return 0
    if title.startswith(RELEASE_TITLE):
        print(f"Release PR ({title!r}): version changes are expected.")
        return 0
    print("::error::This PR changes a package version, but it is not a release PR.")
    for path in changed:
        print(f"  {path}")
    print(
        f"Versions change only in a release PR titled '{RELEASE_TITLE} vX.Y.Z' (/haywire-release). "
        "Revert the version lines in this PR."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
