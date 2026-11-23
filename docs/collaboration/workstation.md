---
status: draft
doc_template: workflow
scope: W13, a developer sets up a workstation for core and the organisation libraries they work on, with the umbrella when several run in one studio
see-also:
  - index.md
  - new-org-library.md
  - ../adr/0081-libraries-from-other-repositories-run-from-an-umbrella-environment.md
---

# A developer's workstation

**For:** maintainers and contributors who work on more than one repository. Working on
core alone needs only core ([Developing Haywire: setup](../guides/development.md#setup)).

```mermaid
sequenceDiagram
    autonumber
    actor You as Developer
    participant Folder as haywire/ (the umbrella)
    participant Core as haywire-repo/
    participant Lib as haybale-<name>/
    participant CC as Claude Code

    You->>Folder: clone going-haywire/umbrella as haywire/
    You->>Core: clone core inside it, as haywire-repo/
    You->>Lib: clone each library you work on, beside core
    Note over Lib: one library: its own uv sync runs<br/>its tests and the studio with core
    opt several libraries in one studio
        You->>Folder: ① bin/umbrella-sync: lists the libraries cloned<br/>on this machine, then uv sync
    end
    Note over Core,Lib: each clone's committed files give a session there<br/>the workflow, its hooks and the Farmhand bridge
    You->>CC: a session in the clone you work on
```

An agent can do all of this for you: the [start page](../agents/start.md) is written for it.

| Step | Who | Where the rule or command lives |
|---|---|---|
| The layout and the umbrella | developer | [going-haywire/umbrella](https://github.com/going-haywire/umbrella#readme), [ADR 0081](../adr/0081-libraries-from-other-repositories-run-from-an-umbrella-environment.md) |
| One library | developer | [Contributing: in a library](contributing.md#in-a-library) |
| ① Only some libraries | developer | [umbrella README](https://github.com/going-haywire/umbrella#readme): `bin/umbrella-sync` writes the untracked `pyproject.toml` and `uv.lock` from the repositories cloned on this machine |
| The developer tooling | developer | [dev/README](https://github.com/going-haywire/haywire/blob/master/dev/README.md) |
| Worktrees: core's and a library's | developer, lead | [The workflow: parallel sessions](workflow.md#parallel-sessions) |
| A second machine | developer | [second-machine.md](second-machine.md) |
