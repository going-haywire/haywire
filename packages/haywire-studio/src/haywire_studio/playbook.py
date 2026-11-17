"""The release states ``haywire share`` reports, and the agent playbook generated from them.

``State`` is the closed set of values on the ``STATE:`` line (and ``state`` in
``--json``). ``PLAYBOOK`` has exactly one row per state; a test fails when the two
differ, so the instructions written into a project's ``CLAUDE.md`` cannot omit a
state the tool can print.

``RELEASE_GATE_LABELS`` are the GitHub labels of the release reminders, issues that
record a decision affecting the next release, and ``render_release_gates`` the
``CLAUDE.md`` section that tells an agent when to read them and to open one only on the
owner's word (``docs/guides/sharing-libraries.md`` §7.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class State(str, Enum):
    READY = "READY"
    RELEASED = "RELEASED"
    NOTHING_TO_RELEASE = "NOTHING_TO_RELEASE"
    BLOCKED = "BLOCKED"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    UNPUSHED = "UNPUSHED"
    RELEASE_PR_OPEN = "RELEASE_PR_OPEN"
    STALE_MARKER = "STALE_MARKER"
    FAILED = "FAILED"
    USAGE = "USAGE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Row:
    """What an agent does when the tool reports *state*."""

    state: State
    meaning: str
    action: str


PLAYBOOK: tuple[Row, ...] = (
    Row(
        State.READY,
        "Everything is in order.",
        "Run `uv run --frozen haywire share --bump patch`. "
        "Use `minor` or `major` only if the owner said so.",
    ),
    Row(State.RELEASED, "This change is already released.", "Nothing. Do not run `share` again."),
    Row(
        State.NOTHING_TO_RELEASE,
        "Nothing under `barn/` or the root `pyproject.toml` changed since the last release.",
        "Nothing. Commit a change first if one was intended.",
    ),
    Row(
        State.BLOCKED,
        "A fixable problem stops the release.",
        "Run the command on the `NEXT:` line, then `share --status` again.",
    ),
    Row(
        State.NEEDS_HUMAN,
        "Only the owner can proceed.",
        "Paste the whole output, checklist included, to the owner and wait. "
        "Run the `THEN:` command only after they confirm.",
    ),
    Row(
        State.UNPUSHED,
        "A release commit exists that the remote does not have.",
        "Run `uv run --frozen haywire share --resume` once. If it fails, stop and tell the owner.",
    ),
    Row(
        State.RELEASE_PR_OPEN,
        "A release PR is open and not merged.",
        "Give the owner the PR link (the `PR:` line) and wait. Do not merge it, tag, or run `share` again.",
    ),
    Row(
        State.STALE_MARKER,
        "An interrupted release does not match this checkout.",
        "Stop and tell the owner.",
    ),
    Row(
        State.FAILED,
        "A step failed and its changes were reverted.",
        "Read the error, fix its cause, run `share --status`. Do not retry in a loop.",
    ),
    Row(State.USAGE, "The command line was wrong.", "Fix the command; see `share --help`."),
    Row(State.UNKNOWN, "Anything else.", "Stop and paste the full output to the owner."),
)

STANDING_RULES = (
    "Always `uv run --frozen`, so `uv` does not re-lock; "
    "if `uv.lock` changed unintentionally, `git checkout uv.lock`.",
    "Run `share --status` before acting, and again after any unclear result "
    "(a denial message, a timeout). The tool may have run.",
    "Never run `share --bump` twice for one change.",
    "Never tag, push tags, force-push, or edit versions, `install_spec` or `marketstall.toml` by hand.",
    "`STOP` means stop. Do not work around it.",
)


def render_playbook() -> str:
    """Return the Markdown for the playbook: standing rules, then one table row per state."""
    lines = [f"- {rule}" for rule in STANDING_RULES]
    lines += ["", "`uv run --frozen haywire share --status` ends with a `STATE:` line. Act on it:", ""]
    lines += ["| `STATE:` | Meaning | You do |", "|---|---|---|"]
    lines += [f"| `{row.state.value}` | {row.meaning} | {row.action} |" for row in PLAYBOOK]
    return "\n".join(lines)


@dataclass(frozen=True)
class GateLabel:
    """A GitHub label of a release reminder, and when an agent reads the issues carrying it."""

    name: str
    color: str
    """Hex colour without ``#``, as ``gh label create --color`` takes it."""
    description: str
    meaning: str
    checked: str


RELEASE_GATE_LABELS: tuple[GateLabel, ...] = (
    GateLabel(
        "todo-pre-release",
        "D93F0B",
        "Reminder: to do before the next release",
        "Something the owner decided to do before the next release of this project.",
        "Before `haywire share`, `--dry-run` included: "
        "`gh issue list --label todo-pre-release --state open`. "
        "If any are open, list them and ask the owner whether to release anyway.",
    ),
    GateLabel(
        "after-core-release",
        "FBCA04",
        "Reminder: to do once a haywire-core release contains the needed change",
        "A dependency to raise (usually the `haywire-core` floor) once a released "
        "haywire-core contains the change on the issue's `Waits for:` line.",
        "At the start of a session: `gh issue list --label after-core-release --state open`; "
        "check each one as below and tell the owner which can now be done.",
    ),
)

WAITS_FOR_PREFIX = "Waits for: going-haywire/haywire@"


def render_release_gates() -> str:
    """Return the Markdown for the release reminders section of a project's ``CLAUDE.md``."""
    lines = [
        "A release reminder is an issue that records a decision affecting the next release, so "
        "it is not forgotten. It is a help, not a rule: open one only when the owner agrees. "
        "When a change you make needs something done at release time (most often a "
        "dependency floor to raise once a release contains a change), propose the issue to "
        "the owner: its title, the label, the steps, and for `after-core-release` a first "
        f"line `{WAITS_FOR_PREFIX}<sha> (#<pr>)`. Link a prepared branch's draft PR to it.",
        "",
        "| Label | Meaning | Read |",
        "|---|---|---|",
    ]
    lines += [f"| `{label.name}` | {label.meaning} | {label.checked} |" for label in RELEASE_GATE_LABELS]
    lines += [
        "",
        "The change on a `Waits for:` line is released when the latest haywire-core on PyPI "
        "contains the commit:",
        "",
        "```sh",
        "v=$(curl -s https://pypi.org/pypi/haywire-core/json | jq -r .info.version)",
        'gh api "repos/going-haywire/haywire/compare/v$v...<sha>" --jq .status  '
        "# behind or identical: released",
        "```",
        "",
        "Create the labels when the owner agrees to the first reminder (safe to repeat):",
        "",
        "```sh",
    ]
    lines += [
        f'gh label create {label.name} --color {label.color} --description "{label.description}" --force'
        for label in RELEASE_GATE_LABELS
    ]
    lines += [
        "```",
        "",
        "If `gh` is missing or not logged in, or the repository is not on GitHub, tell the "
        "owner the reminders could not be read; never report that none are open.",
    ]
    return "\n".join(lines)
