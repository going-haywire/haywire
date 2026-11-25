---
name: a-dependency-floor-is-the-oldest-version-known-to-work
description: a published package's third-party requirement has a floor that is the oldest version known to work, raised only for a feature or fix it needs, with no cap or pin without a known break; a CI job tests every floor with uv's lowest-direct resolution
status: accepted
see-also: ADR-0087
level: architectural
---

# A dependency floor is the oldest version known to work

**Context.**

- Core's `opencv-contrib-python>=5.0.0.93` floor had no reason behind it and kept visiongraph 1.3.0 from installing next to core (fixed in #237).
- Most floors were the version current when the line was written. `attrs==25.4.0` and `cattrs==25.3.0` were exact pins from 2025-11-15 (`3d88fd8c8`) with no reason recorded. Core never imports `attrs`, and cattrs 25.3 itself requires `attrs>=25.4.0`.
- A bare name (`numpy`, `fastapi`, `packaging`) means "any version" to a resolver: uv's lowest resolution picked numpy 1.3.0, which does not build on Python 3.12.
- A library installs next to other libraries in one environment, so a needless floor or cap in one of them refuses a combination that would work.

**Decision.**

- **Scope.** Third-party requirements in `[project.dependencies]` and `[project.optional-dependencies]` of the published packages (`packages/*`, `barn/*`). Internal ones (`haywire-*`, `haybale-*`) stay lockstep (ADR 0087).
- **A floor is the oldest version known to work.** Every requirement has one. It goes up only when a feature, a bug fix or a security fix needs it, and a comment next to it gives the reason when the code doesn't make it obvious.
- **No caps and no exact pins** without a known break, named in a comment (`mcp>=1.28,<2`: mcp 2 drops the low-level server decorators the studio host uses).
- **A requirement is declared where it is imported**, and only there (`scripts/check_deps.py`).
- **CI holds the floors true.** The `floors` job in `ci.yml` resolves every direct requirement to its floor (`UV_RESOLUTION=lowest-direct`, `uv sync --upgrade`) and runs the non-browser tests on Linux and Python 3.12, on every pull request and on master.
- **The workspace's dev group gets floors too**, at the version in use: the job lowers it as well. They follow no policy; they only stop the job from installing an ancient pytest.

**Considered.**

- *Floors at the version current when written.* The old practice; that is how the opencv floor happened.
- *Caps at the next major as a precaution.* They refuse working combinations, and a library cannot lift a cap in its dependency's metadata.
- *Testing floors only before a release.* Under batched releases (ADR 0087) a broken floor would surface weeks after the change that broke it.
- *One reusable `floors` workflow in `going-haywire/.github` for core and the libraries.* Core's jobs are all its own; calling `.github` would be a new pattern, and every change to the job would wait for a `.github` release and a pin bump in core. The libraries get theirs inside `library-ci.yml`, which they already call.
- *A nightly job, or macOS too.* A nightly needs someone to read it; a resolution is the same on every platform, and only wheel availability differs.

**Consequences.**

- A change that needs a newer API raises the floor in the same commit, or the `floors` job fails.
- A floor below what another requirement forces (numpy 1.26 while opencv 4.13 needs numpy 2) is not tested by the job until that requirement drops. It still belongs there: it is what this package needs.
- The org libraries get a `floors` job in `going-haywire/.github`'s `library-ci.yml`, as a later step. For a library that installs core from PyPI it also tests the `haywire-core` floor; for one that reaches core by path, only its third-party floors.
