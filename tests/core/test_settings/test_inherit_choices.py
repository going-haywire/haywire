"""The "— Inherit —" entry on tiered appearance selects.

``skin``, ``layout_direction`` and ``node_theme`` are mirrors: while unset they
track the tier above, and a local set wins. That inheritance was previously
only reachable through the panel's reset button — a • prefix and a menu item.
An explicit empty choice makes the select *show* the state instead.

The invariant worth pinning is the tier split: the framework settings are the
floor of every chain, so offering them an inherit entry would promise a
fallback that does not exist.
"""

import pytest

from haywire.core.graph.properties import GraphProperties
from haywire.core.node.properties import NodeProperties
from haywire.core.skin.settings import (
    INHERIT_LABEL,
    NodeDefaultSkinSettings,
    _layout_direction_choices,
    _layout_direction_choices_inheritable,
    _node_skin_choices,
    _node_skin_choices_inheritable,
    _node_theme_choices,
    _node_theme_choices_inheritable,
)
from haywire.core.types.enums import LayoutDirection
from haywire.ui.widget.converters import UnsetAsEmptyChoiceConverter

pytestmark = pytest.mark.unit

_INHERITABLE = (
    _layout_direction_choices_inheritable,
    _node_skin_choices_inheritable,
    _node_theme_choices_inheritable,
)
_FLOOR = (_layout_direction_choices, _node_skin_choices)


@pytest.mark.parametrize("choices", _INHERITABLE)
def test_inheritable_tiers_offer_an_empty_choice(choices):
    options = choices()
    assert options[""] == INHERIT_LABEL


@pytest.mark.parametrize("choices", _INHERITABLE)
def test_inherit_is_listed_first(choices):
    """It reads as the default state, so it belongs at the top of the list."""
    assert next(iter(choices())) == ""


@pytest.mark.parametrize("choices", _FLOOR)
def test_the_framework_tier_offers_no_inherit(choices):
    """The floor has nothing above it to inherit from."""
    assert "" not in choices()


def test_the_framework_theme_tier_says_none_not_inherit():
    """node_theme's empty key IS meaningful at the floor — it means no node
    theme, leaving the workbench theme's node tokens standing. That is a real
    choice, but it is not inheritance, so it must not be labelled as one."""
    assert _node_theme_choices()[""] != INHERIT_LABEL
    assert "None" in _node_theme_choices()[""]


# ---------------------------------------------------------------------------
# The empty value has to survive every read path
# ---------------------------------------------------------------------------


def test_an_empty_layout_direction_coerces_to_the_default():
    """coerce() already degrades unrecognised values rather than raising, which
    is why the empty entry costs layout_direction nothing."""
    assert LayoutDirection.coerce("") is LayoutDirection.LEFT_TO_RIGHT


def test_an_empty_skin_is_falsy_not_none():
    """UINode._render falls back on a FALSY skin, not on `is None`.

    Pinning the distinction: the select emits "", so an `is None` check would
    let the empty string through to the skin registry as a lookup key and
    render every node with the error skin.
    """
    assert not ""


@pytest.mark.parametrize(
    ("bag", "field"),
    [
        (NodeProperties, "skin"),
        (NodeProperties, "layout_direction"),
        (NodeProperties, "node_theme"),
        (GraphProperties, "default_skin"),
        (GraphProperties, "layout_direction"),
        (GraphProperties, "node_theme"),
    ],
)
def test_tiered_fields_use_an_inheritable_option_source(bag, field):
    options = bag._property_settings()[field].widget_config["properties"]["options"]
    assert options in _INHERITABLE, f"{bag.__name__}.{field} must offer '{INHERIT_LABEL}'"


@pytest.mark.parametrize("field", ["studio_skin", "studio_layout_direction", "studio_node_theme"])
def test_framework_fields_do_not_use_an_inheritable_option_source(field):
    options = NodeDefaultSkinSettings._property_settings()[field].widget_config["properties"]["options"]
    assert options not in _INHERITABLE, f"studio.{field} is the floor — it inherits from nothing"


# ---------------------------------------------------------------------------
# Displaying unset AS the empty choice
# ---------------------------------------------------------------------------


class TestUnsetAsEmptyChoice:
    """A mirror defaults to None, which matches no option key — so without a
    mapping the select opens blank and the inherit entry appears only once
    someone picks it. The state most needing a label would be the only one
    without one."""

    def test_unset_displays_as_the_empty_choice(self):
        assert UnsetAsEmptyChoiceConverter().to_view(None) == ""

    def test_a_real_value_passes_through(self):
        assert UnsetAsEmptyChoiceConverter().to_view("t2b") == "t2b"

    def test_picking_inherit_writes_unset_not_empty(self):
        """The half that makes this safe. A stored "" reads as locally set, so
        a one-way mapping would let picking "— Inherit —" STOP the mirror from
        tracking its parent tier — stuck on a value that merely looks
        inherited."""
        assert UnsetAsEmptyChoiceConverter().to_model("") is None

    def test_picking_a_real_value_passes_through(self):
        assert UnsetAsEmptyChoiceConverter().to_model("t2b") == "t2b"

    def test_picking_inherit_leaves_the_field_unset(self):
        """End to end against a real bag: the round trip must not dirty it."""
        props = NodeProperties()
        props.layout_direction = UnsetAsEmptyChoiceConverter().to_model("")

        assert props.is_locally_set("layout_direction") is False
        assert "layout_direction" not in props.to_dict().get("values", {})

    def test_a_raw_empty_string_would_have_dirtied_it(self):
        """Pins WHY the to_model half exists — remove it and this is what the
        model gets."""
        props = NodeProperties()
        props.layout_direction = ""

        assert props.is_locally_set("layout_direction") is True
