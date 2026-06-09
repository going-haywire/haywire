# Handoff — Widget unification (SimpleWidget vs BaseWidget) + widget perf attribution

> **SUPERSEDED (2026-06-09).** All open decisions in this handoff are resolved by
> [`docs/adr/0007-widget-unification-basewidget.md`](../../docs/adr/0007-widget-unification-basewidget.md)
> and were implemented on branch `widget-unification`. Retained as the
> measurement/analysis record only.

**Date:** 2026-06-07
**Branch:** `widget-perf-verification` (off `master`, not committed, not pushed)
**Origin:** a thermo-nuclear code-quality review of the widget module and its
interaction with skin / factories / dataports.

---

## TL;DR for the next agent

Two intertwined questions were being chased:

1. **Code quality:** should `BaseWidget` + `PropertyBinding` + the converter zoo
   be unified into one canonical widget base (deleting `SimpleWidget`), trimmed,
   or moved out of `haywire-core` entirely?
2. **Performance:** which part of a widget actually costs time on the 200-node
   graph, and does the SimpleWidget/BaseWidget choice matter for it?

**Both questions are now substantially answered by measurement** (see Findings).
The remaining open work is (a) a decision on the unification, gated on a
roadmap question only the user can answer, and (b) optionally chasing the *real*
perf lever, which turned out to be **not the widget**.

Do **not** re-derive the review from scratch — the analysis, the plan, and three
working test artifacts already exist. Read them first (paths below).

---

## Read these first (don't duplicate)

- **The verification plan** (decision rules, thresholds, test design):
  [`docs/plans/widget-unification-perf-verification.md`](../../docs/plans/widget-unification-perf-verification.md)
- **Test artifacts on the branch** (`tests/ui/widget/`):
  - `_sync_fixtures.py` — shared scaffolding: minimal `DataPort` builder, a
    `_StandInElement`, and the three widget shapes (Simple / Base+default /
    Base+converter), each exposing a one-call `_sync_to_view` driver.
  - `test_sync_path_parity.py` — Test 3 (5 tests, `@pytest.mark.unit`, **5/5
    pass**). Includes the finding-#2 double-activation guard.
  - `test_sync_path_perf.py` — Test 1 microbenchmark (`@pytest.mark.perf`).
  - `test_widget_cost_attribution.py` — instrumentation over the real
    `graphs/10x200nodes.haywire` (`@pytest.mark.perf`).
- **Production code under discussion** (all paths relative to repo root):
  - `packages/haywire-core/src/haywire/ui/widget/` — `simple.py`, `base.py`,
    `binding.py`, `converters.py`, `factory.py`, `registry.py`, `decorator.py`,
    `interface.py`, `globals.py`, `identity.py`.
  - `packages/haywire-core/src/haywire/ui/skin/{base,factory}.py` — how skins
    call `render_widget`.
  - `packages/haywire-core/src/haywire/core/types/port.py` — the DataPort
    contract widgets bind to (`get_value`/`set_value`/`_data.on_changed`,
    `widget_key`/`widget_config`, `ShowWidgetStrategy`).
- **Relevant memory:** `project_large_graph_perf` (200+ node sluggishness root
  causes — Layerize on pan, Vue reactive cascade across mounted nodes).

---

## Key findings (the load-bearing conclusions)

### A. Usage audit — the converter/binding pipeline is demoware

`BaseWidget`, `PropertyBinding`, and the entire converter zoo are used **only by
`haybale-example`** (the demo library). Every production widget (`haybale-core`'s
7) uses `SimpleWidget`, which touches none of it. Several sub-features have
**zero callers anywhere**, not even the demo:

- `source_property != "value"` → the `_navigate_path` / `_update_nested_property`
  nested-property engine in `binding.py`.
- `UpdateTrigger.{ON_BLUR,ON_ENTER,DEBOUNCED}` + the `threading.Timer` debounce.
- `PropertyPathConverter`, `ExtractorConverter`, `IdentityConverter`,
  `FormattingConverter` (referenced only in docstrings).

This split was named **"Pile A" (real capabilities: multi-element bindings,
converters, per-binding mode/validation — exercised by the demo) vs "Pile B"
(implemented, exercised by nothing)** in the discussion.

### B. Perf — the SimpleWidget/BaseWidget choice is performance-irrelevant here

Measured on `graphs/10x200nodes.haywire` (200 `PerformanceTester` nodes, **0
edges**, 11 `NumberWidget`s each = **2200 widgets**, all unlinked → all rendered):

- **`render_widget` = only 13%** of render wall time (0.334s of 2.627s). The
  other **87% is the rest of the node card** (port rows, pins, labels, skin
  layout) — NOT the widget.
- The SimpleWidget-vs-BaseWidget delta lives inside the *sync* portion of that
  13%, and with 0 edges nothing propagates, so it fires once at render and never
  again. **The base-class choice moves a sliver of a sliver.**
