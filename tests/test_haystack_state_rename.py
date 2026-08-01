# tests/test_haystack_state_rename.py

from unittest.mock import MagicMock, patch
import pytest


@pytest.mark.unit
def test_rename_updates_last_name_and_broadcasts(tmp_path):
    from haybale_haystack import persistence
    from haybale_haystack.state.haystack_state import HaystackState

    hs = HaystackState.__new__(HaystackState)
    hs._workspace_root = tmp_path
    settings = MagicMock()
    settings.last_haystack_name = "old"
    hs._haystack_settings = settings

    with (
        patch.object(persistence, "rename_haystack", return_value=True),
        patch.object(hs, "_broadcast_data_mutated") as bcast,
    ):
        ok = hs.rename_haystack("old", "new")

    assert ok is True
    assert settings.last_haystack_name == "new"  # pointer kept in lockstep
    bcast.assert_called_once()  # peer sessions notified
