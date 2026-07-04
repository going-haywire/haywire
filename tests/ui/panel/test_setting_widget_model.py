import haywire.core.graph.editor  # noqa: F401

from haywire.core.types import WidgetModel
from haywire.barn.builtin.types import FLOAT
from haywire.ui.panel.setting_widget_model import SettingWidgetModel


def _make_model(initial=1.0):
    """A model bound to its (always-required, ADR 0016) shared cell."""
    written = []

    def make_setter(coerce):
        def handler(e):
            written.append(coerce(e.value))

        return handler

    cell = FLOAT.create_field(default_override={"value": initial})
    model = SettingWidgetModel(
        field_id="x",
        itype=FLOAT,
        value=initial,
        widget_config={"properties": {"min": 0.0}},
        make_setter=make_setter,
        field=cell,
    )
    return model, written


def test_satisfies_widget_model_protocol():
    model, _ = _make_model()
    assert isinstance(model, WidgetModel)
    assert model.id == "x"
    assert model.widget_config["properties"]["min"] == 0.0


def test_get_value_reflects_seed():
    model, _ = _make_model(2.5)
    assert model.get_value() == 2.5


def test_set_value_forwards_to_setter_only():
    # Widget -> model writes route through the setter (descriptor/registry);
    # the shared cell is written by that path, never raw by the model
    # (ADR 0016 — a raw write would bypass set-or-unset bookkeeping).
    model, written = _make_model(1.0)
    model.set_value(3.0)
    assert written == [3.0]
    assert model.get_value() == 1.0  # display follows the CELL, not the widget


def test_apply_external_updates_field_without_setter():
    model, written = _make_model(1.0)
    model.apply_external(9.0)
    assert model.get_value() == 9.0
    assert written == []  # external apply must NOT re-fire the setter


def test_data_is_a_datafield_with_on_changed():
    model, _ = _make_model()
    assert hasattr(model.data, "on_changed")


# ---------------------------------------------------------------------------
# Task 8: bind to the shared cell for display; write through the setter
# ---------------------------------------------------------------------------


def _make_shared_model(initial=1.0):
    """A model backed by a PROVIDED cell (the bag's shared DataField)."""
    written = []

    def make_setter(coerce):
        def handler(e):
            written.append(coerce(e.value))

        return handler

    cell = FLOAT.create_field(default_override={"value": initial})
    model = SettingWidgetModel(
        field_id="x",
        itype=FLOAT,
        value=initial,
        widget_config={},
        make_setter=make_setter,
        field=cell,
    )
    return model, cell, written


def test_provided_cell_is_used_by_reference():
    model, cell, _ = _make_shared_model(1.0)
    # No throwaway field — the model reads/writes the shared cell.
    assert model.data is cell


def test_registry_sync_into_cell_is_reflected_in_display():
    model, cell, written = _make_shared_model(1.0)
    # A registry/edge sync writes the shared cell directly (not via the widget).
    cell.set_value(7.0)
    assert model.get_value() == 7.0
    # apply_external (the panel's sync hook) refreshes display without re-firing
    # the setter.
    model.apply_external(cell.get_value())
    assert written == []


def test_no_reentrancy_loop_on_equal_value():
    model, cell, written = _make_shared_model(1.0)
    # A registry sync → cell.set_value → apply_external must no-op on equal value
    # (no re-entry into the setter).
    cell.set_value(4.0)
    model.apply_external(4.0)
    model.apply_external(4.0)  # idempotent
    assert written == []
