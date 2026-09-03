# Trackpad vs mouse wheel cannot be decided per event

**Symptom.** Zoom jumped mid-pan. Panning down to the bottom of the viewport
zoomed *out*; panning back to the top zoomed *in*. Measured: a fast vertical
trackpad swipe drove zoom from 0.30 to 0.02 going down, and 0.30 to 2.96 going
up.

**Cause.** `handleWheel` in `zoom/pan.vue` classified every wheel event on its
own:

```js
const isMouseWheel = e.deltaMode === 1 ||
    (e.deltaMode === 0 && Math.abs(e.deltaY) >= 50 && e.deltaX === 0);
```

Both halves of that test are satisfied by the middle of a normal trackpad
swipe. A vigorous flick reaches 60–80 px per event, and a *deliberate vertical*
swipe has `deltaX` exactly `0`. So the fast part of every pan was read as a
mouse wheel and routed to zoom — which is why the jump always happened
mid-gesture, and always in the direction of travel.

## The fix: classify the gesture, not the event

The two input devices are not separable event-by-event — the delta ranges
genuinely overlap — but the *streams* differ:

- **trackpad** — a dense burst (events ~8–16 ms apart) that **ramps up** from
  small deltas, because it tracks finger velocity.
- **mouse wheel** — sparse discrete notches, each already at full magnitude.

So classify the first event of a gesture and **latch** it until the stream goes
quiet (`WHEEL_GESTURE_GAP_MS`, 100 ms). A trackpad swipe always opens small, so
the opening event classifies correctly, and the latch then carries the gesture
through the fast middle that used to misfire.

One asymmetry is deliberate: a latched `wheel` may downgrade to `trackpad` if
later events show two axes or small deltas, but a latched `trackpad` can never
flip to `wheel`. Zoom leaking into a pan is the failure being fixed; the
reverse is merely a missed zoom.

`_looksLikeMouseWheel` decides only that opening event, so it can be strict:
non-zero `deltaMode` is always a real wheel, any `deltaX` or any `|deltaY| < 50`
is a trackpad, and `wheelDeltaY` not being a multiple of 120 rules out a wheel
in Chrome and Safari. That last signal is a tiebreak only — a trackpad `deltaY`
of 40 or 80 also lands on a multiple of 120, which is exactly why it must not
be used on its own.

## Regression check

`.scratch/pan-perf/wheelcheck.py` replays realistic gesture traces and asserts
both halves — that a swipe pans **and** does not zoom, and that a wheel notch
and a pinch still do zoom:

```sh
uv run python .scratch/pan-perf/wheelcheck.py     # 6/6 cases
```

The "and pans" half is not optional. An assertion that only checks "zoom did
not change" is satisfied by a handler that does nothing at all, which is a very
easy way to "fix" this bug and break panning instead.

## If you touch this again

- Test the **fast** swipe, not a gentle one. The old code handled slow swipes
  (`|deltaY| < 50`) and diagonal swipes (`deltaX != 0`) correctly; only the
  fast straight-line case broke, which is why it survived casual use.
- Do not reach for a bigger magnitude threshold. There is no threshold that
  separates them — a trackpad flick and a wheel notch overlap in every
  per-event property except the shape of the stream around them.
