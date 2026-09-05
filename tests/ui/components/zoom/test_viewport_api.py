"""``ZoomPanContainer.get_viewport()`` — the read side of a future persisted viewport.

The load-bearing part is the ``None``. Python learns the viewport only when the
client reports one, and the value it would otherwise have to invent (zoom 1.0 at
pan 0,0) is a place the content usually is NOT. Persisting that for a graph no
canvas ever mounted would, on restore, drop the user into empty space — so "not
known yet" has to stay distinguishable from a real reading.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from nicegui import events

from haywire.ui.components.zoom.pan import Viewport, ZoomPanContainer

pytestmark = pytest.mark.unit

# Lazily-captured persistent NiceGUI default client. Mirrors the fixture of the
# same name in tests/ui/skin/conftest.py — kept local because conftest fixtures
# do not cross sibling directories.
_CLIENT: list = []


def _noop_page() -> None:  # registration target for a headless Client
    pass


@pytest.fixture
def nicegui_slot_context():
    """Keep a valid NiceGUI default slot active for the test body."""
    from nicegui import Client

    if not _CLIENT:
        _CLIENT.append(Client(cast(Any, _noop_page), request=None))
    with _CLIENT[0]:
        yield


@pytest.fixture
def container(nicegui_slot_context) -> ZoomPanContainer:
    return ZoomPanContainer(initial_zoom=1.0)


def _report(container: ZoomPanContainer, zoom, pan_x, pan_y) -> None:
    """Deliver a `transform-changed` exactly as the Vue side would."""
    container._handle_transform_changed(
        events.GenericEventArguments(
            sender=container,
            client=container.client,
            args={"zoom": zoom, "panX": pan_x, "panY": pan_y},
        )
    )


def test_viewport_is_unknown_until_the_client_reports(container):
    """Not 'zoom 1.0 at the origin' — unknown. See this module's docstring."""
    assert container.get_viewport() is None


def test_viewport_reflects_what_the_client_reported(container):
    _report(container, 0.0694, 44.2, -135.5)
    assert container.get_viewport() == Viewport(zoom=0.0694, pan_x=44.2, pan_y=-135.5)


def test_latest_report_wins(container):
    _report(container, 0.5, 10.0, 20.0)
    _report(container, 2.0, -30.0, -40.0)
    assert container.get_viewport() == Viewport(zoom=2.0, pan_x=-30.0, pan_y=-40.0)


def test_values_are_floats_even_when_the_client_sends_ints(container):
    """JSON gives back ints for whole numbers; a viewport is continuous."""
    _report(container, 1, 0, 0)
    vp = container.get_viewport()
    assert vp is not None
    assert isinstance(vp.zoom, float)
    assert isinstance(vp.pan_x, float)
    assert isinstance(vp.pan_y, float)


def test_a_malformed_report_leaves_the_last_good_viewport(container):
    """The handler swallows errors; it must not blank a known-good reading."""
    _report(container, 0.5, 10.0, 20.0)
    container._handle_transform_changed(
        events.GenericEventArguments(sender=container, client=container.client, args={})
    )
    assert container.get_viewport() == Viewport(zoom=0.5, pan_x=10.0, pan_y=20.0)
