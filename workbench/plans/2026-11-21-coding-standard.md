# Python coding standard: design and roadmap

Settled with the user in an inquisition on 2026-11-21 (Q1–Q24 below). The standard
itself is `docs/reference/coding-standards.md`; this plan holds only the decisions and
the work that brings the code and tooling in line with it. Each slice's last task marks
its row in *Status* done, with commit, date and deviations.

## Starting a session on this plan

1. One branch, one PR per slice. Load the `haywire-workflow` skill before any git command.
2. Read *Decisions*, then the slice. *Evidence* holds the counts as of 2026-11-21:
   recount before relying on one.
3. A slice that turns a rule on changes the config **and** migrates the code in the same
   PR, so CI is green, and updates the rule's `Enforced by:` line in the standard.
4. A mass auto-fix commit is added to `.git-blame-ignore-revs` (created in R1) and lands
   when few branches are open: it conflicts with every open worktree.
5. A tracking issue holds one sub-issue per slice (created in R0).

## Problem

- No coding standard exists. `/code-review`'s Standards axis finds only CONTRIBUTING's
  process rules and falls back on its smell baseline.
- The code is split on conventions agents copy from whichever file they read last
  (`Optional[X]` vs `X | None`, quoted forward references, `typing.List`).
- The one written standard, `.claude/rules/python-docs.md`, is visible to Claude only.

## Decisions

| # | Decision |
|---|---|
| Q1 | Layers: a citable normative core (for `/code-review`, agents, maintainer), each rule with reason and example, plus this roadmap. |
| Q2 | Binds repo code (`packages/`, `barn/`, `tests/`, `scripts/`); rules that protect a mechanism also running in authors' libraries are tagged for them; node templates follow every rule. |
| Q3 | Home: `docs/reference/coding-standards.md`, in the mkdocs nav, baked for Farmhand. |
| Q4 | The roadmap is this dated plan, never in `docs/`. |
| Q5 | Rule shape: stable ID `CS-<area><n>`, title, Why, ✗/✓ example, Enforced by, Scope. |
| Q6 | Lean: tooling first; a rule enters the doc only if a tool can't check it, it has cost something here, and it is haywire-specific or the code is split on it. |
| Q7 | `.claude/rules/python-docs.md` moves into the standard as section D; `.claude/rules/` keeps a path-scoped pointer so agents still load it on `.py` edits. |
| Q8 | Sections: Docstrings & comments, Typing, Errors, Imports, State & DI, Logging; See also for naming, async traps, tests. |
| Q9 | Modern annotation syntax, ruff `UP` including PEP 695. |
| Q10 | `from __future__ import annotations` required (ruff `I002`); plus the runtime-read annotation rule. |
| Q11 | mypy `check_untyped_defs` + `disallow_incomplete_defs` repo-wide now; public surface fully annotated (review); `disallow_untyped_defs` per package later. |
| Q12 | Escape hatches: mypy `warn_unused_ignores` + `ignore-without-code`, ruff `RUF100` + `PGH004`; a reason per ignore/noqa/cast; `Any` only at a boundary (forward-only). |
| Q13 | Errors: link errors-arch; `Refusal` vs failure; broad except only at a boundary or in best-effort code that logs; narrowest catch; ruff `S110`/`S112`. |
| Q14 | Import sorting: ruff `I`, explicit `known-first-party`. |
| Q15 | Imports are top-level; a local import names its reason (cycle, heavy/optional dependency, reload). `PLC0415` stays off. |
| Q16 | One pass over existing local imports: doubtful → move, except imports of a barn module (`haybale_*`), which stay with a `# reload:` comment. |
| Q17 | State & DI: injector → ambient accessor for objects the injector doesn't build → named process-wide exceptions; a new accessor or global is a maintainer decision; never `ContextVar` for app state. |
| Q18 | `getLogger(__name__)`; `print` only in CLI output (ruff `T20` with per-file ignores); log-level rule. |
| Q19 | Docstring shape by ruff `D2xx`/`D4xx` (Google convention), without D1xx, D415, D417; content by review. |
| Q20 | Retire `trim-docs`, `trim-batch`, `curate-trim-examples` and their manifest. |
| Q21 | Scope tags `repo` / `libraries too`; `haywire init` adds `TID252` to an author's ruff config; `UP`/`I` stay out of authors' projects. |
| Q22 | Admission test written in the doc; maintainer approves every change (`agent files` treatment); a tool-enforced rule shrinks to one line; a retired rule keeps its ID as a tombstone. |
| Q23 | Doc first, then one PR per rule family, cheapest first. |
| Q24 | Defaults: tests/ follow the general rules, exempt from `T20`, `D` and `disallow_incomplete_defs`; no ADR (every choice is reversible config). |

Out of scope: taste rules; restating tool-enforced rules; binding third-party libraries
beyond the scaffold's TID252; migrating existing `Any`; docstring rewrite campaigns;
redesigning DI.

## Evidence (packages/ + barn/ unless noted, 2026-11-21)

