# Third-party dependency floors: proposal

Task `chore/dependency-floors`.

| Status | |
|---|---|
| Decided | 2026-11-25: A(a), B(b), C(a), D(a) |
| Implemented | in the PR of this branch; the ADR, CS-I5 and the insight there are canonical, this page is the proposal as sent |

Every result below comes from a scratch copy of this branch at `5af279877`. Since then
the opencv floor dropped to `>=4.13.0.90` (#237); image passes at it. mcp 2.3.0 breaks
the studio host (`'_FarmhandServer' object has no attribute 'list_tools'`), so the `<2`
cap guards a real break.

## 1. The written rule

### Where each piece lives

| Piece | Place | Why there |
|---|---|---|
| The decision and its reasons | `docs/adr/0095-a-dependency-floor-is-the-oldest-version-known-to-work.md` (0095 is free on every remote branch) | Same format as 0087, which it sits beside: 0087 covers internal floors, 0095 third-party ones |
| The rule a review cites | `docs/reference/coding-standards.md`, new **CS-I5** under *I · Imports* (CS-I2 *Dependencies point one way* already lives there) | It meets the page's three tests: no tool checks "a reason, no cap", the opencv floor cost a blocked visiongraph 1.3.0, and the code disagrees with itself today (exact pins next to bare names) |
| The uv trap found while testing | `.insights/project_uv_lowest_direct_relocks.md` plus an entry in the index | A silent failure: see *2. The trap* |
| How to run it locally | One line in `docs/guides/development.md`, *Tests* | Every command lives there |

### Draft ADR 0095

```markdown
---
name: a-dependency-floor-is-the-oldest-version-known-to-work
description: a published package's third-party requirement has a floor that is the oldest version known to work, raised only for a feature or fix it needs, no cap or pin without a known break; a CI job tests every floor with uv's lowest-direct resolution
status: accepted
see-also: ADR-0087
level: architectural
---

# A dependency floor is the oldest version known to work

**Context.**

- Core's `opencv-contrib-python>=5.0.0.93` floor had no reason behind it and kept visiongraph 1.3.0 from installing next to core.
- Most floors were the version current when the line was written. `attrs==25.4.0` and `cattrs==25.3.0` have been exact pins since 2025-11-15 (`3d88fd8c8`), with no reason recorded. Core never imports `attrs`, and cattrs 25.3 itself requires `attrs>=25.4.0`.
- Bare names (`numpy`, `fastapi`, `packaging`) mean "any version" to a resolver: uv's lowest resolution picks numpy 1.3.0, which does not build on Python 3.12.
- A library installs next to other libraries in one environment, so a needless floor or cap in one of them refuses a combination that would work.

**Decision.**

- **Scope.** Third-party requirements in `[project.dependencies]` and `[project.optional-dependencies]` of the published packages (`packages/*`, `barn/*`). Internal ones (`haywire-*`, `haybale-*`) stay lockstep (ADR 0087).
- **A floor is the oldest version known to work.** Every requirement has one. It goes up only when a feature, a bug fix or a security fix needs it, and a comment next to it gives the reason when the reason isn't obvious from the code.
- **No caps and no exact pins** without a known break, named in a comment (`mcp>=1.28,<2`: MCP 2 changes the server API).
- **A requirement is declared where it is imported**, and only there (`scripts/check_deps.py`); a package does not repeat its dependencies' dependencies.
- **CI holds the floors true.** The `floors` job resolves every direct requirement to its floor (`uv sync --resolution lowest-direct`) and runs the non-browser tests on Linux, on every pull request and on master.
- The workspace's dev group gets floors too, at the version in use: the job lowers it as well. They follow no policy; they only stop the job from installing a 2015 pytest.

**Considered.**

- *Floors at the version current when written.* Today's practice; that is how the opencv floor happened.
- *Caps at the next major as a precaution.* They refuse working combinations, and a library cannot lift a cap in its dependency's metadata.
- *Testing floors only before a release.* Under batched releases (ADR 0087) a broken floor would surface weeks after the change that broke it.
- *Floors from Python 3.12 support alone.* Correct as a lower bound, but proves nothing without a test.

**Consequences.**

- A change that needs a newer API raises the floor in the same commit, or the `floors` job fails.
- A floor below what another requirement forces (numpy 1.26 while opencv 5 needs numpy 2) is not tested by the job until that requirement drops. It still belongs there: it is what this package needs.
- The org libraries can run the same job through the reusable library CI, as a later step.
```

### Draft CS-I5

```markdown
### CS-I5 · A third-party requirement has a floor, and a cap only for a known break

`"numpy>=1.26"`, not `"numpy"` (any version, so it allows a version that does not build)
and not `"numpy==2.3.5"` (refuses everything else). The floor is the oldest version known
to work. It goes up only for a feature or fix the code needs, with the reason in a
comment when the code doesn't make it obvious. A cap (`<2`) or exact pin names the break
it guards. Internal `haywire-*` and `haybale-*` floors follow ADR 0087 instead.

**Why**: a library installs next to others in one environment. A floor with no reason
(`opencv-contrib-python>=5.0.0.93`) kept visiongraph 1.3.0 from installing (ADR 0095).
**Enforced by**: the `floors` CI job (each floor works) and review (no cap without a
reason). **Scope**: libraries too.
```

## 2. The lowest-version CI job

**Recommended:** a `floors` job in core's `.github/workflows/ci.yml`. Linux
(`ubuntu-24.04`) only, Python 3.12 (the `requires-python` floor), the non-browser tier, on
every pull request and on master, beside `tests`:

```yaml
  # Every direct requirement at its floor (ADR 0095). UV_RESOLUTION applies to every uv
  # command: a plain `uv sync` after a lowest-direct lock quietly relocks at highest.
  floors:
    name: floors
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    env:
      UV_RESOLUTION: lowest-direct
    steps:
      - checkout, setup-uv, uv python install (as in tests)
      - run: uv sync --upgrade --all-extras --dev
      - name: Raise the file-watch limit
        run: sudo sysctl -w fs.inotify.max_user_instances=8192
      - name: pytest (not browser, not perf) at the floors
        run: uv run pytest -m "not browser and not perf" -n 4 -q --maxfail=0
```

- **Why the non-browser tier:** it covers what the floors change: cattrs, packaging,
  watchdog, huggingface_hub, numpy. The browser tier mostly tests nicegui, whose floor is
  the version in use anyway. Locally the browser tier passed at the floors too (430 passed),
  so adding it later costs only runner time.
- **Why Linux only:** a resolution is the same on every platform. What differs on macOS is
  whether an old version ships a wheel. That's rare for these packages, and the regular
  macOS jobs don't test old versions either.
- **Why every PR:** about 4 minutes, in parallel with the other jobs, and a floor broken by
  a change shows up in that change's PR. A nightly would need a new workflow and a person
  who reads it.
- **Two traps:** `uv lock --resolution lowest-direct` followed by a plain `uv sync`
  relocks at highest without saying so (my first run tested the newest versions this way).
  And once the lock is in lowest-direct mode, uv keeps the versions it already holds:
  after #237 lowered the opencv floor, opencv stayed at 5.0.0.93 until
  `--upgrade-package`. So the job sets `UV_RESOLUTION=lowest-direct` and runs
  `uv sync --upgrade --all-extras --dev`. The insight records both.
- **Org libraries, later:** a `floors` job in `going-haywire/.github`'s `library-ci.yml`,
  with the same Linux-only, non-browser setup and an input to switch it off. That's a
  separate PR in `.github`, then each library's caller pins the new release (#231).
  For a library that installs core from PyPI it also tests its `haywire-core` floor. For a
  development library, core comes from the path source, so it doesn't.

## 3. The audit

Locally, with the proposed specs: `uv lock --resolution lowest-direct` resolves and
`uv sync --all-extras --dev` installs. Results:

- **Non-browser tier: 10234 passed**, 2 skipped, 2 xfailed (3 min 51 s).
- **Browser tier: 430 passed**, 2 skipped, 1 xpassed.
- **audio at numpy 1.26.4: 158 passed.** opencv 5 forces numpy 2.0 in the workspace, so I
  tested this one by hand.
- **Today's specs, before any change:** `uv lock --resolution lowest-direct` fails. The
  resolver picks numpy 1.3.0 for haybale-audio, and its `setup.py` is Python 2 and does
  not build.

"At floor" is the version the lowest-direct resolution installed: what the job tests.

### haywire-core

| Requirement | Now | Code needs | Proposed | At floor | Reason |
|---|---|---|---|---|---|
| nicegui | `>=3.18.0` | the framework | `>=3.18.0` | 3.18.0 | unchanged; #9 set it on purpose |
| watchdog | `>=6.0.0` | `Observer`, `FileSystemEventHandler`, `observers.api.BaseObserver` | `>=4.0` | 4.0.0 | 6.0 was the version current at the time; 4.0 is the first with Python 3.12 wheels, and the tests pass |
| injector | `>=0.22.0` | `Injector`, `Module`, `provider`, `singleton` | `>=0.22.0` | 0.22.0 | unchanged |
| attrs | `==25.4.0` | never imported | **removed** | (26.1.0 via cattrs) | core never imports it. The pin only mirrored cattrs 25.3's own `attrs>=25.4.0`, and cattrs brings attrs itself. `check_deps.py`'s `KNOWN_OK` entry and the release skill's note go with it |
| cattrs | `==25.3.0` | `cattrs.preconf.json.make_converter`, `unstructure`, `dumps` | `>=23.2` | 23.2.1 | added as "latest" with *new PrimitiveType approach* (`3d88fd8c8`), no reason in log, insights or ADRs. 23.2 is the first release for Python 3.12; the API used has existed since 22.1 |
| toml | `>=0.10.2` | | `>=0.10.2` | 0.10.2 | unchanged (the last release) |
| tomlkit | `>=0.13` | comment-preserving edits | `>=0.13` | 0.13.0 | unchanged (#`86cf30c33` relies on it) |
| packaging | bare | `Version`, `SpecifierSet`, `Requirement`, `canonicalize_name` | `>=23.2` | 23.2 | first with Python 3.12 classifiers; the strict PEP 440 parsing of 22.0 is what the code expects |
| typing_extensions | bare | `TypedDict` | `>=4.6` | 4.14.1 (cattrs/nicegui force it) | the first floor that also covers 3.12 |
| markdown2 | `>=2.5` | | `>=2.5` | 2.5.0 | unchanged |
| pygments | `>=2.18` | `HtmlFormatter` | `>=2.18` | 2.20.0 (nicegui forces it) | unchanged |
| fastapi | bare | `FastAPI`, `Request`, responses | `>=0.109.1` | 0.133.0 | nicegui's own floor. starlette 1.3.1 (also from nicegui) forces 0.133 in practice, which the job tests |

### haywire-studio

| Requirement | Now | Proposed | At floor | Reason |
|---|---|---|---|---|
| jedi | `>=0.19` | `>=0.19` | 0.19.0 | unchanged: 0.19 is the first for Python 3.12 |
| fastapi | bare | `>=0.109.1` | 0.133.0 | as in core |
| mcp | `>=1.28,<2` | `>=1.28,<2` | 1.28.0 | unchanged: the low-level server API needs 1.28, and the cap guards MCP 2's break, as the comment will say |
| psutil | bare | `>=5.9.6` | 5.9.6 | first with Python 3.12 wheels |
| cryptography | `>=42` | `>=42` | 42.0.0 | unchanged (`7cd396c8f`, security) |
| anyio | **undeclared**, imported | `>=4.5` | 4.16.0 | `check_deps.py` reports it missing. 4.5 is mcp's floor |
| httpx | **undeclared**, imported | `>=0.27.1` | 0.28.0 | as above; mcp's floor |

### barn

| Library | Requirement | Now | Proposed | At floor | Reason |
|---|---|---|---|---|---|
| audio | numpy | bare | `>=1.26` | 2.0.0 (opencv forces it); audio passes on 1.26.4 | first with Python 3.12 wheels |
| audio | samplerate, soundfile, sounddevice | `>=0.2.4`, `>=0.12`, `>=0.5` | unchanged | 0.2.4, 0.12.0, 0.5.0 | tests pass at each |
| image | numpy | bare | `>=1.26` | 2.0.0 (opencv 4.13 forces it) | as audio. **This line sits right above opencv's: see decision B** |
| image | opencv-contrib-python | `>=4.13.0.90` (#237) | untouched | 4.13.0.90 | #237's AVIF reason; image tests pass at the floor (255 passed) |
| image | pillow | `>=12.0` | unchanged | 12.0.0 | tested at 12.0 only |
| image | fastapi | bare | `>=0.109.1` | 0.133.0 | as core |
| image | typing_extensions | bare | **removed** | | no longer imported (`check_deps.py`: unused) |
| image | torch (extra `torch`) | bare | `>=2.2` | not installed: `--all-extras` doesn't reach a member's extra, as in today's CI | first for Python 3.12 |
| models | huggingface_hub | `>=2.4` | unchanged | 2.4.0 | the code reads private modules (`_tree_cache`, `utils._shared_blobs`) that 2.4 has; noted in a comment |
| models | httpx | `>=0.28` | unchanged | 0.28.0 | |
| models | fastapi | bare | `>=0.109.1` | 0.133.0 | as core |
| models | starlette | bare | `>=0.27` | 1.3.1 (nicegui forces it) | `ClientDisconnect` exists in every release; 0.27 is mcp's floor |
| marketplace | packaging | bare | `>=23.2` | 23.2 | as core |
| core, example, testing | typing_extensions | bare | **removed** | | not imported (`check_deps.py`: unused) |
| graph-editor, haystack, share, studio, TEST_A | (nicegui, toml) | | unchanged | | |

### Workspace dev group (not published)

`pytest>=9.1`, `pytest-cov>=7.0`, `pytest-timeout>=2.4`, `pytest-xdist>=3.8`,
`mypy>=2.1`, `playwright>=1.60`, `pytest-playwright>=0.8`, `requests>=2.32`, all at the
version in use. **pytest 9.0 fails** `test_rotation_keeps_the_centre_and_four_turns_come_back`
(nested `approx`), so the floor is 9.1.

## Found on the way (not this task)

**pytest 9.2.0, the current release, fails the same test** (checked against today's lock
with `uv run --frozen --with pytest==9.2.0`). The next lock upgrade on master breaks it.
The test compares a dict of tuples with `pytest.approx`. 9.1 accepts that, 9.0 and 9.2
don't. The fix is one assertion per node. It's a separate `fix/` task. I left it out of
this one to keep the PR to dependencies.

## Decisions

- **A. The CI job.** (a) Linux, non-browser tier, every PR and master, in `ci.yml`
  *(recommended)*; (b) as (a) plus macOS once a PR is ready; (c) a nightly workflow
  instead.
- **B. haybale-image's numpy line**, right above the opencv line. A change here conflicts
  with `fix/image-opencv-floor`. (a) That task adds `numpy>=1.26` with its opencv change,
  and this PR leaves the numpy line alone *(recommended)*; (b) this PR changes it, and
  whichever PR merges second resolves a one-line conflict. Either way the other image lines
  (fastapi, typing_extensions, torch) change here: they're far enough from the opencv line
  to merge cleanly.
- **C. Declared vs. imported.** (a) This PR also removes the four unused
  `typing_extensions` and declares studio's `anyio` and `httpx` *(recommended: the ADR's
  "declared where imported" bullet, and `check_deps.py` comes out clean)*; (b) floors only,
  with the rest left for later.
- **D. The rule's home.** (a) ADR 0095 plus CS-I5 under *Imports* *(recommended)*; (b) a
  new *P · Packaging* area in the coding standards, starting with CS-P1.
