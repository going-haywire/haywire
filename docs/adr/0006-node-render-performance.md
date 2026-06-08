# Node-graph render performance: cache `expects_arguments`, lazy pin tooltips

**Context.** Opening a graph (selecting one in the Haystack editor) renders every
node card synchronously on the Python side before anything reaches the browser.
On a 200-node reference graph (`graphs/10x200nodes.haywire`, 0 edges, 23 ports ×
200 nodes) this took ~2.7 s. Profiling the skin render path (see
`tests/ui/widget/test_skin_render_profile.py`) attributed the cost precisely and
overturned two intuitive-but-wrong hypotheses along the way:

- Widget construction is NOT dominant — `render_widget` is only ~13 % of render.
- The dominant *single* cost is NiceGUI's `events.handle_event` →
  `helpers.expects_arguments` → `inspect.signature`, called ~674× per node
  (~135 000× for the graph). Every `.props()` / `.style()` / `.classes()`
  mutation fires an observable change handler, which re-introspects the same
  tiny, fixed set of handler functions every time. `expects_arguments` is pure
  and the handlers' signatures never change, so all but the first call per
  handler is wasted.
- The largest *element-count* source is pin tooltips: each port eagerly builds a
  QTooltip + 1–2 labels (3 elements). At 23 ports/node that is ~69 of the ~155
  elements per node (~45 %), all invisible until hovered. Measured at ~23–30 %
  of render time.

**Decision.** Two independent, measured optimizations:

1. **Cache `expects_arguments`** at app startup. `haywire.ui.nicegui_patches`
   wraps `nicegui.helpers.expects_arguments` in `functools.lru_cache`, applied
   once from `HaywireApp.__init__` before any rendering. Guarded: it raises at
   startup if the NiceGUI internal moves/renames, rather than silently reverting
   to the slow path. Measured: real-app render 2.72 s → 2.18 s (~1.25×).

2. **Lazy pin tooltips.** `NodeSkin._add_pin_tooltip` no longer builds the
   tooltip at render. It attaches `mouseenter` → build-and-show / `mouseleave` →
   hide handlers; the tooltip (3 elements) is constructed on first hover only.
   The QTooltip is given `no-parent-event` so our handlers are the SOLE
   visibility controller. Measured: render 2.44 s → 1.67 s with tooltips
   removed-from-render-path (~1.46×); elements/node 155 → 86.

The two stack: graph-open drops from ~2.7 s toward ~1.4 s.

**Why patch a vendored internal.** `expects_arguments` is not cached on NiceGUI
`main` (checked 2026-06); upstream's stated guidance for large UIs is to render
fewer elements (staggered/culled), not to optimize per-element cost — see
zauberzeug/nicegui#338 and discussion #2876. The cache is a tiny, pure-function,
correctness-neutral win we cannot get any other way short of forking. The guard
keeps it safe across version bumps; the long-term fix is an upstream
`functools.cache` PR, after which this patch is deleted.

**Why `no-parent-event` + explicit show/hide for tooltips.** A tooltip built on
`mouseenter` mounts *after* the event fired, so Quasar's own hover listener
misses the first hover (tooltip appears only on the second). Manually calling
`show()` while leaving Quasar's hide active then orphans tooltips on screen
(two controllers disagree). Making our handlers the sole controller
(`no-parent-event`) is the only deterministic option; it mirrors how
`node_menu_builder` drives flyouts explicitly on hover rather than via Quasar.

**Consequences.**

- First hover of a given pin pays a server round-trip to build+show its tooltip
  (subsequent hovers are instant). Consistent with existing hover-built UI
  (`node_menu_builder`). Accepted.
- The `expects_arguments` patch is a startup-time monkeypatch of a third-party
  internal — flagged in code with a guard and a removal condition (upstream
  cache lands).
- Culling / deferred mount of off-screen node cards remains the larger,
  unaddressed lever (helps both graph-open and pan; the upstream-endorsed
  approach). These two optimizations are orthogonal to it and do not block it.
- The measurement instruments (profile, attribution, cache benchmark) are kept
  as `@pytest.mark.perf` tests, excluded from the default suite. See
  `tests/ui/widget/README.md`.
