# Framework version gate — inquisition-settled design

Status: design settled via `/inquisition`, unimplemented.

Diagnosis this builds on: [`internals/handoff/library-manager-version-gate.md`](../handoff/library-manager-version-gate.md).
Restart/self-update research: [`internals/issues/REPORT_framework_self_update_and_restart.md`](../issues/REPORT_framework_self_update_and_restart.md).

## Problem

A `haywire init` project pins `haywire-studio~=X.Y.Z` at scaffold time
(`init.py:23-39`, `_release_pin()`) and never moves. The framework is
deliberately frozen per-project, and **nothing detects that a newer framework
release exists** — the marketplace catalogs haybales only, never
`haywire-core`/`haywire-studio`.

Meanwhile the marketplace tags haybales as updateable by comparing the cached
`min_version` against the installed version (`refresh.py:41-67`), and
`uv pip install <spec>` (`library_manager.py:273-305`) resolves **fresh**
against the requested spec's tree. Already-installed packages are only reuse
candidates — their declared `Requires-Dist` is not binding. So taking a haybale
update can pull `haywire-core` forward while `haywire-studio` stays put.

Old studio + new core = `ImportError` at runtime (the observed incident: the
`get_bridge` → `get_stdout_tee` rename in `a0198949`, shipped in core 0.0.31,
against studio 0.0.29).

Empirically tested in the handoff doc:

| Approach | Result |
| --- | --- |
| Studio pins `haywire-core~=0.0.31` | Silently plans a downgrade, no warning |
| Studio pins `haywire-core==0.0.31` | Still silently downgrades |
| `uv pip install -c constraints.txt` | ✅ Refused — "No solution found… unsatisfiable" |

The user is handed an inviting ▲ "v0.0.34 available" with no signal that taking
it breaks their studio, and — until now — no way to update the framework even
if they knew.

## Goal

Three things that compose:

1. **Make the unsafe install impossible** (constraint file → resolver refusal).
2. **Give the user a way out** (framework update affordance in the shell).
3. **Warn before the click, not after** (framework floor in the catalog).

## Decisions

### 1. Constraint-file gate (correctness backstop)

`dry_run()` and `install()` pass `-c <constraints-file>` pinning
**`haywire-core`, `haywire-studio`, `nicegui`** to their **currently-installed
exact versions**, read from the running venv via `importlib.metadata.version()`.

A conflict makes uv's resolver fail → the existing `RuntimeError` →
`ui.notify(type="negative")` path already carries it. Only the constraint file
and a better message are new.

- **Not** the full `pip_publish_order` set — the in-monorepo `haybale-*`
  libraries *are* what marketplace installs are supposed to upgrade.
- Pinned to installed reality, not to studio's declared `Requires-Dist`: a
  declared want can itself be stale; what is running cannot.
- `dry_run()` and `install()` must use **identical** flags, or the pre-eviction
  set and the actual install diverge (same rule as the existing `--no-sources`).

### 2. Framework update lives in Studio, not the marketplace

Updating the framework is **not** a marketplace concern — the marketplace
depends on the framework it would be updating. The affordance is a
**check-for-updates control in the app shell** (`shell.py:656` topbar /
`:677` statusbar), owned by `haywire-core`.

**Mechanism — pin-bump only, no in-process `uv sync`:**

```text
① [⟳ Check for updates]              shell control, sticky dot
        ↓  offline → "Couldn't reach PyPI. Try again later."
        ↓  up to date → "Haywire 0.0.34 — you're up to date."
② "Haywire 0.0.35 is available"  (you're on 0.0.34)
   ┌──────────────────────────────────────────────┐
   │  What happens:                               │
   │  1. Your pyproject.toml pin is updated       │
   │  2. Studio quits                             │
   │  3. You run `uv run haywire` — the new       │
   │     version installs on launch               │
   │                          [Continue] [Cancel] │
   └──────────────────────────────────────────────┘
        ↓
③ checking…  (uv sync --dry-run, diffed vs baseline)      <1s
        ↓ conflict → "haybale-foo requires haywire-core<0.0.35.
        ↓             Update or remove it first."  [Close] — nothing written
④ "No conflicts found."          ← framing: NOT a promise about launch
        ↓
⑤ "Unsaved work will be lost."
                     [Continue anyway] [Cancel]
        ↓
⑥ write pin → verify → app.shutdown()
        ↓
⑦ terminal (atexit, after uvicorn's own shutdown lines):
     ─────────────────────────────────────────────
      Haywire updated:  0.0.34 → 0.0.35  (pinned)
      Restart to load it:   uv run haywire
     ─────────────────────────────────────────────
```

