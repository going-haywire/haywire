---
serve: developer
status: current
doc_template: guide
scope: Read when the session runs in herdr (the session-start hook says so) — how the lead and tasks, messages, the task view and merges run there
see-also:
  - ../workflow.md
  - herdr.md
---

# herdr

How the lead and tasks of *Lead and tasks* in [the workflow](../workflow.md) run in
[herdr](https://herdr.dev/guide/), the slot `dev/orchestrators/herdr/`
(ADR 0090). A herdr session carries `HC_TERMINAL_ID`, its address; the session-start hook
then names this file.

## The places

- A worktree lives at `~/.herdr/worktrees/haywire-repo/<kind>-<name>` and opens as a
  *space* under the repository; each space holds *tabs*. A session's name is
  *space / tab* (`haywire-repo / fix/edge-drag`); its address (`t1g`) goes only in
  brackets: `haywire-repo / fix/edge-drag (t1g)`.
- The session-start hook renames a worktree session's tab, while it is still called by its
  number, to its branch, and tells a main-folder session to name its tab by role (`lead`,
  `research`, …). It warns when other live sessions share the main folder.

## Created

The user may create the worktree in herdr (*New worktree*); the session in it runs
`python3 scripts/worktree_setup.py` first.

The lead starts a task itself, from the main folder on an up-to-date `master`:

```sh
git worktree add ~/.herdr/worktrees/haywire-repo/<kind>-<name> -b <kind>/<name> origin/master
(cd ~/.herdr/worktrees/haywire-repo/<kind>-<name> && python3 scripts/worktree_setup.py)
herdr-app do space.new --name <kind>-<name> \
  --folder ~/.herdr/worktrees/haywire-repo/<kind>-<name> --argv '["claude"]' --task "<brief>"
```

Then, before the session starts, record the lead:
`(cd <worktree> && python3 scripts/worktree_setup.py --lead <your address>)`; the brief
([the template](../brief.md)) carries the same address. A peer ("spin up a thread") gets
neither, only your address for messages.

The space opens under the repo and the agent starts with the brief as its first message;
`hc ls` shows whether it did (`herdr-app` reports only that the terminal was created). If
`herdr-app` is not there, the user opens the space (*Open worktree*) and gives the agent
the brief. A library task's worktree goes beside the repositories instead
(`git worktree add ../<repo>-<name> …`); *Open worktree* opens a space on it.

## Messages

`hc send <address> "<text>"` arrives as the other agent's next input; `hc ls` lists the
sessions with their space / tab; `hc --skill` prints the protocol. A task reports to the
lead with `hc send` **before its turn ends**, including what the user told it directly.
Without `hc`, the user relays.

**Needs a decision** (the workflow's four steps): the task ends its reply with the lead's
address and sends the lead one line with its own. The lead marks the task's tab
`? <name>` (`herdr-app do tab.rename --id <tab> --name "? <name>"`) and drops the `? ` on
"Decided". The hook names a task's tab after its branch; the lead may add its tag
(`core › <branch>`).

## The view

`tasks.py` adds each task's session through the slot's `agents.py`, which reads
`hc ls --json`: the address after the task's name, and its status.

## Merged

After `finish`, the user right-clicks the task's space → *Remove worktree* (it deletes the
folder, the branch is already gone) and closes the space.

## A second machine

Install herdr on it and add it to the first machine's herdr under *Settings → Machines*
(its host from `~/.ssh/config`), to run its sessions from one place. `hc ls` then lists
the live agents of both machines.
