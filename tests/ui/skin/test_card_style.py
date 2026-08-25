"""BaseSkin.card_style — per-node appearance props layered over a skin's defaults.

card_style only reads ``wrapper.node.props``, so these drive it with a stub
wrapper rather than standing up a graph and library system.
"""

from types import SimpleNamespace

import pytest

from haywire.core.node.properties import NodeProperties
from haywire.ui.skin.base import BaseSkin


class _Skin(BaseSkin):
    """Concrete BaseSkin — render() is abstract but card_style never calls it."""

    def __init__(self):  # bypass the widget-factory __init__; card_style needs none
        pass

    def render(self, main_card, wrapper):  # pragma: no cover - never invoked
        raise AssertionError("render() is not exercised by these tests")


def _wrapper(props=None):
    return SimpleNamespace(node=SimpleNamespace(props=props))


def _style(props=None) -> str:
    """card_style over one fixed set of skin defaults — the DefaultNodeSkin's."""
    return _Skin().card_style(
        _wrapper(props),
        background="var(--hw-node-bg)",
        border_color="#333333",
        border_thickness=3,
        border_roundness=16,
    )


class TestDefaults:
    def test_no_props_bag_renders_the_skin_defaults(self):
        style = _style()
        assert "background: var(--hw-node-bg);" in style
        assert "border: 3px solid #333333;" in style
        assert "border-radius: 16px;" in style

    def test_unset_props_render_the_skin_defaults(self):
        """The behaviour-preserving case: a node that overrides nothing."""
        assert _style(NodeProperties()) == _style()

    def test_empty_string_is_not_an_override(self):
        """A cleared colour field reads back "" — that is unset, not black."""
        props = NodeProperties()
        props.body_color = ""
        assert "background: var(--hw-node-bg);" in _style(props)

    def test_a_default_valued_field_is_not_an_override(self):
        """Inheritance is decided on is_locally_set, not on the value.

        The props carry concrete defaults so they survive the widget layer, so
        a node that has never been styled holds a real colour — it must still
        render the skin's look, not its own default.
        """
        props = NodeProperties()
        assert props.body_color  # a concrete value, not None
        assert not props.is_locally_set("body_color")
        assert "background: var(--hw-node-bg);" in _style(props)

    def test_resetting_a_field_returns_the_card_to_the_skin(self):
        props = NodeProperties()
        props.body_color = "#112233"
        assert "background: #112233;" in _style(props)
        props.reset("body_color")
        assert "background: var(--hw-node-bg);" in _style(props)

    def test_writing_the_default_value_still_counts_as_an_override(self):
        """Deliberately picking the default colour is a choice, not an unset."""
        props = NodeProperties()
        default = props.body_color
        props.body_color = "#abcdef"
        props.body_color = default
        assert props.is_locally_set("body_color")
        assert f"background: {default};" in _style(props)


class TestOverrides:
    def test_body_color_replaces_the_background(self):
        props = NodeProperties()
        props.body_color = "#112233"
        assert "background: #112233;" in _style(props)

    def test_body_color_replaces_a_gradient_wholesale(self):
        props = NodeProperties()
        props.body_color = "#112233"
        style = _Skin().card_style(
            _wrapper(props),
            background="linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            border_color="#4f46e5",
            border_thickness=3,
            border_roundness=16,
        )
        assert "background: #112233;" in style
        assert "linear-gradient" not in style

    def test_alpha_colors_pass_through_untouched(self):
        """#rrggbbaa is how opacity is expressed — there is no opacity field."""
        props = NodeProperties()
        props.body_color = "#11223344"
        props.border_color = "#aabbccdd"
        style = _style(props)
        assert "background: #11223344;" in style
        assert "border: 3px solid #aabbccdd;" in style

    def test_border_fields_override_independently(self):
        props = NodeProperties()
        props.border_thickness = 7
        assert "border: 7px solid #333333;" in _style(props)
        assert "border-radius: 16px;" in _style(props)

    def test_zero_thickness_is_an_override_not_an_unset(self):
        props = NodeProperties()
        props.border_thickness = 0
        assert "border: 0px solid #333333;" in _style(props)