Writes the **root `pyproject.toml` only** (`haywire-studio`,
`haybale-marketplace` — every lockstep dist declared there). The scaffolded
barn library's own `haywire-core` floor is left alone: `~=0.0.31` already
admits `0.0.34` (verified — `~=0.0.31` ≡ `>=0.0.31, ==0.0.*`), so it is not a
hazard for patch moves.

**Step ③ — pre-write conflict check.** `uv sync --dry-run` runs against the
**real** workspace before anything is written (a temp-dir copy resolves
*differently* — `[tool.uv.sources]` carries `{workspace = true}` and, under
`--dev`, absolute dev-repo paths). Write-resolve-restore: hold the original
`pyproject.toml` text in memory, write the proposed pin, resolve, restore in a
`finally`.

Measured <1s on the dev repo. **Its output is noisy with pre-existing drift** —
a real run reported "Would uninstall 33 packages" (editable
`haybale-visiongraph` and its tree) purely because the venv held packages the
lockfile didn't. **Diff against a baseline dry-run** and show only what *our*
pin changes, or the dialog alarms the user with 33 removals it didn't cause.

**What the check is worth.** It reliably blocks a bad pin — an unsatisfiable
resolution (a barn library whose floor excludes the new core) is deterministic
and knowable now. It does **not** bless a good one: resolution is not
installation, the real sync happens later inside `uv run` (downloads, sdist
builds, a possibly-moved index). Word the result "no conflicts found", never
"your next launch will succeed".

**Step ⑤ — no unsaved-work detection.** A static confirmation. `GraphEntry.unsaved`
and `is_haystack_dirty` live in `haybale-haystack`, which `haywire-core` cannot
import; querying across that boundary would need a new protocol, and the user is
better placed to know. Cancel, save, come back. Matches the existing
close-confirmation precedent (`haystack_editor.py:415`) — warn, never save on
the user's behalf.

**Step ⑥ — `app.shutdown()`.** Verified available and safe: under Haywire's
`reload=False` it takes the `Server.instance.should_exit = True` branch
(`nicegui/app/app.py:194-204`), a graceful uvicorn shutdown, so lifespan
handlers run and the Farmhand MCP host stops cleanly — the exact path
`os.execv` would have bypassed. The user never touches the terminal to quit.

**Step ⑦ — `atexit`, not `on_shutdown`.** Registered when the update is
confirmed, so the banner prints *after* uvicorn's own shutdown logging and is
genuinely the last thing on screen.

**One decision drives both the banner and the exit code.** They are not the same
mechanism — the banner is for the human at the terminal, the exit code is for a
future supervisor — but they must never disagree. Set a single
update-confirmed flag that produces both: `atexit.register(...)` for the banner
now, and the sentinel exit code for the supervisor later. A single source means
an exit *without* an update (cancel, crash, ordinary quit) cannot print
"Haywire updated", and making the banner conditional under a supervisor becomes
one check rather than reconciling two states.

Ordering verified: `atexit` handlers run during interpreter shutdown — after
`SystemExit` propagates, before the code reaches the shell — so the banner
still prints last *and* the code still arrives intact.

**No explicit sync step.** `uv run` syncs by default (`--no-sync` exists to opt
out), so `uv run haywire` installs the new pin at launch. This is why ③ matters:
that install is unsupervised and happens after all our UI is gone.

**Why not in-process upgrade + self-restart** (research, all verified against
primary sources):

- Home Assistant — the closest analogue — has an in-app restart button **only
  because a supervisor exists**; the bare pip/venv install gets neither managed
  updates nor managed restarts.
- On Windows, upgrading `haywire-studio` means replacing `haywire.exe` **while
  it runs**; `DeleteFileW` fails on files with open handles.
