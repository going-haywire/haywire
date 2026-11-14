---
name: untrusted-pull-requests-meet-nothing-with-power
description: Code and text from a fork's pull request never reach anything that holds write rights, secrets or tools — workflows with rights read only metadata and uploaded data, agent sessions never start in a fork's checkout, a reviewer that reads the pull request can do nothing, and files that steer agents or CI hold the merge until read line by line
status: accepted
see-also: ADR-0079
level: architectural
---

# Untrusted pull requests meet nothing with power

**Context.**

- A pull request from a fork brings code nobody has reviewed and text anybody can write: description, comments, commit messages, code comments, test fixtures.
- Code becomes dangerous next to rights. GitHub workflows that react to a pull request with write rights (`pull_request_target`, `workflow_run`) have been used to take over repositories by running the pull request's code; third-party Actions have been rewritten under their tags.
- Text becomes dangerous next to agents. Instructions planted in a pull request can steer an agent that reads it; no model reliably resists them.
- A repository's agent files are both code and text with power: `CLAUDE.md`, skills and rules instruct an agent, and the hooks in `.claude/settings.json` run shell commands in every session started in a checkout.

**Decision.**

- **A workflow with write rights or secrets never checks out, installs or runs code from an unmerged pull request.** `ci.yml` runs on `pull_request` with a read-only token; it uploads its test reports and event file as data. `test-results.yml` (`workflow_run`) publishes them, and `pr-intake.yml` (`pull_request_target`) labels from metadata and the list of changed paths; both come from `master`. Event values reach their scripts through environment variables only.
- **Every Action is pinned to a commit**, with its version as a comment; Dependabot proposes updates.
- **No agent session starts in a checkout of a fork's pull request**, and `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD` stays unset, so a session never takes a pull request's agent files as its own.
- **A pull request runs locally only after a review judged it safe**, in its own worktree, by hand or from a session started in the main checkout. A doubtful one runs in a GitHub Codespace or not at all.
- **What reads the pull request has no power; what has power never reads it raw.** An agent reviewing a fork's pull request reads a file a script prepared (hidden content made visible, agent and CI files flagged) and holds read-only tools only; posting, labelling and merging stay with the main session, on the maintainer's word.
- **A pull request that changes `CLAUDE.md`, `AGENTS.md`, `.mcp.json`, `.claude/` or `.github/` is labelled `agent files`**, and the merge hook refuses until the maintainer has read those lines and removed the label. Such changes are allowed, not refused.

**Considered.**

- *An agent reviewer told to treat pull request content as data, with its normal tools.* One successful injection could push, comment or merge under the maintainer's name.
- *Running a pull request's tests locally before review.* Runs a stranger's code with the maintainer's rights, credentials and `~/.haywire`; CI already ran the same tests in isolation.
- *Refusing pull requests that touch agent or CI files.* Closes the most powerful route, but blocks legitimate fixes and does not stop instructions hidden in ordinary files.
- *An AI reviewer running on GitHub.* Fork pull requests get no secrets under `pull_request`; making it work needs `pull_request_target` next to untrusted code, and it pays for reviews of every drive-by pull request.

**Consequences.**

- A change to `test-results.yml` or `pr-intake.yml` takes effect only after its merge; the pull request that makes it cannot test it.
- Reviewing a fork's pull request takes a deliberate extra step before anything runs locally.
- Changing an agent or CI file costs a line-by-line read, also for the maintainer's own pull requests.
- The reviewer agent is specified but not built (issue #99).
