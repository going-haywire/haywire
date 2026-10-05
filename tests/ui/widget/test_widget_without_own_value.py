"""A widget on a field that holds no own value refuses edits instead of raising."""

import pytest

from haywire.barn.builtin.types import ADD, FLOAT
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort

from tests.ui.widget._sync_fixtures import _BaseDefaultFloatWidget

pytestmark = pytest.mark.unit


def _port(type_cls) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=PortType.INLET,
    )


def _pooled_port() -> DataPort:
    from haybale_core.types import PooledType

    port = _port(PooledType[FLOAT])
    port.data.set_value(1.5, source_id="e1")
    return port


def test_a_pooled_field_and_an_add_slot_hold_no_own_value():
    assert not _pooled_port().data.accepts_own_value()
    assert not _port(ADD).data.accepts_own_value()
    assert _port(FLOAT).data.accepts_own_value()


def test_a_direct_widget_write_on_a_pooled_port_is_refused(monkeypatch):
    port = _pooled_port()
    widget = _BaseDefaultFloatWidget(port)
    widget.render()

    shown: list[object] = []
    monkeypatch.setattr(widget, "on_model_changed", shown.append)

    widget.set_value(9.0)

    assert port.get_value() == {"e1": 1.5}
    assert shown == [{"e1": 1.5}]


def test_a_view_edit_on_a_pooled_port_is_refused(monkeypatch):
    port = _pooled_port()
    widget = _BaseDefaultFloatWidget(port)
    widget.render()

    binding = widget._bindings[0]
    resynced: list[bool] = []
    monkeypatch.setattr(binding, "sync_to_view", lambda: resynced.append(True))

    binding._sync_to_model(9.0)

    assert port.get_value() == {"e1": 1.5}
    assert resynced == [True]
