"""Hover tips drawn in the browser, for elements that carry their text as attributes.

An element with ``data-hw-tip`` (a bold first line) and optionally
``data-hw-tip-desc`` (a second line) shows a tooltip while the pointer is over
it. One script per page serves every such element, so the server registers no
listener for it and a hover makes no round trip. ``add_pin_tooltip`` writes the
attributes; ``add_hover_tip_script`` installs the script.
"""

from __future__ import annotations

from nicegui import ui

#: Attribute holding a hover tip's first line; its presence makes the element a tip trigger.
TIP_ATTR = "data-hw-tip"
#: Attribute holding a hover tip's optional second line.
TIP_DESC_ATTR = "data-hw-tip-desc"

# Quasar's own tooltip classes give the tip QTooltip's look and its z-index (9000).
# Placed as QTooltip places by default: centred below the trigger, flipped above
# when there is no room. Pressing or scrolling hides it, so a pan or a drag never
# carries a tip along.
_SCRIPT = """<script>
(function () {
  if (window.__hwHoverTip) return;
  window.__hwHoverTip = true;
  var tip = null, anchor = null, GAP = 10, MARGIN = 4;
  function box() {
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "q-tooltip q-tooltip--style no-pointer-events text-xs hw-hover-tip";
      tip.setAttribute("role", "tooltip");
      tip.style.display = "none";
      document.body.appendChild(tip);
    }
    return tip;
  }
  function hide() {
    anchor = null;
    if (tip) tip.style.display = "none";
  }
  function show(el) {
    anchor = el;
    var t = box();
    t.replaceChildren();
    var title = document.createElement("div");
    title.className = "text-weight-bold";
    title.textContent = el.getAttribute("data-hw-tip");
    t.appendChild(title);
    var desc = el.getAttribute("data-hw-tip-desc");
    if (desc) {
      var line = document.createElement("div");
      line.textContent = desc;
      t.appendChild(line);
    }
    t.style.display = "block";
    var r = el.getBoundingClientRect(), w = t.offsetWidth, h = t.offsetHeight;
    var left = Math.min(Math.max(MARGIN, r.left + r.width / 2 - w / 2), window.innerWidth - w - MARGIN);
    var top = r.bottom + GAP;
    if (top + h > window.innerHeight - MARGIN) top = Math.max(MARGIN, r.top - GAP - h);
    t.style.left = left + "px";
    t.style.top = top + "px";
  }
  document.addEventListener("pointerover", function (e) {
    var el = e.target && e.target.closest ? e.target.closest("[data-hw-tip]") : null;
    if (el === anchor) return;
    if (el) show(el); else hide();
  }, true);
  document.addEventListener("pointerdown", hide, true);
  document.addEventListener("wheel", hide, { capture: true, passive: true });
})();
</script>"""


def add_hover_tip_script() -> None:
    """Install the hover-tip script on the current page; a second call on the same page does nothing more."""
    ui.add_head_html(_SCRIPT)
