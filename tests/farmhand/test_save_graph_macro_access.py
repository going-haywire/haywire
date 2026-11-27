"""haybale-haystack_save_graph writes a macro document (``.hwm``) only for an admin.

A macro document is a file in its library, and every write into a library needs
the admin tier; the tool's own tier is edit, so the tool checks inside.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from haybale_haystack.farmhands.graph_tools import HaystackSaveGraphTool
from haywire.core.access import AccessTier
from haywire.core.farmhand import FarmhandError

pytestmark = pytest.mark.unit


def _save(tier: AccessTier, path: Path | None, save_as: str | None = None) -> MagicMock:
    """Run the tool on an entry at ``path`` as a ``tier`` caller; returns the state's ``save_graph``."""
    entry = MagicMock(path=path, binding_id="b1")
    state = MagicMock()
    state.get_by_id.return_value = entry
    state.save_graph.return_value = True
    ctx = MagicMock()
    ctx.can_access.side_effect = tier.satisfies
    ctx.state.return_value = state
    ctx.workspace_root.return_value = Path("/workspace")
    tool = HaystackSaveGraphTool()
    try:
        asyncio.run(tool.run(ctx, binding_id="b1", save_as=save_as))
    except FarmhandError:
        pass
    return state.save_graph


def test_an_edit_caller_cannot_save_a_macro_document():
    save_graph = _save(AccessTier.EDIT, Path("/lib/macros/gain.hwm"))

    save_graph.assert_not_called()


def test_the_refusal_is_access_denied():
    entry = SimpleNamespace(path=Path("/lib/macros/gain.hwm"), binding_id="b1")
    ctx = MagicMock()
    ctx.can_access.side_effect = AccessTier.EDIT.satisfies
    ctx.state.return_value.get_by_id.return_value = entry

    with pytest.raises(FarmhandError) as raised:
        asyncio.run(HaystackSaveGraphTool().run(ctx, binding_id="b1"))
    assert raised.value.code == "access_denied"


def test_an_edit_caller_cannot_save_a_graph_as_a_macro_document(tmp_path):
    entry_path = tmp_path / "a.haywire"
    save_graph = _save(AccessTier.EDIT, entry_path, save_as=str(tmp_path / "gain.hwm"))

    save_graph.assert_not_called()


def test_an_admin_saves_a_macro_document():
    save_graph = _save(AccessTier.ADMIN, Path("/lib/macros/gain.hwm"))

    save_graph.assert_called_once()


def test_an_edit_caller_still_saves_a_graph():
    save_graph = _save(AccessTier.EDIT, Path("/workspace/graphs/a.haywire"))

    save_graph.assert_called_once()
