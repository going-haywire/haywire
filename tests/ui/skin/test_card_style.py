"""BaseSkin.card_style — per-node appearance props layered over a skin's defaults.

card_style only reads ``wrapper.node.props``, so these drive it with a stub
wrapper rather than standing up a graph and library system.
"""

import json
from types import SimpleNamespace

import pytest

from haywire.barn.builtin.types import FILL
from haywire.core.node.properties import NodeProperties
from haywire.ui.skin.base import BaseSkin


def _solid(color: str) -> FILL:
    """A one-stop solid fill — the common case, spelled once."""
    return FILL(kind="solid", stops=[{"color": color, "at": 0}])


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

    def test_a_default_valued_field_is_not_an_override(self):
        """Inheritance is decided on is_locally_set, not on the value.

        The props carry concrete defaults so they survive the widget layer, so
        a node that has never been styled holds a real fill — it must still
        render the skin's look, not its own default.
        """
        props = NodeProperties()
        assert props.body_fill.to_css()  # a concrete value, not None
        assert not props.is_locally_set("body_fill")
        assert "background: var(--hw-node-bg);" in _style(props)

    def test_resetting_a_field_returns_the_card_to_the_skin(self):
        props = NodeProperties()
        props.body_fill = _solid("#112233")
        assert "background: #112233;" in _style(props)
        props.reset("body_fill")
        assert "background: var(--hw-node-bg);" in _style(props)

    def test_writing_the_default_value_still_counts_as_an_override(self):
        """Deliberately picking the default fill is a choice, not an unset."""
        props = NodeProperties()
        default = props.body_fill
        props.body_fill = _solid("#abcdef")
        props.body_fill = FILL(kind=default.kind, angle=default.angle, stops=default.stops)
        assert props.is_locally_set("body_fill")
        assert f"background: {default.to_css()};" in _style(props)


class TestOverrides:
    def test_a_solid_fill_replaces_the_background(self):
        props = NodeProperties()
        props.body_fill = _solid("#112233")
        assert "background: #112233;" in _style(props)

    def test_a_solid_fill_replaces_a_skin_gradient_wholesale(self):
        props = NodeProperties()
        props.body_fill = _solid("#112233")
        style = _Skin().card_style(
            _wrapper(props),
            background="linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            border_color="#4f46e5",
            border_thickness=3,
            border_roundness=16,
        )
        assert "background: #112233;" in style
        assert "linear-gradient" not in style

    def test_a_gradient_fill_reaches_the_card(self):
        """The capability the type exists for: what example_skin hardcodes in
        Python is now expressible per node."""
        props = NodeProperties()
        props.body_fill = FILL(
            kind="linear",
            angle=135,
            stops=[{"color": "#667eea", "at": 0}, {"color": "#764ba2", "at": 100}],
        )
        assert "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);" in _style(props)

    def test_a_radial_fill_reaches_the_card(self):
        props = NodeProperties()
        props.body_fill = FILL(
            kind="radial", stops=[{"color": "#fff", "at": 0}, {"color": "#000", "at": 100}]
        )
        assert "background: radial-gradient(circle, #fff 0%, #000 100%);" in _style(props)

    def test_alpha_colors_pass_through_untouched(self):
        """#rrggbbaa is how opacity is expressed — there is no opacity field."""
        props = NodeProperties()
        props.body_fill = _solid("#11223344")
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
            body_fill=None, border_color=None, border_thickness="fat", border_roundness=None
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
        assert props.body_fill.to_css() != "#ffffffff"
        assert props.border_color not in (None, "#ffffffff")

    def test_an_unset_number_never_reads_back_as_none(self):
        """NumberWidget has no null state either — None would render as 0."""
        for name in ("border_thickness", "border_roundness"):
            assert getattr(NodeProperties(), name) is not None

    def test_rendering_a_node_does_not_dirty_its_appearance(self):
        """An echo of the value the widget was given must not mark it set —
        otherwise every node that is merely looked at gets styled."""
        props = NodeProperties()
        for name in ("body_fill", "border_color", "border_thickness", "border_roundness"):
            setattr(props, name, getattr(props, name))  # the browser's echo
        assert props.to_dict()["values"] == {}

    def test_an_edited_fill_survives_save_and_reload(self):
        props = NodeProperties()
        props.body_fill = _solid("#11223344")
        props.border_thickness = 7

        reloaded = NodeProperties()
        reloaded.from_dict(props.to_dict())

        assert reloaded.body_fill.to_css() == "#11223344"
        assert reloaded.border_thickness == 7
        assert "background: #11223344;" in _style(reloaded)
        assert "border: 7px solid" in _style(reloaded)

    def test_a_gradient_survives_a_real_json_roundtrip(self):
        """A FILL is an object; unflattened it would raise in json.dumps and the
        graph would simply fail to save."""
        props = NodeProperties()
        props.body_fill = FILL(
            kind="linear",
            angle=90,
            stops=[{"color": "#667eea", "at": 0}, {"color": "#764ba2", "at": 100}],
        )

        reloaded = NodeProperties()
        reloaded.from_dict(json.loads(json.dumps(props.to_dict())))

        assert isinstance(reloaded.body_fill, FILL)
        assert reloaded.body_fill.to_css() == "linear-gradient(90deg, #667eea 0%, #764ba2 100%)"


class TestRenameMigration:
    """Two renames have landed: color_override → body_color → body_fill.

    The second also changed type, so it cannot be a key swap — the restore path
    writes straight into the cell and BaseField rejects a bare string.
    """

    @pytest.mark.parametrize("old_name", ["color_override", "body_color"])
    def test_an_old_colour_loads_as_a_solid_fill(self, old_name):
        """Settings.from_dict skips unknown keys silently, so without the shim
        an old graph's colour would vanish rather than fail."""
        props = NodeProperties()
        props.from_dict({"values": {old_name: "#abcdef"}, "promoted": {}})
        assert isinstance(props.body_fill, FILL)
        assert props.body_fill.to_css() == "#abcdef"
        assert props.is_locally_set("body_fill")

    def test_the_later_spelling_wins_when_both_are_present(self):
        """A graph written between the two renames keeps the value the user
        last saw, not a resurrected older one."""
        props = NodeProperties()
        props.from_dict({"values": {"color_override": "#111111", "body_color": "#222222"}, "promoted": {}})
        assert props.body_fill.to_css() == "#222222"

    def test_nothing_reserializes_under_an_old_name(self):
        props = NodeProperties()
        props.from_dict({"values": {"color_override": "#abcdef"}, "promoted": {}})
        values = props.to_dict()["values"]
        assert "color_override" not in values
        assert "body_color" not in values

    def test_a_migrated_graph_renders(self):
        """The migration is only worth anything if the fill reaches the card."""
        props = NodeProperties()
        props.from_dict({"values": {"body_color": "#11223344"}, "promoted": {}})
        assert "background: #11223344;" in _style(props)
