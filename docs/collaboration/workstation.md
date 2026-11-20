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
        You->>Folder: ① drop the missing libraries from the umbrella's<br/>pyproject.toml locally, then uv sync
    end
    You->>CC: claude plugin marketplace add going-haywire/.github (once per machine)
    You->>CC: claude plugin install haywire-dev@going-haywire --scope project (each library clone)
```

| Step | Who | Where the rule or command lives |
|---|---|---|
| The layout and the umbrella | developer | [going-haywire/umbrella](https://github.com/going-haywire/umbrella#readme), [ADR 0081](../adr/0081-libraries-from-other-repositories-run-from-an-umbrella-environment.md) |
| One library | developer | [Library CONTRIBUTING: setting up](https://github.com/going-haywire/.github/blob/main/CONTRIBUTING.md#setting-up) |
| ① Only some libraries | developer | ADR 0081, consequences: a missing repository is dropped from the umbrella's `pyproject.toml` locally |
| The dev plugin | developer | [haywire-dev README](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/README.md) |
| Worktrees: core's and a library's | developer, lead | [The workflow skill: parallel sessions](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/skills/haywire-workflow/SKILL.md#parallel-sessions) |
| A second machine | developer | [second-machine.md](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/skills/haywire-workflow/second-machine.md) |
