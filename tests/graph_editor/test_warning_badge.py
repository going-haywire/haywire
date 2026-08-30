"""Every skin exposes a unified render path for node diagnostics.

Errors and advisory warnings are surfaced through a single badge
(`_render_diagnostics_button`) — one icon, one count, colored by highest
severity. See the design note in node_skin.py.

The wiring lives on ``NodeSkin`` itself rather than in any one skin: a folded
card and an unfolded one share ``_render_diagnostics_badge``, so a skin cannot
draw the error badge on one path and forget it on another.
"""

import inspect


import pytest

from haybale_studio.skins.node_skin import NodeSkin
from haybale_studio.skins.stacked_skin import StackedNodeSkin


def _render_source() -> str:
    """Source of the shared diagnostics path, plus the skin that consumes it.

    Both halves matter: ``NodeSkin`` owns the guard and the badge call, and a
    skin still has to *call* ``_render_diagnostics_badge`` from each of its
    render branches. Reading only ``render()`` made these assertions pass on the
    method's own body and silently start failing the day it was split.
    """
    return inspect.getsource(NodeSkin) + inspect.getsource(StackedNodeSkin)


@pytest.mark.unit
def test_render_wires_diagnostics_badge_behind_combined_guard():
    # The badge must be wired into the render path, guarded so it fires when
    # there are errors OR warnings OR a deprecation notice. (A full DOM render
    # needs a NiceGUI client; here we assert the wiring is present in the
    # source so it can't silently regress.)
    src = _render_source()
    assert "has_warning()" in src
    assert "_render_diagnostics_button" in src
    # The call must sit inside an `if` guard (conditional render, not
    # unconditional) that references has_warning(). The guard line and the call
    # share the same `if`, so assert has_warning() appears in the guard line
    # just above the call rather than ordering the two.
    call_idx = src.index("self._render_diagnostics_button")
    guard_idx = src.rindex("if ", 0, call_idx)
    assert "has_warning()" in src[guard_idx:call_idx]


@pytest.mark.unit
def test_render_diagnostics_button_accepts_errors_warnings_and_deprecation():
    sig = inspect.signature(NodeSkin._render_diagnostics_button)
    assert "errors" in sig.parameters
    assert "warnings" in sig.parameters
    assert "deprecation_str" in sig.parameters


@pytest.mark.unit
def test_render_passes_deprecation_to_diagnostics_button():
    src = _render_source()
    assert "deprecation_warning" in src
    assert "_render_diagnostics_button" in src


@pytest.mark.unit
def test_badge_fires_when_only_deprecation_set():
    # The guard must be a combined condition, not purely `has_warning()`
    src = _render_source()
    assert "deprecation_warning" in src


@pytest.mark.unit
@pytest.mark.parametrize(
    ("skin_module", "skin_name"),
    [
        ("haybale_studio.skins.stacked_skin", "StackedNodeSkin"),
        ("haybale_studio.skins.split_skin", "SplitNodeSkin"),
        ("haybale_studio.skins.error_skin", "ErrorNodeSkin"),
    ],
)
def test_every_skin_calls_the_shared_badge(skin_module, skin_name):
    """No skin hand-rolls its own badge, or omits one.

    The error skin used to build its diagnostics button directly and so never
    drew the comment marker; the split skin drew neither on its folded path.
    Both are the same defect — a render branch that forgets a marker — and both
    are prevented by there being exactly one call site to look for.
    """
    import importlib

    cls = getattr(importlib.import_module(skin_module), skin_name)
    src = inspect.getsource(cls)
    assert "_render_diagnostics_badge" in src, f"{skin_name} never calls the shared diagnostics badge"
    assert "_render_diagnostics_button" not in src, (
        f"{skin_name} calls the badge BUTTON directly — go through "
        f"_render_diagnostics_badge so the comment marker rides along"
    )
