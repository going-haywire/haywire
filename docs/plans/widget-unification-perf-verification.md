# Verification Plan — BaseWidget vs SimpleWidget sync-path cost

> **Purpose.** Decide whether `SimpleWidget` can be deleted and `BaseWidget`
> (stripped of dead "Pile B" machinery) become the single canonical widget base,
> *without* regressing the value-propagation hot path that already makes 200+ node
> graphs sluggish (see `.claude` memory `project_large_graph_perf`).
>
> This plan answers **only** review finding #3: "verify the per-sync converter
> overhead is acceptable, or make `create_default_binding()` provably as cheap as
> `SimpleWidget`'s direct `setattr`." It does not implement the unification.

## The question, made precise

The hot path is **model → view** (`_sync_to_view`), which fires on *every* port
value change — i.e. every edge propagation, every worker write. For one port:

- **SimpleWidget** (`simple.py`):
  `port.get_value()` → (None? default) → `setattr(el, prop, value)`. One virtual
  call + one setattr. No converter, no isinstance branch.
- **BaseWidget** via `PropertyBinding._sync_to_view`
  (`binding.py`):
  `source_property=="value"` branch → `port.get_value()` →
  `converter.to_view(model_value)` (virtual call into `PrimitiveUnwrappingConverter`,
  which does an `isinstance(dict)` check + `hasattr(value,"value")` unwrap) →
  `setattr`. Plus a `try/except` frame around the whole thing.

So the per-sync delta to measure is: **one extra virtual call + one isinstance +
one hasattr + a try/except frame.** The View→Model path (user typing) is NOT hot
and is out of scope — humans don't generate propagation storms.

**Decision rule (set the threshold before measuring, not after):**

- **GREEN — unify.** BaseWidget `_sync_to_view` is within **1.5×** of SimpleWidget
  in the microbenchmark AND the realistic-graph propagation benchmark shows
  **< 5% wall-clock regression** at 200 nodes. The abstraction is free enough.
- **YELLOW — unify but add a fast path.** Micro delta is real (≥1.5×) but the
  graph benchmark is < 5%. Proceed with unification, but special-case the
  `source_property=="value"` + `PrimitiveUnwrappingConverter` combo so
  `create_default_binding()` skips the converter call (inline the unwrap). Re-run
  to confirm it lands GREEN.
- **RED — keep SimpleWidget.** Graph benchmark ≥ 5% regression even after the
  YELLOW fast path. `SimpleWidget` is a deliberate fast path, not redundant
  duplication. Revert review recommendation to "move converters/Pile B out of
  core, keep both base classes."

Pick 1.5× / 5% as the pre-registered numbers. If you want different thresholds,
change them *now*, in this doc, before running anything.

---

## Test 1 — Microbenchmark: isolated `_sync_to_view` cost

