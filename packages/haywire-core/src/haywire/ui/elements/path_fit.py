"""A one-line path that crops its middle to fit the width it is given.

``crop_candidates`` builds the renderings of a path, longest first;
``fitted_path`` draws them all into one line, and a script in the browser shows
the first that fits, choosing again whenever the line is resized or its
renderings change. The full path is the line's tooltip. When even the shortest
rendering does not fit, it ends in an ellipsis.

The stylesheet (``PATH_FIT_CSS``) is part of the studio's ``STATIC_CSS``; a page
built without it shows every rendering stacked. The script is sent once per
page by the first line drawn on it.
"""

from __future__ import annotations

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
PATH_FIT_CSS = (
    f" .{FIT_CLASS} {{ position: relative; min-width: 0; overflow: hidden; white-space: nowrap; }}"
    f" .{FIT_CLASS} > * {{ position: absolute; left: 0; top: 0; visibility: hidden; white-space: nowrap; }}"
    # The last of several renderings cuts its start, so the file name stays; text-align keeps it left.
    f" .{FIT_CLASS} > :last-child:not(:first-child) {{ direction: rtl; text-align: left; }}"
    f" .{FIT_CLASS}:not([{FIT_ATTR}]) > :first-child,"
    + ",".join(f" .{FIT_CLASS}[{FIT_ATTR}='{i}'] > :nth-child({i + 1})" for i in range(MAX_CANDIDATES))
    + " { position: static; visibility: visible; overflow: hidden; text-overflow: ellipsis; }"
)

# One ResizeObserver serves every line on the page. The fit writes only the line's
# own attribute, which Vue does not render, so a re-render keeps the choice.
_SCRIPT = """(function () {
  if (!window.hwPathFit) {
    var watched = new Set();
    var fit = function (el) {
      var width = el.clientWidth;
      if (!width) return;
      var kids = el.children, pick = kids.length - 1;
      for (var i = 0; i < kids.length; i++) {
        if (kids[i].scrollWidth <= width) { pick = i; break; }
      }
      var value = String(pick);
      if (el.getAttribute("%(attr)s") !== value) el.setAttribute("%(attr)s", value);
    };
    var observer = new ResizeObserver(function (entries) {
      entries.forEach(function (entry) { fit(entry.target); });
    });
    var adopt = function (el) {
      if (!watched.has(el)) { watched.add(el); observer.observe(el); }
      fit(el);
    };
    var prune = function () {
      watched.forEach(function (el) {
        if (!el.isConnected) { observer.unobserve(el); watched.delete(el); }
      });
    };
    var pruneSoon = null;
    // Lines mounted later (a panel shown for the first time, a re-created
    // element) join on arrival, and a line whose renderings were replaced
    // chooses again; only the added subtrees are queried.
    new MutationObserver(function (records) {
      records.forEach(function (record) {
        var target = record.target;
        if (target.nodeType === 1 && target.classList.contains("%(cls)s")) adopt(target);
        record.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          if (node.classList.contains("%(cls)s")) adopt(node);
          Array.prototype.forEach.call(node.getElementsByClassName("%(cls)s"), adopt);
        });
        if (record.removedNodes.length && watched.size && !pruneSoon) {
          pruneSoon = setTimeout(function () { pruneSoon = null; prune(); }, 1000);
        }
      });
    }).observe(document.documentElement, { childList: true, subtree: true });
    window.hwPathFit = {
      scan: function () {
        prune();
        document.querySelectorAll(".%(cls)s").forEach(adopt);
      },
    };
  }
  requestAnimationFrame(function () { window.hwPathFit.scan(); });
})();""" % {"attr": FIT_ATTR, "cls": FIT_CLASS}


def ensure_path_fit_script() -> None:
    """Send the path-fit script to the current page, once; later calls on the same page do nothing."""
    client = ui.context.client
    if getattr(client, "_hw_path_fit", False):
        return
    client._hw_path_fit = True  # type: ignore[attr-defined]
    client.run_javascript(_SCRIPT)


class FittedPath(ui.element):
    """One line showing a path, its middle cropped to fit the width the line is given.

    The line carries no text style of its own: chain ``.classes()`` for size,
    colour and font, and give it a width (``w-full``, or ``flex-1`` in a row).
    Hovering shows the full path. ``set_text`` shows plain text instead, uncropped
    and without a tooltip, for a placeholder such as "not saved". Showing what
    the line already shows again changes nothing, so a caller may call either
    on every refresh.

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
        self._renderings: list[str] = []
        ensure_path_fit_script()
        if path is not None:
            self.set_path(path)
        else:
            self.set_text(text)

    def set_path(self, path: PurePath) -> None:
        """Show ``path``, cropped to fit, with the full path as the tooltip."""
        if self._show(crop_candidates(path)) or self.path != path:
            # Assigned rather than passed through props(): a quote in a path would break its parsing.
            self._props["title"] = str(path)
            self.update()
        self.path = path

    def set_text(self, text: str) -> None:
        """Show ``text`` as it is, with no tooltip."""
        if self._show([text]) or self.path is not None:
            self._props.pop("title", None)
            self.update()
        self.path = None

    def _show(self, renderings: list[str]) -> bool:
        """Draw ``renderings`` unless they are already drawn; return whether they were drawn."""
        if renderings == self._renderings:
            return False
        self._renderings = renderings
        self.clear()
        with self:
            for i, rendering in enumerate(renderings):
                # Left-to-right marks keep a leading ``..`` in order inside the right-to-left last rendering.
                last_of_many = len(renderings) > 1 and i == len(renderings) - 1
                ui.label(f"\u200e{rendering}\u200e" if last_of_many else rendering)
        return True


def fitted_path(path: PurePath | None = None, *, text: str = "") -> FittedPath:
    """Draw ``path`` as one line that crops its middle to fit; see ``FittedPath``.

    Args:
        path: The path to show; ``None`` shows ``text`` instead.
        text: Plain text shown, uncropped, when there is no path.
    """
    return FittedPath(path, text=text)
