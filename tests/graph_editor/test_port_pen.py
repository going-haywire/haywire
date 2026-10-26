"""The port pen on the Ports panel, checked against the lock.

The pen needs level mode edit, which a locked level refuses even to an admin. Port
reorder and edge propagation are in ``test_structure_edits.py``; card and Ports
panel widgets write through the level's route, see ``test_level_routes.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import Client, ui

from haybale_graph_editor.access import level_mode
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import AccessTier, LevelMode
from haywire.core.graph.edit_route import EditRoute


def _noop_page() -> None:  # registration target for a headless Client
    pass


# =============================================================================
# Port edit dialog (the Ports panel's pen)
# =============================================================================


def _resolved_port() -> Any:
    from haywire.core.types.enums import PortOrigin

    return SimpleNamespace(
        id="p1", label="Gain", description="", widget_key=None, origin=PortOrigin.RESOLVED
    )


def _pen_ctx(tier: AccessTier, locked: bool, editor: Any) -> tuple[Any, SimpleNamespace]:
    """Return a session context whose route writes to ``editor``, and the level it reads ``mode`` off.

    The route reads ``level.mode`` at each call, so a test can lock the level mid-dialog.
    """
    level = SimpleNamespace(mode=level_mode(tier.satisfies, locked))
    edit = SimpleNamespace(
        active_node=MagicMock(), active_route=EditRoute(lambda: editor, lambda: level.mode)
    )
    ctx = SimpleNamespace(can_access=tier.satisfies, data={EditState: edit}, session=MagicMock())
    return ctx, level


def _open_dialog(ctx: Any) -> Client:
    """Open the pen's edit dialog for ``ctx``; return its client."""
    from haybale_graph_editor.panels.properties.introspect import node_ports

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        node_ports.NodePortsPanel()._open_editor(_resolved_port(), "n1", ctx)
    return client


def _apply_button(client: Client) -> Any:
    return next(
        (el for el in client.elements.values() if isinstance(el, ui.button) and el.text == "Apply"), None
    )


def _apply_relabelled(client: Client, label: str) -> None:
    """Type ``label`` into the open dialog's Label field and press Apply."""
    with client:
        label_input = next(
            el
            for el in client.elements.values()
            if isinstance(el, ui.input) and el.props.get("label") == "Label"
        )
        label_input.value = label
        _fire_click(_apply_button(client))


def _fire_click(element: Any) -> None:
    listener_id = next(iter(element._event_listeners))
    element._handle_event({"listener_id": listener_id, "args": {}})


def _metadata_editor() -> Any:
    editor = MagicMock()
    editor.set_port_metadata.return_value = (True, None)
    return editor


@pytest.mark.unit
@pytest.mark.parametrize(
    ("tier", "locked"), [(AccessTier.ADMIN, True), (AccessTier.VIEW, False)], ids=["locked-admin", "view"]
)
def test_the_port_pen_refuses_below_edit(tier: AccessTier, locked: bool):
    editor = _metadata_editor()
    ctx, _level = _pen_ctx(tier, locked, editor)
    client = _open_dialog(ctx)
    if _apply_button(client) is not None:
        _apply_relabelled(client, "Level")

    editor.set_port_metadata.assert_not_called()


@pytest.mark.unit
def test_an_open_port_dialog_refuses_once_the_level_is_locked():
    editor = _metadata_editor()
    ctx, level = _pen_ctx(AccessTier.ADMIN, False, editor)
    client = _open_dialog(ctx)

    level.mode = LevelMode.OPERATE
    _apply_relabelled(client, "Level")

    editor.set_port_metadata.assert_not_called()


@pytest.mark.unit
def test_the_port_pen_applies_for_edit():
    editor = _metadata_editor()
    ctx, _level = _pen_ctx(AccessTier.EDIT, False, editor)
    client = _open_dialog(ctx)
    _apply_relabelled(client, "Level")

    editor.set_port_metadata.assert_called_once_with("n1", "p1", label="Level")
