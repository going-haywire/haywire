"""The path-fit script shows the longest split of a path that fits its line, and chooses again on change.

The rule is restated here, independently of the script: every split keeps ``a`` leading and
``b`` trailing parts around ``..`` (``a, b >= 1``, ``a + b < n``); the longest string that fits
wins, ties going to more trailing, then more leading parts. Below ``1 + 1`` come ``../a/b`` and
``../b``, the last cutting its start so the file name stays.
"""

from __future__ import annotations

from html import escape
from pathlib import PurePath, PurePosixPath, PureWindowsPath

import pytest
from playwright.sync_api import Page

from haywire.ui.elements.path_fit import (
    _SCRIPT,
    FIT_ATTR,
    FIT_CLASS,
    PARTS_ATTR,
    PATH_FIT_CSS,
    TEXT_ATTR,
    parts_attr,
)

pytestmark = pytest.mark.browser

_LONG = PurePosixPath(
    "/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/barn/haybale-core/nodes/graph_node.py"
)
_MONO = "font: 12px monospace; height: 16px"
_SANS = "font: 13px sans-serif; height: 18px"
# A measured width this close to the line's width is a tie the test cannot call either way.
_SLACK = 1.0


def _ranked(path: PurePath) -> list[tuple[str, str]]:
    """Return ``(rendering, kind)`` for ``path`` in the order the rule prefers them."""
    sep = "\\" if isinstance(path, PureWindowsPath) else "/"
    anchor = path.anchor
    parts = list(path.parts[1:] if anchor else path.parts)
    n = len(parts)
    splits = [
        (anchor + sep.join([*parts[:a], "..", *parts[n - b :]]), a, b)
        for a in range(1, n)
        for b in range(1, n - a)
    ]
    splits.sort(key=lambda s: (-len(s[0]), -s[2], -s[1]))
    ranked = [(str(path), "full")] + [(s[0], "crop") for s in splits]
    if n > 2:
        ranked.append((sep.join(["..", *parts[-2:]]), "crop"))
    if n > 1:
        ranked.append((sep.join(["..", parts[-1]]), "tail"))
    return ranked


def _line(line_id: str, path: PurePath, style: str, width: int) -> str:
    return (
        f'<div id="{line_id}" class="{FIT_CLASS}" style="{style}; width: {width}px"'
        f' {TEXT_ATTR}="{escape(str(path))}" {PARTS_ATTR}="{escape(parts_attr(path))}"></div>'
    )


def _install(page: Page, body: str) -> None:
    page.set_content(f"<html><head><style>{PATH_FIT_CSS}</style></head><body>{body}</body></html>")
    page.evaluate(_SCRIPT)


def _settle(page: Page) -> None:
    # A ResizeObserver runs before the paint after a layout; two frames later it has run.
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def _shown(page: Page, line_id: str) -> tuple[str, str | None]:
    return tuple(
        page.evaluate(
            f"() => {{ const l = document.querySelector('#{line_id}');"
            f" return [l.textContent, l.getAttribute('{FIT_ATTR}')]; }}"
        )
    )


def _sweep(page: Page, line_id: str, widths: list[int], texts: list[str]) -> dict:
    """Resize the line through ``widths``; return what it showed at each and every text's DOM width."""
    return page.evaluate(
        """async ([id, widths, texts]) => {
            const line = document.querySelector('#' + id);
            const probe = document.createElement('span');
            probe.style.cssText = 'position:absolute; visibility:hidden; white-space:pre; font:inherit';
            document.body.appendChild(probe);
            probe.style.font = getComputedStyle(line).font
                || [getComputedStyle(line).fontStyle, getComputedStyle(line).fontWeight,
                    getComputedStyle(line).fontSize, getComputedStyle(line).fontFamily].join(' ');
            const measured = {};
            for (const t of texts) {
                probe.textContent = t;
                measured[t] = probe.getBoundingClientRect().width;
            }
            probe.remove();
            const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
            const shown = [];
            for (const w of widths) {
                line.style.width = w + 'px';
                await frame();
                shown.push([w, line.clientWidth, line.textContent, line.getAttribute('data-hw-fit')]);
            }
            return {measured, shown};
        }""",
        [line_id, widths, texts],
    )


def _assert_rule(ranked: list[tuple[str, str]], sweep: dict) -> list[int]:
    """Assert the longest-fit rule at each width; return the rank shown at each."""
    measured = sweep["measured"]
    texts = [t for t, _ in ranked]
    ranks = []
    for width, client, text, kind in sweep["shown"]:
        assert text in texts, (width, text)
        rank = texts.index(text)
        assert kind == ranked[rank][1], (width, text, kind)
        ranks.append(rank)
        if rank < len(ranked) - 1:
            assert measured[text] <= client + _SLACK, (width, text, measured[text])
        # Nothing the rule prefers fits clearly.
        better = [t for t in texts[:rank] if measured[t] <= client - _SLACK]
        assert not better, (width, text, better)
    return ranks


_PATHS = [
    _LONG,
    PurePosixPath("graphs/sub/dir/deeper/still/foo.haywire"),
    PureWindowsPath("C:/Users/me/projects/haywire/haywire-repo/graphs/foo.haywire"),
    PurePosixPath("/" + "/".join(f"dir{i:02d}" for i in range(22)) + "/leaf.py"),
]


