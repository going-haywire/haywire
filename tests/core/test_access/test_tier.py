"""AccessTier — cumulative four-tier access vocabulary (ADR 0027)."""

import pytest

from haywire.core.access import AccessTier


def test_values_are_the_wire_strings():
    assert AccessTier.VIEW == "view"
    assert AccessTier.OPERATE == "operate"
    assert AccessTier.EDIT == "edit"
    assert AccessTier.ADMIN == "admin"


def test_constructed_from_string():
    assert AccessTier("edit") is AccessTier.EDIT


def test_unknown_string_raises():
    with pytest.raises(ValueError, match="superuser"):
        AccessTier("superuser")


def test_ranks_are_ordered():
    assert AccessTier.VIEW.rank < AccessTier.OPERATE.rank < AccessTier.EDIT.rank < AccessTier.ADMIN.rank


@pytest.mark.parametrize(
    ("held", "required", "expected"),
    [
        (AccessTier.ADMIN, AccessTier.ADMIN, True),
        (AccessTier.ADMIN, AccessTier.EDIT, True),
        (AccessTier.ADMIN, AccessTier.OPERATE, True),
        (AccessTier.ADMIN, AccessTier.VIEW, True),
        (AccessTier.EDIT, AccessTier.ADMIN, False),
        (AccessTier.EDIT, AccessTier.EDIT, True),
        (AccessTier.EDIT, AccessTier.OPERATE, True),
        (AccessTier.EDIT, AccessTier.VIEW, True),
        (AccessTier.OPERATE, AccessTier.ADMIN, False),
        (AccessTier.OPERATE, AccessTier.EDIT, False),
        (AccessTier.OPERATE, AccessTier.OPERATE, True),
        (AccessTier.OPERATE, AccessTier.VIEW, True),
        (AccessTier.VIEW, AccessTier.ADMIN, False),
        (AccessTier.VIEW, AccessTier.EDIT, False),
        (AccessTier.VIEW, AccessTier.OPERATE, False),
        (AccessTier.VIEW, AccessTier.VIEW, True),
    ],
)
def test_satisfies_is_cumulative(held, required, expected):
    assert held.satisfies(required) is expected


# --- required_tier ---------------------------------------------------


def test_required_tier_reads_the_class_identity():
    from haywire.core.access import required_tier

    identity = type("Identity", (), {"requires": AccessTier.ADMIN})()
    cls = type("Thing", (), {"class_identity": identity})
    assert required_tier(cls) is AccessTier.ADMIN


def test_required_tier_defaults_to_edit_without_a_class_identity():
    """A bare test double is held to the default requirement, so it does not fail open."""
    from haywire.core.access import required_tier

    assert required_tier(type("Bare", (), {})) is AccessTier.EDIT


def test_required_tier_defaults_to_edit_when_identity_lacks_the_field():
    """Node/skin/widget identities have no requires field; asking does not raise."""
    from haywire.core.access import required_tier

    identity = type("Identity", (), {"label": "x"})()
    cls = type("Thing", (), {"class_identity": identity})
    assert required_tier(cls) is AccessTier.EDIT


def test_required_tier_handles_a_none_identity():
    from haywire.core.access import required_tier

    cls = type("Thing", (), {"class_identity": None})
    assert required_tier(cls) is AccessTier.EDIT


def test_required_tier_coerces_a_raw_wire_string():
    """@panel(requires="admin") is an untyped decorator kwarg — no dataclass
    validation stands between the author's string and this function."""
    from haywire.core.access import required_tier

    identity = type("Identity", (), {"requires": "admin"})()
    cls = type("Thing", (), {"class_identity": identity})
    result = required_tier(cls)
    assert result is AccessTier.ADMIN
    assert result.satisfies(AccessTier.VIEW)  # would raise if still a bare str


def test_required_tier_requires_edit_on_an_invalid_tier_string():
    """A typo in requires=... must not become an AttributeError at render time."""
    from haywire.core.access import required_tier

    identity = type("Identity", (), {"requires": "admni"})()
    cls = type("Thing", (), {"class_identity": identity})
    assert required_tier(cls) is AccessTier.EDIT


def test_coerce_requirement_keeps_a_tier():
    from haywire.core.access import coerce_requirement

    assert coerce_requirement(AccessTier.ADMIN) is AccessTier.ADMIN


def test_coerce_requirement_reads_a_tier_name():
    from haywire.core.access import coerce_requirement

    assert coerce_requirement("operate") is AccessTier.OPERATE


def test_coerce_requirement_rejects_an_unknown_name():
    from haywire.core.access import coerce_requirement

    with pytest.raises(ValueError, match="admni"):
        coerce_requirement("admni")


def test_coerce_requirement_rejects_a_level_mode():
    from haywire.core.access import LevelMode, coerce_requirement

    with pytest.raises(TypeError):
        coerce_requirement(LevelMode.EDIT)


def test_panel_decorator_rejects_a_level_mode():
    from haywire.barn.builtin.surfaces import AppSettings
    from haywire.core.access import LevelMode
    from haywire.ui.panel.base import BasePanel
    from haywire.ui.panel.decorator import panel

    with pytest.raises(TypeError):
        panel(label="X", surface=AppSettings, requires=LevelMode.EDIT)(type("P", (BasePanel,), {}))


def test_editor_decorator_rejects_a_level_mode():
    from haywire.core.access import LevelMode
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.decorator import editor

    with pytest.raises(TypeError):
        editor(label="X", requires=LevelMode.EDIT)(type("E", (BaseEditor,), {}))


def test_farmhand_decorator_rejects_a_level_mode():
    from haywire.core.access import LevelMode
    from haywire.core.farmhand import Farmhand, farmhand

    async def run(self, ctx) -> dict:
        return {}

    with pytest.raises(TypeError):
        farmhand(instructions="x", requires=LevelMode.EDIT)(type("F", (Farmhand,), {"run": run}))
