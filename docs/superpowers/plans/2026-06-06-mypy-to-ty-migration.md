# Migration: mypy → ty (Astral type checker)

**Date:** 2026-06-06
**Status:** ✅ **ty at ZERO + wired into CI non-blocking** (2026-06-06). All diagnostics
resolved: Bucket A real bugs, splat-site annotations, the generic `BaseRegistry[T]` refactor,
the state-container casts, and the long tail of scattered DI/descriptor/stub cases. mypy clean
(341), ruff clean, 1548 unit + 84 integration tests pass.

`ty==0.0.44` is a pinned dev-dependency; `.github/workflows/ty.yml` runs `uv run ty check` with
`continue-on-error: true` (mypy.yml stays the gate). **The migration is functionally complete.**
What remains is the *deliberate flip* — only when ty 1.0 / parity warrants it: set
`continue-on-error: false` in ty.yml, then retire mypy across the 7 footprint touch points
below (both `[tool.mypy]` blocks, `mypy.yml`, the `tests.yml` mypy step, README badge+command,
CLAUDE.md's two commands, the `verify` skill). Until then ty rides along, surfacing its view
without gating.

**Final tally — 117 → 0 across the session.** ~9 documented suppressions total (each notes why
the code is correct: descriptor `-> T` ergonomics, `is_dataclass`/`hasattr`-guarded runtime
narrowing ty can't follow, NiceGUI `__exit__` vs `*_`, intentional Signal-handler variance,
duck-typed `libraries`). Everything else was a genuine fix: real type bugs, truthful
annotations, casts at honest inference-blind spots, the generic refactor, and one dead-code
removal (`app.py` `library_service.cleanup()` — a method that never existed).

**Registry refactor (design-driven, commit `e2883fc9`):** the deferred `_register_class`
cluster was the symptom of accidental drift across the registry subclasses (inconsistent
prompting). Resolved by making `BaseRegistry` generic — `BaseRegistry[T]` bound to a
`RegisteredClass` protocol (`class_identity` as a read-only property member so subtypes like
`NodeIdentity` don't trip `ClassVar`/attribute invariance). All 11 registries now bind their
element type with one uniform `_register_class(self, cls: type[X],
library_identity: Optional[...] = None)` signature. Two new bases introduced by design decision:
`BaseTheme` (themes accept two sibling classes) and `class_identity` on the `Settings` base.
Cleared ~19 diagnostics with **one cast pair** (internal scan-result sites) and the
state-container `# type: ignore[return-value]` → `cast` swap. No new suppressions.

**Round 3 note (annotations can surface deeper diagnostics):** annotating
`parent_identity: NodeIdentity | None` in the `@node` decorator let ty check assignments it had
skipped while the value was loosely typed — trading 2 `asdict` diagnostics for 3 deeper ones
(`base.class_identity` is `Unknown` through `__bases__`; the `**identity_kwargs` splat into
`NodeIdentity(...)`). Resolved honestly: `cast(NodeIdentity, ...)` at the `__bases__` read +
`dict[str, Any]` on the kwargs bags. Net more type-honest end-to-end. One justified suppression
added: `converters.py:248` `len(current)` (defensive navigation guarded by `except TypeError`;
no annotation re-broadens `current` after the isinstance chain).

**Suppression principle (agreed):** add `# ty: ignore` *only* where the code is correct
and ty is wrong (e.g. `__exit__` vs NiceGUI's `*_` base, stdlib stub overloads). Where ty's
complaint points at a genuinely loose type, fix the type instead. Never suppress a real defect
or to lower a count. The port.py/popup.py splat sites were resolved by **annotation, not
suppression** — typing the merged dict `dict[str, Any]` (its true type) stops ty widening it to
a concrete union it then checks key-by-key. Zero `# ty: ignore` so far.
**Driver:** Tooling consolidation on Astral (ruff, uv, ty) + faster local/CI type checks.
*Not* driven by a mypy capability gap.

---

## TL;DR

ty 0.0.44 emits **117 diagnostics** on a codebase mypy considers **clean** (`Success: no
issues found in 341 source files`). Triaged, those 117 collapse to **77 distinct source
locations**, and ~46% trace to **three** systemic `**kwargs`/dict-splat lines that ty can't
narrow. The genuinely actionable items (~15–20) are mostly *real type bugs mypy let through*
and are worth fixing **regardless of which checker wins**.

**Strategy:** trial-first → fix the real bugs under mypy → re-run ty → adopt ty *non-blocking*
in CI with mypy still gating → flip to ty only once it reaches zero. ty is 0.0.x (beta); it is
**not** the gate until it's at parity for this codebase.

---

## Why (decision log)

| Decision | Choice | Rationale |
|---|---|---|
| Motivation | Speed + Astral consolidation | Already all-in on ruff/uv; want one vendor + faster checks. No specific mypy limitation forced this. |
| Cutover strategy | Trial → non-blocking CI, mypy stays gate | ty is beta (0.0.44); codebase is mypy-clean and CLAUDE.md treats any type error as stop-the-line. Don't trade the safety net for a consolidation goal. |
| Handling the 117 | Triage first, fix real bugs decoupled from ty | A meaningful slice are real bugs mypy missed — fix them as plain mypy-clean changes, value independent of the ty bet. |
| Registry cluster | **Deferred** | The 8 `_register_class` overrides are an architectural decision (generic `BaseRegistry[T]`) in DI/registry territory CLAUDE.md says to confirm before touching. Handle via the `design` skill later, not in the bug-fix batch. |

---

## Trial results (ty 0.0.44, 2026-06-04 build)

Run against the same roots as the canonical mypy command:

```sh
uvx ty check packages/haywire-core/src/ packages/haywire-studio/src/ \
  barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ \
  barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ \
  barn/haybale-TEST_A/haybale_test_a/
# → Found 117 diagnostics
```

**117 diagnostics → 77 distinct locations.** Top concentrations:

| Diagnostics | Location | Root cause |
|---|---|---|
| 38 | `port.py:587` `cls(**port_kwargs)` | One heterogeneous-dict splat into a constructor; ty emits one error per param. |
| 16 | `popup.py:19`, `popup.py:152` | Same family — `str \| bool \| Unknown` from kwargs/splat. |
| 8 | `*/registry.py` `_register_class` | One base-class signature, narrowed in 8 subclasses (deferred — see below). |
| ~7 | `stdlib/builtins.pyi`, `dataclasses.pyi` | ty resolving stdlib overloads (`sorted`, `len`, `asdict`) differently. |
| rest | scattered | See buckets. |

By rule: `invalid-argument-type` ×62, `invalid-method-override` ×15, `invalid-return-type` ×12,
`unresolved-attribute` ×11, `call-top-callable` ×6, plus a long misc tail.

---

## Buckets

### Bucket A — real issues, fix under mypy NOW (decoupled from ty)

These are genuine; mypy (non-strict config) was lenient. Fixing them is a pure win even if ty
is never adopted. Run `uv run mypy <roots>` after each per CLAUDE.md.

- **`convert` parameter rename** — `compound_adapters.py` (haybale-core + haybale-example)
  override `BaseAdapter.convert(self, value: Any)` with parameter named `values`. Because either
  can be passed as a keyword (`convert(value=...)`), the rename violates LSP. **Validated: zero
  callers use the `values=` keyword** (all positional) — safe rename `values` → `value`.
- **`to_view` / `to_model`** — `haybale_example/widgets/example_widget.py:110,124,138`,
  `BindingConverter` overrides. Same LSP family (param name / variance). Verify before editing.
- **`callback.__name__` on bare `Callable`** — `validation.py:140,151,449`,
  `registry/base.py:869,880`. A `Callable` type doesn't guarantee `__name__`; latent footgun in
  logging. Type the params as a Protocol exposing `__name__`, or guard with `getattr`.
- **`share.py` return type** — `haywire_studio/share.py:116` returns `list[object]` where
  `list[str]` is annotated (`_read_os_field`). Real.
- **`utcnow` deprecation** — `warning[deprecated]`; replace with `datetime.now(timezone.utc)`.
- **`__exit__` overrides** — `popup.py:73`, `pan.py:291`. Confirm signature matches the context
  manager protocol before changing.

### Bucket B — ty inference weaknesses (suppress or refactor, NOT bugs)

- `port.py:587` `cls(**port_kwargs)` (38) and `popup.py` (16): ty can't narrow a heterogeneous
  dict splatted into a constructor. Fix once at the splat site — either a typed-construction
  refactor or a single `# ty: ignore[invalid-argument-type]`. Kills ~54 diagnostics at 3 lines.
- `call-top-callable` (6): ty infers `Top[(...) -> object]` for DI-resolved callables.

### Bucket C — stdlib/stub-driven

- `builtins.pyi` (`sorted`, `len` overloads), `dataclasses.pyi` (`asdict`). Likely suppressible;
  re-evaluate after a ty version bump — stub resolution is actively improving in 0.0.x.

### Deferred — registry `_register_class` contravariance (8 overrides)

Base: `def _register_class(self, cls: Type, library_identity) -> str | None`. Subclasses
(adapter, node, state, types, editor, panel, skin, widget) narrow `cls` to `type[BaseNode]`,
`type[BaseAdapter]`, `type[IWidget]`, etc. Narrowing a parameter violates LSP.

**Target end-state:** make `BaseRegistry[T]` generic so each subclass *binds* `T` rather than
*narrows* an override — type-correct under ty, mypy-strict, and at call sites. This is an
architectural change to the registry hierarchy → do it **deliberately via the `design` skill**,
not as a drive-by. Until then, leave as-is (mypy passes) or suppress in ty.

---

## Sequence

1. **(now)** Land Bucket A as mypy-clean fixes. Start with the validated `convert` rename.
2. Re-run ty; confirm the count drops to ~the suppressible remainder (B + C + deferred).
3. Add `# ty: ignore[...]` for the systemic splat sites (B) and stub cases (C).
4. Add ty to CI **non-blocking** — new step/workflow with `continue-on-error: true`; **mypy
   remains the gate**.
5. Design + land generic `BaseRegistry[T]` (deferred cluster) via the `design` skill.
6. Once `uvx ty check <roots>` is at zero, flip: ty becomes the gate, retire mypy.

## Footprint to change when flipping (step 6)

Seven touch points carry mypy today:
- Root `pyproject.toml` `[tool.mypy]` + `mypy_path` list, and the `dev` dependency.
- `packages/haywire-studio/pyproject.toml` `[tool.mypy]`.
- `.github/workflows/mypy.yml` (dedicated workflow).
- `.github/workflows/tests.yml` mypy step (`continue-on-error`).
- `README.md` badge + `uv run mypy` command.
- `CLAUDE.md` (two mypy commands).
- `.claude/skills/verify/SKILL.md`.

## ADR

Hold. The genuinely architectural, hard-to-reverse decision is the **generic `BaseRegistry[T]`**
refactor — which is *deferred and not yet made*. Write the ADR when that decision is taken (via
`design`), not for "we eased ty in non-blocking" (reversible).
