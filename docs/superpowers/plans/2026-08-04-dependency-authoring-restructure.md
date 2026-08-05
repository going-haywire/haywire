# Dependency authoring restructure — share wizard

**Status:** LANDED 2026-08-05 (branch `feat/dependency-authoring-restructure`)
**Date:** 2026-08-04
**Supersedes:** the Union/Replace apply-mode model in `steps/drift.py`

> Implementation notes, where it differed from this spec:
>
> - `--yes` declares undeclared imports with **no pin** rather than `>=installed`,
>   matching the interactive screen's default. Re-detecting to synthesize a floor
>   was both redundant (the report already names what is missing) and wrong under
>   §1.1 — an unpinned declaration constrains no consumer.
> - `check_requires_haywire` → `check_require`; `haywire_core_floor()` survives as
>   a thin wrapper over the new `haywire_core_requirement_of()`, since callers that
>   only want the specifier outnumber those needing the three-way distinction.
> - The doc sweep was wider than §8's checklist: `haybale-package-canon.md`,
>   `haybale-marketplace-arch.md` and `sharing-libraries.md` all carried
>   `requires_haywire` TOML samples, and the marketplace arch doc listed the
>   Detect Dependencies button in its capability matrix.

---

## 1. Problem

The share wizard writes one authored answer — the `haywire-core` floor — through
**two independent carriers**: the `[project] dependencies` entry in each barn
library's `pyproject.toml`, and `requires_haywire` in the marketstall entry.
Nothing derives one from the other, so they drift.

Three concrete vectors, all present in the code today:

1. **The drift step clobbers the framework floor.** `apply_drift_replace()`
   overwrites the entire `[project] dependencies` array from `detect_deps`
   output, which emits `haywire-core>={installed}`. An author who deliberately
   kept `>=0.0.20` silently gets it raised. Worse: `plan_framework()` is called
   *after* the drift apply, so its "keep the current declaration" option — the
   recommended, consequence-free-looking one — computes from the already-clobbered
   value. The pre-selected safe choice is the one that raises the floor.

2. **`--yes` publishes an empty gate.** `_resolve_framework_answer` returns
   `None` without `--requires-haywire`, printing "Framework requirement
   unchanged". `apply_framework` never runs, `pipeline.requires_haywire` stays
   `None`, and step 5 stamps `requires_haywire = ""` on every entry while the
   pyprojects carry a real floor.

3. **The consistency check cannot see vector 2.** `check_framework_consistency`
   skips on `if not declared: continue`, so an empty `requires_haywire` is
   treated as "nothing to compare". It also runs at step 1, before anything is
   written — it validates the *previous* publish's state.

The root cause is a seam drawn **by carrier** instead of **by decision type**.
One dependency (`haywire-core`) is a policy choice about consumers and needs an
author; the rest are facts about what the code imports and need a report.

### 1.1 The compounding problem: floors are not computable

`pyproject_version_lag` flags declared haybale floors that lag the installed
version, and the fix raises them. This applies the author's dev-machine state as
a compatibility statement for consumers — the exact anti-pattern the codebase
already rejects for third-party deps (`test_union_keeps_user_spec_for_third_party`,
"would narrow consumer compatibility based on the author's dev-machine state").

`haybale_dists` is derived from `haywire.libraries` entry points, so it includes
**third-party haybales the publishing author does not control**. Raising those
floors forces every consumer to upgrade a package the author has no authority
over.

The correct floor — the lowest version that still works — requires resolving and
testing each candidate version. Static AST scanning cannot reach it. Every
automated floor is therefore a guess, and a tool that prompts for a guess is
worse than one that stays silent, because the guess ships with the authority of
a deliberate choice.

---

## 2. Decisions

Settled through interview. Each row is a decision, not a derivation.

