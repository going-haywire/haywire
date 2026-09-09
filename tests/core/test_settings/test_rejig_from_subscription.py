"""Dynamic ports driven by a settings field, not a config port's on_change.

`on_change='method'` string dispatch was retired for settings (ADR 0013), so a
node whose port shape depends on a user choice must drive `rejig()` from a
`subscribe_field` callback instead. Nothing else asserts that combination, and
it fails *silently* if it doesn't hold: `subscribe_field`'s adapter catches
callback exceptions and logs them (settings.py), so a `rejig` that blew up
inside the callback would leave the ports stale with no traceback anywhere the
caller can see. Every assertion here is therefore on the resulting port set.
"""

from typing import Any, cast

import pytest

from haywire.core.di.context import get_settings_registry
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, bag, setting
from haywire.barn.builtin.types import BOOL, INT

pytestmark = [pytest.mark.unit, pytest.mark.core]


class _Shape(NodeSettings):
    count = setting[INT](2, label="Count")
    enable_extra = setting[BOOL](False, label="Enable Extra")


@node(
    label="Rejig From Subscription",
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class _RejigFromSettingNode(BaseNode):
    """Port shape driven by two settings fields, both via subscribe_field."""

    shape = bag(_Shape)

    def init(self):
        self.add(BOOL.as_inlet("static_inlet", label="Static"))
        self._build_dynamic()

    def post_init(self):
        self.rebuild_calls = 0
        self.shape._subscribe_field("count", self._on_shape_changed)
        self.shape._subscribe_field("enable_extra", self._on_shape_changed)

    def _on_shape_changed(self, value, old):
        self.rebuild_calls += 1
        with self.rejig(include=r"^(dyn_|extra$)"):
            self._build_dynamic()

    def _build_dynamic(self):
        for i in range(max(0, self.shape.count)):
            self.add(INT.as_inlet(f"dyn_{i}", label=f"Dynamic {i}"))
        if self.shape.enable_extra:
            self.add(BOOL.as_outlet("extra", label="Extra"))


class _StubWrapper:
    """`rejig` is NodeData port machinery and needs no graph — the only thing
    a port rebuild reaches for through the wrapper is the dirty-marking, which
    is counted here so the tests can assert the rebuild was announced."""

    graph = None
    state = None

    def __init__(self):
        self.structural_marks = 0

    def mark_as_structuraly_dirty(self):
        self.structural_marks += 1


@pytest.fixture(autouse=True)
def _needs_registries(library_system):
    """NodeData.__init__ resolves the type + settings registries from DI."""
    get_settings_registry()


def _make_node() -> _RejigFromSettingNode:
    # The node is abstract (no worker) and the wrapper is a stub — both are
    # deliberate: rejig is port machinery and needs neither.
    instance = cast(Any, _RejigFromSettingNode)(node_id="rejig-test", wrapper=_StubWrapper())
    instance.init()
    instance.post_init()
    return instance


def _dyn_ports(instance):
    return sorted(p for p in instance.ports if p.startswith("dyn_"))


def test_initial_ports_come_from_the_setting_default():
    instance = _make_node()
    assert _dyn_ports(instance) == ["dyn_0", "dyn_1"]
    assert "static_inlet" in instance.ports


def test_setting_write_rebuilds_ports_through_rejig():
    """The load-bearing assertion for the settings-first node design."""
    instance = _make_node()

    instance.shape.count = 4

    assert instance.rebuild_calls == 1, "subscribe_field callback did not fire"
    assert _dyn_ports(instance) == ["dyn_0", "dyn_1", "dyn_2", "dyn_3"]


def test_rejig_removes_ports_the_rebuild_no_longer_adds():
    instance = _make_node()

    instance.shape.count = 1

    assert _dyn_ports(instance) == ["dyn_0"]


def test_rejig_leaves_ports_outside_the_include_pattern_alone():
    instance = _make_node()

    instance.shape.count = 0

    assert _dyn_ports(instance) == []
    assert "static_inlet" in instance.ports, "static port was swept up by rejig"


def test_a_second_field_drives_the_same_rebuild():
    """Two subscribe_field registrations on one callback, per its contract."""
    instance = _make_node()
    assert "extra" not in instance.ports

    instance.shape.enable_extra = True

    assert instance.rebuild_calls == 1
    assert "extra" in instance.ports
    assert _dyn_ports(instance) == ["dyn_0", "dyn_1"], "unrelated ports disturbed"


def test_redundant_write_does_not_fire():
    """Cell events are transition-only, so a no-op write must not rebuild."""
    instance = _make_node()

    instance.shape.count = 2  # already the default

    assert instance.rebuild_calls == 0
