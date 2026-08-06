# Library Origin: a second axis for installed libraries

**Status:** Design settled 2026-08-06 via inquisition. Unbuilt — no code written this
session. Glossary updated (`docs/reference/glossary.md`: **InstallType**, **Library
Origin**, `is_project_library()`, `project_writable_libraries()`, plus two flagged
ambiguities). Supersedes the original handoff of the same name (2026-08-04), which is
preserved below under "Original handoff" for context.

## Problem / goal

`InstallType` (`install_type.py:8`) conflates two different questions: **mechanism**
(how did this library reach the Python environment — REGULAR / EDITABLE / FOLDER) and
**origin** (where did the code come from / who owns it — framework / this project /
PyPI / git / unknown). Only mechanism is represented today; origin exists piecemeal
across three definitions that overlap for the common case and diverge for the
uncommon one (`Haybale.source`, `is_project_library`, `project_local_libraries`).

This design gives origin a real, single representation, and centralizes "is this
library protected from Disable/Uninstall" into one predicate — replacing the scattered
per-call-site checks that the narrow `is_required()` fix (2026-08-04, already landed)
exemplified but did not generalize.

**Goal is dual:** badge accuracy (users can tell "my own code" from "someone else's git
checkout") AND safety-gating correctness (Disable/Uninstall/registry-layer protection
can't silently miss a case because a check was re-derived ad hoc at a new call site).
Both are one classification problem, not two.

## Non-goals / explicit scope boundaries

- **Purely additive w.r.t. current protected-library behavior.** The set of libraries
  protected from Disable/Uninstall today (FOLDER + project-local + has-dependents) is
  identical after this design lands. This is a centralization/correctness refactor,
  not a policy change. See the matrix below for the exact invariant.
- **`Origin.UNKNOWN` is NOT protected.** An editable install with no catalog entry
  (bare `pip install -e ../some-other-repo` outside the marketplace flow) stays exactly
  as disable/uninstallable as it is today. We don't newly restrict a working workflow
  because we can't classify it — origin's job is to correctly protect FRAMEWORK/
  PROJECT_LOCAL, not to become a general trust gate.
- **No `direct_url.json` / `importlib.metadata` provenance parsing.** Distinguishing
  pypi from git for a no-catalog-entry install would need real install-metadata
  inspection; out of scope for this pass. No-catalog EDITABLE/REGULAR both resolve to
  `Origin.UNKNOWN` rather than a guessed value — a wrong guess is worse than an honest
  unknown for a safety classification.
- **`LibraryRegistry`/`LibraryDiscovery` (core) do NOT gain workspace-root awareness.**
  This was the "real architectural decision" the original handoff flagged as needing
  its own pass — settled here as: no, core stays workspace-agnostic. Origin
  computation lives entirely at the marketplace/studio layer.
- **The registry-layer `disable_library()` guard is FOLDER-only, not full protection.**
  See "Known, accepted asymmetry" below — this is deliberate, not an oversight.
- **`is_editable()` (mechanism-only "can source be edited in place") is unchanged.**
  It correctly answers a mechanism question, not a protection question, and stays out
  of the origin/protection predicate entirely.
- **`project_writable_libraries()` (Farmhand's write-gate, renamed from
  `project_local_libraries()`) keeps its current broader behavior** — all EDITABLE
  installs, not just `origin=project_local` ones. Only the name changes, to stop
  implying it means the same thing as the new origin classification.

## The model

### Two orthogonal axes

| Axis | Type | Values | Computed by | Workspace-aware? |
| --- | --- | --- | --- | --- |
| Mechanism | `InstallType` (unchanged) | `REGULAR`, `EDITABLE`, `FOLDER` | `LibraryDiscovery._detect_install_type()` (path vs. site-packages) | No |
| Origin | `LibraryOrigin` (new) | `FRAMEWORK`, `PROJECT_LOCAL`, `PYPI`, `GIT`, `UNKNOWN` | `compute_library_origin()`, new | Yes |

### Origin detection rules, in order

1. `mechanism is InstallType.FOLDER` → `Origin.FRAMEWORK`. Direct implication, no path
   analysis — there is exactly one FOLDER library (`builtin`), discovered through its
   own dedicated folder-scan path in `discovery.py`, structurally distinct from the pip
   entry-point path. Revisit only if a second FOLDER-mechanism library ever ships.
2. Else, `is_project_library(lib, workspace_root)` (path under `workspace_root/barn`)
   → `Origin.PROJECT_LOCAL`.
3. Else, if a catalog `Haybale` row exists for this library, its `source` field
   (`"pypi"` / `"git"`) maps directly → `Origin.PYPI` / `Origin.GIT`.
4. Else → `Origin.UNKNOWN`. (No catalog row — e.g. bare `pip install -e` outside the
   marketplace flow. Honest "don't know," never guessed from mechanism.)

### The centralized predicate

`LibraryOrigin.is_protected` (a property on the enum) is `True` for `FRAMEWORK` and
`PROJECT_LOCAL`, `False` for everything else including `UNKNOWN`. This is the single
thing every gating call site consults — replacing the OR-of-scattered-checks pattern
`is_required()`'s narrow fix used but didn't generalize.

"Required" (the purple badge) stays a **separate**, broader concept:
`origin.is_protected OR has_installed_dependents(lib)` — a library can be Required
because it's protected by origin, because something depends on it, or both. These are
independent reasons surfaced as one user-facing signal (see glossary: "required" vs
"dependent").

### Origin × Mechanism → action matrix

The invariant this design must preserve exactly (same protected set, before and
after):

| Mechanism | Origin | Registry `disable_library()` | UI Disable/Uninstall | Required badge |
| --- | --- | --- | --- | --- |
| FOLDER | `framework` | **Blocked** (new core guard) | Blocked | Yes |
| EDITABLE | `project_local` | Allowed *by core* (see asymmetry below) | **Blocked** (UI checks `origin.is_protected`) | Yes |
| EDITABLE | `pypi` / `git` / `unknown` | Allowed | Allowed, unless has dependents | Only if has dependents |
| REGULAR | `pypi` / `git` / `unknown` | Allowed | Allowed, unless has dependents | Only if has dependents |

REGULAR+`project_local` and FOLDER+non-`framework` don't occur in practice (nothing
under `barn/` is ever a site-packages install; FOLDER always implies `framework` per
rule 1) — not modeled as reachable rows. "Unless has dependents" is the pre-existing
`get_installed_dependents()` check, orthogonal to origin, untouched by this design.

