"""A one-line path that crops its middle to fit the width it is given.

``crop_candidates`` builds the renderings of a path, longest first;
``fitted_path`` draws them all into one line, and a script in the browser shows
the first that fits, choosing again whenever the line is resized. The full path
is the line's tooltip. When even the shortest rendering does not fit, it ends
in an ellipsis.
"""

from __future__ import annotations

import json
from pathlib import PurePath, PureWindowsPath

from nicegui import ui

#: Class of a fitted-path line; the script observes every element carrying it.
FIT_CLASS = "hw-path-fit"
#: Attribute the script sets on a line: the index of the rendering it shows.
FIT_ATTR = "data-hw-fit"
#: Most renderings ``crop_candidates`` returns; the CSS has one selector per index.
MAX_CANDIDATES = 5


def crop_candidates(path: PurePath) -> list[str]:
    """Return renderings of ``path``, longest first, each hiding more of its middle.

    The order is: the full path; its two leading and two trailing parts around
    ``..``; one leading and one trailing part; ``..`` and the last two parts;
    ``..`` and the last part. A rendering that would hide nothing is left out.

    Example::

        crop_candidates(PurePosixPath("/Volumes/Ddrive/06_tool/haywire/haywire-repo"))
        # ["/Volumes/Ddrive/06_tool/haywire/haywire-repo",
        #  "/Volumes/Ddrive/../haywire/haywire-repo",
        #  "/Volumes/../haywire-repo",
        #  "../haywire/haywire-repo",
        #  "../haywire-repo"]
    """
    sep = "\\" if isinstance(path, PureWindowsPath) else "/"
    anchor = path.anchor
    parts = list(path.parts[1:] if anchor else path.parts)
    candidates = [str(path)]

    def around(lead: int, trail: int) -> None:
        if len(parts) > lead + trail:
            candidates.append(anchor + sep.join([*parts[:lead], "..", *parts[-trail:]]))

    def tail(trail: int) -> None:
        if len(parts) > trail:
            candidates.append(sep.join(["..", *parts[-trail:]]))

    around(2, 2)
    around(1, 1)
    tail(2)
    tail(1)
    return candidates


# Every rendering but the chosen one is lifted out of the flow and hidden, so it
# still has its natural width for the script to measure.
_CSS = (
    f".{FIT_CLASS} > * {{ position: absolute; left: 0; top: 0; visibility: hidden; white-space: nowrap; }}"
    f" .{FIT_CLASS}:not([{FIT_ATTR}]) > :first-child,"
    + ",".join(f" .{FIT_CLASS}[{FIT_ATTR}='{i}'] > :nth-child({i + 1})" for i in range(MAX_CANDIDATES))
    + " { position: static; visibility: visible; overflow: hidden; text-overflow: ellipsis; }"
)

# One ResizeObserver serves every line on the page. The fit writes only the line's
# own attribute, which Vue does not render, so a re-render keeps the choice.
_SCRIPT = """(function () {
  if (!window.hwPathFit) {
    var style = document.createElement("style");
    style.textContent = %s;
    document.head.appendChild(style);
    var watched = new Set();
    var fit = function (el) {
      var width = el.clientWidth;
      if (!width) return;
      var kids = el.children, pick = kids.length - 1;
      for (var i = 0; i < kids.length; i++) {
        if (kids[i].scrollWidth <= width) { pick = i; break; }
      }
      var value = String(pick);
      if (el.getAttribute("%s") !== value) el.setAttribute("%s", value);
    };
    var observer = new ResizeObserver(function (entries) {
      entries.forEach(function (entry) { fit(entry.target); });
    });
    var adopt = function (el) {
      if (!watched.has(el)) { watched.add(el); observer.observe(el); }
      fit(el);
    };
    // Lines mounted after the script ran (a panel shown for the first time, a
    // re-created element) join on arrival; only the added subtrees are queried.
    new MutationObserver(function (records) {
      records.forEach(function (record) {
        record.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          if (node.matches(".%s")) adopt(node);
          node.querySelectorAll(".%s").forEach(adopt);
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
    window.hwPathFit = {
      scan: function () {
        watched.forEach(function (el) {
          if (!el.isConnected) { observer.unobserve(el); watched.delete(el); }
        });
        document.querySelectorAll(".%s").forEach(adopt);
      },
    };
  }
  requestAnimationFrame(function () { window.hwPathFit.scan(); });
})();""" % (json.dumps(_CSS), FIT_ATTR, FIT_ATTR, FIT_CLASS, FIT_CLASS, FIT_CLASS)


def fitted_path(path: PurePath) -> ui.element:
    """Draw ``path`` as one line of small muted text that crops its middle to fit.

    Call ``install_path_fit`` after drawing the lines; until it runs, the line
    shows the full path cut off with an ellipsis.
    """
    with ui.element("div").classes(
        f"{FIT_CLASS} relative w-full min-w-0 h-4 leading-4 overflow-hidden whitespace-nowrap"
        " text-xs hw-text-muted"
    ) as line:
        for candidate in crop_candidates(path):
            ui.label(candidate)
    line._props["title"] = str(path)
    return line


def install_path_fit() -> None:
    """Fit every path line on the current page now and whenever one is resized.

    Installs the script once per page; each later call fits the lines drawn since.
    """
    ui.run_javascript(_SCRIPT)
