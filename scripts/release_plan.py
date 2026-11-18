"""Decide what a run of .github/workflows/publish.yml does. Standard library only.

A release is the merge of a release PR (ADR 0088): a push to the default branch whose
lockstep version differs from the latest ``v*`` tag. The workflow then tags that commit,
publishes, and writes the release notes. A pushed ``v*.*.*`` tag (recovery, by the user)
publishes as it always did; a manual dispatch on the default branch re-runs the release of
the version in the tree, creating the tag only if it is missing. Any other push is no release.

Writes ``release`` (``true``/``false``), ``version`` and ``tag`` to ``$GITHUB_OUTPUT``. ``tag`` is
the tag the workflow must create, empty when it exists or is not to be created. Exits 1, with a
message, when the run cannot be trusted to publish the right thing.

Environment: ``GITHUB_EVENT_NAME``, ``GITHUB_REF``, ``GITHUB_REF_TYPE``, ``GITHUB_REF_NAME``,
``DEFAULT_BRANCH``. Reads ``packages/haywire-core/pyproject.toml`` and ``git tag`` in the checkout.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

VERSION = re.compile(r"^\d+\.\d+\.\d+$")
RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
CORE_PYPROJECT = Path("packages/haywire-core/pyproject.toml")


class PlanError(Exception):
    """The run cannot be trusted to publish the right thing; the message says why."""


@dataclass(frozen=True)
class Plan:
    release: bool
    version: str = ""
    tag: str = ""
    """The tag to create on the pushed commit; empty when none is to be created."""
    note: str = ""


def latest_release(tags: list[str]) -> str | None:
    """Return the highest ``vX.Y.Z`` tag of *tags*, or ``None``; other tags are ignored."""
    found = [(tuple(int(p) for p in m.groups()), tag) for tag in tags if (m := RELEASE_TAG.match(tag))]
    return max(found)[1] if found else None


def decide(
    event: str,
    ref: str,
    ref_type: str,
    ref_name: str,
    default_branch: str,
    tree_version: str,
    tags: list[str],
) -> Plan:
    """Return what the run does, given the event, the pushed ref, the tree's version and the tags."""
    if ref_type == "tag":
        version = ref_name.removeprefix("v")
        if not RELEASE_TAG.match(ref_name):
            raise PlanError(f"tag {ref_name!r} is not vX.Y.Z")
        return Plan(True, version, "", f"tag {ref_name} pushed: publishing it")
    if ref != f"refs/heads/{default_branch}":
        return Plan(False, note=f"{ref} is not {default_branch} or a release tag: nothing to release")
    if not VERSION.match(tree_version):
        raise PlanError(f"the lockstep version {tree_version!r} is not X.Y.Z")
    wanted = f"v{tree_version}"
    latest = latest_release(tags)
    if event == "workflow_dispatch":
        return Plan(True, tree_version, "" if wanted in tags else wanted, f"dispatch: releasing {wanted}")
    if wanted == latest:
        return Plan(False, note=f"{wanted} is the latest tag: nothing to release")
    if wanted in tags:
        raise PlanError(
            f"the tree's version {wanted} is tagged but is not the latest ({latest}): no release"
        )
    return Plan(True, tree_version, wanted, f"{wanted} differs from the latest tag ({latest}): releasing")


def emit(plan: Plan) -> None:
    lines = f"release={'true' if plan.release else 'false'}\nversion={plan.version}\ntag={plan.tag}\n"
    if target := os.environ.get("GITHUB_OUTPUT"):
        with open(target, "a") as handle:
            handle.write(lines)
    print(plan.note)
    print(lines, end="")


def main() -> int:
    try:
        tree_version = tomllib.loads(CORE_PYPROJECT.read_text())["project"]["version"]
        tags = subprocess.run(
            ["git", "tag", "--list", "v*"], capture_output=True, text=True, check=True
        ).stdout.split()
        plan = decide(
            os.environ.get("GITHUB_EVENT_NAME", ""),
            os.environ.get("GITHUB_REF", ""),
            os.environ.get("GITHUB_REF_TYPE", ""),
            os.environ.get("GITHUB_REF_NAME", ""),
            os.environ.get("DEFAULT_BRANCH", "master"),
            tree_version,
            tags,
        )
    except PlanError as exc:
        print(f"::error::{exc}")
        return 1
    emit(plan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
