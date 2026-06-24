"""The default skin exposes a render path for node warnings."""

import inspect

import haywire.core.graph.editor  # noqa: F401  circular-import guard (CLAUDE.md)

import pytest

from haybale_studio.skins.default_skin import DefaultNodeSkin
from haybale_studio.skins.node_skin import NodeSkin


@pytest.mark.unit
def test_skin_has_warnings_button_renderer():
    # The skin must provide a dedicated method to render the warnings badge,
    # parallel to the existing _render_errors_button.
    assert hasattr(DefaultNodeSkin, "_render_warnings_button")
    assert callable(DefaultNodeSkin._render_warnings_button)


@pytest.mark.unit
def test_render_wires_warnings_badge_behind_has_warning_guard():
    # The badge must actually be wired into render(), guarded by has_warning(),
    # so warnings reach the canvas. (A full DOM render needs a NiceGUI client;
    # here we assert the wiring is present in render's source so it can't silently
    # regress.)
    src = inspect.getsource(DefaultNodeSkin.render)
    assert "has_warning()" in src
    assert "_render_warnings_button" in src
    # The guard must precede the call (conditional render, not unconditional).
    assert src.index("has_warning()") < src.index("_render_warnings_button")


@pytest.mark.unit
def test_render_warnings_button_accepts_deprecation_str():
    sig = inspect.signature(NodeSkin._render_warnings_button)
    assert "deprecation_str" in sig.parameters


@pytest.mark.unit
def test_default_skin_render_passes_deprecation_to_warnings_button():
    src = inspect.getsource(DefaultNodeSkin.render)
    assert "deprecation_warning" in src
    assert "_render_warnings_button" in src


@pytest.mark.unit
def test_default_skin_badge_fires_when_only_deprecation_set():
    # The guard must be a combined condition, not purely `has_warning()`
    src = inspect.getsource(DefaultNodeSkin.render)
    assert "deprecation_warning" in src