**File:** `tests/ui/widget/test_sync_path_perf.py` (new), marked
`@pytest.mark.perf` (register the marker in `pyproject.toml` `[tool.pytest]`
`markers`, mirroring the existing `slow` / `integration` entries; exclude from the
default run via `-m "not perf"` if CI shouldn't pay for it).

**What it measures:** wall-clock of N (e.g. 100_000) repeated `_sync_to_view`
calls on a real `FLOAT` `DataPort`, for three widget shapes:

1. `SimpleWidget` subclass → baseline.
2. `BaseWidget` + `create_default_binding()` (the SimpleWidget-equivalent path —
   this is the one that decides GREEN vs YELLOW).
3. `BaseWidget` + an explicit converter (`Converters.range(...)`) → upper bound on
   "real converter" cost, for context.

**Construction notes (so the benchmark hits the real code, not a mock):**

- Build the port the way production does. Tests don't construct `DataPort`
  directly — use the spec route: `FLOAT.as_inlet("v", widget=Widget.config())`
  then `DataPort.from_spec(...)`, or reuse whatever fixture
  `tests/ui/harness/test_widgets.py` / `haybale_testing` already provides for a
  typed port with a value. Confirm `port.get_value()` returns an unwrapped float.
- Render is NiceGUI-bound (`create_element()` returns a `ui.number`). For a pure
  CPU microbenchmark you want to avoid the NiceGUI client/slot machinery:
  substitute a tiny stand-in element object exposing just the bound property
  (`class _El: value = 0.0`) and bind against that, OR drive `_sync_to_view`
  directly after monkeypatching `self.ui_element` to the stand-in. The goal is to
  time the **sync logic**, not Vue/Quasar setattr reactivity (which is identical
  for both paths and would just add noise).
- Drive the loop by calling the bound `_sync_to_view` directly, alternating the
  source value each iteration (`port.set_value(i)` then sync) so the converter
  can't be hoisted/cached by chance.

**Measurement hygiene:**

- `time.perf_counter()`, not `timeit`'s import overhead. Warm up ~1_000 iters
  first (let the methods JIT-warm in CPython's sense — attribute caches, etc.).
- Run each shape 5×, take the median, report all three medians + the ratios.
- Assert the *ratio*, not absolute time: `assert base_default <= 1.5 * base_simple`.
  Absolute numbers are machine-dependent and will flake in CI; the ratio is stable.

**Skeleton:**

```python
import time, pytest

pytestmark = pytest.mark.perf
N = 100_000

def _bench(sync_fn, port, n=N):
    for i in range(1000):          # warmup
        port.set_value(float(i)); sync_fn()
    t0 = time.perf_counter()
    for i in range(n):
        port.set_value(float(i)); sync_fn()
    return time.perf_counter() - t0

def test_sync_to_view_ratio(float_port_factory):
    simple = _bench(*make_simple(float_port_factory()))
    default = _bench(*make_base_default(float_port_factory()))
    converter = _bench(*make_base_converter(float_port_factory()))
    print(f"\nsimple={simple:.4f}  base_default={default:.4f}  "
          f"base_converter={converter:.4f}  "
          f"ratio_default={default/simple:.2f}  ratio_conv={converter/simple:.2f}")
    assert default <= 1.5 * simple, "create_default_binding() path too costly"
```

This single test answers GREEN-vs-YELLOW. If `ratio_default` is already < 1.5,
the converter call is cheap and you're done at the micro level. If it's ≥ 1.5,
that's the signal to build the YELLOW fast path and re-run.

---

## Test 2 — Realistic propagation benchmark (the one that actually decides)

The micro number is informative but the *real* question is whether the delta is
visible against everything else that happens per propagation (the Vue reactive
cascade, slot work). A 2× microbenchmark delta on a path that's 1% of frame cost
is irrelevant; a 1.2× delta on a path that's 40% of frame cost matters. **Test 2
is the load-bearing one.**

**File:** `tests/ui/widget/test_graph_propagation_perf.py` (new),
`@pytest.mark.perf`.

**What it measures:** build a graph approximating the sluggish case from the
`project_large_graph_perf` memory — **200 nodes, each with a few primitive inline
widgets** — wire them in a chain (or fan) so a single upstream value change
propagates through all of them, and time the full propagation under two builds:

- **Build A:** widgets are today's `SimpleWidget` (`haybale-core` as-is).
- **Build B:** the same widgets reimplemented on stripped `BaseWidget` +
  `create_default_binding()`.

**How to get Build B without a full migration:** you don't need to rewrite
`haybale-core`. Create throwaway `BaseWidget` twins of `NumberWidget`/`TextWidget`/
`CheckboxWidget` in the test module (decorated into a test library, or registered
directly into a `WidgetRegistry` fixture), pointed at the same `compatible_types`.
Build the graph once with the SimpleWidget keys, once with the BaseWidget-twin
keys. Reuse the DI / registry fixtures from `tests/core/di/test_config.py` and the
existing graph-build helpers the integration suite already uses.

**Trigger + measure:**

- Render the node cards (or skip rendering and just exercise the binding layer —
  see caveat below), then fire one `port.set_value()` at the source and let
  `on_changed` cascade. Time wall-clock from the source write to quiescence.
- Run 5× each build, median, assert `B <= 1.05 * A` (the 5% rule).

**Critical caveat — what "propagation" includes:**
`_sync_to_view` only fires if a widget is actually subscribed to that port's
`on_changed`, which only happens after `render()`. Two honest options:

1. **Binding-layer only (recommended first):** render is mocked out / elements are
   stand-ins, so you isolate the binding + converter cost across 200×K ports
   without NiceGUI in the loop. This is a clean A/B of *exactly the code under
   question* and won't flake on Vue timing. If B regresses here, it's real.
2. **Full render (confirmation only):** actually render 200 node cards via the
   skin factory and measure end-to-end. More faithful but much noisier and
   slower; use it only to sanity-check a borderline result from option 1. Likely
   needs the Playwright/`harness` infra that `tests/ui/harness/` already sets up.

Start with option 1. It's the apples-to-apples measurement; option 2 just confirms
the delta doesn't get *amplified* by render (it won't — render cost is identical
between builds).

---

## Test 3 — Correctness parity (gate before trusting any timing)

Perf numbers are meaningless if the two paths don't produce identical behavior.
Before reporting timing, prove the BaseWidget-default path is behaviorally
equivalent to SimpleWidget for the primitive cases. These are normal
`@pytest.mark.unit` tests, not perf:

- **Initial sync:** fresh widget, port has value `v` → after `render()`,
  `ui_element.value == v` for both paths. Repeat for `None` → `get_default_value()`.
- **Model→view:** `port.set_value(x)` → `ui_element.value == x` for both.
- **View→model:** simulate the UI event → `port.get_value() == x` for both.
- **Readonly:** `IS_READONLY=True` SimpleWidget vs `ONE_WAY` BaseWidget binding —
  view→model does NOT write the port in either.
- **Cleanup:** after `cleanup()`, the `on_changed` subscription is gone (assert
  `port._data.on_changed.has_observers()` is False) and `_cleaned_up` is True for
  both. This also catches the double-activation bug (#2) if it leaves a dangling
  subscriber.

If parity fails, stop — the unification has a correctness problem that outranks
perf, and finding #2 (double-activation) is the first suspect.

---

## Sequencing

1. **Test 3 (parity)** first — cheap, and if it fails the perf work is premature.
   Also forces you to confront finding #2 up front.
2. **Test 1 (micro)** — gives the GREEN/YELLOW signal and tells you whether the
   fast path is needed.
3. **Test 2, option 1 (binding-layer graph)** — the actual decision.
4. **Test 2, option 2 (full render)** — only if (3) is borderline (within a point
   or two of the 5% line).

## What "done" looks like

A short results table in this doc:

| path | micro (median, 100k) | ratio vs simple | graph 200-node | regression |
|---|---|---|---|---|
| SimpleWidget | … | 1.00 | … | — |
| BaseWidget + default | … | … | … | …% |
| BaseWidget + default + fast path | … | … | … | …% |

…plus a one-line verdict: GREEN / YELLOW / RED per the pre-registered rule, which
directly resolves review finding #3 and tells us whether to delete `SimpleWidget`.

## Notes / risks

- **No existing perf harness.** This plan introduces the first `perf` marker and
  microbenchmark convention. Keep it excluded from the default `pytest` run
  (`addopts` currently has no `-m` filter; add `perf` to the markers list and run
  perf explicitly with `uv run pytest -m perf`). Don't let these gate CI on
  absolute timings — ratio asserts only.
- **CPython variance.** Even ratios wobble on a loaded laptop. Run on an idle
  machine; the 5× median is there to absorb noise, not eliminate it. If a result
  lands inside ±1 point of a threshold, treat it as "build the fast path and
  re-measure," not as a coin flip.
- **This measures the trimmed BaseWidget.** Run Test 1/2 against a `PropertyBinding`
  that has already had Pile B removed (nested-nav, debounce, trigger variants), or
  at least confirm those branches are not on the `source_property=="value"` path
  (they aren't — but verify the `try/except` and the one `if source_property ==
  "value"` branch are the only overhead). Measuring the un-trimmed version would
  unfairly penalize the proposal with code that would be deleted anyway.
```

---

## Verdict (recorded 2026-06-09)

**GREEN — unified.** Per ADR-0007 Finding B, the SimpleWidget-vs-BaseWidget
sync-path delta is performance-irrelevant: `render_widget` is ~13% of node-card
render and the sync delta is a small fraction of that. No fast path was needed;
`SimpleWidget` was deleted and `BaseWidget` is the single canonical base. The
unification was implemented on branch `widget-unification` (see
[`adr/0007`](../adr/0007-widget-unification-basewidget.md)).
