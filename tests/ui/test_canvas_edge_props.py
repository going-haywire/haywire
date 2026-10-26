"""Canvas props behind edge appearance: the hit padding setting."""

import pytest

from haywire.core.edge.settings import EdgeDefaultSettings
from haywire.ui.components.graph.canvas import _EDGE_SETTING_PROPS

pytestmark = pytest.mark.unit


def test_the_hit_padding_reaches_the_canvas_as_a_prop():
    assert _EDGE_SETTING_PROPS["hit_padding"] == "edge-hit-padding"
    assert EdgeDefaultSettings._settings_descriptors()["hit_padding"]._default == 20