class TestClamping:
    """min/max in a widget_config are UI-only, so a hand-edited graph JSON can
    carry anything. A negative border breaks the pin geometry silently."""

    @pytest.mark.parametrize(
        ("thickness", "expected"),
        [(-5, 0), (0, 0), (32, 32), (900, 32)],
    )
    def test_thickness_is_clamped(self, thickness, expected):
        props = NodeProperties()
        props.border_thickness = thickness
        assert f"border: {expected}px solid" in _style(props)

    @pytest.mark.parametrize(
        ("roundness", "expected"),
        [(-5, 0), (0, 0), (64, 64), (900, 64)],
    )
    def test_roundness_is_clamped(self, roundness, expected):
        props = NodeProperties()
        props.border_roundness = roundness
        assert f"border-radius: {expected}px;" in _style(props)

    def test_non_numeric_falls_back_instead_of_breaking_the_render(self):
        """Defence in depth for a bag that is not a NodeProperties.

        A real NodeProperties cannot hold "fat" — the INT cell coerces on
        write, so a hand-edited graph carrying one fails at *load*. But
        card_style duck-types ``wrapper.node.props``, so any object can arrive
        here, and a bad value must not take the whole card's render down.
        """
        props = SimpleNamespace(
            body_color=None, border_color=None, border_thickness="fat", border_roundness=None
        )
        assert "border: 3px solid #333333;" in _style(props)


class TestPersistence:
    """The reported bug: colours reverted to #ffffffff on leaving a node.

    Cause: the props defaulted to None, PrimitiveUnwrappingConverter maps a
    None model value onto the *widget's* default (#ffffffff for the alpha
    picker), and the browser echoes that back as a genuine edit — so simply
    rendering a node wrote white into its graph.
    """

    def test_an_unset_colour_never_reads_back_as_the_widget_default(self):
        props = NodeProperties()
        for name in ("body_color", "border_color"):
            value = getattr(props, name)
            assert value is not None, f"{name} defaults to None — the widget will invent one"
            assert value != "#ffffffff"

    def test_an_unset_number_never_reads_back_as_none(self):
        """NumberWidget has no null state either — None would render as 0."""
        for name in ("border_thickness", "border_roundness"):
            assert getattr(NodeProperties(), name) is not None

    def test_rendering_a_node_does_not_dirty_its_appearance(self):
        """An echo of the value the widget was given must not mark it set —
        otherwise every node that is merely looked at gets styled."""
        props = NodeProperties()
        for name in ("body_color", "border_color", "border_thickness", "border_roundness"):
            setattr(props, name, getattr(props, name))  # the browser's echo
        assert props.to_dict()["values"] == {}

    def test_an_edited_colour_survives_save_and_reload(self):
        props = NodeProperties()
        props.body_color = "#11223344"
        props.border_thickness = 7

        reloaded = NodeProperties()
        reloaded.from_dict(props.to_dict())

        assert reloaded.body_color == "#11223344"
        assert reloaded.border_thickness == 7
        assert "background: #11223344;" in _style(reloaded)
        assert "border: 7px solid" in _style(reloaded)


class TestRenameMigration:
    def test_color_override_loads_as_body_color(self):
        """Settings.from_dict skips unknown keys silently, so without the shim
        an old graph's colour would vanish rather than fail."""
        props = NodeProperties()
        props.from_dict({"values": {"color_override": "#abcdef"}, "promoted": {}})
        assert props.body_color == "#abcdef"

    def test_new_name_wins_when_both_are_present(self):
        props = NodeProperties()
        props.from_dict({"values": {"color_override": "#111111", "body_color": "#222222"}, "promoted": {}})
        assert props.body_color == "#222222"

    def test_nothing_reserializes_under_the_old_name(self):
        props = NodeProperties()
        props.from_dict({"values": {"color_override": "#abcdef"}, "promoted": {}})
        assert "color_override" not in props.to_dict()["values"]