| # | Decision |
|---|---|
| Q1 | One vocabulary across all surfaces; the step split is wizard-only |
| Q2 | **Detect Dependencies affordance removed** from the Library Overview Editor entirely — dependency authoring is share-wizard-only |
| Q3 | Screen for removals is **removals only**; additions are a separate screen |
| Q4/Q8 | Per-item pulldowns, not modes; lag gets its own screen (**B**) |
| Q7 | **No automatic floor raising for any haybale.** Lag becomes a fact, out of `has_drift` |
| Q9 | Marketstall `require` is **derived** per-library from the pyproject floor at write time |
| Q10 | Field becomes `require = "haywire-core>=0.0.38"` — **full requirement token** |
| Q11 | **Breaking change** — no migration, no dual-read |
| Q12 | `scripts/generate_marketstall.py` adopts the new field + three-way logic; derivation helper is **shared** |
| Q13 | **Entry-level ownership** — each step mutates only the entries it owns |
| Q14 | Acknowledgement survives **only** for undeclared-but-imported deps |
| Q15 | **Two pipeline modules**: `detect.py` (pure) and `dependencies.py` (all writes) |
| Q16 | Screens named after the **finding**, not the operation |
| Q17 | Glossary lands **with the code**, not now |
| Q18 | Pre-existing doc inaccuracies fold into this spec's checklist |
| Q19 | `_version_tuple` accuracy fixed; five other items are non-goals |

### 2.1 Why `haywire-core` is treated differently

The asymmetry is deliberate and worth defending, because it looks like an
exception:

- it is **one** decision per publish, not N, so it receives real attention
- the framework is the axis authors actually reason about
- the recommended option is **keep declared**, so the default narrows nothing
- the consequence is stated in consumer terms (`_excluded_range` names who is
  locked out)

That is a floor set by an informed human answering one question — not a tool
inferring from installed metadata. Same operator, entirely different epistemics.

---

## 3. The screens

Six screens over two pipeline modules.

```text
1. Detect                  detect.py         pure — writes nothing
2. Framework requirement   dependencies.py   the one authored floor
3. Unused declarations     dependencies.py   declared, not imported
4. Undeclared imports      dependencies.py   imported, not declared
5. Version floors          dependencies.py   floors behind installed
5b. Confirm                dependencies.py   validated preview, then apply
```

Screens are named after the **finding**, not the operation. "Unused
declarations" is true whether the author removes them or keeps them;
"Removals" is true in only one branch. Screen 1's report uses the same three
headings, so a finding reads identically in the report and on the screen that
resolves it.

### 3.1 Screen 1 — Detect

Read-only. Writes nothing. Reports, per barn library:

- **Unused declarations** — declared, not imported (§3.3)
- **Undeclared imports** — imported, not declared (§3.4)
- **Version floors** — declared floor below installed (§3.5), stated as fact
- **Unresolved imports** — nothing could be mapped; highest-risk category,
  given real prominence rather than a footnote
- **Malformed manifest** — `read_manifest_lenient` degradation, which currently
  produces a maximal drift report whose cause is invisible until apply throws

### 3.2 Screen 2 — Framework requirement

UX unchanged from today's `plan_framework()` / `apply_framework()`. Recommended
option remains **keep the current declaration**.

Writes the `haywire-core` entry — and **only** that entry — in every barn
library's pyproject. It is the sole source for the marketstall `require`
(§4).

Because `plan_framework()` now runs **before** any other dependency write, its
"keep the current declaration" option computes from the author's actual prior
declaration. Vector 1 is closed structurally, not by ordering.

### 3.3 Screen 3 — Unused declarations

The only destructive, genuinely optional decision: *remove declarations the
source no longer imports?*

Binary, not a three-way mode. No acknowledgement flag — an unused declaration is
inert, so both answers are legitimate. `detect_deps` cannot see dynamic imports,
so removal remains risky and stays opt-in.

### 3.4 Screen 4 — Undeclared imports

Per-item pulldown, four options:

| option | result |
|---|---|
| **no-pin** | `foo` — declared, no floor. Narrows nothing. |
| **`>=installed`** | `foo>=2.1.0` |
| **custom** | any valid PEP 440 specifier; validated before 5b |
| **skip** | not declared — **sets the acknowledgement flag** |

`skip` is the one outcome with no defensible default reading: the library will
fail to install for consumers. It must be *possible* (the dynamic-import blind
spot makes it occasionally correct) and it must be *marked*.

**`--yes` rule:** refuse only when a detected import has no declaration and no
explicit skip. Removals, floors, and pin choices all have safe defaults, so a
non-interactive publish proceeds through them — a usability gain over today,
where any drift blocks `--yes` entirely.

### 3.5 Screen 5 — Version floors

Per-item pulldown: **keep** / **sync to installed** / **custom**.

