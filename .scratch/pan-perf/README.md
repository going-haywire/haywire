# Automated pan-perf harness

Drives a real browser against a real studio and runs the RESULTS.md measurement
protocol with nobody in the loop. Built because the protocol's own conclusion
was that a hand-panned run cannot resolve anything at 300 nodes — five runs of
identical code spanned 5.85–11.31 fps. These scripts pin down every input the
hand version left loose: window size, zoom, pan gesture, settle time, engine
flags, and which branch the studio is actually running.

Spread across three automated runs of identical code, the same measurement now
lands inside ~6%.

## The scripts

| | |
|---|---|
| `panperf.py` | the measurement driver — N runs, markdown rows, medians, `runs.jsonl` |
| `paintcheck.py` | **did every on-screen card actually get painted** — the check fps cannot do |
| `wheelcheck.py` | does a trackpad swipe stay a pan, and do wheel/pinch still zoom |
| `probe.py` | one-shot "did it land where I think it did" — scene census + screenshot |
| `js.py` | evaluate arbitrary JS against the settled canvas |
| `stacking.py` | census of paint-chunk / stacking-context inducing CSS on the canvas |
| `analyze_trace.py` | summarize a devtools trace: per-thread busy, self time by event |
| `session.py` | shared plumbing (login, readiness, overlay buttons) — not run directly |

## Usage

```sh
# three runs on the current branch, Chrome, rows + median
uv run python .scratch/pan-perf/panperf.py --runs 3

# A/B a CSS hypothesis without editing source or restarting the studio
uv run python .scratch/pan-perf/panperf.py --runs 3 \
    --css '.number-drag::after { transform: scaleX(0) !important; }'

# what is the main thread actually doing
uv run python .scratch/pan-perf/panperf.py --runs 1 --trace /tmp/t.json
uv run python .scratch/pan-perf/analyze_trace.py /tmp/t.json --last 5

# the "cards are half-drawn / it flickers" symptom, captured
uv run python .scratch/pan-perf/panperf.py --runs 1 --shots .scratch/pan-perf/shots

# cross-engine
uv run python .scratch/pan-perf/panperf.py --engine firefox --runs 3
```

The studio is started if it is down (`studioctl start`, idempotent — it reuses
one you already have open and never spawns a second).

## How it gets in

Auth is on (`auth.enabled` in `~/.haywire/security.json`), and the gate covers
the websocket that *is* the application, not just the page. A browser cannot
attach an `Authorization` header to its own websocket handshake, so the agent
bearer token is no use here — the harness signs a session cookie directly with
`~/.haywire/session_secret` and adds it to the browser context. No password
lives in the repo, and a change to the login form's markup cannot break it.

It signs in as the first admin-tier **user** in the roster.

## fps is not the only instrument, and it lies about one thing

**A framerate run cannot see whether the canvas was drawn**, and is actively
misled by it: not painting half the cards is cheap, so the broken configuration
measures *faster* (87 fps with 53 of 208 cards missing, against 38 fps with all
208). That is how a `will-change` promotion survived an earlier fps-only review
for months.

So any change to compositing, promotion, layer structure or `will-change` gets
checked with both:

```sh
uv run python .scratch/pan-perf/paintcheck.py --zoom 0.069        # everything in view
uv run python .scratch/pan-perf/paintcheck.py --zoom 0.069 --pan  # and mid-motion
```

It boxes every unpainted card in an annotated PNG, so a false positive is
obvious at a glance. It excludes cards behind the debug HUD and the minimap — a
flat panel over a card reads exactly like an unpainted one — and it needs no
debug overlay, so it works when the HUD is switched off.

## Things that will bite you

- **Restart the studio after touching a `.vue`.** They compile at import; a
  browser reload is not enough. `studioctl restart`.
- **A `--shots` run is not a measurement.** Screenshotting costs frame time.
  Read its fps as diagnostic only.
- **`pan px` is an output, not an input.** It is frames × per-frame travel, so
  a faster engine racks up more of it. It answers "did the content move at
  all"; it does not normalise workload. Comparing a 6 fps row against an 87 fps
  row on pan travel is meaningless. (Related: at zoom 0.09 `_clampPanValues`
  refuses much of the requested sweep — the run gets ~16–25 px/frame of the
  80 px it asks for. Constant across runs, so it does not affect comparisons.)
- **Chrome vs Chromium.** `--engine chrome` uses the real Google Chrome
  (`channel="chrome"`), which is what the symptom was reported in. `chromium`
  is Playwright's bundled build.
- **Headed, native DPR, on purpose.** `viewport=` would force a device-metrics
  override and change the compositing path; headless rasters differently.
  `--headless` exists for CI, never for chasing a hand-observed symptom.
- **Playwright keeps CDP's Runtime domain enabled**, so `console.debug` in a hot
  path is serialized as if devtools were open. Measured: it makes no difference
  here (6.06 vs 6.05 fps), but `--silence-console` re-checks that on any graph
  where it might.
