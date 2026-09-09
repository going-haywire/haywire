"""Field names may not collide with the framework's members on a bag.

A settings bag's attribute namespace belongs to the author's fields — they
become graph-JSON keys, TOML keys and panel labels. Every framework operation
is therefore `_`-prefixed, and a field may not be.

Before this guard, a field named `to_dict` shadowed the serializer and made
`BaseNode.to_dict()` raise `TypeError` when the graph was **saved** — silent at
declaration, fatal much later.
"""

import pytest

from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.settings import NodeSettings, setting
from haywire.core.settings.settings import Settings
from haywire.barn.builtin.types import BOOL, INT

pytestmark = [pytest.mark.unit, pytest.mark.core]


def test_underscore_prefixed_field_is_rejected_at_class_definition():
    with pytest.raises(TypeError, match=r"may not start with '_'"):

        class Bad(NodeSettings):
            _hidden = setting[INT](7, label="Hidden")


def test_the_error_names_the_class_and_the_field():
    with pytest.raises(TypeError, match=r"Bad2\._hidden"):

        class Bad2(NodeSettings):
            _hidden = setting[INT](7)


def test_the_error_suggests_a_fix():
    """The message has to teach, since the rule is otherwise invisible."""
    with pytest.raises(TypeError, match=r"ui_state=UiState.HIDDEN"):

        class Bad3(NodeSettings):
            _hidden = setting[BOOL](False)


def test_a_field_colliding_with_internal_state_is_rejected():
    """`_set_keys` is a data descriptor collision that used to blow up with
    `AttributeError: 'int' object has no attribute 'add'` at construction."""
    with pytest.raises(TypeError, match=r"may not start with '_'"):

        class Bad4(NodeSettings):
            _set_keys = setting[INT](3)


def test_ordinary_field_names_are_fine():
    class Good(NodeSettings):
        threshold = setting[INT](5, label="Threshold")
        enabled = setting[BOOL](True, label="Enabled")

    bag = Good(registry=create_test_settings_registry())
    assert bag.threshold == 5
    assert bag.enabled is True


def test_redeclaring_an_inherited_field_is_still_legal():
    """How a family node narrows a shared bag — `selection_bag()` does this."""

    class Base(NodeSettings):
        mode = setting[INT](1, label="Mode")

    class Narrowed(Base):
        mode = setting[INT](2, label="Mode (narrowed)")

    bag = Narrowed(registry=create_test_settings_registry())
    assert bag.mode == 2


def test_non_setting_attributes_are_not_policed():
    """Only `setting` descriptors are field names; helpers and constants are
    ordinary class attributes and may be spelled however the author likes."""

    class WithHelpers(NodeSettings):
        _PRIVATE_CONSTANT = 42
        value = setting[INT](1)

        def _helper(self):
            return self._PRIVATE_CONSTANT

    bag = WithHelpers(registry=create_test_settings_registry())
    assert bag._helper() == 42


def test_the_framework_namespace_is_disjoint_from_field_names():
    """The invariant the rule rests on: nothing public remains on Settings, so
    '_'-prefixed framework members and non-'_' field names cannot overlap."""
    assert [n for n in dir(Settings) if not n.startswith("_")] == []
