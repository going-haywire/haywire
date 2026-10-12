"""The canvas lock rule: a lock caps the effective tier at operate."""

from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.access import allows
from haywire.core.access import AccessTier

pytestmark = pytest.mark.unit


def _ctx(tier: AccessTier) -> MagicMock:
    ctx = MagicMock()
    ctx.can_access.side_effect = lambda required: tier.satisfies(required)
    return ctx


def test_unlocked_follows_the_real_tier():
    assert allows(_ctx(AccessTier.EDIT).can_access, False, AccessTier.EDIT) is True
    assert allows(_ctx(AccessTier.VIEW).can_access, False, AccessTier.OPERATE) is False


def test_locked_caps_at_operate():
    admin = _ctx(AccessTier.ADMIN)
    assert allows(admin.can_access, True, AccessTier.EDIT) is False
    assert allows(admin.can_access, True, AccessTier.OPERATE) is True


def test_lock_never_raises():
    assert allows(_ctx(AccessTier.VIEW).can_access, True, AccessTier.OPERATE) is False
