"""The agent files a Haywire repository commits: harness configs, and an org library's files.

A harness config is a harness's own small config file that points it at the project's own Haywire:
the Farmhand bridge (``haywire farmhand bridge``), started from the project's environment.
Every supported harness gets its harness config, whoever created the project, so the project works
the same for everyone who opens it. :data:`HARNESSES` is the one list; supporting another
harness means adding its writer there.

An org library gets more (:func:`write_org_files`): core's workflow hooks in its harness configs, T3's
``t3.json``, the declaration of core's developer docs, and its CI callers from ``.github``'s
workflow templates.

Writers merge into files that already exist and keep everything else in them.
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from collections.abc import Callable
from datetime import date
from pathlib import Path

#: The command every harness config starts the bridge with, from the project's own environment.
BRIDGE_COMMAND = ["uv", "run", "--frozen", "--quiet", "haywire", "farmhand", "bridge"]
SERVER = "farmhand"


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _claude(project: Path) -> list[Path]:
    """Claude Code: the bridge in ``.mcp.json``, allowed and switched on in ``.claude/settings.json``."""
    mcp = project / ".mcp.json"
    config = _read_json(mcp)
    command, *args = BRIDGE_COMMAND
    config.setdefault("mcpServers", {})[SERVER] = {"command": command, "args": args}
    _write_json(mcp, config)

    settings_path = project / ".claude" / "settings.json"
    settings = _read_json(settings_path)
    allow = settings.setdefault("permissions", {}).setdefault("allow", [])
    if f"mcp__{SERVER}" not in allow:
        allow.append(f"mcp__{SERVER}")
    enabled = settings.setdefault("enabledMcpjsonServers", [])
    if SERVER not in enabled:
        enabled.append(SERVER)
    _write_json(settings_path, settings)
    return [mcp, settings_path]


#: Every supported harness and the writer of its harness config.
HARNESSES: dict[str, Callable[[Path], list[Path]]] = {"Claude Code": _claude}


def write_harness_configs(project: Path) -> list[Path]:
    """Write or refresh every supported harness's config in ``project``; return the files written."""
    written: list[Path] = []
    for writer in HARNESSES.values():
        written += writer(project)
    return written


# -- an org library's files ------------------------------------------------------------

#: Where a library's CI callers and its ``dependabot.yml`` come from: GitHub's workflow templates.
ORG_REPO = "going-haywire/.github"
CI_FILES = {
    ".github/workflows/ci.yml": "workflow-templates/ci.yml",
    ".github/workflows/nightly.yml": "workflow-templates/nightly.yml",
    ".github/workflows/pr-intake.yml": "workflow-templates/pr-intake.yml",
    ".github/dependabot.yml": "workflow-templates/dependabot.yml",
}
CORE = "../haywire-repo"
_HOOKS = f'"$CLAUDE_PROJECT_DIR"/{CORE}/dev/hooks/'
_CORE_CHECK = (
    f'[ -d "$CLAUDE_PROJECT_DIR/{CORE}/dev/hooks" ] || echo "Core is not beside this folder, so the '
    "workflow hooks and the Farmhand bridge cannot run: clone going-haywire/haywire as "
    f"{CORE}, or in a worktree run its setup (t3.json's *Worktree setup*).\""
)
_CLAUDE_START = "<!-- haywire:org-library:start -->"
_CLAUDE_END = "<!-- haywire:org-library:end -->"
_CLAUDE_BLOCK = f"""{_CLAUDE_START}
## Working in this repository

This is a going-haywire library: it follows core's workflow, and its own rules are
*In a library* on core's contributing page
([docs/collaboration/contributing.md](https://github.com/going-haywire/haywire/blob/master/docs/collaboration/contributing.md#in-a-library)).
Read the workflow before the first branch, commit, push or `gh pr` command of any task: the
Farmhand bridge serves it as `farmhand://dev/collaboration/workflow.md`
(the file: `{CORE}/docs/collaboration/workflow.md`), and the hooks refuse a commit until
this session has. This repository's committed files (`.mcp.json`, `.claude/settings.json`,
`t3.json`) bring the workflow, its hooks and the bridge from core beside it, with nothing to
install; `uv run haywire init --org-files` refreshes them. Start this folder's studio with
`python3 {CORE}/dev/scripts/studio.py start` (`stop`, `status`), never `uv run haywire studio
start`, which runs without the libraries of the other org repositories.
{_CLAUDE_END}
"""


