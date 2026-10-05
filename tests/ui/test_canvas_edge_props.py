"""Canvas props behind edge appearance: the hit padding setting."""

import pytest

from haywire.ui.components.graph.canvas import _CANVAS_SETTING_PROPS
from haywire.ui.components.graph.settings import CanvasSettings

pytestmark = pytest.mark.unit


def test_the_hit_padding_reaches_the_canvas_as_a_prop():
    assert _CANVAS_SETTING_PROPS["edge_hit_padding"] == "edge-hit-padding"
    assert CanvasSettings._settings_descriptors()["edge_hit_padding"]._default == 8
