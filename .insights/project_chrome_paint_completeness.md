# Chrome silently stops painting a promoted layer — and fps rewards it

**Symptom.** On `graphs/10x300nodes.haywire`, zoomed out, Chrome drew only part
of the canvas: whole rows of node cards simply absent below a fixed horizontal
line, **at rest, indefinitely**. Reported as "the rendering does not show all
the nodes, only sections of them, sometimes only half of them".

**Cause.** `will-change: transform` on `.zoom-pan-content` (`zoom/pan.vue`).
Promoted, Chrome will not paint the whole layer once the content in view gets
large. Removing the promotion paints everything.

Measured with `.scratch/pan-perf/paintcheck.py`, counting cards whose client
rect actually carries pixels:

| zoom | cards in view | unpainted, promoted | unpromoted |
|---|---|---|---|
| 0.069 (fit) | 300 | **152** | 0 |
| 0.09 | 208 | **53** | 0 |
| 0.15 | 62 | 0 | 0 |

It is geometric, not a flicker or a race: a hard cut, in the same place, at
rest. Under ~60 cards in view it does not happen at all.

## The trap: framerate cannot see this, and is actively misled by it

Not drawing half the canvas is **cheap**. So the broken configuration measures
*faster*:

| | Chrome fps @0.09 | cards painted |
|---|---|---|
| promoted | **86.8** | 155 / 208 |
| unpromoted | 38.1 | 208 / 208 |

This is exactly how the promotion survived an earlier review. The comment in
`pan.vue` read *"will-change: transform is KEPT — removing promotion was tested
separately, made no difference in Firefox, and trended worse in Chrome."* True,
honestly measured, and wrong, because the instrument was fps.

The same mistake was then repeated while fixing the *other* Chrome bug
([[project_chrome_layerize_3d_transform]]): that fix was reported as having
resolved the rendering symptom too, based on comparing two screenshots by eye.
It had not — it fixed the unpainted app *shell*, while the blank node regions
survived untouched (49.7% vs 50.7% unpainted, with and without it).

**Rule: any change to compositing, promotion, layer structure or `will-change`
must be checked with `paintcheck.py`, never with `panperf.py` alone.** And do
not accept a screenshot as evidence of paint completeness — the failure looks
plausible at a glance, because what is missing is missing.

```sh
uv run python .scratch/pan-perf/paintcheck.py --zoom 0.069   # worst case: everything in view
uv run python .scratch/pan-perf/paintcheck.py --zoom 0.069 --pan
```

It writes an annotated PNG boxing every unpainted card, so a false positive is
visible immediately. (It already excludes cards sitting behind the debug HUD and
the minimap — a flat panel over a card reads exactly like an unpainted one.)

## Not a Chrome-only optimisation at Firefox's expense

A/B'd in one Firefox session: **19.08 fps unpromoted vs 19.07 promoted**,
spreads fully overlapping, and 278/278 cards painted either way. Firefox does
not care about the promotion in either direction, so removing it is a pure
Chrome correctness win with no Firefox cost. Worth stating explicitly, because
this file's sibling problem *was* a case of Chrome-flavoured CSS hurting
Firefox, and the two must not be conflated.

## If promotion is ever restored

Gate it on zoom. It is harmless at >= 0.15, where the painted area is small, so
a zoom-thresholded class (the canvas already has `data-lod-level` /
`zoom-pan-lod*` machinery for exactly this shape of rule) would recover the
framerate where it is safe. Re-run `paintcheck.py` at 0.069 afterwards — that is
the case that breaks first.
