"""The release states ``haywire share`` reports, and the agent playbook generated from them.

``State`` is the closed set of values on the ``STATE:`` line (and ``state`` in
``--json``). ``PLAYBOOK`` has exactly one row per state; a test fails when the two
differ, so the instructions written into a project's ``CLAUDE.md`` cannot omit a
state the tool can print.
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
