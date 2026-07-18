"""DataField.on_changed fires a FieldChange payload (value, old, field_id).

Increment 1 of the cell-authoritative settings design (ADR 0016): the cell
becomes the one change primitive, so its event must carry the old value and
the field's identity — the (name, value, old) contract bag.subscribe promises
rides on this payload.
"""

from haywire.barn.builtin.types import FLOAT
from haywire.core.types.fields import FieldChange


def _make_field(seed: float):
    return FLOAT.create_field(default_override={"value": seed})


def test_on_changed_delivers_field_change_with_old_value():
    cell = _make_field(1.0)
    seen: list[FieldChange] = []
    cell.on_changed.append(seen.append)

    cell.set_value(2.0)

    assert len(seen) == 1
    change = seen[0]
    assert isinstance(change, FieldChange)
    assert change.value == 2.0
    assert change.old == 1.0


def test_field_id_defaults_empty_and_is_stampable():
    cell = _make_field(0.5)
    assert cell.field_id == ""

    cell.field_id = "ns.node.cfg.threshold"
    seen: list[FieldChange] = []
    cell.on_changed.append(seen.append)

    cell.set_value(0.75)

    assert seen[0].field_id == "ns.node.cfg.threshold"


def test_manual_fire_defaults_old_to_none():
    """binding.py re-fires a container after in-place mutation — old is unknowable."""
    cell = _make_field(3.0)
    seen: list[FieldChange] = []
    cell.on_changed.append(seen.append)

    cell.fire(3.0)

    assert seen[0].value == 3.0
    assert seen[0].old is None


def test_reset_and_from_dict_stay_silent():
    """Silent-restore semantics are unchanged: reset()/from_dict() never fire."""
    cell = _make_field(1.0)
    seen: list[FieldChange] = []
    cell.on_changed.append(seen.append)

    cell.reset()
    cell.from_dict(FLOAT(value=9.0).to_dict())

    assert seen == []
