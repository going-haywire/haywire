"""A one-line path that crops its middle to fit the width it is given.

``fitted_path`` draws one line carrying the path's text and parts; a script in
the browser writes into it the longest rendering that fits, and chooses again
whenever the line is resized or its path changes. A rendering keeps ``a``
leading and ``b`` trailing parts around ``..`` (``a, b >= 1``); the longest
string that fits wins, ties going to more trailing, then more leading parts,
so parts come back one at a time as the line widens. Below one part on each
side come ``../a/b`` and ``../b``; when even ``../b`` does not fit, its start is
cut, so the file name stays. The full path is the line's tooltip.

The stylesheet (``PATH_FIT_CSS``) is part of the studio's ``STATIC_CSS``. The
script is sent once per page by the first line drawn on it; until it runs, a
line shows its full text, cut at the end.
"""

from __future__ import annotations

import json
from pathlib import PurePath, PureWindowsPath

from nicegui import ui

#: Class of a fitted-path line; the script observes every element carrying it.
FIT_CLASS = "hw-path-fit"
#: Attribute the script sets on a line: the kind of rendering, ``full``, ``crop``, ``tail`` or ``text``.
FIT_ATTR = "data-hw-fit"
#: Attribute carrying the line's text: the full path, or plain text.
TEXT_ATTR = "data-hw-text"
#: Attribute carrying a path's parts, as written by ``parts_attr``; absent for plain text.
PARTS_ATTR = "data-hw-parts"


def parts_attr(path: PurePath) -> str:
    """Return ``path`` as the JSON list ``[anchor, separator, *parts]`` the script crops from.

    Example::

        parts_attr(PurePosixPath("/Volumes/data/repo"))  # '["/", "/", "Volumes", "data", "repo"]'
        parts_attr(PurePosixPath("graphs/a.haywire"))    # '["", "/", "graphs", "a.haywire"]'
    """
    sep = "\\" if isinstance(path, PureWindowsPath) else "/"
    anchor = path.anchor
    parts = path.parts[1:] if anchor else path.parts
    return json.dumps([anchor, sep, *parts])


PATH_FIT_CSS = (
    f" .{FIT_CLASS} {{ min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }}"
    # Before the script writes the line, it shows its text, cut at the end.
    f" .{FIT_CLASS}:empty::before {{ content: attr({TEXT_ATTR}); }}"
    # The text stays left-to-right inside a line that cuts its start, so ``../`` keeps its place.
    f" .{FIT_CLASS} > span {{ unicode-bidi: isolate; direction: ltr; }}"
    f" .{FIT_CLASS}[{FIT_ATTR}='tail'] {{ direction: rtl; text-align: left; }}"
)

# One ResizeObserver serves every line on the page. A line's renderings and their
# widths (canvas measureText in the line's font) are cached until its text, parts
# or font change, so a resize only scans the cached widths. The script writes a
# span of its own into the line, which Vue does not render, so a re-render keeps it.
_SCRIPT = """(function () {
  if (!window.hwPathFit) {
    var watched = new Set(), cache = new WeakMap(), widthOf = new WeakMap();
    var ctx = document.createElement("canvas").getContext("2d");
    var rank = function (text, partsJson) {
      if (partsJson === null) return [{ text: text, kind: "text" }];
      var spec = JSON.parse(partsJson), anchor = spec[0], sep = spec[1], p = spec.slice(2), n = p.length;
      var splits = [];
      for (var a = 1; a < n; a++) {
        for (var b = 1; a + b < n; b++) {
          splits.push({ a: a, b: b, text: anchor + p.slice(0, a).concat("..", p.slice(n - b)).join(sep) });
        }
      }
      splits.sort(function (x, y) { return y.text.length - x.text.length || y.b - x.b || y.a - x.a; });
      var out = [{ text: text, kind: "full" }];
      splits.forEach(function (s) { out.push({ text: s.text, kind: "crop" }); });
      if (n > 2) out.push({ text: ["..", p[n - 2], p[n - 1]].join(sep), kind: "crop" });
      if (n > 1) out.push({ text: ".." + sep + p[n - 1], kind: "tail" });
      return out;
    };
    // Reads only: the rendering a line of this width shows.
    var choose = function (el, width) {
      var cs = getComputedStyle(el);
      var font = [cs.fontStyle, cs.fontWeight, cs.fontSize, cs.fontFamily].join(" ");
      var spacing = parseFloat(cs.letterSpacing) || 0;
      var text = el.getAttribute("%(text)s") || "", parts = el.getAttribute("%(parts)s");
      var key = font + "|" + spacing + "|" + text + "|" + parts, entry = cache.get(el);
      if (!entry || entry.key !== key) {
        var ranked = rank(text, parts);
        ctx.font = font;
        entry = { key: key, ranked: ranked, widths: ranked.map(function (r) {
          return ctx.measureText(r.text).width + spacing * r.text.length;
        }) };
        cache.set(el, entry);
      }
      for (var i = 0; i < entry.ranked.length; i++) {
        if (entry.widths[i] <= width + 0.01) return entry.ranked[i];
      }
      return entry.ranked[entry.ranked.length - 1];
    };
    var show = function (el, pick) {
      var span = el.firstElementChild;
      if (!span || span.tagName !== "SPAN") {
        span = document.createElement("span");
        el.replaceChildren(span);
      }
      if (span.textContent !== pick.text) span.textContent = pick.text;
      if (el.getAttribute("%(fit)s") !== pick.kind) el.setAttribute("%(fit)s", pick.kind);
    };
    // Every choice is made before any line is written, so many lines cost one layout.
    var refit = function (els) {
      var picks = [];
      els.forEach(function (el) {
        var width = widthOf.get(el);
        if (width !== undefined && el.isConnected) picks.push([el, choose(el, width)]);
      });
      picks.forEach(function (p) { show(p[0], p[1]); });
    };
    var observer = new ResizeObserver(function (entries) {
      var els = entries.map(function (entry) {
        widthOf.set(entry.target, entry.contentRect.width);
        return entry.target;
      });
      refit(els);
    });
    var adopt = function (el) {
      if (!watched.has(el)) { watched.add(el); observer.observe(el); }
    };
    var prune = function () {
      watched.forEach(function (el) {
        if (!el.isConnected) { observer.unobserve(el); watched.delete(el); }
      });
    };
    var pruneSoon = null;
    // Lines mounted later (a panel shown for the first time, a re-created
    // element) join on arrival; a line whose text or parts change chooses again.
    new MutationObserver(function (records) {
      var changed = new Set();
      records.forEach(function (record) {
        if (record.type === "attributes") { changed.add(record.target); return; }
        record.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          if (node.classList.contains("%(cls)s")) adopt(node);
          Array.prototype.forEach.call(node.getElementsByClassName("%(cls)s"), adopt);
        });
        if (record.removedNodes.length && watched.size && !pruneSoon) {
          pruneSoon = setTimeout(function () { pruneSoon = null; prune(); }, 1000);
        }
      });
      if (changed.size) refit(changed);
    }).observe(document.documentElement, {
      childList: true, subtree: true, attributes: true, attributeFilter: ["%(text)s", "%(parts)s"],
    });
    // A web font that arrives late changes every width.
    if (document.fonts) {
      document.fonts.addEventListener("loadingdone", function () {
        watched.forEach(function (el) { cache.delete(el); });
        refit(watched);
      });
    }
    window.hwPathFit = {
      scan: function () {
        prune();
        document.querySelectorAll(".%(cls)s").forEach(adopt);
      },
    };
  }
  requestAnimationFrame(function () { window.hwPathFit.scan(); });
})();""" % {"fit": FIT_ATTR, "text": TEXT_ATTR, "parts": PARTS_ATTR, "cls": FIT_CLASS}


