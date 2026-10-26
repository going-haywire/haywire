"""The label hierarchy — heading, section label, subject, hint — comes from ``hui``, not hand-set classes.

Design guide §3.6. A label with a hand-written heading style drifts from the
others the moment one of them changes, which is how five heading styles came to
exist.
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.ui import elements as hui

_REPO = Path(__file__).resolve().parents[2]

# A ui.label styled as a heading or section label by hand. Spans lines, so a
# .classes( call split over several is read whole.
_HAND_HEADING = re.compile(
    r"""ui\.label\((?:[^()]|\([^()]*\))*\)\s*\.classes\(\s*["'][^"']*"""
    r"""\b(uppercase|tracking-wid\w*|font-semibold|text-base|text-lg|text-xl|text-2xl)\b"""
)

# Display and page-title tiers of §3.1, and a demo page that is not app UI.
_ALLOWED = {
    ("packages/haywire-core/src/haywire/ui/app/shell.py", "text-lg"),
    ("packages/haywire-core/src/haywire/ui/components/popup/popup.py", "text-2xl"),
    ("barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py", "text-2xl"),
    ("barn/haybale-studio/haybale_studio/editors/component_docs_editor.py", "text-base"),
}


def _ui_sources() -> list[Path]:
    """Every UI source outside the canvas (skins, node widgets); visiongraph is a symlinked other repo."""
    return [
        path
        for path in (*_REPO.glob("barn/*/*/**/*.py"), *_REPO.glob("packages/*/src/**/*.py"))
        if "haybale-visiongraph" not in path.parts
        and not {"skins", "skin", "widgets"} & set(path.parts)
        and path.name != "elements.py"
    ]


@pytest.mark.unit
def test_no_ui_code_styles_a_heading_by_hand() -> None:
    hits = []
    for path in _ui_sources():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(_REPO).as_posix()
        for match in _HAND_HEADING.finditer(text):
            if (rel, match.group(1)) in _ALLOWED:
                continue
            hits.append(f"{rel}:{text.count(chr(10), 0, match.start()) + 1} ({match.group(1)})")

    assert not hits, f"hand-styled heading, use hui.heading / hui.section_label: {hits}"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


@pytest.mark.unit
@pytest.mark.anyio
async def test_each_label_tier_carries_its_class(user: User) -> None:
    built: dict[str, ui.element] = {}
    labels: dict[str, ui.label] = {}

    @ui.page("/")
    def page() -> None:
        built["heading"] = hui.heading("Review")
        built["section"] = labels["section"] = hui.section_label("Version")
        built["subject"] = hui.subject("numpy-tools", mono=True, tone="--hw-positive")
        built["hint"] = hui.hint("Nothing is written yet.")
        built["indented"] = hui.indented()
        with hui.box() as box:
            built["box"] = box

    await user.open("/")

    assert "hw-heading" in built["heading"].classes
    assert "hw-section-label" in built["section"].classes
    assert labels["section"].text == "Version"  # CSS uppercases it; the text stays readable
    assert {"hw-subject", "font-mono"} <= set(built["subject"].classes)
    assert built["subject"].style["color"] == "var(--hw-positive) !important"
    assert "hw-hint" in built["hint"].classes
    assert "hw-indented" in built["indented"].classes
    assert "hw-box" in built["box"].classes
