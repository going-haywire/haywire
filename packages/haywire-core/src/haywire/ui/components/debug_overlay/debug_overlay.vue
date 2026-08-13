<template>
  <div
    ref="overlay"
    v-show="visible"
    class="debug-overlay"
    :style="containerStyle"
  >{{ text }}</div>
</template>

<script>
// Canvas debug/performance HUD.
//
// Self-contained port of internals/perf_probe.js: a requestAnimationFrame loop
// measures FPS / frame time / worst-1% (p99) jank, a PerformanceObserver counts
// main-thread long tasks (>50ms), and a periodic DOM census reports element /
// node / pin / path counts plus the current zoom + LOD level. Zoom and pan are
// read straight from the container's _zoomPanControls so no Python round-trip
// is needed per frame.
export default {
  name: 'DebugOverlay',

  props: {
    containerId: { type: String,  required: true },
    position:    { type: String,  default: 'bottom-left' },
    visible:     { type: Boolean, default: false },
    censusIntervalMs: { type: Number, default: 1000 },
  },

  data() {
    return {
      text: 'debug overlay\nstarting…',
    };
  },

  computed: {
    containerStyle() {
      const POSITIONS = {
        'top-left':     'top: 10px; left: 10px;',
        'top-right':    'top: 10px; right: 10px;',
        'bottom-left':  'bottom: 10px; left: 10px;',
        'bottom-right': 'bottom: 10px; right: 10px;',
      };
      return (
        'position: absolute; ' +
        'z-index: 1002; ' +
        'pointer-events: none; ' +
        'white-space: pre; ' +
        'font: 11px/1.4 monospace; ' +
        'padding: 8px 10px; ' +
        'border-radius: 6px; ' +
        'border: 1px solid var(--hw-border); ' +
        'background: var(--hw-bg-overlay, rgba(0,0,0,0.82)); ' +
        'color: var(--hw-text-body, #0f0); ' +
        'min-width: 230px; ' +
        'box-shadow: 0 2px 12px rgba(0,0,0,0.4); ' +
        'backdrop-filter: blur(2px); ' +
        (POSITIONS[this.position] || POSITIONS['bottom-left'])
      );
    },
  },

  mounted() {
    // Non-reactive measurement state — updated every frame, no Vue reactivity needed.
    this._lastT        = performance.now();
    this._times        = [];     // recent frame durations (ms)
    this._longTasks    = 0;
    this._longTaskMs   = 0;
    this._stalls       = 0;      // rAF-gap fallback: frames longer than STALL_MS
    this._frameCounter = 0;
    this._censusLastT  = 0;      // last DOM census (ms); interval is a prop
    this._censusCost   = 0;      // how long the last census took (ms)
    this._textLastT    = 0;      // last HUD text refresh (ms)
    this._census       = {};
    this._rafId        = null;
    this._observer     = null;
    // Node-measurement traffic (window.__hwMeasureStats, published by canvas.vue).
    // Tracked as a per-second rate as well as a total: the question these answer
    // is whether measurement settles to zero once a graph has finished laying out.
    this._measureLastT     = performance.now();
    this._measureLastSent  = 0;
    this._measureLastBatch = 0;
    this._measureRate      = { sent: 0, batches: 0 };
    this._longTaskSupported = false;
    this.STALL_MS      = 50;     // matches the PerformanceLongTaskTiming threshold

    // Long-task observer (main-thread blocks > 50ms). PerformanceObserver throws
    // if 'longtask' is unsupported; the supported flag lets the HUD show 'n/a'
    // instead of a misleading 0. buffered:true picks up tasks fired before mount.
    try {
      this._observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this._longTasks  += 1;
          this._longTaskMs += entry.duration;
        }
      });
      this._observer.observe({ type: 'longtask', buffered: true });
      this._longTaskSupported = true;
    } catch (e) {
      // 'longtask' unavailable (e.g. Safari/Firefox) — fall back to rAF stalls.
      this._longTaskSupported = false;
    }

    if (this.visible) this._start();
  },

  beforeUnmount() {
    this._stop();
    if (this._observer) { this._observer.disconnect(); this._observer = null; }
  },

  watch: {
    visible(on) {
      if (on) this._start();
      else this._stop();
    },
  },

  methods: {
    _start() {
      if (this._rafId != null) return;
      this._lastT = performance.now();
      this._times = [];
      // Reset so the "skip first interval" stall guard re-arms on every restart;
      // the longtasks/stalls counters stay cumulative for the session.
      this._frameCounter = 0;
      // Re-baseline the measurement rate, otherwise the first sample after a
      // hidden period reports the whole gap as one second's worth of traffic.
      const ms = window.__hwMeasureStats;
      this._measureLastT     = this._lastT;
      this._measureLastSent  = ms ? ms.sent : 0;
      this._measureLastBatch = ms ? ms.batches : 0;
      this._measureRate      = { sent: 0, batches: 0 };
      // Force the readout to paint on the first tick rather than 100ms in.
      this._textLastT = 0;
      // Sets _censusLastT, so the interval gate below starts from now.
      this._runCensus();
      this._rafId = requestAnimationFrame(this._tick);
    },

    _stop() {
      if (this._rafId != null) {
        cancelAnimationFrame(this._rafId);
        this._rafId = null;
      }
    },

    _pct(arr, p) {
      if (!arr.length) return 0;
      const s = [...arr].sort((a, b) => a - b);
      return s[Math.min(s.length - 1, Math.floor(p * s.length))];
    },

    _runCensus() {
      const censusStart = performance.now();
      const container = document.getElementById(this.containerId);
      const content = container
        ? container.querySelector('.zoom-pan-content')
        : document.querySelector('.zoom-pan-content');
      const scope = content || document.body;

      // These counts walk the whole canvas subtree, so their cost scales with
      // the graph being diagnosed — on a 33k-element graph the naive version
      // cost enough to dominate the frame times the HUD was reporting. Keep
      // this loop cheap; see _tick's frame budget for when it is skipped.
      const totalEls = scope.querySelectorAll('*').length;

      // Top-level nodes only — ports also carry data-node-id sometimes. The
      // ':scope >' selector gets the same answer as filtering every match by
      // closest(), without an ancestor walk per node (5k walks on a 200-node
      // graph, since each node holds ~24 pins).
      // By class, not #node-container: the id is duplicated across canvases
      // when several graphs are open, and `scope` already pins us to this one.
      const nodeHost = scope.querySelector('.node-container') || scope;
      const nodes = nodeHost.querySelectorAll(':scope > [data-node-id]').length;
      const pins  = scope.querySelectorAll('.connection-pin').length;
      const paths = scope.querySelectorAll('svg path').length;

      let zoom = null;
      let lod = null;
      if (container) {
        if (container._zoomPanControls) zoom = container._zoomPanControls.getZoom();
        lod = container.getAttribute('data-lod-level');
      }

      this._census = {
        totalEls,
        nodes,
        pins,
        paths,
        zoom: zoom != null ? zoom.toFixed(3) : 'n/a',
        lod: lod || 'n/a',
      };
      // Self-reported so the HUD's own cost is visible rather than silently
      // folded into the frame times it displays.
      this._censusCost = performance.now() - censusStart;
      this._censusLastT = censusStart;
    },

    _tick(now) {
      if (this._rafId == null) return;

      const dt = now - this._lastT;
      this._lastT = now;
      this._frameCounter += 1;
      this._times.push(dt);
      if (this._times.length > 180) this._times.shift(); // ~3s window

      // rAF-gap fallback: a frame interval over STALL_MS means the main thread
      // was blocked for that long (the same thing 'longtask' reports, minus the
      // 50ms-task attribution). Skip the very first interval after (re)start,
      // which is inflated by mount/visibility timing rather than real jank.
      if (this._frameCounter > 1 && dt > this.STALL_MS) this._stalls += 1;

      // Census on a wall-clock interval, and only when the previous frame had
      // room for it. The census walks the entire canvas subtree, so on a large
      // graph it is itself a source of jank — skipping it while frames are
      // already blowing the budget keeps the HUD from taxing the very frames
      // it is meant to diagnose. A pathological graph may then census rarely;
      // that is the intended trade (the counts move slowly, the frame times
      // do not).
      // Starvation guard: on a graph slow enough that NO frame has room, run it
      // anyway once the interval has been missed 10x over, so the counts cannot
      // freeze permanently on exactly the graphs worth inspecting.
      const sinceCensus = now - this._censusLastT;
      const censusDue = sinceCensus >= this.censusIntervalMs;
      const frameHasRoom = dt < this.STALL_MS;
      const censusOverdue = sinceCensus >= this.censusIntervalMs * 10;
      if (censusDue && (frameHasRoom || censusOverdue)) this._runCensus();

      // Sample measurement traffic once a second (counters are cumulative, so
      // the rate is a delta over the elapsed window).
      const ms = window.__hwMeasureStats;
      if (ms && now - this._measureLastT >= 1000) {
        const elapsed = (now - this._measureLastT) / 1000;
        this._measureRate = {
          sent: (ms.sent - this._measureLastSent) / elapsed,
          batches: (ms.batches - this._measureLastBatch) / elapsed,
        };
        this._measureLastT = now;
        this._measureLastSent = ms.sent;
        this._measureLastBatch = ms.batches;
      }

      // Refresh the readout ~10x/sec, not every frame: `this.text` is reactive,
      // so each write is a Vue update plus a DOM write, and _pct sorts the frame
      // window to find p99. None of that is worth doing at 60fps for a display
      // no one can read that fast — the sampling above stays per-frame.
      if (now - this._textLastT < 100) {
        this._rafId = requestAnimationFrame(this._tick);
        return;
      }
      this._textLastT = now;

      const avg   = this._times.reduce((a, b) => a + b, 0) / this._times.length;
      const fps   = 1000 / avg;
      const worst = this._pct(this._times, 0.99);
      const c     = this._census;

      const longTaskLine = this._longTaskSupported
        ? `longtasks ${this._longTasks}  (${this._longTaskMs.toFixed(0)}ms)`
        : `longtasks n/a`;

      // "measure" reads: per-second batches (= websocket messages) and node
      // measurements, then session totals as sent/observed. A settled graph
      // shows 0/s; sent << observed is the dedupe doing its job.
      const mr = this._measureRate;
      const measureLine = ms
        ? `measure ${mr.batches.toFixed(1)}/s  ${mr.sent.toFixed(0)} nodes/s\n` +
          `  sent ${ms.sent}/${ms.observed}  batches ${ms.batches}`
        : `measure n/a`;

      this.text =
        `Haywire perf\n` +
        `fps ${fps.toFixed(0).padStart(3)}   frame ${avg.toFixed(1)}ms\n` +
        `p99 frame ${worst.toFixed(1)}ms  (jank>33ms)\n` +
        `${longTaskLine}\n` +
        `stalls>${this.STALL_MS}ms ${this._stalls}\n` +
        `-------------------------\n` +
        `zoom ${c.zoom}   LOD ${c.lod}\n` +
        `DOM els ${c.totalEls}  (census ${this._censusCost.toFixed(1)}ms)\n` +
        `nodes ${c.nodes}  pins ${c.pins}  paths ${c.paths}\n` +
        `${measureLine}`;

      this._rafId = requestAnimationFrame(this._tick);
    },
  },
};
</script>

<style scoped>
.debug-overlay {
  user-select: none;
  -webkit-user-select: none;
}
</style>
