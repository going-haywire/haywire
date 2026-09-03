<template>
  <div
    ref="overlay"
    v-show="visible"
    class="debug-overlay"
    :style="containerStyle"
  ><span>{{ text }}</span><span
      v-if="lastRow"
      class="hw-perf-row"
    >{{ lastRow }}</span><span class="hw-perf-bar"><button
      class="hw-perf-btn"
      :disabled="recording"
      @click="applyZoomTarget"
    >zoom {{ zoomTarget }}</button><button
      class="hw-perf-btn"
      :disabled="recording"
      @click="startRecording"
    >{{ recording ? '● ' + phaseLabel : 'record ' + recordSeconds + 's' }}</button><button
      class="hw-perf-btn"
      :disabled="recording"
      @click="autoPan = !autoPan"
    >{{ autoPan ? 'auto-pan' : 'hand-pan' }}</button><button
      v-if="lastRow"
      class="hw-perf-btn"
      :disabled="recording"
      @click="copyLastRow"
    >{{ copyLabel }}</button></span></div>
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
    // Length of one `record` run. Long enough to cover a whole gesture, short
    // enough that a human can hold a steady pan for the duration.
    recordSeconds: { type: Number, default: 5 },
    // Lead-in before the window opens, so the gesture is already up to speed
    // when the first frame is counted. Without it the run measures the reaction
    // time between clicking and touching the trackpad.
    countdownSeconds: { type: Number, default: 3 },
    // How long a finished run stays on screen before the rolling readout resumes.
    resultHoldMs: { type: Number, default: 15000 },
    // One-click zoom so every run starts from the same scale. Note the pan
    // container floors zoom at "canvas fills viewport" when its min-zoom setting
    // is automatic, so a small target can land higher than asked — the button
    // reports what it actually got, and that is what a run records.
    zoomTarget: { type: Number, default: 0.09 },
    // Auto-pan sweep. A hand gesture cannot hold pan distance constant, and
    // `pan px` spanned a 2x range across runs of IDENTICAL code — larger than
    // any effect worth measuring, which made single-run comparisons worthless
    // (five runs of one branch came back 5.85–11.31 fps).
    //
    // The sweep drives pan from the measuring rAF loop itself: a fixed number
    // of CSS px per FRAME, reversing at the ends. Per-frame (not per-ms) is the
    // whole point — every frame then does the same amount of work regardless of
    // how slow the engine is, so a 2 fps engine and a 60 fps engine are asked
    // the identical question and `pan px` falls out as frames x speed. Driving
    // it by wall-clock would silently hand the slow engine longer jumps.
    autoPanPxPerFrame: { type: Number, default: 40 },
    // Half-width of the sweep, in CSS px either side of where it started.
    // _clampPanValues pins an axis whose scaled canvas is narrower than the
    // viewport, so the sweep runs on Y as well to guarantee real movement.
    autoPanSpanPx: { type: Number, default: 600 },
  },

  data() {
    return {
      text: 'debug overlay\nstarting…',
      // Reactive only because the template reads them — written a few times
      // per run, never per frame.
      recording: false,
      phaseLabel: '',
      // Last finished run's RESULTS.md row, shown verbatim and selectable so it
      // can always be taken by hand, whatever the clipboard does.
      lastRow: '',
      copyLabel: 'copy row',
      // Whether `record` drives the pan itself. On by default: a run nobody had
      // to hand-pan is the reproducible one, and the manual mode only exists to
      // reproduce the older rows in RESULTS.md that were gathered by trackpad.
      autoPan: true,
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
    // Fixed-window recorder (see startRecording). Null when not recording.
    this._rec          = null;
    this._recHoldUntil = 0;      // keeps a finished run's readout on screen
    // Every run of the session, so several can be compared without scrollback.
    window.__hwPerfRuns = window.__hwPerfRuns || [];

    // Capability check via supportedEntryTypes — NOT a try/catch.
    //
    // observe({type}) with an unsupported type does NOT throw: per the
    // Performance Timeline spec it aborts quietly (a console warning at most).
    // So a try/catch reports "supported" on a browser that silently registered
    // nothing, and every counter then reads a clean, entirely fictional zero.
    //
    // This mattered: Firefox supports neither 'longtask' nor
    // 'long-animation-frame', so runs taken there reported `lt-obs: yes` with
    // 0 long tasks and 0 LoAF, and that was read as "the main thread is idle".
    // It meant "nothing was ever being counted".
    const supportsEntry = (name) => {
      const types = (window.PerformanceObserver && PerformanceObserver.supportedEntryTypes) || [];
      return Array.prototype.indexOf.call(types, name) !== -1;
    };

    // Long-task observer (main-thread script blocks > 50ms).
    this._longTaskSupported = supportsEntry('longtask');
    if (this._longTaskSupported) {
      this._observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this._longTasks  += 1;
          this._longTaskMs += entry.duration;
        }
      });
      this._observer.observe({ type: 'longtask', buffered: true });
    }

    // Long Animation Frames. This is the one that settles main-thread vs
    // compositor, and 'longtask' CANNOT: a long task is only the script part of
    // a task, so style/layout/paint inside the frame update goes largely
    // unattributed — which is exactly why this API was added afterwards. A run
    // showing 80ms frames and no long tasks is therefore NOT evidence the main
    // thread is idle; a run showing 80ms frames and no LoAF entries is.
    //
    // LoAF only reports frames >= 50ms, which is below the frames of interest
    // here, so silence is meaningful rather than a sampling gap.
    this._loafCount = 0;
    this._loafMs    = 0;
    this._loafSlMs  = 0;   // style + layout portion, the part longtask misses
    this._loafSupported = supportsEntry('long-animation-frame');
    if (this._loafSupported) {
      this._loafObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this._loafCount += 1;
          this._loafMs    += entry.duration;
          if (entry.styleAndLayoutStart) {
            this._loafSlMs += (entry.startTime + entry.duration) - entry.styleAndLayoutStart;
          }
        }
      });
      this._loafObserver.observe({ type: 'long-animation-frame', buffered: true });
    }

    // Main-thread occupancy probe — engine-agnostic, and the reason LoAF is not
    // enough.
    //
    // LoAF only reports animation frames of 50ms or more. Chrome's frames here
    // average ~40ms, just under that, so LoAF stays silent whatever the main
    // thread is doing; Firefox does not implement it at all. Neither can answer
    // "is the main thread the bottleneck" for this workload.
    //
    // A MessageChannel task posted from inside the rAF callback runs AFTER the
    // browser has finished that frame's rendering update — style, layout, paint
    // and the compositor commit, main-thread side. The delay before it fires is
    // therefore the main thread's per-frame work, measured directly:
    //
    //   main ≈ frame  → main-thread bound; JS/CSS branches are worth building
    //   main << frame → the frame is waiting on raster / GPU / vsync instead
    //
    // MessageChannel rather than setTimeout(0) because setTimeout is clamped to
    // ~4ms once nested, which is the same order as the number being measured.
    this._mainBusyMs      = 0;
    this._mainBusySamples = 0;
    this._pendingT0       = null;
    this._mc = new MessageChannel();
    this._mc.port1.onmessage = () => {
      if (this._pendingT0 === null) return;
      this._mainBusyMs += performance.now() - this._pendingT0;
      this._mainBusySamples += 1;
      this._pendingT0 = null;
    };
    this._mc.port1.start();

    if (this.visible) this._start();
  },

  beforeUnmount() {
    this._stop();
    if (this._observer) { this._observer.disconnect(); this._observer = null; }
    if (this._loafObserver) { this._loafObserver.disconnect(); this._loafObserver = null; }
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
      // A hold left over from before the overlay was hidden would otherwise
      // freeze the readout on a stale run for up to resultHoldMs.
      this._recHoldUntil = 0;
      // Sets _censusLastT, so the interval gate below starts from now.
      this._runCensus();
      this._rafId = requestAnimationFrame(this._tick);
    },

    _stop() {
      if (this._rafId != null) {
        cancelAnimationFrame(this._rafId);
        this._rafId = null;
      }
      // Drop an in-flight run rather than reporting a window the loop stopped
      // measuring halfway through.
      this._rec = null;
      this.recording = false;
      this.phaseLabel = '';
    },

    _pct(arr, p) {
      if (!arr.length) return 0;
      const s = [...arr].sort((a, b) => a - b);
      return s[Math.min(s.length - 1, Math.floor(p * s.length))];
    },

    /** Begin a fixed-length measurement window.
     *
     *  The rolling readout is for watching; comparing two branches needs ONE
     *  number per run, taken over the same interval, under the same gesture.
     *
     *  For the duration the HUD writes no text and the census is suspended.
     *  Both touch the DOM (the census also walks the entire canvas subtree,
     *  which is exactly the cost being diagnosed), and a run that includes its
     *  own instrument is not comparable against a run that skipped it. The
     *  scene counts are therefore snapshotted here, at the start.
     */
    startRecording() {
      if (this.recording || this._rafId == null) return;
      this._rec = {
        phase:   'countdown',
        // Counters and the scene snapshot are filled in at _openWindow, once
        // the countdown has elapsed — the census may still refresh during it.
        primed:  false,
        startT:  performance.now(),
        frames:  0,
        times:   [],
        stalls:  0,
      };
      this.recording = true;
      this.phaseLabel = `${this.countdownSeconds}`;
      // Nagged at the start, not the end: once the run is over the row is
      // already stamped '(unset)' and has to be fixed by hand in the table.
      const tag = window.__hwPerfBranch
        ? ''
        : '\n⚠ __hwPerfBranch unset — row will say (unset)';
      this.text = this.autoPan
        ? `starting in ${this.countdownSeconds}…\nauto-pan — hands off${tag}`
        : `starting in ${this.countdownSeconds}…\nbegin panning NOW${tag}`;
      this._recHoldUntil = 0;
    },

    /** Countdown elapsed — take the snapshot and open the measurement window. */
    _openWindow(now) {
      const r = this._rec;
      const c = this._census || {};
      r.phase  = 'recording';
      r.startT = now;
      // Cumulative counters — differenced at the end to get this run's share.
      r.longTasks  = this._longTasks;
      r.longTaskMs = this._longTaskMs;
      r.loafCount  = this._loafCount;
      r.loafMs     = this._loafMs;
      r.loafSlMs   = this._loafSlMs;
      r.mainBusyMs = this._mainBusyMs;
      r.mainBusySamples = this._mainBusySamples;
      // Pan travel, so a run can prove it actually panned. `_clampPanValues`
      // CENTERS an axis whose scaled canvas is smaller than the viewport and
      // refuses to move it — at zoom 0.15 the 8000px canvas is only 1200px
      // wide, so on a wider window horizontal pan is pinned and a vigorous
      // trackpad sweep moves nothing. A run that measured a static transform
      // must not be compared against one that measured a moving one.
      const el = document.getElementById(this.containerId);
      r.controls = (el && el._zoomPanControls) || null;
      r.lastPan  = r.controls ? r.controls.getPan() : null;
      r.panPx    = 0;
      // Auto-pan anchor: the sweep is measured from wherever the canvas sits
      // when the window opens, so it never depends on prior manual panning.
      r.autoPan  = this.autoPan && !!r.controls;
      r.panOrigin = r.lastPan ? { x: r.lastPan.x, y: r.lastPan.y } : null;
      r.panDir   = 1;
      r.panOff   = 0;
      r.zoom = c.zoom != null ? c.zoom : 'n/a';
      r.lod  = c.lod  != null ? c.lod  : 'n/a';
      r.totalEls = c.totalEls;
      r.nodes = c.nodes;
      r.pins = c.pins;
      r.paths = c.paths;
      this.phaseLabel = 'recording…';
      this.text = r.autoPan
        ? `● recording ${this.recordSeconds}s — auto-pan, hands off`
        : `● recording ${this.recordSeconds}s — keep panning`;
    },

    /** Jump the canvas to `zoomTarget` so runs start from the same scale.
     *
     *  Reads the achieved zoom back rather than trusting the request: the pan
     *  container clamps to its own floor, which with an automatic min-zoom is
     *  "canvas fills viewport" and therefore depends on the window size.
     */
    applyZoomTarget() {
      const el = document.getElementById(this.containerId);
      const controls = el && el._zoomPanControls;
      if (!controls) {
        this.text = 'zoom: no pan controls on this container';
        this._recHoldUntil = performance.now() + 3000;
        return;
      }
      controls.setZoom(this.zoomTarget);
      const got = controls.getZoom();
      const floored = Math.abs(got - this.zoomTarget) > 1e-6;
      // Force the scene counts to catch up with the new LOD before a run
      // snapshots them.
      this._runCensus();
      this.text = floored
        ? `zoom ${got.toFixed(3)}  (asked ${this.zoomTarget}, floored at min)\n` +
          `LOD ${this._census.lod} — record from here`
        : `zoom ${got.toFixed(3)}   LOD ${this._census.lod}\nready to record`;
      this._recHoldUntil = performance.now() + 4000;
    },

    /** Advance the auto-pan sweep by exactly one frame's worth of travel.
     *
     *  A triangle wave: `autoPanPxPerFrame` px per frame along a diagonal,
     *  reversing at +/- `autoPanSpanPx` from where the run started. Diagonal
     *  because `_clampPanValues` pins whichever axis is narrower than the
     *  viewport at low zoom — moving both guarantees the content actually
     *  travels, and `pan px` in the finished row proves whether it did.
     *
     *  Deliberately stepped per FRAME rather than per elapsed ms. The sweep is
     *  the workload under measurement, so every engine must be handed the same
     *  work per frame; scaling by dt would give a slow engine longer jumps and
     *  quietly change the thing being compared.
     */
    _stepAutoPan(r) {
      if (!r.controls || !r.panOrigin) return;
      r.panOff += this.autoPanPxPerFrame * r.panDir;
      if (r.panOff >= this.autoPanSpanPx) {
        r.panOff = this.autoPanSpanPx;
        r.panDir = -1;
      } else if (r.panOff <= -this.autoPanSpanPx) {
        r.panOff = -this.autoPanSpanPx;
        r.panDir = 1;
      }
      r.controls.setPan(r.panOrigin.x + r.panOff, r.panOrigin.y + r.panOff);
    },

    _finishRecording(now) {
      const r = this._rec;
      this._rec = null;
      this.recording = false;

      const elapsed = now - r.startT;
      const t = r.times;
      const mean = t.length ? t.reduce((a, b) => a + b, 0) / t.length : 0;
      const round = (n) => Math.round(n * 100) / 100;

      const run = {
        // Set from the console (`window.__hwPerfBranch = 'perf/…'`) so a run
        // carries which branch produced it; the HUD cannot know.
        branch:      window.__hwPerfBranch || '(unset)',
        seconds:     round(elapsed / 1000),
        // Frames over wall clock, NOT 1000/mean: a run that drops frames shows
        // it here, where a mean over the surviving intervals hides it.
        fps:         round((r.frames * 1000) / (elapsed || 1)),
        meanFrameMs: round(mean),
        p50FrameMs:  round(this._pct(t, 0.50)),
        p95FrameMs:  round(this._pct(t, 0.95)),
        p99FrameMs:  round(this._pct(t, 0.99)),
        maxFrameMs:  round(t.length ? Math.max(...t) : 0),
        stalls:      r.stalls,
        longTasks:   this._longTasks  - r.longTasks,
        // Carried explicitly because a zero count is otherwise ambiguous: it
        // reads the same whether no task ran long or the browser never
        // reported any. The distinction decides whether "0 long tasks against
        // N stalls" is evidence the main thread is idle — the whole
        // main-thread-vs-compositor question turns on it.
        longTaskObs: this._longTaskSupported,
        loafCount:   this._loafCount - r.loafCount,
        loafMs:      Math.round(this._loafMs   - r.loafMs),
        loafSlMs:    Math.round(this._loafSlMs - r.loafSlMs),
        loafObs:     this._loafSupported,
        // Mean main-thread work per frame. Compare against meanFrameMs:
        // close means main-thread bound, far below means it is not.
        mainMs:      round((this._mainBusyMs - r.mainBusyMs)
                       / Math.max(1, this._mainBusySamples - r.mainBusySamples)),
        panPx:       Math.round(r.panPx),
        // How the pan was driven. An auto row is reproducible; a hand row is
        // not, and the two must never be compared — every row in RESULTS.md
        // predating the sweep is a hand row.
        pan:         r.autoPan ? `auto${this.autoPanPxPerFrame}` : 'hand',
        // Which engine produced the run. longtask/LoAF exist only in
        // Chromium, so a Firefox row and a Chrome row are not the same
        // measurement and must never be compared column-for-column.
        engine:      (navigator.userAgent.indexOf('Firefox') !== -1) ? 'ff'
                     : (navigator.userAgent.indexOf('Chrome') !== -1) ? 'cr' : 'other',
        longTaskMs:  Math.round(this._longTaskMs - r.longTaskMs),
        zoom: r.zoom, lod: r.lod,
        totalEls: r.totalEls, nodes: r.nodes, pins: r.pins, paths: r.paths,
      };

      window.__hwPerfRuns.push(run);
      run.row = this._markdownRow(run);

      // The row is logged BARE and last: a console prefix travels with the text
      // when it is copied out of devtools, and would have to be deleted by hand
      // from every pasted table row.
      console.log('[hw-perf]', JSON.stringify(run));
      console.log(run.row);

      this.phaseLabel = '';
      this.lastRow = run.row;
      this.copyLabel = 'copy row';
      this.text =
        `RUN ${window.__hwPerfRuns.length}   ${run.seconds}s\n` +
        `${run.branch}\n` +
        `fps ${run.fps}   frame ${run.meanFrameMs}ms\n` +
        `p95 ${run.p95FrameMs}  p99 ${run.p99FrameMs}  max ${run.maxFrameMs}\n` +
        `stalls ${run.stalls}  longtasks ${run.longTasks} (${run.longTaskMs}ms)\n` +
        (run.loafObs
          ? `LoAF ${run.loafCount} (${run.loafMs}ms)  style+layout ${run.loafSlMs}ms\n`
          : `LoAF n/a\n`) +
        `main-thread ${run.mainMs}ms of ${run.meanFrameMs}ms frame\n` +
        `pan travel ${run.panPx}px (${run.pan})` +
        (run.panPx < 200
          ? (r.autoPan
              // The sweep asked for movement and the container refused it, so
              // the run measured a near-static transform. Almost always the
              // low-zoom clamp pinning both axes.
              ? '  ⚠ SWEEP PINNED — clamped\n'
              : '  ⚠ BARELY MOVED\n')
          : '\n') +
        `-------------------------\n` +
        `zoom ${run.zoom}   LOD ${run.lod}\n` +
        `DOM els ${run.totalEls}  nodes ${run.nodes}  pins ${run.pins}`;
      // Hold the result on screen. Without this the rolling readout overwrites
      // it 100ms later — before anyone has read the number they asked for.
      this._recHoldUntil = now + this.resultHoldMs;
    },

    /** One RESULTS.md table row. Column order must match the table there. */
    _markdownRow(run) {
      return `| ${run.branch} | ${run.fps} | ${run.meanFrameMs} | ${run.p95FrameMs} | ` +
             `${run.p99FrameMs} | ${run.maxFrameMs} | ${run.stalls} | ` +
             `${run.engine} | ${run.longTasks} (${run.longTaskMs}ms) | ` +
             `${run.longTaskObs ? 'yes' : 'NO'} | ` +
             `${run.loafObs ? run.loafCount + ' (' + run.loafMs + 'ms)' : 'n/a'} | ` +
             `${run.loafObs ? run.loafSlMs : 'n/a'} | ${run.mainMs} | ${run.panPx} | ` +
             `${run.zoom} | ${run.lod} | ${run.pan} |`;
    },

    /** Copy the last run's row. Bound to a button ON PURPOSE.
     *
     *  An earlier version copied automatically when the run finished, which
     *  cannot work: `navigator.clipboard.writeText` needs transient user
     *  activation, and by then the click that started the run is 8 seconds old
     *  (3s countdown + 5s window). Chrome rejects with NotAllowedError — and
     *  since nothing awaited the promise, it surfaced as an unhandled rejection
     *  while the HUD still claimed the row had been copied.
     *
     *  A button press is its own activation, so the write is permitted. The row
     *  is also rendered selectable above, so a failure here is never a dead end.
     */
    copyLastRow() {
      if (!this.lastRow) return;
      this._copyToClipboard(this.lastRow).then((ok) => {
        this.copyLabel = ok ? 'copied ✓' : 'copy failed';
        setTimeout(() => { this.copyLabel = 'copy row'; }, 2000);
      });
    },

    /** Copy `text`; resolves to whether it worked, and never rejects.
     *
     *  Mirrors `clipboard_script` in ui/elements/elements.py — keep them in
     *  step. The execCommand fallback is not optional: navigator.clipboard is
     *  undefined outside a secure context, and a studio reached over a LAN
     *  address on plain http is not one (localhost is, which is why this never
     *  fails where it gets tested). It also catches the case where the API is
     *  present but refuses the write.
     */
    _copyToClipboard(text) {
      if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text).then(
          () => true,
          () => this._copyFallback(text),
        );
      }
      return Promise.resolve(this._copyFallback(text));
    },

    _copyFallback(text) {
      try {
        const area = document.createElement('textarea');
        area.value = text;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.top = '-1000px';
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(area);
        return ok;
      } catch (error) {
        return false;
      }
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

      // Recording window. Everything below writes DOM or walks the canvas
      // subtree, so it is skipped wholesale until the run closes — see
      // startRecording for why the instrument must stay out of its own numbers.
      if (this._rec) {
        const r = this._rec;
        if (r.phase === 'countdown') {
          const left = this.countdownSeconds * 1000 - (now - r.startT);
          if (left <= 0) {
            this._openWindow(now);
          } else {
            // One write per whole second, not per frame — the countdown is
            // outside the window, but there is no reason to make it expensive.
            const secs = Math.ceil(left / 1000);
            if (String(secs) !== this.phaseLabel) {
              this.phaseLabel = String(secs);
              const tag = window.__hwPerfBranch
                ? ''
                : '\n⚠ __hwPerfBranch unset — row will say (unset)';
              this.text = `starting in ${secs}…\nbegin panning NOW${tag}`;
            }
          }
        } else if (!r.primed) {
          // The first interval spans the phase change. Rebase so neither the
          // window nor the frame stats carry it.
          r.primed = true;
          r.startT = now;
        } else {
          r.frames += 1;
          r.times.push(dt);
          if (dt > this.STALL_MS) r.stalls += 1;
          // One probe per frame. A frame whose probe has not fired yet is
          // skipped rather than queued, so the sample is always paired.
          if (this._pendingT0 === null) {
            this._pendingT0 = performance.now();
            this._mc.port2.postMessage(0);
          }
          // Drive the sweep BEFORE the pan accounting below, so this frame's
          // movement lands in this frame's `pan px` rather than the next one's.
          if (r.autoPan) this._stepAutoPan(r);
          if (r.controls) {
            // Manhattan path length, not net displacement: a sweep that returns
            // to where it started still moved the content the whole way.
            const p = r.controls.getPan();
            r.panPx += Math.abs(p.x - r.lastPan.x) + Math.abs(p.y - r.lastPan.y);
            r.lastPan = p;
          }
          if (now - r.startT >= this.recordSeconds * 1000) this._finishRecording(now);
        }
        this._rafId = requestAnimationFrame(this._tick);
        return;
      }

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
      if (now - this._textLastT < 100 || now < this._recHoldUntil) {
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

/* The result row, verbatim and selectable. The overlay is user-select:none and
 * pointer-events:none, so without both overrides the row would be visible and
 * impossible to take by hand — which is the whole point of showing it. */
.debug-overlay .hw-perf-row {
  display: block;
  margin-top: 8px;
  padding: 4px 6px;
  border-radius: 4px;
  border: 1px dashed var(--hw-border);
  pointer-events: auto;
  user-select: text;
  -webkit-user-select: text;
  cursor: text;
  white-space: pre-wrap;
  word-break: break-all;
  opacity: 0.85;
}

.debug-overlay .hw-perf-bar {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

/* The overlay container stays pointer-events:none so it never eats a canvas
 * gesture underneath it — the buttons re-enable them for themselves alone. */
.debug-overlay .hw-perf-btn {
  flex: 1;
  pointer-events: auto;
  font: inherit;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--hw-border);
  background: transparent;
  color: inherit;
  cursor: pointer;
  white-space: nowrap;
}

.debug-overlay .hw-perf-btn:disabled {
  opacity: 0.55;
  cursor: default;
}
</style>