- Under `os.execv`, NiceGUI's shutdown handlers never run — bypassing rather
  than avoiding the lifespan/task-scope trap, leaving a stale identity sidecar
  and a hard MCP transport drop.
- Deferring the sync to the next `uv run` collapses the mixed-version window to
  zero and sidesteps the Windows lock entirely.

A supervisor-parent design (uvicorn's spawn-fresh-child + Home Assistant's
sentinel exit code) remains open as a later step for true one-click. Blocked on
verifying uv's install atomicity.

**Exit-code seam (built now, unused by A).** `run_app()` currently returns
`None` and `main()` returns without a code on the app path (`app.py:355-357`) —
subcommands propagate one (`raise SystemExit(handler(args))`), the app does not.
A supervisor distinguishes "user quit" from "restart me" by a sentinel exit code
(Home Assistant's `RESTART_EXIT_CODE = 100`); today every exit looks identical
from outside. Make `run_app()` return an exit code and `main()` propagate it,
and have the update-confirmed path return a distinct code. Nothing in A reads
it — this is ~3 lines that make C additive instead of an entry-point refactor.

Audited for other blockers; none found. Carrying over unchanged: the pin write,
the step-③ conflict check, and `app.shutdown()` (already the graceful
`should_exit` path both models want). A supervisor would replace only step ⑦'s
"relaunch it yourself" — so the `atexit` banner must become conditional on no
supervisor being present. The `__mp_main__` guard (`app.py:360`) already
anticipates spawn-based multiprocessing, and `get_stdout_tee().install()`
ordering is load-bearing (uvicorn resolves `ext://sys.stdout`), so a parent
process must not re-wrap stdout — the child keeps owning it.

**Pin-write → restart window:** no special handling. The gate stays truthful to
what is *running*, so an install refused during the window is correctly
refused.

**Startup mismatch check (derived, not stored).** On startup compare the
declared floor in the root `pyproject.toml` (`Requirement(...).specifier`) with
`importlib.metadata.version("haywire-studio")`. If **floor > installed**, show:

> `pyproject.toml` requests 0.0.35 but 0.0.34 is running — this environment
> wasn't synced. Launch with `uv run haywire`.

No stored marker: a marker can go stale (hand-edited pin, upgrade by other
means), whereas pin-vs-installed is the actual condition and is always current.
Success needs no acknowledgement — the notice simply stops appearing.

What it really catches is a **bypassed** sync (`--no-sync`/`UV_FROZEN`, a bare
`.venv/bin/haywire`, an IDE run config), not a failed one: if the resolve fails
at launch, studio never starts and there is no UI to report it. That population
— developer machines — is exactly where the original `ImportError` skew arose.

### 3. Marketstall gains `requires_haywire`

New `Haybale` field storing the **full PEP 440 specifier** (`>=0.0.31`,
`~=0.0.31`, `>=0.0.31,<1.0.0`), not a bare version — the author picks the
operator.

Written at share time from **one authored answer** into **two carriers**:

| Install path | Guarded by |
| --- | --- |
| `uv add haybale-foo` (bare) | `Requires-Dist` floor in the wheel — nothing else |
| marketplace install | constraint file (correctness) + `requires_haywire` (pre-emptive gate) |

These are **disjoint**, not redundant. Dropping the `pyproject.toml` floor would
leave the bare-`uv` path — the one with no UI to warn anyone — unguarded.

**A floor is a restriction on consumers, not a record of what you tested.**
Raising it forces every consumer to upgrade their project first, and some can't
or won't. So: **lowest necessary**, and the scaffold default becomes `>=X.Y.Z`
(not `~=X.Y.Z`).

Share-time prompt, following the deps-drift consequence pattern
(`_overview_edit_dialog.py:244-249` — concrete counted consequences, note empty
when there is none):

```text
Framework requirement                    haywire-core, installed: 0.0.34

  ● >=0.0.31   keep the current declaration              [recommended]
      Usable by projects on Haywire 0.0.31 and newer.
      No consumer has to upgrade.

  ○ >=0.0.34   require the version you built against
      Consumers on 0.0.31–0.0.33 must update their project
      before they can install this library.

  ○ ~=0.0.31   compatible release
      Also excludes Haywire 0.1.0 and newer.

  ○ custom …   any valid PEP 440 specifier, validated on entry
```

- **One project-wide answer**, matching lockstep versioning (ADR 0023).
  Libraries built and tested against one installed framework have no honest
  basis for differing floors.
- **CLI**: `--requires-haywire '<specifier>'`. A `--yes` run with no flag
  **keeps the declared floor** — that default is inert (changes nothing, locks
  nobody out), which is exactly what `--yes` is for. This differs from the
  drift precedent, which refuses in `--yes` mode (`cli.py:66-72`) because
  *both* of its options mutate and one is lossy; here doing nothing is safe.
  Raising a floor — the consequential, consumer-excluding direction — always
  requires the explicit flag.
- **No MCP carrier.** Share Farmhand tools were planned but dropped; only
  `catalog_tools.py` and `install_tools.py` exist. The share-wizard plan's
  "CLI / UI / MCP" line is an aspiration, not current state (that same doc
  lists the wrappers as out of scope). If they are ever built they inherit the
  same optional parameter.
- **Consistency check at share time** (remediable-precondition shape): re-read
  the library's actual `haywire-core` specifier and compare to
  `requires_haywire`. **Compare parsed `SpecifierSet` objects, never raw
  strings** — `packaging` reorders on `str()` (`>=0.0.31,<1.0.0` →
  `<1.0.0,>=0.0.31`), so string comparison yields false drift.
- **No ceiling by default.** A `<0.1.0` stamped at scaffold time becomes a lie
  the moment `0.1.0` ships and nobody will remember to update it. Authors who
  want a ceiling type one. **The `0.1.0` release must revisit every published
  floor** — record this as a release-checklist item.

### 4. `min_version` → `version` (breaking rename)

The field was **never** a floor. It is written as `min_version=version` at
publish (`marketstall.py:140`), displayed as the version
(`library_overview_editor.py:333`), and compared as the version
(`:349`, `refresh.py:63`). Nothing resolves against it. The docs have to
disclaim it (*"a floor, not 'latest'"*) — a doc patch over a misnomer.

With `requires_haywire` (a real specifier) arriving alongside, keeping
`min_version` (a bare version that is not a minimum) would be actively
misleading.

- **Hard rename, no back-compat alias.** Population is one external stall
  (visiongraph, fixable) + monorepo barns (sweepable).
- Format stays strict `x.y.z`, parsed with `Version()` — its only job is the
  update comparison.
- **Strict validation**: a `[[haybales]]` entry without `version` raises
  `MalformedMarketplaceError`, matching the existing `name` check
  (`parsing.py:31-33`). Never parse to `""` — that silently disables update
  reporting via `if h.stale or not h.min_version: continue`.
- **`[[caches]]` are discarded and refetched** on parse failure. They are
  derived artifacts, and `_merge_cache()` reads the previous cache
  (`refresh.py:148-158`), so a strict parser would otherwise block the very
  refresh that heals the file. Cost: one cycle of `stale` bookkeeping.

### 5. Loop closure

A framework-blocked haybale install names the shell control as the remedy —
a message referencing it, which keeps framework updates out of the
marketplace's ownership.

## Implementation order

Part 1 is independent and shippable alone. Parts 3–4 are coupled: the rename
must land before `requires_haywire`, or the schema churns twice.

1. **Constraint-file gate** (`library_manager.py`) — the safety fix. No schema
   change, no UI. Ships first, alone.
2. **`min_version` → `version`** — schema rename, strict validation, cache
   discard, find/replace sweep over in-repo stalls + barns, fix visiongraph.
3. **`requires_haywire`** — `Haybale` field, parsing, share-wizard prompt,
   dual write, `SpecifierSet` consistency check.
4. **Shell check-for-updates control** — PyPI query, dialog, pin write, sticky
   indicator.
5. **Scaffold default** `~=` → `>=` in `init.py`.
6. **Glossary + docs** — see tasks below.

## Tasks

- [ ] `library_manager.py`: build constraint file (core/studio/nicegui, installed
      exact versions); pass `-c` in `dry_run()` **and** `install()` identically;
      translate resolver failure into "Update Haywire Studio first" naming the
      shell control.
- [ ] `parsing.py`: `min_version` → `version`, required, raise
      `MalformedMarketplaceError` when absent.
- [ ] `types.py`: rename field; add `requires_haywire`; add both to
      `_TOML_FIELDS`.
- [ ] `refresh.py`: rename usages; discard-and-refetch on cache parse failure.
- [ ] `library_overview_editor.py` / `library_browser_editor.py`: rename usages.
- [ ] Sweep in-repo `marketstall.toml` / stall files + barns; fix visiongraph.
- [ ] Share pipeline: framework-requirement step (project-wide, consequence-
      annotated options, custom PEP 440 input validated on entry).
- [ ] Share pipeline: dual write (`pyproject.toml` floor + `requires_haywire`)
      from one answer; `SpecifierSet`-based consistency precondition.
- [ ] `cli.py`: `--requires-haywire '<specifier>'`; `--yes` with no flag keeps
      the declared floor (inert default, no refusal).
- [ ] `marketstall.py`: emit `requires_haywire`.
- [ ] `shell.py`: check-for-updates control + sticky indicator; PyPI query
      (offline → "couldn't reach PyPI"; current → "you're up to date").
- [ ] Update dialog: what-happens explainer → conflict check → unsaved-work
      confirmation → pin write → `app.shutdown()`.
- [ ] Conflict check: baseline `uv sync --dry-run`, then write-resolve-restore
      with the proposed pin (original text in memory, restored in `finally`);
      **diff against baseline** so pre-existing venv drift isn't reported as
      ours. Frame the result "no conflicts found".
- [ ] Update-confirmed flag drives **both** the `atexit` banner ("Haywire
      updated: X → Y (pinned) / Restart: uv run haywire") and the exit code —
      one source, so they cannot disagree.
- [ ] `app.py`: `run_app()` returns an exit code, `main()` propagates it
      (`raise SystemExit(...)` on the app path too); update-confirmed exit
      returns a distinct code. Unused by this plan — the seam for a supervisor.
- [ ] Startup mismatch check: declared floor vs installed → "environment wasn't
      synced" notice.
- [ ] `init.py`: scaffold `>=X.Y.Z` instead of `~=X.Y.Z`.
- [ ] **Glossary**: update `min_version` → `version` entry; add
      `requires_haywire`; update the `updates_available` entry.
- [ ] Docs: `haybale-package-canon.md`, `haybale-marketplace-arch.md`,
      `sharing-libraries.md`, `subscribing-to-marketplaces.md` — all carry
      `min_version` examples and the "floor, not latest" disclaimer.
- [ ] Release checklist: `0.1.0` must revisit every published framework floor.

## Deferred

- **Supervisor-parent restart** for true one-click. Blocked on verifying uv's
  install atomicity (hardlink-vs-copy, write atomicity, behaviour when the env
  is in use) and on Windows testing. The exit-code seam is built as part of this
  plan, so what remains is the supervisor itself.
  **Undecided, needs its own design session:** the `haywire` console script is
  owned by `haywire-studio` (`pyproject.toml:26-27`), so a supervisor shipped
  there would upgrade *itself* — reintroducing the Windows entry-point lock this
  design avoids. Options include a separate supervisor package, or keeping
  `uv run` as the outer layer so the supervisor wraps only the server. Do not
  pre-empt this here.
- **Share-time framework floor lag warning** — `_detect_pyproject_version_lag()`
  skips non-haybale dists (`detect.py:104-113`), so a stale `haywire-core` floor
  is invisible today. **Advisory-only**, no auto-fix: for haybale deps the
  correct floor is mechanically "what's installed" (lockstep), but for
  `haywire-core` the installed version is only an upper bound on what the
  library needs. Separate issue.

## Corrections made during the inquisition

- **`~=0.0.31` does admit `0.0.34`.** An earlier claim that the barn library's
  pin causes resolver conflicts was wrong (verified with `packaging`). It only
  bites at `0.1.0`.
- **In-process self-restart was rejected** on research evidence, reversing the
  initial preference for one-click.
- **Verbatim string comparison of specifiers is unsafe** — `packaging` reorders
  on `str()`.
