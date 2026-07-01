# `tests/ui/widget/` — widget parity + render-performance instruments

This directory holds two distinct kinds of tests. Know which you're touching.

## 1. Regression guards (run in CI, `@pytest.mark.unit`)

| File | Guards |
|------|--------|
| `test_sync_path_parity.py` | The unified `BaseWidget` `bind()` path produces correct model→view behavior for primitives; cleanup detaches the port subscription; `render()` subscribes exactly once (finding #2). Keep these green if you touch the widget binding layer. |

Shared scaffolding lives in `_sync_fixtures.py` (a minimal `DataPort` builder, a
`_StandInElement` / `_RecordingElement`, and two `BaseWidget` shapes — default
`bind()` and explicit converter). It is imported by the parity test, the sync
microbenchmark, and the `bind()` sugar/nested tests.

## 2. Performance instruments (`@pytest.mark.perf`, excluded from the default run)

These are **measurement tools**, not pass/fail regression guards. They print
tables; their asserts only check structural facts (e.g. "we rendered 2200
widgets") so a number can't be silently measuring the wrong thing. They informed
[ADR-0006](../../../docs/adr/0006-node-render-performance.md).

| File | Measures |
|------|----------|
| `test_sync_path_perf.py` | Microbenchmark: cost of `BaseWidget`'s `sync_to_view` on the default `bind()` path vs an explicit-converter path. Concluded the base-class choice is perf-irrelevant for inline widgets (ADR-0007 Finding B). |
| `test_widget_cost_attribution.py` | On the real 200-node graph: `render_widget` is only ~13 % of render; the rest is the node card. |
| `test_skin_render_profile.py` | cProfile + element census of one node-card render. Found the `expects_arguments`/`inspect.signature` hot spot and the tooltip element count. |
| `test_expects_arguments_cache.py` | Wall-time speedup from caching `expects_arguments` on the real graph (~1.41× in harness). Doubles as the before/after yardstick for that optimization. |

Run them explicitly (they need the heavyweight `library_system` fixture; the
200-node reference graph is built fresh by `conftest.build_perf_graph`):

```sh
uv run pytest -m perf tests/ui/widget/ -s      # -s surfaces the printed tables
```

The default `pytest` run excludes them via `addopts = "... -m 'not perf'"` in
`pyproject.toml`, so CI does not pay for them.

### Reusing them

If you change the skin render path, the node card, or the widget binding layer
and want to know the perf impact, re-run the relevant instrument before/after and
compare the printed numbers — that is the intended use. They are kept (not
deleted after the investigation) precisely so the next person can re-measure
against the same reference graph rather than re-deriving the harness.
```