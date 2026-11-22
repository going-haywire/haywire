# dev/

The going-haywire development tooling: the hooks that guard the workflow, the scripts the
workflow runs, and one folder per orchestrator. Code only; the workflow itself is a docs page,
[docs/collaboration/workflow.md](../docs/collaboration/workflow.md), which the Farmhand bridge
serves to every agent session of an org repository (`farmhand://dev/collaboration/workflow.md`).

| Path | What |
|---|---|
| `hooks/*.sh` | `block-dangerous-git`, `require-workflow-read` + `mark-workflow-read`, `guard-pr-merge`, `session-role`, `session-place` |
| `scripts/finish.py`, `scripts/tasks.py` | Finish a merged task; list the tasks in flight (standard library only) |
| `orchestrators/<tool>/` | One slot per orchestrator (`t3`, `herdr`): `session.sh` for `session-place`, optionally `agents.py` for `tasks.py`, a `doctor.py` where the tool needs setting up. The agent's how-to and a person's setup are docs pages: `docs/collaboration/orchestrators/<tool>-agent.md` and `<tool>.md` (ADR 0090) |
| `.claude-plugin/`, `hooks/hooks.json`, `skills/workflow/` | Transitional: the `haywire-dev` plugin the org's libraries still install from the `going-haywire` marketplace, until #212 gives each library its own adapters |

Core runs these files in place: `.claude/settings.json` calls `dev/hooks/`, and
`scripts/finish.py`, `scripts/tasks.py` and `.claude/skills/workflow` are links into this folder.
An org library reaches the same files through the core clone beside it (`../haywire-repo/dev/`).

`tests/scripts/test_claude_hooks.py` keeps core's wiring and `hooks/hooks.json` in step.
