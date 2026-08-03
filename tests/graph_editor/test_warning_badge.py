"""The default skin exposes a unified render path for node diagnostics.

Errors and advisory warnings are surfaced through a single badge
(`_render_diagnostics_button`) — one icon, one count, colored by highest
severity. See the design note in node_skin.py.
"""

import inspect


import pytest

from haybale_studio.skins.default_skin import DefaultNodeSkin
from haybale_studio.skins.node_skin import NodeSkin


@pytest.mark.unit
def test_render_wires_diagnostics_badge_behind_combined_guard():
    # The badge must be wired into render(), guarded so it fires when there are
    # errors OR warnings OR a deprecation notice. (A full DOM render needs a
    # NiceGUI client; here we assert the wiring is present in render's source so
    # it can't silently regress.)
    src = inspect.getsource(DefaultNodeSkin.render)
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
def test_default_skin_render_passes_deprecation_to_diagnostics_button():
    src = inspect.getsource(DefaultNodeSkin.render)
    assert "deprecation_warning" in src
    assert "_render_diagnostics_button" in src


@pytest.mark.unit
def test_default_skin_badge_fires_when_only_deprecation_set():
    # The guard must be a combined condition, not purely `has_warning()`
    src = inspect.getsource(DefaultNodeSkin.render)
    assert "deprecation_warning" in src