def ensure_path_fit_script() -> None:
    """Send the path-fit script to the current page, once; later calls on the same page do nothing."""
    client = ui.context.client
    if getattr(client, "_hw_path_fit", False):
        return
    client._hw_path_fit = True  # type: ignore[attr-defined]
    client.run_javascript(_SCRIPT)


class FittedPath(ui.element):
    """One line showing a path, its middle cropped to fit the width the line is given.

    The line keeps as many leading and trailing parts as fit, the file name
    side first, and gives them back one at a time as it widens. It carries no
    text style of its own: chain ``.classes()`` for size, colour and font, and
    give it a width (``w-full``, or ``flex-1`` in a row). Hovering shows the
    full path. ``set_text`` shows plain text instead, uncropped and without a
    tooltip, for a placeholder such as "not saved". Showing what the line
    already shows again changes nothing, so a caller may call either on every
    refresh.

    Example::

        hui.fitted_path(Path("/Volumes/data/projects/haywire/repo")).classes("hw-hint w-full")

        line = hui.fitted_path(text="Untitled").classes("hw-hint font-mono flex-1")
        line.set_path(saved_to)      # later: show the path it was saved to
        line.set_text("not saved")   # or a placeholder again
    """

    def __init__(self, path: PurePath | None = None, *, text: str = "") -> None:
        super().__init__("div")
        self.classes(FIT_CLASS)
        self.path: PurePath | None = None
        ensure_path_fit_script()
        if path is not None:
            self.set_path(path)
        else:
            self.set_text(text)

    def set_path(self, path: PurePath) -> None:
        """Show ``path``, cropped to fit, with the full path as the tooltip."""
        # Assigned rather than passed through props(): a quote in a path would break its parsing.
        self._show({TEXT_ATTR: str(path), PARTS_ATTR: parts_attr(path), "title": str(path)})
        self.path = path

    def set_text(self, text: str) -> None:
        """Show ``text`` as it is, with no tooltip."""
        self._show({TEXT_ATTR: text})
        self.path = None

    def _show(self, props: dict[str, str]) -> None:
        """Set the line's text props to ``props``, dropping the others, unless they are already set."""
        shown = {key: self._props[key] for key in (TEXT_ATTR, PARTS_ATTR, "title") if key in self._props}
        if shown == props:
            return
        for key in shown:
            self._props.pop(key)
        self._props.update(props)


def fitted_path(path: PurePath | None = None, *, text: str = "") -> FittedPath:
    """Draw ``path`` as one line that crops its middle to fit; see ``FittedPath``.

    Args:
        path: The path to show; ``None`` shows ``text`` instead.
        text: Plain text shown, uncropped, when there is no path.
    """
    return FittedPath(path, text=text)