Pre-set to the **currently declared specifier**, so the no-interaction outcome is
provably no change. Nothing narrows unless the author reaches in — this is what
preserves the §1.1 guarantee inside an action surface.

Title must stay neutral. "Lags" or "Stale floors" editorialise toward *fix me*,
which is precisely what the fact-not-finding decision removed.

### 3.6 Screen 5b — Confirm

Shows the resulting `[project] dependencies` lines per library. Reachable **only
when every custom entry parses** as a valid PEP 440 specifier. This is the gate,
not a receipt: the write happens after it.

---

## 4. The marketstall `require` field

**Breaking change.** `requires_haywire` (bare specifier) → `require` (full
requirement token).

```toml
# before
requires_haywire = ">=0.0.38"

# after
require = "haywire-core>=0.0.38"
```

### 4.1 Why the token form

The bare-specifier shape cannot distinguish two different states:

| state | bare shape | token shape |
|---|---|---|
| nobody authored an answer | `""` | field omitted |
| deliberately no floor | `""` | `require = "haywire-core"` |
| floor declared | `">=0.0.38"` | `require = "haywire-core>=0.0.38"` |

Screen 4's **no-pin** option makes a floorless declaration something the wizard
actively produces, so the marketstall must be able to say so. The token form is
the only shape of the three that can.

### 4.2 Derived, not authored

`_build_entry_for_library` reads the floor off `lib_dir`'s pyproject at write
time. `pipeline.requires_haywire` no longer feeds step 5.

Consequences:

- **Vectors 2 and 3 become unreachable.** An empty `require` cannot be produced
  by a publish; a library with no `haywire-core` declaration is a screen-1
  finding.
- **`require` becomes per-library.** Today one project-wide string is stamped on
  every entry, so a library with a differing floor is misrepresented. Derivation
  stops assuming agreement.

