---
status: draft
doc_template: guide
scope: Setting up herdr as the orchestrator for haywire's lead and tasks
see-also:
  - index.md
  - ../lead-and-tasks.md
---

# herdr

[herdr](https://herdr.dev/guide/) runs terminal sessions in *spaces* and *tabs*, with
worktrees under `~/.herdr/worktrees/`, and lets agents message each other with `hc`. How
the agents use it is in the workflow skill's
[herdr file](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/skills/haywire-workflow/orchestrators/herdr.md).

| Role | In herdr |
|---|---|
| The lead | A session in a space on the main folder, its tab named `lead` |
| A task | A space on its worktree, its tab named after the branch; the lead opens it with `herdr-app do space.new`, or you do with *Open worktree* |
| A report | `hc send <address> "…"` to the lead |
| The task view | `tasks.py` shows each task's session address and status (`hc ls`) |

## Setup

1. Install herdr and `hc` ([the guide](https://herdr.dev/guide/)), and `jq`.
2. Open a space on the main folder. Right-click it → *New worktree* creates a task's
   worktree and space; the agent runs `python3 scripts/worktree_setup.py` there first.
3. At session start the agent learns its address and how to reach the others; a worktree
   tab still called by its number is renamed to the branch.
4. After a merge and `finish`, right-click the task's space → *Remove worktree*.
5. A second machine: herdr there too, added under *Settings → Machines* on the first.

## Starting the studio

The [umbrella](https://github.com/going-haywire/umbrella#readme) provides
`bin/haywire-studio`, which runs the full studio, every library included, from the checkout
or worktree it starts in, a worktree on its own studio port. Link it onto your `PATH` once
(the umbrella's README says how). With these two settings it starts from any space:

`~/.config/herdr-app/keys.json`, under `"global"` (`cmd-shift-s` opens a `studio` tab):

```json
"cmd-shift-s": {"command": "tab.new", "args": {"name": "studio", "argv": ["haywire-studio"]}}
```

`~/.config/herdr-app/programs.json` (*Haywire studio* in the agent menu):

```json
{ "programs": { "haywire-studio": { "name": "Haywire studio", "run": ["haywire-studio"], "match": ["haywire"] } } }
```

The command runs on the space's machine, so a remote Linux space needs the umbrella there
too (as the parent folder of its repositories) and `haywire-studio` on its login `PATH`.
Its studio listens on 127.0.0.1: `ssh -L <port>:localhost:<port> <machine>`.