- The microbenchmark showed `BaseWidget+create_default_binding()._sync_to_view`
  is **3.18×** `SimpleWidget`'s bare `setattr` — but that is a 3× multiplier on
  a ~1µs path that is itself a tiny fraction of cost. Real-world ratio is likely
  *lower* (the stand-in setattr is cheaper than a real NiceGUI reactive one).

### C. Two claims that got corrected by measurement (don't repeat them)

1. **"Widget construction (centers 1+2) dominates"** — WRONG. It's 13%. The
   skin's per-port card structure dominates render.
2. **`enqueue_update` count (203,000 during render) looks alarming but is a red
   herring** — `Outbox.enqueue_update` is `self.updates[id] = element`,
   idempotent per element id, so the count overstates real cost massively. It is
   a cheap dict write, not 203k websocket messages. (Annotated in the test.)

### D. The actual perf levers (both orthogonal to the unification)

- Slow **render**: the 87% non-widget node-card cost (skin structure per port).
- Slow **pan/zoom** (likely the user's original pain): browser-side count of
  *mounted* Vue components → deferred mount / culling for off-screen nodes. This
  is invisible to the Python-side render test; it matches the
  `project_large_graph_perf` memory.
- For inline inlet widgets specifically, the default `ShowWidgetStrategy.NOT_LINKED`
  means **linked ports render no widget at all** (zero cost), and unlinked ports
  only churn on user typing — so center-3 (value-sync) cost is largely designed
  out except for display/`ALWAYS` widgets on churning ports.

---

## Decisions still open

1. **THE gating question (needs the user):** is there a roadmap item for a
   **multi-element widget** (Vector3 / Color / coupled inputs)? That is the only
   thing `BaseWidget`'s Pile A capabilities buy.
   - **If yes** → keep `BaseWidget` in core, **delete Pile B**, optionally unify
     `SimpleWidget` into the trimmed base.
   - **If no** → the whole `BaseWidget`/converter apparatus is demoware; move it
     next to `haybale-example`.
2. **If unifying on `BaseWidget`:** two prerequisites, in order, per the plan:
   (1) trim Pile B first (don't canonicalize dead code onto the hot path);
   (2) fix the binding double-activation (finding #2) — currently only saved by
   `PropertyBinding._is_active`; becomes everyone's path if Base is canonical.
   The perf gate (finding B) is already satisfied — perf is *not* a blocker.

---

## Suggested next steps (pick based on the user's actual pain)

- **If the goal is the code-quality cleanup:** use the `design` skill to settle
  the ownership/decomposition (move vs trim vs unify) before touching code —
  this touches base classes and the core/library boundary, which CLAUDE.md says
  to confirm before implementing. Then implement Pile B deletion as the
  low-risk first move (pure deletion, no behavior change, covered by the parity
  test).
- 

## Suggested skills

- **`design`** — for the unification ownership/boundary decision (base-class
  hierarchy + core/library boundary; CLAUDE.md requires confirming these).
- **`verify`** / **`haywire-codesanitizer`** — after any code change, to run the
  full ruff + mypy + pytest suite clean (CLAUDE.md mandates this post-refactor).
- **`haywire-ui`** — to load widget/skin/editor UI architecture docs into context
  before editing the rendering path.

---

## Practical notes / gotchas

- **Perf tests are excluded from the default suite.** `pyproject.toml` adds the
  `perf` marker and `-m 'not perf'` to `addopts`. Run them explicitly:
  `uv run pytest -m perf tests/ui/widget/ -s` (the `-s` surfaces the printed
  tables, which are the real deliverable; the asserts are guard rails).
- **Headless rendering works** under NiceGUI's default auto-index client — no
  browser/page needed (`with ui.card(): skin_factory.render(...)`). The
  attribution test relies on this.
- **A git hook blocks `git restore .` / `git checkout .` patterns** (anything
  where the path arg starts with a literal dot). Use explicit paths with a `--`
  and `./` prefix: `git restore -- uv.lock ./.claude/settings.json`.
- **`uv run` / `python3 -c` invocations auto-touch `uv.lock` and append a Bash
  permission to `.claude/settings.json`.** These were repeatedly reverted to keep
  the branch clean — check `git status` and restore them if they reappear.
- Test-file convention: `import haywire.core.graph.editor` **first** to avoid a
  circular import (per CLAUDE.md).
- `PerformanceTester` node def:
  `barn/haybale-testing/haybale_testing/nodes/testbed/test_performance.py` —
  adds 10 dynamic `FLOAT` inlets + 1 config inlet, all `NumberWidget`.

## Branch state

Uncommitted on `widget-perf-verification`:

- `pyproject.toml` (perf marker)
- `docs/plans/widget-unification-perf-verification.md` (new)
- `tests/ui/widget/` (new: `__init__.py`, `_sync_fixtures.py`, 3 test files)
- this handoff (`internals/handoff/widget-unification.md`)

Nothing committed or pushed. No production code changed yet — all work so far is
analysis + tests. The first production change will be the unification decision's
implementation (Pile B deletion is the recommended, lowest-risk starting point).
