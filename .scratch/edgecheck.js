/**
 * edgecheck — paste into the Chrome console on a studio tab with detached edges.
 *
 *   hwEdgeCheck()          report on every canvas in the page
 *   hwEdgeCheck({fix:true}) ...and then force a full re-measure, to see if the
 *                           geometry is recoverable at all
 *
 * What each field answers:
 *
 *   canvases[].connected   more than one canvas, or a disconnected one, means a
 *                          stale component is still alive and still processing
 *                          messages meant for the live one.
 *   scaleRatio             drawn span ÷ real pin span, on screen. ~1 is correct
 *                          geometry. A ratio of k means the edges were measured
 *                          at a zoom k times wrong — 2.9 says they were measured
 *                          believing zoom was 1 while it was ~0.35. This is the
 *                          decisive test for the wrong-zoom theory and needs no
 *                          access to the Vue instance.
 *   worstPx                how far the worst endpoint sits from its pin.
 *   missingPins            edges whose pins cannot be found at all. These are
 *                          the ones _updateEdge gives up on, leaving whatever
 *                          geometry they already had — the console errors you
 *                          see. If a node here has holder:false, that canvas's
 *                          nodes are gone from the DOM; if cullVisible:false,
 *                          the node is culled and the edge is simply waiting.
 */
window.hwEdgeCheck = function (opts) {
  const options = opts || {};
  const report = [];

  document.querySelectorAll('.graph-canvas').forEach((root) => {
    const paths = Array.from(
      root.querySelectorAll('.connection-svg path[data-edge-id]'),
    ).filter((p) => !p.id.endsWith('_hitarea'));

    const pinsOf = (edgeId) => {
      const m = /^(.*)\[(.*)\]->(.*)\[(.*)\]$/.exec(edgeId);
      if (!m) return null;
      return {
        outletNode: m[1],
        inletNode: m[3],
        outlet: document.getElementById(`${m[2]}@${m[1]}`),
        inlet: document.getElementById(`${m[4]}@${m[3]}`),
      };
    };
    const centre = (el) => {
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width };
    };
    const screenAt = (path, len) => {
      const ctm = path.getScreenCTM();
      if (!ctm) return null;
      const q = path.getPointAtLength(len);
      return { x: q.x * ctm.a + q.y * ctm.c + ctm.e, y: q.x * ctm.b + q.y * ctm.d + ctm.f };
    };
    const dist = (a, b) => Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);

    let worstPx = 0;
    let worstEdge = null;
    const ratios = [];
    const missingPins = [];

    paths.forEach((p) => {
      const pins = pinsOf(p.id);
      if (!pins) return;
      if (!pins.outlet || !pins.inlet) {
        const nodeState = (id) => {
          const holder = document.getElementById(id);
          const cull = holder && holder.querySelector(':scope > .hw-node-cull');
          return {
            node: id,
            holder: !!holder,
            connected: !!(holder && holder.isConnected),
            cullVisible: cull && cull._hwCull ? cull._hwCull.isVisible() : null,
          };
        };
        missingPins.push({
          edge: p.id,
          outlet: !!pins.outlet,
          inlet: !!pins.inlet,
          nodes: [nodeState(pins.outletNode), nodeState(pins.inletNode)],
        });
        return;
      }
      const a = screenAt(p, 0);
      const b = screenAt(p, p.getTotalLength());
      if (!a || !b) return;
      const pa = centre(pins.outlet);
      const pb = centre(pins.inlet);
      if (!pa.w || !pb.w) return;

      const err = Math.max(dist(a, pa), dist(b, pb));
      if (err > worstPx) {
        worstPx = err;
        worstEdge = p.id;
      }
      const real = dist(pa, pb);
      if (real > 1) ratios.push(dist(a, b) / real);
    });

    const zoomEl = root.closest('[id^="zoom-pan-"]') || document.querySelector('.zoom-pan-content');
    report.push({
      canvasId: root.dataset.hwCanvasId,
      connected: root.isConnected,
      onScreen: root.getBoundingClientRect().width > 0,
      edges: paths.length,
      drawnStamp: Number(root.dataset.hwEdgeDrawn || 0),
      parkedStamp: Number(root.dataset.hwEdgeParked || 0),
      batches: Number(root.dataset.hwEdgeBatch || 0),
      worstPx: Math.round(worstPx),
      worstEdge,
      scaleRatio: ratios.length
        ? Number((ratios.reduce((s, r) => s + r, 0) / ratios.length).toFixed(3))
        : null,
      transform: zoomEl ? getComputedStyle(zoomEl).transform : null,
      missingPinCount: missingPins.length,
      missingPins: missingPins.slice(0, 5),
    });
  });

  console.table(
    report.map((r) => ({
      canvas: r.canvasId,
      connected: r.connected,
      onScreen: r.onScreen,
      edges: r.edges,
      worstPx: r.worstPx,
      scaleRatio: r.scaleRatio,
      missing: r.missingPinCount,
      batches: r.batches,
    })),
  );
  console.log('full report', report);

  if (options.fix) {
    document.querySelectorAll('.graph-canvas').forEach((root) => {
      const ctrl = root._graphCanvasControls;
      console.log('forcing re-measure on', root.dataset.hwCanvasId, 'controls:', !!ctrl);
    });
    console.log('now select all nodes (ctrl+A) and deselect, then re-run hwEdgeCheck()');
  }
  return report;
};

console.log('edgecheck loaded — run hwEdgeCheck()');
