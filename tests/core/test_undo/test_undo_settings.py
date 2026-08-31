"""UndoSettings feeds UndoConfig's max_actions default."""

import pytest

pytestmark = pytest.mark.unit


def test_max_actions_default():
    from haywire.core.undo.settings import UndoSettings

    assert UndoSettings().max_actions == 100


def test_undo_config_defaults_to_the_setting():
    """A bare UndoConfig() takes its limit from UndoSettings, not a literal."""
    from haywire.core.undo.config import UndoConfig
    from haywire.core.undo.settings import UndoSettings

    assert UndoConfig().max_actions == UndoSettings().max_actions


def test_explicit_max_actions_still_wins():
    """Named configs pin their own limit; the setting must not override them."""
    from haywire.core.undo.config import UndoConfig

    assert UndoConfig(max_actions=25).max_actions == 25
