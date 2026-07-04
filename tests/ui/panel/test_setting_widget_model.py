import haywire.core.graph.editor  # noqa: F401

from haywire.core.types import WidgetModel
from haywire.barn.builtin.types import FLOAT
from haywire.ui.panel.setting_widget_model import SettingWidgetModel


def _make_model(initial=1.0):
    """A model bound to its (always-required, ADR 0016) shared cell.

    ``on_edit`` is a plain callback collecting calls — no setter-factory
    indirection (Task 9): the model forwards raw values, it never decides
    write policy (validate/coerce/error-chrome live in the caller's closure).
    """
    edits = []
    cell = FLOAT.create_field(default_override={"value": initial})
    model = SettingWidgetModel(
        field_id="x",
        widget_config={"properties": {"min": 0.0}},
        cell=cell,
        on_edit=edits.append,
    )
    return model, cell, edits


def test_satisfies_widget_model_protocol():
    model, _, _ = _make_model()
    assert isinstance(model, WidgetModel)
    assert model.id == "x"
    assert model.widget_config["properties"]["min"] == 0.0


def test_get_value_reflects_seed():
    model, _, _ = _make_model(2.5)
    assert model.get_value() == 2.5


def test_set_value_forwards_raw_value_to_on_edit_only():
    # Widget -> model writes forward the RAW value to on_edit; the model never
    # writes the cell itself (ADR 0016 — a raw write would bypass whatever
    # write policy on_edit implements: validate/setattr or set_global/save).
    model, cell, edits = _make_model(1.0)
    model.set_value(3.0)
    assert edits == [3.0]
    assert cell.get_value() == 1.0  # model did NOT write the cell
    assert model.get_value() == 1.0  # display follows the CELL, not the edit


def test_get_value_reads_the_cell_live():
    model, cell, edits = _make_model(1.0)
    # A write into the shared cell (descriptor setattr, registry write-through,
    # edge drive) is what get_value() reflects — never on_edit's doing.
    cell.set_value(7.0)
    assert model.get_value() == 7.0
    assert edits == []


def test_data_is_the_provided_cell():
    model, cell, _ = _make_model()
    assert model.data is cell
    assert hasattr(model.data, "on_changed")


def test_set_value_does_not_touch_cell_even_when_on_edit_is_a_noop():
    # If on_edit chooses not to write anywhere (e.g. validation rejects the
    # value), the model must not have already mutated the cell itself.
    model, cell, _ = _make_model(1.0)
    model.set_value(999.0)
    assert cell.get_value() == 1.0
