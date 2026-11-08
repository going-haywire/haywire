"""The release steps only a person can do, and the checklist that hands them over.

Creating the GitHub repository and registering a PyPI pending publisher need the
owner's accounts. ``HUMAN_ONLY_STEPS`` is the one list of them; ``init`` and
``share`` render from it, so what an agent is told to hand over cannot differ
between the two.

Example::

    steps = checklist(["create_github_repo"], repo_root, project_name="my-project")
    print("\\n".join(steps))
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from haywire.core.publishing.barn import barn_library_dirs
from haywire.core.publishing.git import git, git_remote

_GITHUB_REMOTE = re.compile(r"github\.com[:/](?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?/?$")


@dataclass(frozen=True)
class StepContext:
    """What a step needs to print concrete values."""

    repo_root: Path
    project_name: str = ""
    dist_names: tuple[str, ...] = ()

    @property
    def remote_url(self) -> str:
        result = git(["remote", "get-url", "origin"], cwd=self.repo_root, timeout=10.0)
        return result.stdout.strip() if result.ok else ""


@dataclass(frozen=True)
class HumanStep:
    """One step only the owner can do.

    ``render`` returns the instruction lines; ``is_done`` returns whether it is
    verifiably done, or ``None`` when nothing can check it.
    """

    id: str
    title: str
    render: Callable[[StepContext], list[str]]
    is_done: Callable[[StepContext], bool | None]


def github_owner_repo(remote_url: str) -> tuple[str, str] | None:
    """Return ``(owner, repo)`` for a github.com remote URL, or ``None`` for any other host."""
    match = _GITHUB_REMOTE.search(remote_url.strip())
    return (match["owner"], match["repo"]) if match else None


def library_names(repo_root: Path) -> tuple[str, ...]:
    """Distribution names of every ``barn/*`` library, as declared in its ``pyproject.toml``."""
    import toml

    names: list[str] = []
    for lib_dir in barn_library_dirs(repo_root):
        try:
            name = toml.loads((lib_dir / "pyproject.toml").read_text()).get("project", {}).get("name")
        except (OSError, toml.TomlDecodeError):
            continue
        if isinstance(name, str) and name:
            names.append(name)
    return tuple(names)


def _render_create_repo(ctx: StepContext) -> list[str]:
    name = ctx.project_name or ctx.repo_root.name
    return [
        "Create an empty GitHub repository (no README, no .gitignore):",
        "  https://github.com/new",
        f"  Repository name: {name}",
        "Then, in the project folder:",
        "  git remote add origin <the repository URL>",
        "  git push -u origin <default branch>",
    ]


def _created_repo_done(ctx: StepContext) -> bool | None:
    if not ctx.remote_url:
        return False
    return git_remote(["ls-remote", "origin", "HEAD"], cwd=ctx.repo_root).ok


def _render_pending_publisher(ctx: StepContext) -> list[str]:
    parsed = github_owner_repo(ctx.remote_url)
    owner, repo = parsed if parsed else ("<owner>", "<repository>")
    lines = ["Register a pending publisher on PyPI, once per project name:"]
    lines.append("  https://pypi.org/manage/account/publishing/")
    for name in ctx.dist_names or ("<distribution name>",):
        lines.append(f"  PyPI project name : {name}   (exactly this)")
    lines += [
        f"  Owner             : {owner}",
        f"  Repository        : {repo}",
        "  Workflow name     : publish.yml",
        "  Environment name  : pypi",
    ]
    if parsed is None:
        lines.append("  (the origin remote is not on github.com: fill owner and repository by hand)")
    return lines


def _render_pypi_environment(ctx: StepContext) -> list[str]:
    return [
        "Create the GitHub environment the publish workflow uses:",
        "  repository → Settings → Environments → New environment → name it `pypi`",
    ]


def _never_checkable(_ctx: StepContext) -> bool | None:
    return None


HUMAN_ONLY_STEPS: dict[str, HumanStep] = {
    step.id: step
    for step in (
        HumanStep(
            "create_github_repo", "Create the GitHub repository", _render_create_repo, _created_repo_done
        ),
        HumanStep(
            "pypi_pending_publisher",
            "Register a PyPI pending publisher",
            _render_pending_publisher,
            _never_checkable,
        ),
        HumanStep(
            "github_pypi_environment",
            "Create the GitHub `pypi` environment",
            _render_pypi_environment,
            _never_checkable,
        ),
    )
}


def checklist(
    step_ids: list[str] | tuple[str, ...], repo_root: Path, *, project_name: str = ""
) -> list[str]:
    """Return numbered instruction lines for the steps in *step_ids*, skipping verifiably done ones."""
    ctx = StepContext(repo_root=repo_root, project_name=project_name, dist_names=library_names(repo_root))
    lines: list[str] = []
    number = 0
    for step_id in step_ids:
        step = HUMAN_ONLY_STEPS[step_id]
        if step.is_done(ctx) is True:
            continue
        number += 1
        first, *rest = step.render(ctx)
        lines.append(f"{number}. {step.title}. {first}")
        lines.extend(f"   {line}" for line in rest)
    return lines
