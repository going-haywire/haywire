# haywire/ui/panel/scope.py
"""
ScopeDescriptor — metadata for a named scope tab in a panel-consuming editor.

A scope is a top-level navigation tab (e.g. the left icon strip in the
PropertiesEditor). Scopes are registered into PanelRegistry via
register_scope(editor_id, descriptor) — typically called from
BaseLibrary.register_components() before the panels folder is scanned.

Libraries can introduce new scopes by registering a ScopeDescriptor before
registering the panels that reference that scope_id.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@dataclass
class ScopeDescriptor:
    """
    Metadata for a single scope tab in a panel-consuming editor.

    Attributes:
        scope_id:  Short unique ID referenced by @panel(scope=...).
        label:     Human-readable tab label (shown as tooltip on the icon).
        icon:      Material Design icon name for the toolbar button.
        order:     Sort position in the toolbar (lower = higher up). Default 100.
        poll:      Callable(context) -> bool — True if this scope is available
                   given the current session state.  Defaults to always-True.
    """

    scope_id: str
    label: str
    icon: str
    order: int = 100
    poll: Callable[[SessionContext], bool] = field(default_factory=lambda: (lambda ctx: True))
