"""`settings_fields()` — the supported way to iterate a bag's fields.

Replaces reaching for the private `_property_settings()`, which the panel
renderer, the graph-editor farmhands and barn libraries were all already
calling. Module-level rather than a method so the framework keeps its
operations off the bag's attribute namespace, which belongs to the author's
fields.
"""

import pytest

from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.settings import NodeSettings, setting, settings_fields
from haywire.barn.builtin.types import BOOL, INT

pytestmark = [pytest.mark.unit, pytest.mark.core]


class Base(NodeSettings):
    alpha = setting[INT](1, label="Alpha")
    beta = setting[BOOL](False, label="Beta")


class Derived(Base):
    """Redeclares an inherited field and adds one — the `selection_bag()` shape."""

    beta = setting[BOOL](True, label="Beta (overridden)")
    gamma = setting[INT](3, label="Gamma")


def test_accepts_a_class():
    assert list(settings_fields(Base)) == ["alpha", "beta"]


def test_accepts_an_instance():
    bag = Base(registry=create_test_settings_registry())
    assert list(settings_fields(bag)) == ["alpha", "beta"]


def test_matches_the_private_spelling_it_replaces():
    assert settings_fields(Base) == Base._property_settings()


def test_walks_the_mro_base_first():
    """Inherited fields precede subclass ones; a redeclared field keeps its
    base position rather than jumping to the end."""
    assert list(settings_fields(Derived)) == ["alpha", "beta", "gamma"]


def test_a_redeclared_field_resolves_to_the_subclass_descriptor():
    assert settings_fields(Derived)["beta"]._label == "Beta (overridden)"


def test_returns_descriptors_not_values():
    bag = Base(registry=create_test_settings_registry())
    bag.alpha = 42

    fields = settings_fields(bag)

    assert fields["alpha"] is not 42  # noqa: F632 - the point is it's a descriptor
    assert fields["alpha"]._label == "Alpha"


def test_mirroring_a_bag_onto_a_foreign_object():
    """The motivating use — what every wrapper node hand-writes today."""

    class Target:
        alpha = 0
        beta = None

    bag = Base(registry=create_test_settings_registry())
    bag.alpha = 7
    target = Target()

    for name in settings_fields(bag):
        setattr(target, name, getattr(bag, name))

    assert target.alpha == 7
    assert target.beta is False
