---
name: an-orchestrators-text-lives-in-the-docs
description: an orchestrator's slot scripts live in core's dev/orchestrators/<tool>/, its agent how-to and a person's setup in docs/collaboration/orchestrators/; the neutral parts define the contract and name no tool
status: accepted
see-also: ADR-0090, ADR-0092
level: architectural
---

# An orchestrator's text lives in the docs

**Context.**

- ADR 0090 put each orchestrator's agent how-to inside the workflow skill's folder, beside the skill it was meant to stay out of.
- ADR 0092 moves all text to `docs/` and all developer tooling code to core's `dev/`.

**Decision.**

- **Slot scripts** (`session.sh`, `agents.py`, `doctor.py`) live in `dev/orchestrators/<tool>/`.
- **The agent's how-to** is `docs/collaboration/orchestrators/<tool>-agent.md` (`serve: developer`), beside **a person's setup**, `<tool>.md`.
- **The contract** is ADR 0090's: four task events, each with one neutral part, plus "a slot may add session context". The neutral parts and the workflow page name no tool; a root file such as `t3.json` only calls neutral scripts, and each repository's names its own worktree setup line.

**Consequences.**

- Removing an orchestrator removes one `dev/orchestrators/<tool>/` folder and its two pages; nothing else changes.
