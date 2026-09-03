"""Census of what creates paint chunks / stacking contexts in the live canvas.

`Layerize` (PaintArtifactCompositor::Update) turns paint chunks into cc layers,
and its cost tracks the number of chunks — which is set by how many elements
carry a property that forces its own effect/transform/clip node. This walks the
canvas and counts them, so a hypothesis about that cost can be aimed at the
right selector instead of guessed.

    uv run python .scratch/pan-perf/stacking.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import session as S  # noqa: E402

CENSUS = """
() => {
  const canvas = window.__hwPerfCanvas();
  const all = canvas.querySelectorAll('*');
  const tally = {};
  const bump = (k) => { tally[k] = (tally[k] || 0) + 1; };
  const byTag = {};
  const samples = {};

  for (const el of all) {
    const s = getComputedStyle(el);
    const hit = [];
    if (s.willChange && s.willChange !== 'auto') hit.push('will-change:' + s.willChange);
    if (s.transform && s.transform !== 'none') hit.push('transform');
    if (s.filter && s.filter !== 'none') hit.push('filter');
    if (s.backdropFilter && s.backdropFilter !== 'none') hit.push('backdrop-filter');
    if (s.opacity !== '' && parseFloat(s.opacity) < 1) hit.push('opacity<1');
    if (s.mixBlendMode && s.mixBlendMode !== 'normal') hit.push('mix-blend-mode');
    if (s.isolation === 'isolate') hit.push('isolation');
    if (s.contain && s.contain !== 'none') hit.push('contain:' + s.contain);
    if (s.position !== 'static' && s.zIndex !== 'auto') hit.push('positioned+z-index');
    if (s.overflow !== 'visible') hit.push('overflow:' + s.overflow);
    if (s.clipPath && s.clipPath !== 'none') hit.push('clip-path');
    const noMask = 'none 0% 0% / auto repeat border-box border-box scroll';
    if (s.mask && s.mask !== 'none' && s.mask !== noMask) hit.push('mask');
    if (s.perspective && s.perspective !== 'none') hit.push('perspective');
    if (s.transformStyle === 'preserve-3d') hit.push('preserve-3d');
    if (s.position === 'fixed' || s.position === 'sticky') hit.push('position:' + s.position);
    for (const h of hit) {
      bump(h);
      if (!samples[h]) samples[h] = el.className && el.className.baseVal !== undefined
        ? el.className.baseVal : String(el.className || el.tagName);
    }
    if (hit.length) byTag[el.tagName] = (byTag[el.tagName] || 0) + 1;
  }

  return {
    totalEls: all.length,
    tally,
    samples,
    byTag,
    nodeCards: canvas.querySelectorAll('[data-node-id]').length,
    pins: canvas.querySelectorAll('.connection-pin').length,
  };
}
"""


def main() -> int:
    url = S.ensure_studio()
    with sync_playwright() as pw:
        browser = S.launch(pw)
        context, page = S.open_studio(browser, url)
        S.wait_for_canvas(page)
        S.install_helpers(page)
        S.wait_for_nodes_settled(page)

        data = page.evaluate(CENSUS)
        print(
            f"canvas elements: {data['totalEls']}   node cards: {data['nodeCards']}   pins: {data['pins']}\n"
        )
        print("stacking / effect-node inducing properties:")
        for key, n in sorted(data["tally"].items(), key=lambda kv: -kv[1]):
            print(f"{n:8d}  {key}")
            print(f"          e.g. {data['samples'][key][:90]}")
        print("\nby tag:", json.dumps(data["byTag"]))

        # A single node card's own computed chrome, for the raster question.
        card = page.evaluate(
            """() => {
                const el = window.__hwPerfCanvas().querySelector('[data-node-id]');
                const s = getComputedStyle(el);
                const pick = ['position','zIndex','transform','willChange','filter','contain',
                              'boxShadow','borderRadius','background','backdropFilter','isolation',
                              'transformStyle','perspective','backfaceVisibility','overflow'];
                const out = {};
                for (const k of pick) out[k] = s[k];
                out.rect = el.getBoundingClientRect().toJSON();
                out.className = el.className;
                out.inlineStyle = el.getAttribute('style');
                return out;
            }"""
        )
        print("\nfirst node card:")
        print(json.dumps(card, indent=2)[:2500])

        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
