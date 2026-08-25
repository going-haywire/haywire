"""FILL — the structured background type behind a node card's body.

``to_css`` is the whole contract: it is the only thing that turns a FILL into
CSS, and it must be *total*. A graph file is editable by hand, so every
reachable field combination has to yield a valid ``background`` value rather
than raising or emitting something that breaks the card's render.
"""

import json

import pytest

from haywire.barn.builtin.types.fill import LINEAR, RADIAL, SOLID, FILL


class TestDefaults:
    def test_default_is_a_solid_dark_fill(self):
        fill = FILL()
        assert fill.kind == SOLID
        assert fill.to_css() == "#1e1e1eff"

    def test_default_stops_are_not_shared_between_instances(self):
        """A dataclass default_factory, not a shared list — one node mutating
        its stops must not reach every other node's fill."""
        a, b = FILL(), FILL()
        a.stops.append({"color": "#fff", "at": 100})
        assert len(b.stops) == 1


class TestToCss:
    def test_solid_renders_its_first_stop(self):
        assert FILL(stops=[{"color": "#112233", "at": 0}]).to_css() == "#112233"

    def test_solid_ignores_further_stops(self):
        """Switching gradient → solid keeps the stops in the model, so solid has
        to pick one rather than emit a gradient."""
        fill = FILL(stops=[{"color": "#112233", "at": 0}, {"color": "#445566", "at": 100}])
        assert fill.to_css() == "#112233"

    def test_linear_renders_a_gradient(self):
        fill = FILL(
            kind=LINEAR,
            angle=135,
            stops=[{"color": "#667eea", "at": 0}, {"color": "#764ba2", "at": 100}],
        )
        assert fill.to_css() == "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"

    def test_radial_renders_a_circle(self):
        fill = FILL(kind=RADIAL, stops=[{"color": "#fff", "at": 0}, {"color": "#000", "at": 100}])
        assert fill.to_css() == "radial-gradient(circle, #fff 0%, #000 100%)"

    def test_stops_render_in_position_order(self):
        """CSS requires ascending stops; the editor does not enforce an order."""
        fill = FILL(kind=LINEAR, stops=[{"color": "#000", "at": 80}, {"color": "#fff", "at": 10}])
        assert fill.to_css() == "linear-gradient(135deg, #fff 10%, #000 80%)"

    def test_a_one_stop_gradient_is_promoted_to_a_flat_run(self):
        """A gradient needs two stops to be valid CSS."""
        assert FILL(kind=LINEAR, stops=[{"color": "#abc", "at": 0}]).to_css() == (
            "linear-gradient(135deg, #abc 0%, #abc 100%)"
        )

    def test_no_stops_at_all_still_renders(self):
        assert FILL(kind=LINEAR, stops=[]).to_css().startswith("linear-gradient(")

    def test_an_unknown_kind_falls_back_to_solid(self):
        assert FILL(kind="hexagonal", stops=[{"color": "#abc", "at": 0}]).to_css() == "#abc"


class TestHostileValues:
    """A graph file is hand-editable, so to_css must never raise or leak."""

    def test_a_semicolon_in_a_colour_cannot_inject_css(self):
        """The reason FILL exists rather than a free-text CSS string: NiceGUI's
        .style() splits on ';', so a value carrying one would escape its own
        declaration and add arbitrary rules to the card."""
        fill = FILL(stops=[{"color": "red; position: fixed; top: 0; width: 100vw", "at": 0}])
        assert ";" not in fill.to_css()
        assert fill.to_css() == "#1e1e1eff"

    @pytest.mark.parametrize("hostile", ["a{}b", "url(x)/*c*/", "\\65 vil"])
    def test_css_punctuation_is_rejected_wholesale(self, hostile):
        assert FILL(stops=[{"color": hostile, "at": 0}]).to_css() == "#1e1e1eff"

    @pytest.mark.parametrize(("given", "expected"), [(-50, 0), (0, 0), (100, 100), (900, 100)])
    def test_stop_positions_are_clamped(self, given, expected):
        fill = FILL(kind=LINEAR, stops=[{"color": "#111", "at": given}, {"color": "#222", "at": 50}])
        assert f"{expected}%" in fill.to_css()

    def test_a_non_numeric_angle_falls_back(self):
        fill = FILL(kind=LINEAR, stops=[{"color": "#1", "at": 0}, {"color": "#2", "at": 100}])
        fill.angle = "sideways"  # type: ignore[assignment]  # the point: JSON can hold anything
        assert fill.to_css().startswith("linear-gradient(135deg,")

    def test_a_malformed_stop_does_not_raise(self):
        """Non-dict stops are dropped at construction — a hand-edited graph must
        not blow up before to_css ever gets a chance to clean it."""
        fill = FILL(kind=LINEAR, stops=["not-a-dict", None])
        assert fill.stops == [{"color": "#1e1e1eff", "at": 0}]
        assert fill.to_css().startswith("linear-gradient(")

    def test_malformed_stops_mixed_with_good_ones_keep_the_good(self):
        fill = FILL(kind=LINEAR, stops=["junk", {"color": "#abc", "at": 50}])
        assert fill.stops == [{"color": "#abc", "at": 50}]


class TestSerialization:
    def test_roundtrips_through_json(self):
        fill = FILL(
            kind=LINEAR, angle=90, stops=[{"color": "#667eea", "at": 0}, {"color": "#764ba2", "at": 100}]
        )
        restored = FILL.from_dict(json.loads(json.dumps(fill.to_dict())))
        assert restored == fill
        assert restored.to_css() == fill.to_css()

    def test_from_dict_tolerates_garbage(self):
        for junk in [{}, {"kind": "nonsense"}, {"stops": "not-a-list"}, {"angle": "x"}]:
            assert isinstance(FILL.from_dict(junk), FILL)

    def test_from_dict_on_a_non_dict_yields_a_default(self):
        assert FILL.from_dict("nope") == FILL()  # type: ignore[arg-type]  # hand-edited JSON

    def test_equality_is_by_value(self):
        """The settings descriptor no-ops a write equal to the current value, so
        a value-equal FILL must compare equal or every render marks the node
        dirty."""
        assert FILL() == FILL()
        assert FILL(kind=LINEAR) != FILL()


class TestConstruction:
    """FILL absorbs the settings layer's ``{"value": seed}`` seeding shape,
    which fits PrimitiveType — what every setting was until now."""

    def test_accepts_a_positional_colour_string(self):
        assert FILL("#abcdef").to_css() == "#abcdef"

    def test_accepts_a_positional_dict(self):
        assert FILL({"kind": SOLID, "stops": [{"color": "#abcdef", "at": 0}]}).to_css() == "#abcdef"

    def test_accepts_a_positional_fill(self):
        original = FILL(kind=RADIAL, stops=[{"color": "#1", "at": 0}, {"color": "#2", "at": 100}])
        assert FILL(original) == original

    def test_a_positional_none_yields_the_defaults(self):
        assert FILL(None) == FILL()

    def test_from_css_color_builds_a_one_stop_solid(self):
        fill = FILL.from_css_color("#11223344")
        assert fill.kind == SOLID
        assert len(fill.stops) == 1
        assert fill.to_css() == "#11223344"