This is not a new principle — `scripts/generate_marketstall.py` already derives
its value this way, and its docstring makes the same argument ("deriving from it
reproduces the authored answer rather than inventing a second one"). The wizard
diverged from the CI script; this realigns them.

### 4.3 Shared derivation helper

Two near-identical parsers exist and have **already drifted** on the bare case:

- `_haywire_core_specifier(deps)` — `scripts/generate_marketstall.py:185`,
  returns `""` for both absent and bare
- `haywire_core_floor(lib_dir)` — `steps/framework.py:61`, returns `""` for
  absent

Consolidate to one function in **`haywire.core.marketstall`** — where
`check_requires_haywire` already lives, keeping producer and consumer of the
same token side by side:

```python
def haywire_core_requirement(deps: list[str]) -> str | None:
    """None = absent; "haywire-core" = declared, no floor;
    "haywire-core>=X" = declared with a floor."""
```

Parsing splits from IO: the CI script has `deps` in hand, the wizard has a path.

### 4.4 Gate and parser changes

- `check_requires_haywire` gains a token split: parse, verify it names
  `haywire-core`, apply the specifier if any. Bare token → `ok=True`, as absent.
- `parse_haybale` reads **only** `require`. Old marketstalls lose the field →
  treated as absent → gate stays quiet, which `framework_gate`'s docstring
  already sanctions ("a missing `requires_haywire` must never block anything").
- `Haybale._TOML_FIELDS` and the dataclass field rename.
- `InvalidSpecifierError`'s bare-version guard survives unchanged: `"0.0.34"` is
  still malformed, `"haywire-core"` is not.

---

## 5. Entry-level ownership

`set_pyproject_dependencies` replaces the **entire** `[project] dependencies`
array. That is the mechanism behind vector 1. It is replaced by operations that
name what they touch, all going through `edit_toml`:

| operation | owner |
|---|---|
| set one named entry | screen 2 (`haywire-core` only) |
| remove named entries | screen 3 |
| add entries | screen 4 |
| rewrite one entry's specifier | screen 5 |

Screen 3 **cannot** touch the framework entry, because it has no operation that
would express it. The ownership rule becomes structural rather than
conventional — the session's through-line is that correctness held by ordering
is not correctness.

### 5.1 The preservation argument

Entry-level editing also preserves what the tool does not understand.
`[project] dependencies` entries can carry environment markers
(`; sys_platform == "darwin"`), direct references (`foo @ git+...`), and extras
(`visiongraph[onnx,openvino,mediapipe]`). `_format_specifier` regenerates none of
these. Any path that rebuilds the list from detection is lossy for entries it did
not author.

**This closes the extras-loss bug** without a dedicated mechanism: extras were
only ever destroyed via `apply_drift_replace`'s whole-list overwrite, which no
longer exists.

Note the limit: extras are *preserved*, never *validated* — see §7.

### 5.2 Ordering

Append new entries at the end; never reorder existing ones. Today every write
sorts the whole array; entry-level edits leave author ordering intact, which is
more respectful of hand-maintained files.

---

## 6. Pipeline and wizard structure

### 6.1 Modules

`steps/drift.py` is replaced by two modules:

- **`steps/detect.py`** — pure. Multiple consumers: screen 1, `haywire deps
  check`, and anything else needing a read-only dependency report. This is the
  reusable piece, which is why it earns its own module.
- **`steps/dependencies.py`** — every write to `[project] dependencies`,
  including the framework entry. One module owning one file's mutations.

Pipeline goes from 7 to 8 step modules.

### 6.2 Model changes

- `DepDrift.pyproject_version_lag` — retained, but **removed from `has_drift`**.
  Lag is a fact, not drift. `--yes` no longer refuses on it.
- `DepDrift.has_drift` — now true iff a missing-list is non-empty (which is what
  the glossary already claims, incorrectly, today).
- `acknowledge_drift()` narrows to undeclared-but-imported skips only.

### 6.3 Deletions

- `apply_drift_union()` / `apply_drift_replace()` and the Union/Replace vocabulary
- `union_pyproject_deps()` — sole remaining caller was the Edit dialog
- `detect_dependencies()` and `write_pyproject_deps()` in
  `_overview_edit_dialog.py`, **which removes the `haywire_studio` import from
  haybale-marketplace** (one of the two barn→app reaches)
- `check_framework_consistency` — unreachable state under §4.2. The invariant
  becomes a unit test asserting `write_marketstall` output matches each library's
  floor, not a runtime precondition.

### 6.4 Tripwire

`tests/share_pipeline/test_step_sequence.py` hardcodes the seven-module list and
asserts the wizard's `STEPS` covers it. Under §6.1 there are eight modules and
six dependency screens over two of them, so 1:1 no longer holds.

The invariant it was really protecting: **every writing screen has a pipeline
applier**. Restate it that way, and assert the dependency screens all map to
`dependencies`.

`test_framework_step_sits_between_drift_and_version` inverts — the framework
screen now comes **first** among the dependency screens. Its current docstring
justifies the order by commit atomicity; the real reason is now carrier
ownership, and the test should say so.

---

## 7. Non-goals

Explicitly out of scope. Each would at least double the design.

- **Evidence-based floor inference** — resolving old versions to check whether
  imported symbols exist. The only principled basis for an automatic raise, and
  the reason §1.1 concludes floors are not computable. Recorded as the sole
  legitimate future path to automatic raising.
- **Extras validation** — extras are preserved (§5.1) but never checked. If the
  source stops importing `mediapipe`, `visiongraph[onnx,openvino,mediapipe]`
  keeps the extra silently. Extras are outside this system's competence, and
  saying so is better than implying coverage.
- **Bare declarations surfaced** — `numpy`, `fastapi`, `opencv-python` declared
  with no floor stay invisible. An unpinned dep narrows nothing, the correct
  floor is not computable, and flagging it would invite the guess §1.1 removes.
- **The rename wizard** — separate scope; already designed elsewhere.
- **The haybale-marketplace → haywire_studio layering fix** — §6.3 removes one
  import as a side effect; `NetworkSettingsPanel` is untouched.

### 7.1 In scope by exception

**`_version_tuple` accuracy.** Non-numeric segments sort as 0, so `0.0.38rc1`
compares equal to `0.0.38`. Under §3.5 lag becomes *information displayed to the
author*, and information the tool presents must be correct. Replace the
hand-rolled tuple comparison with `packaging.version.Version`, already in the
dependency set and already imported in `steps/framework.py`.

---

## 8. Implementation checklist

The groups below are **not** parallel. §8.1 states what must be ordered and why.

### 8.1 Sequencing

**Core lands first.** `haywire_core_requirement()`, the `require` field, and the
entry-level pyproject operations are what pipeline, generator, and wizard all
build on. Nothing else compiles against a half-migrated `Haybale`.

**The parser change and the CI generator must land in the same commit.**
`parse_haybale` reading `require` only (§4.4) makes every entry written by
`scripts/generate_marketstall.py` unparseable the moment it lands, and that
script runs in CI on every publish
(`.github/workflows/publish.yml:218`). Splitting them across commits publishes a
marketstall whose framework declarations silently vanish — the exact failure
class this design exists to remove. Same commit, or the generator first.

**The wizard lands last.** Screens 3–5 call appliers that must already exist,
and screen 2's reordering only makes sense once `apply_marketstall` derives
(§4.2) — otherwise the framework screen writes a pyproject entry nothing reads.

**The editor deletion is independent** and can land any time; it removes a
caller, not a dependency.

**Docs land with the code**, per Q17 — the glossary describes shipped behaviour,
so the diff in §8 waits for the change it describes.

```text
core ──┬── pipeline ──── wizard
       └── generator  (generator + parser change: SAME COMMIT)

editor deletion — independent
docs — with the code
```

### Core
- [ ] `haywire_core_requirement()` in `haywire.core.marketstall` (§4.3)
- [ ] `Haybale.require` replaces `requires_haywire`; `_TOML_FIELDS` updated
- [ ] `parse_haybale` reads `require` only (breaking, §4.4)
- [ ] `check_requires_haywire` token split; bare token → `ok=True`
- [ ] Entry-level pyproject operations replacing `set_pyproject_dependencies` (§5)
- [ ] `_version_tuple` → `packaging.version.Version` (§7.1)

### Pipeline
- [ ] `steps/detect.py` — pure report (§6.1)
- [ ] `steps/dependencies.py` — all writes, entry-level
- [ ] Delete `steps/drift.py`, `union_pyproject_deps`, `check_framework_consistency`
- [ ] `has_drift` excludes `pyproject_version_lag` (§6.2)
- [ ] `acknowledge_drift()` narrowed to skip-undeclared
- [ ] `--yes` refuses only on unacknowledged undeclared imports (§3.4)
- [ ] `apply_marketstall` derives `require` per-library (§4.2)

### Marketstall generator
- [ ] `scripts/generate_marketstall.py` emits `require`, three-way logic, shared helper (§4.3)
- [ ] Verify `.github/workflows/publish.yml:218` path still produces parseable entries

### Wizard
- [ ] Six screens; `STEPS`, titles, render dispatch, `advance_from_*` (§3)
- [ ] Per-item pulldowns for screens 4 and 5
- [ ] 5b gated on custom-entry validity (§3.6)

### Editor
- [ ] Delete `detect_dependencies()` + `write_pyproject_deps()` from `_overview_edit_dialog.py`
- [ ] Dependencies field becomes read-only, matching how package name is already treated

### Tests
- [ ] Restate tripwire as "every writing screen has an applier" (§6.4)
- [ ] Invert `test_framework_step_sits_between_drift_and_version`, fix its rationale
- [ ] Unit test: `write_marketstall` output matches each library's floor (§6.3)
- [ ] Round-trip: absent / bare / floored `require` (§4.1)

### Docs
- [ ] `share-pipeline-arch.md` §2 — "six steps" is already wrong (7 modules
      today, 8 after); document the screen↔step mapping explicitly rather than
      implying 1:1
- [ ] Glossary: retire **Union (apply mode)**, **Replace (apply mode)**,
      **Detect Dependencies button**; rewrite **Drift gate**,
      **`pyproject_version_lag`**, **DepDrift**, **Diff modal**; fix the
      relationship line (`glossary.md:469`), the example dialogue
      (`glossary.md:537`, cites "Detect → Union"), and the three-meanings note
      (`glossary.md:571`)
- [ ] Add glossary terms: **Unused declaration**, **Undeclared import**,
      **Version floor lag**
- [ ] Fix `glossary.md:236` — `pyproject_version_lag`'s stated rationale
      ("lockstep haybale ecosystem") does not match its entry-point-derived
      scope, which includes third-party haybales
- [ ] Fix `glossary.md:258` — `has_drift` also counts `pyproject_version_lag`
      today, contrary to the entry
