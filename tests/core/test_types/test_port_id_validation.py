"""The dotted port-id namespace is reserved for promoted settings.

A promoted setting's port id IS its ``storage_key`` (``'<accessor>.<field>'``),
and promoted ports share ``node.ports`` with author-declared ones. Reserving
'.' keeps an author from declaring a port that collides with a promoted one.
"""

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types.enums import PortType
from haywire.core.types.utils import create_port_spec


@pytest.mark.parametrize("factory", ["as_inlet", "as_outlet", "as_config"])
def test_dotted_author_port_id_is_rejected(factory):
    with pytest.raises(ValueError, match="reserved for promoted settings"):
        getattr(FLOAT, factory)("props.skin")


@pytest.mark.parametrize("factory", ["as_inlet", "as_outlet", "as_config"])
def test_undotted_author_port_id_is_accepted(factory):
    spec = getattr(FLOAT, factory)("strength")
    assert spec["kwargs"]["id"] == "strength"


def test_promotion_may_use_a_dotted_id():
    """``promoted=True`` marks the framework's own promotion path."""
    spec = create_port_spec(FLOAT, PortType.INLET, "filter.strength", promoted=True)
    assert spec["kwargs"]["id"] == "filter.strength"


def test_promoted_flag_is_required_for_the_dotted_form():
    """The reservation is not bypassable by a plain dotted id."""
    with pytest.raises(ValueError, match="reserved for promoted settings"):
        create_port_spec(FLOAT, PortType.INLET, "filter.strength")