### Known, accepted asymmetry: `project_local` is UI-layer-protected only

`LibraryRegistry.disable_library()` (core, `registry.py:251`) gains a guard for
`mechanism is InstallType.FOLDER` only — refuses (returns `False`, matching the
existing not-found convention; no new exception path) for `builtin`. This is the one
guard core can compute without workspace context.

`project_local` protection is **not** enforced at the registry layer. It remains, as
today, a convention enforced by the marketplace UI's `origin.is_protected` check
(gating the Uninstall button, the Disable block message, the Edit-vs-Uninstall split)
— not an invariant enforced by the registry refusing the call. A future caller that
invokes `LibraryRegistry.disable_library("some-project-lib")` directly, bypassing the
marketplace UI, **will succeed**. This was true before this design and stays true
after it; closing it fully would require giving core either workspace-root awareness
(rejected — see non-goals) or an injected `protected_ids` set from the marketplace
layer (considered and explicitly deferred as unnecessary scope for this pass — "let's
not overdo it"). If a Farmhand tool or CLI script ever exposes `disable_library`
directly, this gap becomes live and should be revisited then, not preemptively.

## Where things live

- **`haybale_marketplace/library_origin.py`** (new module): `LibraryOrigin` enum (with
  `is_protected` property), `compute_library_origin(lib, workspace_root) -> LibraryOrigin`,
  and `is_project_library()` (moved here from `_overview_edit_dialog.py` — it's a
  building block of origin computation now, not a dialog-specific helper).
- **`_overview_edit_dialog.py`**: imports `is_project_library` back for its own
  unrelated uses (`read_os_from_pyproject`'s heap-vs-wheel branching). No longer
  defines it.
- **`InstallType` / `install_type.py`**: unchanged. Still mechanism-only.
  `is_editable()` unchanged.
- **`registry.py` `disable_library()`**: gains the FOLDER-only guard described above.
  No new parameters, no injected state — a self-contained mechanism check core can
  make on its own.
- **Badges (Library Overview / Library Browser)**: two separate badge chips, mechanism
  and origin, no suppression — even the one FOLDER row shows both `[folder]` and
  `[framework]`, consistent with every other row (no special-casing anywhere, UI
  included). The Required badge stays a third, distinct badge.

## Call-site audit (to run at implementation time, not guessed here)

Broad sweep, not just the two known cases — grep repo-wide (excluding tests) for
`InstallType.FOLDER`, `is_project_library`, `install_type.name in (...)`, and
`install_type is InstallType.X` comparisons. For each hit, determine: is this asking a
mechanism question (leave alone) or actually asking "can this be touched" (convert to
`origin.is_protected`)? Known candidates going in:

- `library_browser_editor.py:494` (`is_required()`) — converts to
  `origin.is_protected OR has_dependents`.
- `library_overview_editor.py:479` (Uninstall-button gate, `("REGULAR", "EDITABLE")`
  tuple check) — converts to `not origin.is_protected`.
- `library_overview_editor.py:456` (Edit-vs-Uninstall button split, currently calls
  `is_project_library` directly) — audit whether it should read `origin.is_protected`
  instead now that the broader predicate exists.

## Renames

- `haybale_studio/farmhands/_helpers.py`: `project_local_libraries()` →
  `project_writable_libraries()`. Same behavior (all EDITABLE installs — deliberately
  broader than `origin=project_local`, per Farmhand's actual write-access need).
  Docstring updated to stop implying equivalence with the new origin classification.
  4 callers, all within `haybale-studio/farmhands/` — contained rename.

---

## Original handoff (2026-08-04), preserved for context

Raised while fixing two related marketplace bugs: `builtin` (a framework-owned
library) could be disabled through the UI even though nothing about that makes sense,
and separately, the Update button could silently no-op (see `fix(marketplace): pin the
Update button's install spec to the target version` and `fix(marketplace): stop stale
library state after uninstall/share`, both landed on master the same day). The
Required-badge gap got a narrow fix (below); the broader classification idea it
surfaced was scoped out into its own inquisition — the design above.

### What landed already (narrow fix, same day)

`is_required()` in `library_browser_editor.py` (~line 517) now also returns `True`
when:

- `lib.install_type is InstallType.FOLDER` — framework-owned (currently only
  `builtin`, from `packages/haywire-core/src/haywire/barn/builtin/__init__.py`).
- `is_project_library(lib, marketplace_path)` is `True` — this workspace's own
  `barn/*` library (the function already existed in `_overview_edit_dialog.py:24`,
  used to gate the Edit-vs-Uninstall button split at
  `library_overview_editor.py:456`).

This closed the *UI* gap (the purple "Required" badge, and the Disable button's block
message) using existing primitives — no new `InstallType` value, no new field.
`disable_library()` itself (`registry.py:251`) was still unprotected at the registry
layer at the time — the gap the design above closes (partially — see "Known, accepted
asymmetry").
