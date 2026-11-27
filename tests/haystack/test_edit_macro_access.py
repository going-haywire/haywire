"""Edit Macro… opens a document whose Save writes into a library, so it needs the admin tier."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from nicegui import ui

import haywire.core.di.config as di_config
import haywire.core.macro.source as macro_source
from haybale_haystack.panels.graph.menu import macro as macro_menu
from haybale_haystack.panels.graph.menu.macro import EditMacroMenuPanel
from haybale_haystack.states.haystack_state import HaystackState
from haywire.api.workbench import AccessTier

pytestmark = pytest.mark.unit


def _open(monkeypatch, tier: AccessTier, tmp_path: Path) -> tuple[MagicMock, MagicMock]:
    """Run Edit Macro… as a ``tier`` principal; returns ``(open_macro, notify)``."""
    path = tmp_path / "gain.hwm"
    path.write_text("")
    monkeypatch.setattr(di_config, "get_library_system", MagicMock())
    monkeypatch.setattr(macro_source, "macro_edit_refusal", lambda key, libraries: None)
    monkeypatch.setattr(macro_source, "macro_source_path", lambda key: path)
    notify = MagicMock()
    monkeypatch.setattr(ui, "notify", notify)
    haystack = MagicMock()
    ctx = MagicMock()
    ctx.can_access.side_effect = tier.satisfies
    ctx.app_data = {HaystackState: haystack}

    macro_menu._open_macro(ctx, "lib.gain")
    return haystack.open_macro, notify


def test_edit_macro_is_hidden_below_admin():
    assert EditMacroMenuPanel.class_identity.requires is AccessTier.ADMIN


def test_an_edit_principal_cannot_open_a_macro_to_edit(monkeypatch, tmp_path):
    open_macro, notify = _open(monkeypatch, AccessTier.EDIT, tmp_path)

    open_macro.assert_not_called()
    assert "admin" in notify.call_args.args[0]


def test_an_admin_opens_a_macro_to_edit(monkeypatch, tmp_path):
    open_macro, _ = _open(monkeypatch, AccessTier.ADMIN, tmp_path)

    open_macro.assert_called_once_with(tmp_path / "gain.hwm")