@pytest.mark.parametrize("style", [_MONO, _SANS], ids=["mono", "sans"])
@pytest.mark.parametrize("path", _PATHS, ids=["long", "relative", "windows", "very-long"])
def test_the_line_shows_the_longest_split_that_fits_as_it_grows(
    page: Page, path: PurePath, style: str
) -> None:
    ranked = _ranked(path)
    _install(page, _line("p", path, style, 40))
    widths = list(range(40, 1400, 15))
    ranks = _assert_rule(ranked, _sweep(page, "p", widths, [t for t, _ in ranked]))
    # Parts come back one at a time: the shown rank never worsens as the line grows ...
    assert ranks == sorted(ranks, reverse=True)
    # ... the ends of the sweep are the start-cut tail and the full path ...
    assert ranks[0] == len(ranked) - 1
    assert ranks[-1] == 0
    # ... and many splits between them get their turn, not just two.
    assert len(set(ranks)) >= 6


def test_intermediate_splits_of_a_deep_path_appear(page: Page) -> None:
    _install(page, _line("p", _LONG, _MONO, 40))
    sweep = _sweep(page, "p", list(range(150, 700, 7)), [])
    shown = {text for _, _, text, _ in sweep["shown"]}
    # Steps of 7 px are finer than a 12px monospace character, so every split length gets its turn.
    assert "/Volumes/Ddrive/../haybale-core/nodes/graph_node.py" in shown
    assert "/Volumes/../barn/haybale-core/nodes/graph_node.py" in shown
    assert "/Volumes/Ddrive/../nodes/graph_node.py" in shown


def test_the_tail_keeps_the_file_name_when_even_it_is_too_narrow(page: Page) -> None:
    path = PurePosixPath("graphs/foo.haywire")
    _install(page, _line("n", path, _MONO, 50))
    _settle(page)
    assert _shown(page, "n") == ("../foo.haywire", "tail")
    shown = page.evaluate(
        """() => {
          const line = document.querySelector('#n');
          const text = line.firstElementChild.firstChild, s = text.data;
          const rect = (i) => { const r = document.createRange(); r.setStart(text, i); r.setEnd(text, i + 1);
                                return r.getBoundingClientRect(); };
          const host = line.getBoundingClientRect();
          return {
            tailRight: rect(s.length - 1).right, hostRight: host.right, hostLeft: host.left,
            firstLeft: rect(0).left, dotLeft: rect(1).left, fLeft: rect(3).left,
            overflow: getComputedStyle(line).textOverflow,
          };
        }"""
    )
    # The end of the name sits inside the line, the start is what is cut, and "../" still reads first.
    assert shown["tailRight"] <= shown["hostRight"] + 1
    assert shown["firstLeft"] < shown["hostLeft"]
    assert shown["dotLeft"] < shown["fLeft"]
    assert shown["overflow"] == "ellipsis"


def test_no_direction_marks_reach_the_copied_text(page: Page) -> None:
    _install(page, _line("n", PurePosixPath("graphs/foo.haywire"), _MONO, 50))
    _settle(page)
    text = page.evaluate(
        "() => { const l = document.querySelector('#n'); const r = document.createRange();"
        " r.selectNodeContents(l); getSelection().removeAllRanges(); getSelection().addRange(r);"
        " return getSelection().toString(); }"
    )
    assert text == "../foo.haywire"


def test_a_resized_line_chooses_again(page: Page) -> None:
    _install(page, _line("p", _LONG, _MONO, 900))
    _settle(page)
    assert _shown(page, "p") == (str(_LONG), "full")
    page.evaluate("() => { document.querySelector('#p').style.width = '200px'; }")
    _settle(page)
    assert _shown(page, "p")[1] == "crop"
    page.evaluate("() => { document.querySelector('#p').style.width = '900px'; }")
    _settle(page)
    assert _shown(page, "p") == (str(_LONG), "full")


def test_a_line_whose_path_changes_chooses_again(page: Page) -> None:
    _install(page, _line("p", _LONG, _MONO, 200))
    _settle(page)
    assert _shown(page, "p")[1] == "crop"
    other = PurePosixPath("/short/one.py")
    page.evaluate(
        f"([text, parts]) => {{ const l = document.querySelector('#p');"
        f" l.setAttribute('{TEXT_ATTR}', text); l.setAttribute('{PARTS_ATTR}', parts); }}",
        [str(other), parts_attr(other)],
    )
    _settle(page)
    assert _shown(page, "p") == ("/short/one.py", "full")


def test_plain_text_is_shown_as_it_is(page: Page) -> None:
    _install(
        page,
        f'<div id="t" class="{FIT_CLASS}" style="{_MONO}; width: 40px" {TEXT_ATTR}="not saved yet"></div>',
    )
    _settle(page)
    assert _shown(page, "t") == ("not saved yet", "text")
    assert page.evaluate("() => getComputedStyle(document.querySelector('#t')).textOverflow") == "ellipsis"


def test_a_line_mounted_after_install_is_fitted_without_another_scan(page: Page) -> None:
    _install(page, _line("p", _LONG, _MONO, 900))
    _settle(page)
    # No second install: a panel mounting later is picked up, also nested in a wrapper.
    page.evaluate(
        "html => document.body.insertAdjacentHTML('beforeend', html)",
        "<section>" + _line("late", _LONG, _MONO, 200) + "</section>",
    )
    _settle(page)
    assert _shown(page, "late")[1] == "crop"


def test_a_second_install_keeps_lines_fitted(page: Page) -> None:
    _install(page, _line("p", _LONG, _MONO, 900))
    _settle(page)
    page.evaluate(
        "html => document.body.insertAdjacentHTML('beforeend', html)", _line("late", _LONG, _MONO, 200)
    )
    page.evaluate(_SCRIPT)
    _settle(page)
    assert _shown(page, "late")[1] == "crop"
    assert _shown(page, "p") == (str(_LONG), "full")
