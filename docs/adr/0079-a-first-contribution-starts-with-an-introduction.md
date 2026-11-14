---
name: a-first-contribution-starts-with-an-introduction
description: Before a first pull request, a contributor writes an introduction issue themselves and the maintainer accepts it with a label; a pull request without one is welcomed, labelled and held at the merge, never failed or closed
status: accepted
see-also: ADR-0080
level: architectural
---

# A first contribution starts with an introduction

**Context.**

- Haywire takes contributions from forks, and contributors are expected to work with coding agents. A first pull request can arrive with no human contact before it, possibly written and opened entirely by an agent.
- The project's architecture rules (DI, ownership, registration paths) make many well-meant changes wrong in ways only a conversation before the code avoids.
- The project wants to welcome every contributor and assume good intentions: a process step must not read as a rejection.
- Nobody can prove that a text was written by a person rather than an AI.

**Decision.**

- **Before a first pull request, even a typo fix, the contributor opens an introduction issue** (who they are, what they want to work on, why), written by themselves. The issue form sets the label `introduction`.
- **The maintainer answers and sets `introduction accepted`.** That label, not a comment, is what tools and agents check.
- **From then on the ordinary rules apply:** small fixes go straight to a pull request; anything larger needs an agreed issue first.
- **A pull request from someone without an accepted introduction is welcomed and held, not refused.** `pr-intake.yml` comments with the next step and sets `needs introduction`; the checks stay green and the pull request stays open. Accepting the introduction removes the label automatically. The merge is the only gate: the merge hook refuses while the label is set, and only the maintainer merges.
- **Owners, members and collaborators skip the step**, as do bot accounts.
- **Agents check the rule and never write the introduction.** A contributor's agent looks for an accepted introduction before offering a pull request and leaves writing it to the person.

**Considered.**

- *A failing required check for a missing introduction.* Watertight, but a red mark on someone's first pull request reads as rejection whatever the comment says, and it guards nothing the held merge does not.
- *Closing the pull request and asking for a reopen.* Tidy for the maintainer; the most discouraging option.
- *An introduction without acceptance.* A heads-up, but not a gate: a pull request could be considered before anyone read the introduction.
- *Introductions only for larger work.* Keeps the first contact impersonal for small fixes, which is exactly the contact this rule is about.

**Consequences.**

- A first-time contributor waits for the maintainer's answer before their pull request can merge; their work can go on meanwhile.
- The rule rests on trust: an agent-written introduction cannot be detected, only discouraged.
- The labels `introduction`, `introduction accepted` and `needs introduction` are part of the process; renaming one means changing the issue form, `pr-intake.yml`, the merge hook and the workflow skill together.
- Bot pull requests (Dependabot) get no intake labels; the maintainer reviews them anyway.
