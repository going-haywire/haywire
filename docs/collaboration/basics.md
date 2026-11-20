---
status: draft
doc_template: guide
scope: The software-development terms the Collaboration pages use (repository, commit, branch, pull request, CI, release, ruleset, pin, plugin, worktree), in plain words for readers who are not developers
see-also:
  - index.md
  - ../reference/glossary.md
---

# Basics

The ideas behind every page in this section, one at a time, each building on the ones before.
Plain words first; the folded *Technical detail* boxes are optional. Haywire's own terms
(task, lead, release PR, dependency floor) are defined in the
[glossary](../reference/glossary.md).

## Keeping track of work

**1 · Repository** (*repo*). A project folder that remembers every change ever made to
it: what, by whom and why. Picture a binder with a logbook at the back. Core is one
repository; each library with its own release rhythm (comfyui, protokol, spandrel,
stream, visiongraph) is another.

**2 · Commit.** One saved step in that logbook: a set of changes and a note saying what
and why. Every commit has a unique ID such as `8bfcef9`, a fingerprint of exactly that
state of the whole folder. It can never change, so "pinned to a commit" means "exactly
this logbook entry".

??? info "Technical detail"
    The tool keeping the history is **git**; its logbook is the hidden `.git` folder. The ID
    is a hash of the content and of the whole history before it: change one character and
    the ID changes. Haywire's commit messages read `type(area): summary`, for example
    `fix(editor): keep the selection after undo`.

**3 · Branch.** A separate line of work where changes are made without touching the
official version, called **master** (in haybale-stream: **main**). Every task has its own
branch, named after what it does: `fix/edge-drag`.

**4 · Clone, push, pull.** The shared original lives on GitHub. A **clone** is your full
copy of it; **push** sends your commits up, **pull** brings others' commits down.

**5 · GitHub and the organisation.** GitHub hosts repositories and adds the teamwork
around them: discussions, reviews, and robots that check the work. An **organisation**
is a shared account owning several repositories; ours is `going-haywire`.

## Proposing and accepting changes

**6 · Pull request** (*PR*). A request to take the changes on a branch into master: a
page showing exactly what changed, where people comment and robots report. A **draft** PR
is work in progress; a **ready** PR asks for review.

**7 · Merge.** Accepting a PR: its changes become part of master. Haywire squash-merges:
the branch's commits become one commit on master. Only the maintainer's word "merge"
merges a change; afterwards the task deletes its branch with `finish`.

## Robots that check the work

**8 · CI** (*continuous integration*). A robot that, on every change to a PR, installs the
code on a fresh computer, runs every test and marks the PR passed or failed. Nothing is
merged unless it passed: on Linux for a draft, on Linux and macOS once ready.

**9 · Workflow file.** The robot's instructions: when to start (a PR, a merge, a button,
a timer) and what to do. It lives in the repository (`.github/workflows/`), so changing it
goes through a PR like any other change.

**10 · Nightly run.** A workflow can start on a timer. Every night each library runs its
tests against core's newest code, so a core change that breaks a library shows up the
next morning, before a core release ships it.

??? info "Technical detail"
    GitHub's robot service is **GitHub Actions**; its results appear on a PR as **checks**
    (`ci / lint`, `ci / tests (ubuntu-24.04)`). The timer is written in **cron** form:
    `17 3 * * *` is 03:17 UTC every day, sometimes started late by GitHub.

## Shipping

**11 · Version, release and tag.** A **release** is a published, numbered edition such as
0.5.4; a **tag** is a permanent label on the commit that is that edition. A fix raises the
last number, new features the middle one. In haywire a release is a **release PR** that
changes only version numbers; merging it publishes, and the robot creates the tag.

**12 · PyPI.** The public shop for Python packages, where `pip` and `uv` download from.
Core and the organisation's libraries are published there.

??? info "Technical detail"
    **Trusted publishing**: PyPI is told once which repository, workflow and environment may
    upload a package; at upload time the robot proves its identity, and no password is
    stored anywhere. Setting it up is an owner step: [Publishing to PyPI](../guides/publish-to-pypi.md).

**13 · Dependency and dependency floor.** A library needs core: core is its
**dependency**. The oldest core version it accepts (`>=0.5.4`) is its **dependency
floor**. A library needing a core change not yet released raises its floor; the release
tool then refuses to publish it until that core version is in the shop.

## Protection

**14 · Rulesets.** House rules GitHub's server enforces for everyone, the maintainer and
agents included: master and release tags can never be deleted or rewritten, and master
changes only through a PR whose checks passed. Agents act under the maintainer's account,
so only rules on the server bind them.

## Sharing instructions between repositories

**15 · The shared repository** (`going-haywire/.github`). Holds what every library
shares, once: the contributor guidelines GitHub shows in each library, the shared robot
instructions, the ruleset files, and the catalogue the agents' plugin is installed from.

**16 · Reusable workflow.** Robot instructions in the shared repository that a library uses
by reference. The library's own robot reads them and carries them out inside the library;
the shared repository runs nothing and has no power over the library.

**17 · Read-only token.** The temporary key the robot gets for one run. A read-only key
can read the code but change nothing, so a stranger's PR that runs our tests cannot use
it to harm the repository.

**18 · Pin.** A library names exactly which edition of the shared instructions it uses:
a commit ID, `library-ci.yml@df1b6ec`. A change in the shared repository then cannot break
every library at once, and a tampered repository cannot reach them.

**19 · Moving the pin.** Using a newer edition means changing the pin in a PR, where the
library's robot tries the new edition before anyone merges it.

**20 · Dependabot.** GitHub's robot that checks weekly for newer editions of what a
repository refers to, and opens a PR moving the pin. It recognises newer editions by
their version tags.

## Agents and their add-ons

**21 · Claude Code, agent sessions.** The AI assistant running in a terminal; each running
conversation is a session. It reads the repository's `CLAUDE.md` (through `AGENTS.md`)
when it starts.

**22 · Skill.** A written procedure an agent loads when needed. The **workflow skill** is
haywire's step-by-step for branches, PRs, CI, decisions, merging and cleanup.

**23 · Hook.** A small guard program run automatically around an agent's actions; it can
stop an action. Hooks run on one computer and bind agents only; rulesets (14) run on
GitHub and bind everyone.

**24 · Plugin and marketplace.** A **plugin** bundles skills and hooks for installing in
one go; a **marketplace** is the catalogue a plugin is installed from. Two exist: the
`haywire` plugin for people *using* haywire, and `haywire-dev` (the workflow skill and its
hooks) for people *developing* haywire's repositories.

??? info "Technical detail"
    `haywire-dev` lives once, in core's `plugins/haywire-dev/`. Core uses it in place, with
    nothing to install; the libraries install it from the catalogue in `going-haywire/.github`.
    Its [README](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/README.md)
    has the commands.

## Working in parallel

**25 · Worktree.** An extra working folder of the same repository on its own branch,
sharing one logbook, so several tasks run at once without overwriting each other.

**26 · herdr, the lead and tasks.** herdr runs several agent sessions side by side. The
**lead** talks with you, starts tasks and merges on your word; each **task** works in its
own worktree and reports to the lead.

**27 · Umbrella.** All repositories side by side in one folder, with a small setup that
installs them together, to run the studio with every library at once. Each repository
still tests itself on its own.