- 904 `.py` files; `__future__` annotations in 472; `TYPE_CHECKING` in 218.
- Return annotations: `List`/`Dict`… 152 vs builtins 619; `Optional[` 133 vs `| None` 427;
  quoted 153; `TypeVar(` 39. Repo-wide ruff: UP037 1009, UP006 906, UP045 816, UP035 361,
  I001 1346, T201 679, PLC0415 4514 (690 outside tests).
- mypy outside tests: `check_untyped_defs` 1 error (`log_editor.py:185`), incomplete defs
  455, untyped defs ~741. Repo-wide: 156 unused ignores, 0 ignores without a code.
- `except Exception` 394: 56 silent (pass/continue/return), 171 log at once.
- `print` outside `cli/`: 246 (`share_cli.py` 84, `core/di/config.py` 67, `init.py` 32,
  `app.py` 20).
- ruff `D` (Google): D102 1004, D212 712, D415 308, D205 235, D107 180, D101 152.
- Trim campaign manifest: 11 modules done, 110 pending, untouched since 2026-09-12.
- `haywire init` writes `TID251` only (`haywire_studio/init.py:273`).

## Slices

| # | Slice | Notes |
|---|---|---|
| R0 | Tracking issue + one sub-issue per slice | (user) labels |
| R1 | **The standard**: `coding-standards.md`, mkdocs nav, links from CONTRIBUTING and CLAUDE.md, `.claude/rules/python-docs.md` → pointer, retire the trim skills + manifest + benchmark, `.git-blame-ignore-revs` | `agent files` label |
| R2 | Scaffold: `haywire init` adds `TID252`; test | independent, may go first |
| R3 | mypy `check_untyped_defs` repo-wide (1 fix), `warn_unused_ignores` + `ignore-without-code` (156 deletions) | |
| R4 | ruff `UP` + `I` + `I002` (`known-first-party`), auto-fix per package | blame-ignore |
| R5 | ruff `RUF100`, `PGH004` | |
| R6 | ruff `D2xx`/`D4xx` (Google, minus D415/D417), auto-fix + D205 by hand | blame-ignore |
| R7 | ruff `S110`/`S112`: each of the 56 sites logs or carries `noqa` + reason | judgment |
| R8 | ruff `T20` with per-file ignores; the remaining prints become log calls or CLI output | judgment; `di/config.py` first |
| R9 | mypy `disallow_incomplete_defs` (455) | per package |
| R10 | Local-import pass (Q16), one commit per package | judgment |
| R11 | `disallow_untyped_defs` per package, core first | open-ended |

## Follow-ups outside this plan

- Docs: a DI architecture page (injector, ambient context, strategy hooks, observable
  stores); the standard's CS-S rules link to it once it exists.
- Issue: constructing a library system or `SettingsRegistry` repoints the ambient
  globals (one library system per process); only an explicit activation should write them.
- At a 3.14 floor: drop `from __future__ import annotations` repo-wide (PEP 649/749).

## Status

| Slice | State | Commit / date / deviations |
|---|---|---|
| R0 | done | tracking #182, sub-issues #183–#192 (R2–R11), 2026-11-21 |
| R1 | done (#181, 9433968d2, 2026-11-21) | `.claude/rules/python-docs.md` renamed `coding-standards.md` (pointer); `docstring-cleanup-notes.md` kept: it holds design reasoning no ADR covers |
| R2 | done (#193, 247315661, 2026-11-21) | |
| R3 | done (#194, ca1698508, 2026-11-22) | 155 unused ignores (one fewer than counted); `LogEditor._flush` now skips a cleared log element |
| R4 | done (#195, ec83ccb67, 2026-11-22) | one auto-fix commit, not one per package (squash merges it into one anyway); `UP031` ignored (its sites are JS templates) and `UP038` (deprecated upstream); PEP 695 generics: 16 by ruff's unsafe fix, the three registries and `ProgressSettings.track` by hand; `__init__.py` files keep their import order (exempt from `I001`): sorting them broke the packages' import cycles; `types/fields.py` and `node/{data,decorator}.py` import submodules, not their own package; two tests moved function-local classes to module level (CS-T3 now names that case); `DataField.remove_source` joins the B027 exceptions; `pr-intake` needed #196 for a PR over 300 files; the squash commit went into `.git-blame-ignore-revs` with R5 |
| R5 | done (#186, 2026-11-26) | 62 unused `noqa`, no bare one; 52 named rules never enabled (`BLE001` ×23, `SLF001`, `N802`, …); removed by hand so each reason stays as a plain comment, which R7 builds on |
| R6 | done (#187, 2026-11-27) | 2759 findings, not ~1100: the issue counted packages/ and barn/; tests/ add 1603. D205 is off in tests/ (778 there; review keeps it), the rest of D2/D4 holds there; D403/D405/D416 fixed by hand, not by ruff (it capitalised code names, turned `IMPORTANT:` into a section and broke a NumPy header); D200 by ruff's unsafe fix; the library docs regenerated from the new docstrings; the squash commit goes into `.git-blame-ignore-revs` with the next slice, as R4's did |
| R7 | pending (#188) | |
| R8 | pending (#189) | |
| R9 | pending (#190) | |
| R10 | pending (#191) | |
| R11 | pending (#192) | |
