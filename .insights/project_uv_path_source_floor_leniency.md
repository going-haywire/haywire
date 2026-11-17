---
name: uv path-source floor leniency
description: uv locks a requirement against an editable path source whatever its version, so a library may name a dependency floor above the version in the checkout; if uv starts enforcing the bound, dev environments fail at `uv lock`
type: project
---

**uv does not check a requirement's version against an editable path source.** A library
that requires `haywire-core>=0.5.4` locks without error against the local checkout at
0.5.3, because the dev environment resolves core from a path in `[tool.uv.sources]`.

Haywire relies on it ([ADR 0087](../docs/adr/0087-releases-are-batched-and-a-librarys-dependency-floor-guards-its-release.md)):
a library that needs unreleased core raises its dependency floor to the next patch in
the same commit, and `share`'s preflight, not uv, refuses to release it until PyPI has a
release that satisfies the floor.

**How to apply.**

- A floor above the checked-out version is intended, not a lock error to fix. Do not
  lower it to make a local check pass.
- Do not read a green `uv lock` as proof that a floor is satisfiable on PyPI.
- If a uv upgrade starts enforcing the bound, every dev environment with a waiting
  library fails at `uv lock`; the fallback is a development version on master after each
  release.
