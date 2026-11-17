---
name: releases-are-batched-and-a-librarys-dependency-floor-guards-its-release
description: Core releases when the user decides, not per library need; a library that needs unreleased core merges now with its dependency floor raised to the next patch, and share's preflight refuses a floor no PyPI release satisfies before tagging
status: accepted
see-also: ADR-0086, ADR-0081
level: architectural
---

# Releases are batched; a library's dependency floor guards its release

**Context.**

- A small core change a library needs cost two full releases: View Image's config row needed core v0.5.3 before visiongraph could ship v0.0.45. Core cut 11 releases in 10 days, 4 of them on one day.
- A core release is two PRs, two CI rounds and an 11-wheel publish.
- The library's *commit* never needed the core release, only its own release did: in the development environment the library resolves core from a path source.
- uv does not check a requirement's version against an editable path source: `a>=0.5.4` locks against a local `a` at 0.5.3 without error.

**Decision.**

- **Core releases are batched on demand.** Merged changes pile up; `/haywire-release` runs when the user decides and starts with a view of what waits.
- **A library that needs unreleased core merges now.** The same commit raises its **dependency floor** to the next patch after the latest release (`>=0.5.4` while PyPI has 0.5.3).
- **The floor is the guard.** `share`'s preflight refuses a floor no PyPI release satisfies, before tagging. Offline is a warning, not a refusal.
- **The floor is the record of what waits.** A scan of the org libraries' masters feeds the view at release step 0. `after-core-release` reminders stay only for waits no floor can record (no code yet; projects developing against PyPI core).
- **Every core tag gets a GitHub Release** with generated notes, so a batch has a readable list.
- **Library CI runs on every push against core master, plus nightly**; release step 0 shows each library's latest nightly, because under batching the release is when a break matters.

**Considered.**

- *Releasing core on demand, per library need.* Today's churn.
- *A release train (fixed cadence).* Releases when nothing is ready and waits when something is.
- *Mandatory reminders.* A human step that drifts from the code; the floor cannot.
- *Library work waiting on a branch.* Hides finished work and lets the branch rot.

**Consequences.**

- The decision relies on uv's path-source leniency. If uv starts enforcing the version, dev environments fail at `uv lock`, and master carries a development version after each release.
- A floor is right for good, so there is no raise-after-release step.
- Between a library merge and the core release, the library's master cannot be shared; that is the intended wait.
- The scan reads master of every org library, so a library not yet pushed is invisible to it.
