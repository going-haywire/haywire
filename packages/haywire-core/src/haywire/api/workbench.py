"""The workbench API: what a library imports to build panels, editors and Farmhand tools.

Provisional (ADR 0085): a name in ``__all__`` may change in any minor release,
listed in the release notes, never in a patch release. Nodes, types, widgets
and settings are in ``haywire.api``.

    from haywire.api.workbench import BasePanel, PanelLayout, SessionContext, hui, panel

Imports and ``__all__`` only; the one function serves deprecated names. ``hui`` is the design system,
``haywire.ui.elements``.
"""

# haywire.api comes first: it fixes the import order of the core packages.
import haywire.api  # noqa: F401

from haywire.barn.builtin.surfaces import AppSettings, Barns, CanvasSettings, ExecutionInspector
from haywire.core.access import AccessTier, LevelMode, resolve_tier
from haywire.core.di.context import (
    activity_tracker,
    get_catalog_registry,
    get_library_state_container,
)
from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    FarmhandError,
    FarmhandRegistry,
    ToolAnnotations,
    farmhand,
    truncation_note,
)
from haywire.core.graph.base import BaseGraph
from haywire.core.library.deprecated_names import DeprecatedName, serve_deprecated
from haywire.core.session import SessionContext, react_on, redraw_on
from haywire.core.session.handlers import reveal_on
from haywire.core.signals import (
    ActiveGraphMoved,
    BroadcastClose,
    Close,
    Copy,
    Cut,
    Delete,
    Duplicate,
    EditorCommand,
    GraphDataMutated,
    Paste,
    Redo,
    Reveal,
    RevealComponentDocs,
    RevealComponentSource,
    RevealSignal,
    RevealSource,
    SelectAll,
    SelectionMoved,
    Signal,
    Undo,
    signal_field,
)
from haywire.core.state import AppState, LibraryState, LibraryStateRegistry, SessionState, state
from haywire.ui import elements as hui
from haywire.ui.access_stamp import stamp_requires
from haywire.ui.editor import BaseEditor, EditorTypeRegistry, OpenBehavior, SlotName, editor
from haywire.ui.editor.wrapper import EditorWrapper
from haywire.ui.hover_tip import set_hover_tip
from haywire.ui.modals import confirm_modal
from haywire.ui.panel import BasePanel, PanelLayout, PanelRegistry, panel
from haywire.ui.panel.render_utils import render_schema
from haywire.ui.surface import Surface

#: Names that left ``__all__`` and are still served, with a notice, until the
#: release each entry names. ``tests/api/names.py`` lists them too.
_DEPRECATED: dict[str, DeprecatedName] = {}


def __getattr__(name: str):
    entry = _DEPRECATED.get(name)
    if entry is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return serve_deprecated(__name__, name, entry)


__all__ = [
    # Registries a library's register_components() names
    "EditorTypeRegistry",
    "FarmhandRegistry",
    "LibraryStateRegistry",
    "PanelRegistry",
    # Panel
    "BasePanel",
    "PanelLayout",
    "panel",
    "render_schema",
    # Surfaces a panel appears on
    "AppSettings",
    "Barns",
    "CanvasSettings",
    "ExecutionInspector",
    "Surface",
    # Editor
    "BaseEditor",
    "EditorWrapper",
    "OpenBehavior",
    "SlotName",
    "editor",
    # Session
    "BaseGraph",
    "SessionContext",
    # Signals
    "ActiveGraphMoved",
    "BroadcastClose",
    "Close",
    "EditorCommand",
    "GraphDataMutated",
    "Reveal",
    "RevealComponentDocs",
    "RevealComponentSource",
    "RevealSignal",
    "RevealSource",
    "SelectionMoved",
    "Signal",
    "react_on",
    "redraw_on",
    "reveal_on",
    "signal_field",
    # Keyboard commands an editor answers
    "Copy",
    "Cut",
    "Delete",
    "Duplicate",
    "Paste",
    "Redo",
    "SelectAll",
    "Undo",
    # State
    "AppState",
    "LibraryState",
    "SessionState",
    "state",
    # Access
    "AccessTier",
    "LevelMode",
    "resolve_tier",
    "stamp_requires",
    # Farmhand
    "Farmhand",
    "FarmhandContext",
    "FarmhandError",
    "ToolAnnotations",
    "farmhand",
    "truncation_note",
    # Design system and modals
    "confirm_modal",
    "hui",
    "set_hover_tip",
    # Ambient accessors
    "activity_tracker",
    "get_catalog_registry",
    "get_library_state_container",
]
