"""The wire-type model: ids, the id map, clamping, derivation and matching."""

from types import SimpleNamespace

import pytest

from haywire.core.types import Propagation
from haywire.core.types import wire as wire_module
from haywire.core.types.wire import (
    WILDCARD,
    WireRole,
    WireType,
    declaring_type_of,
    get_wire_type,
    wire_type_of,
    wires_match,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _isolated_id_map(monkeypatch):
    """Each test registers into a copy, so its wire types never leak into the next."""
    monkeypatch.setattr(wire_module, "_WIRE_BY_ID", dict(wire_module._WIRE_BY_ID))


def _wire(name: str, module: str = __name__, **attrs) -> type[WireType]:
    """A wire type class named *name*, defined as if in *module*."""
    namespace = {"__module__": module, "__qualname__": name, "role": WireRole.DEPENDENT, **attrs}
    return type(name, (WireType,), namespace)


class TestIds:
    def test_a_wire_type_is_named_by_its_library_and_class(self):
        plain = _wire("PlainWire")

        assert plain.id == "__system__:wire:PlainWire"
        assert get_wire_type(plain.id) is plain

    def test_id_replaces_the_last_segment(self):
        named = _wire("NamedWire", id="Renamed")

        assert named.id == "__system__:wire:Renamed"

    def test_a_base_without_a_role_is_not_registered(self):
        abstract = type(
            "AbstractWire", (WireType,), {"__module__": __name__, "__qualname__": "AbstractWire"}
        )

        assert not hasattr(abstract, "id")
        assert abstract not in wire_module._WIRE_BY_ID.values()

    def test_the_same_class_defined_again_replaces_the_old_one(self):
        first = _wire("ReloadedWire")
        second = _wire("ReloadedWire")

        assert second.id == first.id
        assert get_wire_type(first.id) is second

    def test_the_same_id_from_another_module_is_refused(self):
        _wire("ClashingWire")

        with pytest.raises(ValueError, match="collision"):
            _wire("ClashingWire", module="some.other.module")


class TestClamp:
    def test_an_allowed_mode_is_kept(self):
        both = _wire("BothWire", propagation=(Propagation.EAGER, Propagation.LAZY))

        assert both.clamp(Propagation.LAZY) is Propagation.LAZY

    def test_a_disallowed_mode_takes_the_default(self):
        eager_only = _wire("EagerOnlyWire", propagation=(Propagation.EAGER,))

        assert eager_only.clamp(Propagation.LAZY) is Propagation.EAGER
        assert eager_only.clamp(None) is Propagation.EAGER

    def test_a_wire_type_without_propagation_clamps_to_none(self):
        none = _wire("NoneWire", propagation=())

        assert none.clamp(Propagation.EAGER) is None


class TestWireTypeOf:
    def test_a_type_answers_with_its_declared_wire_type(self):
        declared = _wire("DeclaredWire")
        value = SimpleNamespace(class_identity=SimpleNamespace(wire_type=declared))

        assert wire_type_of(value) is declared

    def test_a_container_answers_with_its_elements_through_nesting(self):
        declared = _wire("ElementWire")
        element = SimpleNamespace(class_identity=SimpleNamespace(wire_type=declared))
        inner = SimpleNamespace(class_identity=SimpleNamespace(wire_type=None), element_type_cls=element)
        outer = SimpleNamespace(class_identity=SimpleNamespace(wire_type=None), element_type_cls=inner)

        assert wire_type_of(outer) is declared

    def test_a_type_without_identity_or_element_answers_none(self):
        assert wire_type_of(SimpleNamespace()) is None
        assert wire_type_of(None) is None

    def test_an_element_that_is_a_plain_python_type_ends_the_walk(self):
        container = SimpleNamespace(class_identity=SimpleNamespace(wire_type=None), element_type_cls=float)

        assert wire_type_of(container) is None


class TestDeclaringTypeOf:
    def test_a_type_that_declares_a_wire_type_is_its_own_declarer(self):
        declared = _wire("DeclaredWire2")
        value = SimpleNamespace(class_identity=SimpleNamespace(wire_type=declared))

        assert declaring_type_of(value) == (value, declared)

    def test_a_container_answers_with_the_element_that_declares_through_nesting(self):
        declared = _wire("ElementWire2")
        element = SimpleNamespace(class_identity=SimpleNamespace(wire_type=declared))
        inner = SimpleNamespace(class_identity=SimpleNamespace(wire_type=None), element_type_cls=element)
        outer = SimpleNamespace(class_identity=SimpleNamespace(wire_type=None), element_type_cls=inner)

        assert declaring_type_of(outer) == (element, declared)

    def test_a_type_without_identity_or_element_answers_none(self):
        assert declaring_type_of(SimpleNamespace()) is None
        assert declaring_type_of(None) is None

    def test_an_element_that_is_a_plain_python_type_ends_the_walk(self):
        container = SimpleNamespace(class_identity=SimpleNamespace(wire_type=None), element_type_cls=float)

        assert declaring_type_of(container) is None

    def test_wire_type_of_agrees_with_it(self):
        agreed = _wire("AgreeWire")
        element = SimpleNamespace(class_identity=SimpleNamespace(wire_type=agreed))
        outer = SimpleNamespace(class_identity=SimpleNamespace(wire_type=None), element_type_cls=element)

        declared = declaring_type_of(outer)
        assert declared is not None
        assert wire_type_of(outer) is declared[1]


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("lib:wire:A", "lib:wire:A", True),
        ("lib:wire:A", "lib:wire:B", False),
        (WILDCARD, "lib:wire:A", True),
        ("lib:wire:A", WILDCARD, True),
        (WILDCARD, WILDCARD, False),
        (None, "lib:wire:A", False),
        ("lib:wire:A", None, False),
        (None, None, False),
    ],
)
def test_wires_match(a, b, expected):
    assert wires_match(a, b) is expected
