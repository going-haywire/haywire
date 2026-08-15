"""AccessTier — cumulative three-tier access vocabulary (ADR 0027)."""

import pytest

from haywire.core.access import AccessTier


def test_values_are_the_wire_strings():
    assert AccessTier.VIEW == "view"
    assert AccessTier.EDIT == "edit"
    assert AccessTier.ADMIN == "admin"


def test_constructed_from_string():
    assert AccessTier("edit") is AccessTier.EDIT


def test_unknown_string_raises():
    with pytest.raises(ValueError, match="superuser"):
        AccessTier("superuser")


def test_ranks_are_ordered():
    assert AccessTier.VIEW.rank < AccessTier.EDIT.rank < AccessTier.ADMIN.rank


@pytest.mark.parametrize(
    ("held", "required", "expected"),
    [
        (AccessTier.ADMIN, AccessTier.VIEW, True),
        (AccessTier.ADMIN, AccessTier.EDIT, True),
        (AccessTier.ADMIN, AccessTier.ADMIN, True),
        (AccessTier.EDIT, AccessTier.VIEW, True),
        (AccessTier.EDIT, AccessTier.EDIT, True),
        (AccessTier.EDIT, AccessTier.ADMIN, False),
        (AccessTier.VIEW, AccessTier.VIEW, True),
        (AccessTier.VIEW, AccessTier.EDIT, False),
        (AccessTier.VIEW, AccessTier.ADMIN, False),
    ],
)
def test_satisfies_is_cumulative(held, required, expected):
    assert held.satisfies(required) is expected


# --- required_access ---------------------------------------------------


def test_required_access_reads_the_class_identity():
    from haywire.core.access import required_access

    identity = type("Identity", (), {"access": AccessTier.ADMIN})()
    cls = type("Thing", (), {"class_identity": identity})
    assert required_access(cls) is AccessTier.ADMIN


def test_required_access_defaults_to_view_without_a_class_identity():
    """Mid-hot-reload classes and test doubles must not become invisible."""
    from haywire.core.access import required_access

    assert required_access(type("Bare", (), {})) is AccessTier.VIEW


def test_required_access_defaults_to_view_when_identity_lacks_the_field():
    """Node/skin/widget identities have no access field — they are never gated."""
    from haywire.core.access import required_access

    identity = type("Identity", (), {"label": "x"})()
    cls = type("Thing", (), {"class_identity": identity})
    assert required_access(cls) is AccessTier.VIEW


def test_required_access_handles_a_none_identity():
    from haywire.core.access import required_access

    cls = type("Thing", (), {"class_identity": None})
    assert required_access(cls) is AccessTier.VIEW


def test_required_access_coerces_a_raw_wire_string():
    """@panel(access="admin") is an untyped decorator kwarg — no dataclass
    validation stands between the author's string and this function."""
    from haywire.core.access import required_access

    identity = type("Identity", (), {"access": "admin"})()
    cls = type("Thing", (), {"class_identity": identity})
    result = required_access(cls)
    assert result is AccessTier.ADMIN
    assert result.satisfies(AccessTier.VIEW)  # would raise if still a bare str


def test_required_access_denies_to_view_on_an_invalid_tier_string():
    """A typo in access=... must not become an AttributeError at render time."""
    from haywire.core.access import required_access

    identity = type("Identity", (), {"access": "admni"})()
    cls = type("Thing", (), {"class_identity": identity})
    assert required_access(cls) is AccessTier.VIEW
