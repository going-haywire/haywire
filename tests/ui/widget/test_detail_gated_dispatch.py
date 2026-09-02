"""A widget's model->view push is suppressed while it's CSS-hidden by
NodeDetail (design session, 2026-09): the DOM element exists (CSS filter,
not construction gate) but must not keep paying server->view traffic while
invisible.
"""

from typing import Any, cast

import pytest

from haywire.core.types import NodeDetail
from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import _StandInElement, make_float_port

pytestmark = pytest.mark.unit


class _FakeProps:
    def __init__(self, collapsed: bool, detail: str):
        self.collapsed = collapsed
        self.detail = detail


class _FakeWrapper:
    def __init__(self, props: _FakeProps):
        self.node = type("N", (), {"props": props})()


class _RecordingBinding:
    """Stand-in for a PropertyBinding: records each sync_to_view() call.

    A real binding needs an activated element/converter; this is the minimal
    surface BaseWidget.on_model_changed's default body actually calls, so a
    test can prove whether that body ran its loop or short-circuited.
    """

    def __init__(self):
        self.sync_count = 0

    def sync_to_view(self) -> None:
        self.sync_count += 1


class _RecordingWidget(BaseWidget):
    """Minimal BaseWidget: no real bind(), a fake binding standing in for one
    so ``dispatch_count`` reflects whether the DEFAULT on_model_changed body
    actually ran its sync loop (rather than being skipped by the gate).

    The fake binding is appended AFTER render() (not via bind()), so render()'s
    own activation loop never sees it — this widget tests on_model_changed's
    gate in isolation from binding activation.
    """

    def __init__(self, port):
        super().__init__(port)
        self.fake_binding = _RecordingBinding()

    def build(self) -> Any:
        return _StandInElement()

    def render(self) -> Any:
        el = super().render()
        if self.fake_binding not in self._bindings:
            self._bindings.append(cast(Any, self.fake_binding))
        return el

    @property
    def dispatch_count(self) -> int:
        return self.fake_binding.sync_count


def _widget_with_visibility(detail: str, collapsed: bool = False) -> _RecordingWidget:
    port = make_float_port()
    cast(Any, port)._wrapper = _FakeWrapper(_FakeProps(collapsed, detail))
    return _RecordingWidget(port)


def test_dispatch_is_skipped_when_widget_is_detail_hidden():
    w = _widget_with_visibility(NodeDetail.PINS.value)
    w.render()  # initial sync also gated
    before = w.dispatch_count
    w.port.set_value(5.0)
    assert w.dispatch_count == before, "on_model_changed's default body ran while CSS-hidden"


def test_dispatch_fires_normally_when_widget_is_visible():
    w = _widget_with_visibility(NodeDetail.FULL.value)
    w.render()
    before = w.dispatch_count
    w.port.set_value(5.0)
    assert w.dispatch_count == before + 1


def test_folded_card_also_suppresses_dispatch():
    """Folding is still the stronger gate — a folded card's widgets are
    CSS-hidden regardless of the detail rank underneath."""
    w = _widget_with_visibility(NodeDetail.FULL.value, collapsed=True)
    w.render()
    before = w.dispatch_count
    w.port.set_value(5.0)
    assert w.dispatch_count == before


def test_widgets_with_no_visibility_context_dispatch_normally():
    """A widget built outside a node card (e.g. a settings panel) has no
    NodeDetail concept at all — must default to always-dispatch, never
    silently drop updates."""
    port = make_float_port()  # no _wrapper set — the benchmark/settings-panel case
    w = _RecordingWidget(port)
    w.render()
    before = w.dispatch_count
    w.port.set_value(5.0)
    assert w.dispatch_count == before + 1


def test_is_detail_hidden_false_for_a_bare_port():
    port = make_float_port()
    w = _RecordingWidget(port)
    assert w._is_detail_hidden() is False
