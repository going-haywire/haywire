"""Depth indents a port row's CONTENT column, never its pin column.

The load-bearing property: a pin is placed by a negative offset computed from
`card_padding`, which assumes its row begins at the card edge. Indenting the
whole row falsifies that and insets the pin from the border once per nesting
level, silently. Indentation therefore belongs on the content column, whose
geometry no pin offset reads.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from haybale_studio.settings.node_skin_settings import NodeSkinSettings

pytestmark = pytest.mark.unit


@pytest.fixture
def skin():
    """A skin with stubbed geometry settings.

    Built with ``__new__`` — the pattern in ``test_node_skin_is_collapsed.py`` —
    because ``__init__`` needs a widget factory and constructs a real
    ``NodeSkinSettings``. The geometry accessors are ``@property`` reads off
    ``_ui_settings``, so stubbing that bag is what makes them answer.
    """
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    instance = StackedNodeSkin.__new__(StackedNodeSkin)
    instance._ui_settings = cast(
        "NodeSkinSettings",
        SimpleNamespace(
            card_padding=16,
            pin_gutter=20,
            pin_protrusion=0,
            # The real default is negative — it overlaps into the empty half of the
            # gutter — so the stub uses it rather than a tidier positive number.
            content_gap=-15,
            pin_row_height=24,
            pin_column_width=24,
            card_padding_block=8,
            fold_indent=12,
        ),
    )
    return instance


def test_fold_indent_is_a_declared_setting() -> None:
    """Node geometry is user-tunable; the fold indent is geometry like the rest."""
    from haybale_studio.settings.node_skin_settings import NodeSkinSettings

    assert "fold_indent" in NodeSkinSettings._settings_descriptors()


def test_geometry_accessors_are_properties() -> None:
    """Guards the trap this plan was corrected for: these are NOT class constants.

    Reading them off the class yields the descriptor, and arithmetic on that
    raises TypeError.
    """
    from haybale_studio.skins.node_skin import NodeSkin

    assert isinstance(NodeSkin.CONTENT_GAP, property)
    assert isinstance(NodeSkin.PIN_GUTTER, property)
    assert isinstance(NodeSkin.FOLD_INDENT, property)


def test_content_inset_grows_with_depth(skin) -> None:
    """The content column's inset is CONTENT_GAP + depth * FOLD_INDENT."""
    gap = skin.CONTENT_GAP
    step = skin.FOLD_INDENT

    assert skin._content_inset(0) == gap
    assert skin._content_inset(1) == gap + step
    assert skin._content_inset(3) == gap + 3 * step


def test_content_inset_follows_the_live_settings(skin) -> None:
    """Both values are user-editable, so the inset must re-read them, not cache."""
    skin._ui_settings.content_gap = 9
    skin._ui_settings.fold_indent = 20
    assert skin._content_inset(1) == 29


def test_a_zero_fold_indent_flattens_the_card(skin) -> None:
    """0 is a legitimate choice, which is half the reason this is a setting."""
    skin._ui_settings.fold_indent = 0
    assert skin._content_inset(0) == skin._content_inset(4)


def test_negative_depth_is_clamped(skin) -> None:
    assert skin._content_inset(-1) == skin.CONTENT_GAP


def test_pin_cell_style_is_depth_invariant() -> None:
    """The pin column's grid placement must not vary with depth."""
    import inspect

    from haybale_studio.skins.node_skin import NodeSkin

    source = inspect.getsource(NodeSkin._render_port_horizontal)

    # Two pin renders (pin_first and its mirror). Neither cell_style may carry
    # the depth inset — that is the whole invariant this plan establishes.
    pin_cells = [line for line in source.splitlines() if "grid-column: {pin_column}" in line]
    assert len(pin_cells) == 2, f"expected two pin cell placements, got {len(pin_cells)}"

    # The inset reaches the CONTENT margins only.
    assert "inset" in source, "the content column must use the depth inset"
    inset_lines = [line for line in source.splitlines() if "inset" in line]
    assert not any("pin_column" in line for line in inset_lines), (
        "the pin column must never be offset by depth"
    )


def test_render_port_accepts_depth() -> None:
    import inspect

    from haybale_studio.skins.node_skin import NodeSkin

    assert "depth" in inspect.signature(NodeSkin.render_port).parameters
    assert "depth" in inspect.signature(NodeSkin._render_port_horizontal).parameters


def test_render_config_accepts_depth() -> None:
    import inspect

    from haybale_studio.skins.node_skin import NodeSkin

    assert "depth" in inspect.signature(NodeSkin._render_config).parameters


def test_config_indent_grows_with_depth(skin) -> None:
    """A config row is pinless, so depth adds to its existing symmetric indent."""
    base = max(0, skin.PIN_GUTTER + skin.CONTENT_GAP)
    step = skin.FOLD_INDENT

    assert skin._config_indent(0) == base
    assert skin._config_indent(2) == base + 2 * step


def test_config_indent_follows_the_live_settings(skin) -> None:
    """Both PIN_GUTTER and CONTENT_GAP are user-editable; neither may be cached."""
    skin._ui_settings.pin_gutter = 30
    skin._ui_settings.content_gap = 6
    assert skin._config_indent(0) == 36


def test_group_container_does_not_indent_the_row() -> None:
    """The group container must not carry row-level padding/margin classes.

    `pl-2 ml-1` there insets the pin column too, moving a nested pin off the
    card border once per level.
    """
    import inspect

    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    source = inspect.getsource(StackedNodeSkin._render_group)
    assert "pl-2" not in source
    assert "ml-1" not in source


def test_render_group_threads_depth() -> None:
    import inspect

    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    assert "depth" in inspect.signature(StackedNodeSkin._render_group).parameters