def _claude_hooks(project: Path) -> list[Path]:
    """Claude Code in an org library: core's workflow hooks, run from the core clone beside it."""
    path = project / ".claude" / "settings.json"
    settings = _read_json(path)
    # The retired haywire-dev plugin and its marketplace, from a library set up before.
    settings.pop("extraKnownMarketplaces", None)
    plugins = settings.get("enabledPlugins", {})
    plugins.pop("haywire-dev@going-haywire", None)
    if not plugins:
        settings.pop("enabledPlugins", None)
    settings["hooks"] = {
        "SessionStart": [
            {
                "hooks": [
                    {"type": "command", "command": _CORE_CHECK},
                    {"type": "command", "command": _HOOKS + "session-role.sh"},
                    {"type": "command", "command": _HOOKS + "session-place.sh", "timeout": 330},
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {"type": "command", "command": _HOOKS + name}
                    for name in ("block-dangerous-git.sh", "require-workflow-read.sh", "guard-pr-merge.sh")
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Read|ReadMcpResourceTool",
                "hooks": [{"type": "command", "command": _HOOKS + "mark-workflow-read.sh"}],
            }
        ],
    }
    _write_json(path, settings)
    return [path]


def _t3_json(project: Path) -> list[Path]:
    """T3 Code's scripts: the worktree setup through the library's main folder, finish, the studio."""
    common = "$(git rev-parse --path-format=absolute --git-common-dir)"
    finish = (
        f'main=$(cd "{common}/.." && pwd -P); here=$(pwd -P); [ "$here" = "$main" ] && exit 0; '
        'b=$(git branch --show-current); cd "$main" || exit 1; '
        f'if [ -n "$b" ]; then python3 {CORE}/dev/scripts/finish.py "$b"; '
        'else git worktree remove "$here"; fi'
    )
    scripts = {
        "$schema": "https://t3.codes/schema/t3.json",
        "scripts": [
            {
                "name": "Worktree setup",
                "command": f'python3 "{common}/../../haywire-repo/dev/scripts/worktree_setup.py"',
                "icon": "configure",
                "runOnWorktreeCreate": True,
                "async": False,
            },
            {"name": "Finish merged task", "command": finish, "icon": "configure", "runOnSettle": True},
            {
                "name": "Haywire studio",
                "command": f"python3 {CORE}/dev/scripts/studio.py start --browser",
                "icon": "play",
                "runOnWorktreeCreate": False,
            },
        ],
    }
    path = project / "t3.json"
    _write_json(path, scripts)
    return [path]


def _declaration(project: Path) -> list[Path]:
    """``[tool.haywire.agents]``: core's developer docs, which the bridge serves here."""
    path = project / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    if "[tool.haywire.agents]" in text:
        return []
    table = (
        "\n[tool.haywire.agents]\n"
        "# The docs folder whose `serve: developer` pages the Farmhand bridge serves to agent\n"
        "# sessions here: core's, through the core clone beside this repository.\n"
        f'developer-docs = "{CORE}/docs"\n'
    )
    path.write_text(text.rstrip("\n") + "\n" + table, encoding="utf-8")
    return [path]


def _claude_md(project: Path) -> list[Path]:
    """``CLAUDE.md``'s org block: written once, replaced on every refresh, the rest left alone."""
    path = project / "CLAUDE.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if _CLAUDE_START in text and _CLAUDE_END in text:
        head, _, rest = text.partition(_CLAUDE_START)
        tail = rest.partition(_CLAUDE_END)[2].lstrip("\n")
        text = head + _CLAUDE_BLOCK + ("\n" + tail if tail else "")
    elif "\n## Working in this repository\n" in text:
        head, _, rest = text.partition("\n## Working in this repository\n")
        after = rest.find("\n## ")
        tail = rest[after + 1 :] if after != -1 else ""
        text = head + "\n" + _CLAUDE_BLOCK + ("\n" + tail if tail else "")
    else:
        text = text.rstrip("\n") + ("\n\n" if text else "") + _CLAUDE_BLOCK
    path.write_text(text, encoding="utf-8")
    return [path]


def _default_branch(project: Path) -> str:
    """Return the library's default branch: ``origin``'s, else the current one, else ``master``."""
    for args in (["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], ["branch", "--show-current"]):
        result = subprocess.run(["git", *args], cwd=project, capture_output=True, text=True, check=False)
        name = result.stdout.strip().removeprefix("origin/")
        if result.returncode == 0 and name:
            return name
    return "master"


def _latest_release(listing: str) -> tuple[str, str] | None:
    """Return ``(commit, tag)`` of the highest ``vX.Y.Z`` tag in a ``git ls-remote --tags`` listing."""
    commits: dict[str, str] = {}
    for line in listing.splitlines():
        commit, _, ref = line.partition("\t")
        if not ref.startswith("refs/tags/"):
            continue
        tag = ref.removeprefix("refs/tags/")
        if tag.endswith("^{}"):
            commits[tag[:-3]] = commit  # an annotated tag: the commit it points at
        else:
            commits.setdefault(tag, commit)
    versions = {tag: match for tag in commits if (match := re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag))}
    if not versions:
        return None
    tag = max(versions, key=lambda t: tuple(int(n) for n in versions[t].groups()))
    return commits[tag], tag


def fetch_ci_templates() -> tuple[str, str, dict[str, str]]:
    """Return the ``.github`` commit to pin, its label and the text of each CI template.

    The commit is ``.github``'s latest release (its highest ``vX.Y.Z`` tag), labelled with the
    tag, so Dependabot moves the pin to each later release. Without a release yet, it is the
    current commit, labelled with today's date.

    Raises:
        RuntimeError: GitHub could not be reached.
    """
    url = f"https://github.com/{ORG_REPO}"
    listing = subprocess.run(
        ["git", "ls-remote", url, "HEAD", "refs/tags/v*"], capture_output=True, text=True, check=False
    )
    head = [line.split("\t")[0] for line in listing.stdout.splitlines() if line.endswith("\tHEAD")]
    if listing.returncode != 0 or not head:
        raise RuntimeError(f"cannot reach {url}: {listing.stderr.strip()}")
    release = _latest_release(listing.stdout)
    if release is not None:
        commit, label = release
    else:
        commit, label = head[0], f"{date.today().isoformat()}, {ORG_REPO}"
    texts = {}
    for source in CI_FILES.values():
        raw = f"https://raw.githubusercontent.com/{ORG_REPO}/{commit}/{source}"
        with urllib.request.urlopen(raw, timeout=20) as response:  # a fixed https URL
            texts[source] = response.read().decode("utf-8")
    return commit, label, texts


def _ci_files(project: Path, fetch: Callable[[], tuple[str, str, dict[str, str]]]) -> list[Path]:
    """The CI callers and ``dependabot.yml`` a library lacks, from ``.github``'s workflow templates.

    A file the library already has stays untouched: it is the library's own, and Dependabot
    moves its pins.
    """
    missing = {target: source for target, source in CI_FILES.items() if not (project / target).exists()}
    if not missing:
        return []
    commit, label, texts = fetch()
    branch = _default_branch(project)
    pin = f"@{commit} # {label}"
    written = []
    for target, source in missing.items():
        text = texts[source].replace("$default-branch", branch)
        text = re.sub(rf"({re.escape(ORG_REPO)}/\.github/workflows/[\w-]+\.yml)@main\b", rf"\1{pin}", text)
        path = project / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def write_org_files(
    project: Path, *, fetch: Callable[[], tuple[str, str, dict[str, str]]] = fetch_ci_templates
) -> list[Path]:
    """Write or refresh an org library's repository files in ``project``; return the files written.

    The agent files (every harness's config with core's hooks, ``t3.json``, the developer-docs
    declaration, ``CLAUDE.md``'s org block) are rewritten from core
    every time. The CI callers and ``dependabot.yml`` are written only when missing, from
    ``.github``'s workflow templates, pinned to its current commit.

    Args:
        fetch: Returns ``.github``'s commit and its templates; the default reads them from GitHub.
    """
    written = write_harness_configs(project)
    for writer in (_claude_hooks, _t3_json, _declaration, _claude_md):
        written += writer(project)
    return written + _ci_files(project, fetch)
