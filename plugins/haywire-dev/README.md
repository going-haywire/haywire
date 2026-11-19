# haywire-dev

The going-haywire development workflow for Claude Code, as a plugin: the
`haywire-workflow` skill (branches, pull requests, CI, merge, `finish`) and the hooks that
guard it.

| Path | What |
|---|---|
| `skills/haywire-workflow/` | The skill, with `scripts/finish.py` and `scripts/tasks.py` (standard library only) |
| `hooks/*.sh` | `block-dangerous-git`, `require-workflow-skill` + `mark-workflow-skill`, `guard-pr-merge`, `session-role`, `session-place` |
| `hooks/hooks.json` | The plugin's wiring of those hooks |

## One copy, two users

- **Core** (this repository) uses the files in place: `.claude/settings.json` runs the hooks
  from `plugins/haywire-dev/hooks/`, `.claude/skills/haywire-workflow` and
  `scripts/finish.py`, `scripts/tasks.py` are links into this folder. Core needs no install,
  so a fresh clone is guarded from its first session.
- **The org's library repositories** install the plugin from the marketplace in
  [going-haywire/.github](https://github.com/going-haywire/.github), which takes this folder
  from core's `master`. A library's `.claude/settings.json` names the marketplace and
  enables the plugin, but Claude Code does not add a marketplace that only a project's
  settings declare: each machine adds it once, each clone installs the plugin once:

  ```sh
  claude plugin marketplace add going-haywire/.github   # once per machine
  claude plugin install haywire-dev@going-haywire --scope project
  ```

  Until then a library session runs no hooks; `/plugin` lists the plugin under *Errors*
  as enabled but not installed.

`tests/scripts/test_claude_hooks.py` keeps core's wiring and `hooks/hooks.json` in step.
The skill and the hooks are core's to change, through a pull request in core; a library
receives the change when its plugin updates.
