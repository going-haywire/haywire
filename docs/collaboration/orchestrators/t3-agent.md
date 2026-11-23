---
serve: developer
status: current
doc_template: guide
scope: Read when the session runs in T3 Code (the session-start hook says so) — how the lead and tasks, messages, the task view and merges run there
see-also:
  - ../workflow.md
  - t3.md
---

# T3 Code

How the lead and tasks of *Lead and tasks* in [the workflow](../workflow.md) run in
[T3 Code](https://t3.codes), the slot `dev/orchestrators/t3/` and the
repository's `t3.json` (ADR 0090). A T3 session carries `CLAUDE_CODE_ENTRYPOINT=t3-code`
and `T3CODE_THREAD_ID`; the session-start hook then names this file. T3's tools
(`t3_thread_*`, `link_pull_request`, …) load late: find them with the tool search.

## The places

- **The lead** is a T3 thread on the project root (the main folder).
- **A task** is a T3 thread in a worktree of its own, started by the lead with
  `t3_thread_launch`. T3 puts core worktrees under `~/.t3/worktrees/<repo>/`. The thread's
  title is the task's name, its branch.

## Created

The lead calls `t3_thread_launch` with a new worktree from `origin/master`, the branch
`<kind>/<name>` and the brief as the first message. The setup script from `t3.json`, once
imported into the T3 project (*The user's T3 settings*), runs
`python3 scripts/worktree_setup.py` when T3 creates the worktree (`runOnWorktreeCreate`).
`t3.json` sets `async: false` on it so that T3 holds the agent until it exits; T3 before 0.1.11
dropped that field on import (pingdotgg/t3code#40325). Either way the session-start
hook waits while the worktree's setup runs (up to 5 minutes). Do not run
the script again while T3's run is still going. A setup that has not started within 10 s never
runs (T3 runs no script in a worktree it re-creates); the hook then tells you to run it.

**A library task** runs like a core task: T3 creates the worktree in its own folder, and the
library's `t3.json` runs the setup through the library's main folder, which links core beside
the worktree before `uv sync` (*Parallel sessions* in the workflow). The library's committed
`.claude/settings.json` and `.mcp.json` then give the session its hooks and the Farmhand
bridge, with nothing to install. Only for the full studio with every library does the lead
create the worktree beside the repositories itself (`git worktree add ../<repo>-<name> …`) and
start the thread on it with `workspaceStrategy: existing_worktree`; T3 runs no create script
for a worktree it did not create, so the lead runs the setup there.

## Messages

A task reports with `t3_thread_send` to the lead's thread id, which its brief carries; the
message arrives as the lead's next input, no polling. The lead links each task's PR to the
task's thread with `link_pull_request`, so the thread shows it.

## The view

`tasks.py` shows no session column for T3: T3 has no slot `agents.py`. The lead reads its
task threads with `t3_thread_list`, `t3_worktree_list` and the PRs linked to them.

## Merged

**Under T3 the lead sends nothing to a task thread after its PR merges**, which overrides
the workflow's "tell the task 'merged'" (*Finishing as the maintainer*, step 5, and *Lead and
tasks*). A message resumes the thread, and when its worktree is already gone T3 re-creates
the worktree and the branch from local `master` (#198). Instead the lead checks `master`'s
CI itself (step 4), then re-settles the thread, and the settle script runs `finish`.

The settle script from `t3.json`, once imported into the T3 project, runs each time a
worktree thread settles: from the main folder it runs `finish <branch>`, which removes the
worktree and both branches, or removes a worktree left detached. `finish` refuses before the
merge, so an early settle removes nothing.

**Re-settle after a merge.** A task thread can settle by itself before its PR merges (when
its last turn ends); the settle script then finds the PR unmerged and leaves everything.
So after each merge the lead unsettles the task's thread and settles it again, which runs
the settle script once more, now with the PR merged. A thread that has not settled yet
settles when its turn ends, and the script runs then.

A T3 brief therefore promises no "merged" message: the task's last report is *Ready* (or
*Blocked*, *Needs a decision*), and the settle script finishes it. If a branch is re-created
anyway (a crashed task, a user's message), `finish` still removes it as long as its only
extra commits are already on `origin/master`. A thread whose PR has merged does not go on:
its worktree is gone, so unsettling it starts no session. A follow-up is a new thread.

## The user's T3 settings

In every T3 session the session-start hook runs the slot's `doctor.py` and says what T3's own
settings lack; pass that list to the user in your first reply, before other work (T3 does not
display the hook's `systemMessage`), with the docs link the hook gives. The user changes them in
T3:

- *Settings → Worktrees → Cleanup*: *Delete merged worktrees* on; *Keep worktrees with local
  changes* on, *Uncommitted changes*.
- Branch naming: semantic (`feat/`, `fix/`, …).

A project's `t3.json` scripts the user imports in T3 (*Project settings → <project\> → Actions →
Import scripts*), never with `t3_project_update`. When a worktree's setup never ran, the hook
says so: the scripts are probably not imported.

- *Storage cleanup* (off by default) keeps branches; `finish --sweep` deletes them.

## A second machine

A linked environment: `t3_thread_launch` with its `environmentId` starts a thread, worktree
included, on that machine. The second machine's lead is a peer, as in
[second-machine.md](../second-machine.md).
