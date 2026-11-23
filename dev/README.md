# dev/

The going-haywire development tooling: the hooks that guard the workflow, the scripts the
workflow runs, and one folder per orchestrator. Code only; the workflow itself is a docs page,
[docs/collaboration/workflow.md](../docs/collaboration/workflow.md), which the Farmhand bridge
serves to every agent session of an org repository (`farmhand://dev/collaboration/workflow.md`).

| Path | What |
|---|---|
| `hooks/*.sh` | `block-dangerous-git`, `require-workflow-read` + `mark-workflow-read`, `guard-pr-merge`, `session-role`, `session-place` |
| `scripts/worktree_setup.py`, `scripts/finish.py`, `scripts/tasks.py` | Set up a new worktree (core or an org library); finish a merged task; list the tasks in flight (standard library only) |
| `orchestrators/<tool>/` | One slot per orchestrator (`t3`, `herdr`): `session.sh` for `session-place`, optionally `agents.py` for `tasks.py`, a `doctor.py` where the tool needs setting up. The agent's how-to and a person's setup are docs pages: `docs/collaboration/orchestrators/<tool>-agent.md` and `<tool>.md` (ADR 0090) |

Core runs these files in place: `.claude/settings.json` calls `dev/hooks/`, and
`scripts/worktree_setup.py`, `scripts/finish.py` and `scripts/tasks.py` are links into this folder.
An org library reaches the same files through the core clone beside it (`../haywire-repo/dev/`),
from the committed files `going-haywire/.github`'s `templates/library/` gives it.

`tests/scripts/test_claude_hooks.py` checks that core's `.claude/settings.json` runs every hook here.
