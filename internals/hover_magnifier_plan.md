# Implementation Plan — Configurable Hover Magnifier

Status: awaiting review. Derived from the /inquisition session.

## Goal

Replace the hardcoded, hair-trigger node hover-scale with a configurable
**hover magnifier**: a readability aid that scales a node up when zoomed out,
gated by a global toggle, with **asymmetric dwell timing** (deliberate delay
before magnifying, quick release on exit) and a zoom-compensated scale curve.
All knobs live in `EditorPanZoomSettings`.

## Decisions (from inquisition)

- Readability magnifier (scale ↑ as zoom ↓), not a constant focus cue.
- Dwell timer: `mouseenter` arms `hover_enter_delay`; magnify only if still
  hovered; `mouseleave` releases after `hover_exit_delay`.
- Scale curve: linear from `hover_scale_max` (full zoom-out) → 1.0 at
  `hover_scale_cutoff_zoom`. Decoupled from LOD thresholds.
- Global boolean toggle `hover_scale_enabled`; off ⇒ timer never arms.
- Apply: inline `transform: scale` on `.zoom-pan-lod0`, ~120–150ms transition,
  center origin, high z-index while magnified. Edges refresh on the pin shift
  via the existing `_setupHoverObserver` hook.
- Suppressed while dragging a node or connecting an edge.
- **Owner: canvas.vue** (graph-aware; already has per-node hover hooks, edge
  refresh, and `zoomState`). Generic pan.vue stays untouched by this feature.
- Out of scope: LOD hover-reveal (separate deferred follow-up), box-shadow cue
  (stays unconditional), zoomed-out Layerize perf (deferred), keyboard/touch,
  per-node opt-out.

## Settings schema (`EditorPanZoomSettings`)

| name | default | min–max | meaning |
|---|---|---|---|
| `hover_scale_enabled` | `True` | bool | master toggle |
| `hover_scale_max` | `1.5` | 1.0–3.0 | scale when fully zoomed out |
| `hover_scale_cutoff_zoom` | `0.5` | 0.1–1.0 | zoom at/above which scale = 1.0 |
| `hover_enter_delay` | `350` | 0–2000 | ms dwell before magnify |
| `hover_exit_delay` | `0` | 0–1000 | ms before release on leave |

Scale at a given zoom `z` (when enabled and `z < cutoff`):
```
t = (cutoff - z) / (cutoff - min_zoom_floor)   # 0 at cutoff, 1 well zoomed out
scale = 1.0 + t * (hover_scale_max - 1.0)      # clamped to [1.0, hover_scale_max]
```
(Use the container's `_minZoom`-style floor or simply clamp `t` to [0,1] using a
fixed inner reference, e.g. cutoff→0, 0.1→1. Final detail decided in code; the
shape is "linear, 1.0 at cutoff, max when far out.")

## Files & changes (in order)

### 1. `packages/haywire-core/src/haywire/ui/components/zoom/settings.py`
Add the five settings to `EditorPanZoomSettings` with the table's
defaults/ranges/labels/descriptions, following the existing `setting[...]`
style. `setting[bool]` for the toggle (pattern: `ui/prefs/edge_ui.py`),
`setting[int]` for ms delays, `setting[float]` for scales. Assign `order=`
values so they group sensibly after the existing pan/zoom settings.

### 2. `packages/haywire-core/src/haywire/ui/components/graph/canvas.py`
`GraphCanvasVue` must learn the settings (it currently doesn't subscribe).
Mirror the pan.py pattern:
- import + instantiate `EditorPanZoomSettings()` in `__init__`.
- push initial values as kebab-case props (`hover-scale-enabled`,
  `hover-scale-max`, `hover-scale-cutoff-zoom`, `hover-enter-delay`,
  `hover-exit-delay`).
- `subscribe(self._on_setting_changed)`; map the five names → props and
  `self.update()` on change (live-updates, like pan.py).
- Unsubscribe in `cleanup()` (pan.py doesn't, but canvas.py has a real cleanup;
  add it to avoid a dangling subscriber across hot-reload).

### 3. `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`
- **Props:** declare the five new props (with defaults mirroring the schema).
- **`_setupHoverObserver(nodeElement)`** (lines ~193): extend. Keep existing
  edge-refresh wiring. Add:
  - `mouseenter`: if `!hover-scale-enabled` → return. If a drag/edge-connect is
    active (`this.dragState.isDragging` or `this.edgeDrag.mode !== 'idle'`) →
    return. Else start a per-node timer (`hover_enter_delay`); on fire, compute
    scale from current `this.zoomState.zoom` + curve, set
    `lodElement.style.transform = scale(s)`, `style.zIndex = '1001'`, and let the
    existing `transitionstart`→`_scheduleEdgeUpdates` refresh edges.
  - `mouseleave`: clear any pending enter-timer; after `hover_exit_delay`, reset
    `transform`/`zIndex`, refresh edges.
  - Track timers per node (e.g. on the element or a `Map` keyed by nodeId);
    clear on cleanup.
- **CSS:** ensure `.zoom-pan-lod0` has `transition: transform 140ms ease-out`
  (kept alongside the existing box-shadow transition). `transform-origin`
  defaults to center — fine per Q6.
- **Suppression during gesture:** also clear/skip magnify when a drag or
  edge-connect *starts* while a node is magnified (defensive reset).

### 4. (Already done) `pan.vue`
Hover-scale `transform: scale` + `--hover-scale` already removed in a prior
edit. Confirm no stray `--hover-scale` references remain (grep). No new work
unless the grep finds leftovers.

## Edge-refresh correctness
Magnify changes node size ⇒ pin positions move ⇒ edges must follow. The
existing `_setupHoverObserver` already listens for `transitionstart` on
`transform` and calls `_scheduleEdgeUpdates`. Because we now drive `transform`
via the magnifier (which transitions), that hook fires automatically — no new
edge plumbing needed. Verify in-app that edges track the pins during the
magnify/shrink animation.

## Test / verification
- `uv run pytest -m "not integration"` — settings additions shouldn't break
  anything; confirms schema/import wiring (Vue not exercised).
- Manual in-app (the decisive check):
  1. Toggle off ⇒ no magnify, zero hover-timer cost.
  2. Toggle on, zoomed out ⇒ dwell ~350ms magnifies; fly-over does NOT.
  3. Leaving shrinks quickly (exit delay 0).
  4. Zoomed in (≥ cutoff) ⇒ no magnify (scale resolves to 1.0).
  5. Edges stay attached during magnify/shrink.
  6. No magnify while dragging a node or wiring an edge.
  7. Change each setting live ⇒ behavior updates without reload.
- Baseline guard: confirm zoomed-in pan / node-select speed is unchanged from
  the reverted baseline (this feature must not reintroduce the earlier
  regression — it's JS hover only, no mass display toggling).

## Deferred (explicitly not now)
- LOD hover-reveal rework + zoomed-out Layerize perf (probe files retained in
  `internals/`). Candidate couplings to revisit then: dwell-gated LOD reveal,
  magnify-implies-LOD-bump.
- Optional: glossary entry for "hover magnifier" vs "LOD hover-reveal"; ADR for
  the canvas.vue ownership choice. (Skipped for now per review.)
```
