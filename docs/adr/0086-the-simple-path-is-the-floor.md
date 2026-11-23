---
name: the-simple-path-is-the-floor
description: The path from haywire init to the Share wizard needs only git and a host account and nothing added to the product may break it; conveniences are bonuses, advanced users get guidance not enforcement, and the org's own libraries are advanced users whose workflow lives in the org's skill and templates, not in the product
status: accepted
see-also: ADR-0079, ADR-0081
level: architectural
---

# The simple path is the floor

**Context.**

- A beginner runs `haywire init`, works, puts the repository on a host and shares from the Share wizard. That path needs git and a host account and nothing else.
- The org's own libraries need more: pull requests, CI before publishing, a protected master, third-party contributions. Each of those could be built into `init` and `share`.
- Hosts differ. Anything the product requires of GitHub is a requirement of every user, and a requirement of one host excludes the others.

**Decision.**

- **The simple path is the floor.** `init` → work → a repository on a host → the Share wizard needs only git and a host account. No change may make it need more.
- **Conveniences are bonuses.** The generated GitHub `publish.yml` helps beginners; it never becomes a requirement, and the product does not support every host.
- **Advanced users get guidance, not enforcement.** The product imposes no branch model, PR flow or CI; docs and templates show a good way.
- **The org's own libraries are advanced users.** Their workflow is the org's choice, written in the org's skill and templates, not built into the product. It follows core's workflow: PRs, CI, a protected master, third-party PRs welcome.
- **Shared rules have one home per kind**: an org `going-haywire/.github` repository (process files, reusable workflows), short linking `AGENTS.md` and `CLAUDE.md` files, and an org development plugin for Claude's hooks and skill.

**Considered.**

- *One path for everyone.* Gives beginners PRs and CI they did not ask for, and `share` would call a host API.
- *Org-only bespoke extras inside the product.* Puts the org's process into every user's install and makes it look required.
- *A product "developer setup".* A second supported path to maintain, with its own breakage, for users who already know how to set up their own.
- *Copying the shared files into each library.* Copies drift: three library `CLAUDE.md` files already did.

**Consequences.**

- `share` stays host-agnostic: it does not call a host API, and an opt-in PR mode must work with plain git.
- The org's libraries get their process from templates and a plugin that can change without a product release.
- A new library convenience is judged by whether a beginner without it is still on a working path.

## Amendment (ADR 0092)

The "org development plugin for Claude's hooks and skill" is gone: a place of work gets its agent tooling from its committed adapters and its own Haywire environment, developer tooling is code in core's `dev/`, and the workflow is a docs page (ADR 0092).
