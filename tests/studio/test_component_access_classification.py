"""Every shipped editor and panel declares its access deliberately: the default is edit."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.surfaces.edge import EdgeInspector
from haybale_graph_editor.surfaces.graph import GraphInspector
from haybale_graph_editor.surfaces.node import NodeInspector, SettingsInspector
from haybale_graph_editor.surfaces.ports import PortInspector
from haywire.core.access import AccessTier, access_resolver, required_tier, set_access_resolver
from haywire.core.session.context import SessionContext

#: Editors a principal below edit may open: each reads, or gates its own actions.
VIEW_EDITORS = {
    "ActivityEditor",
    "ComponentDocsEditor",
    "ErrorsEditor",
    "FileViewerEditor",
    "GraphEditor",
    "HaystackEditor",
    "LazyFileBrowserEditor",
    "LogEditor",
    "PropertiesEditor",
    "ShortcutsEditor",
}
ADMIN_EDITORS = {"RosterEditor"}

#: Panels a principal below edit reaches: the account menu, the file browser's viewer entry, and
#: the Properties editor's inspector tabs, read-only below edit (ADR 0060).
INSPECTOR_PANELS = {
    "EdgeAdapterChainPanel",
    "EdgeErrorsPanel",
    "EdgePathPanel",
    "EdgePropagationPanel",
    "EdgeStatsPanel",
    "EdgeStylePanel",
    "EdgeWarningsPanel",
    "GraphInfoPanel",
    "GraphMetadataPanel",
    "GraphSettingsPanel",
    "NodeErrorsPanel",
    "NodeInfoPanel",
    "NodePortsPanel",
    "NodePropertiesPanel",
    "NodeSettingsPanel",
    "NodeStatusPanel",
}
VIEW_PANELS = {
    "DeveloperModePanel",
    "LogoutPanel",
    "OpenActivityPanel",
    "OpenInFileViewerMenuPanel",
} | INSPECTOR_PANELS
ADMIN_PANELS = {
    "CloneToLibraryMenuPanel",
    "NewNodeToolbarPanel",
    "OpenRosterPanel",
    "RotateSecretPanel",
    "SecurityPanel",
}


#: Editors and panels at the edit default, listed so that a new one has to be looked at.
EDIT_EDITORS = {
    "CodeEditor",
    "ComponentSourceEditor",
    "LibraryBrowserEditor",
    "LibraryOverviewEditor",
    "ShareEditor",
}
EDIT_PANELS = {
    "ActivitySettingsPanel",
    "AddToStageMenuPanel",
    "AppearanceToolbarPanel",
    "ArrangeSelectionMenuPanel",
    "BringForwardMenuPanel",
    "BringToFrontMenuPanel",
    "CanvasSettingsPanel",
    "ClearDetailOverridesMenuPanel",
    "ClearSettingMenuPanel",
    "CollapseSelectionMenuPanel",
    "CollapseToGroupMenuPanel",
    "CollapseToolbarPanel",
    "CopySelectionMenuPanel",
    "CreateNodeMenuPanel",
    "DebugOverlaySettingsPanel",
    "DebugSettingsPanel",
    "DeleteEdgeMenuPanel",
    "DeleteSelectionMenuPanel",
    "DetachSettingMenuPanel",
    "DetailRankMenuPanel",
    "DetailSelectionMenuPanel",
    "DevelopSelectionMenuPanel",
    "DissolveRerouteMenuPanel",
    "EdgeAdapterEditMenuPanel",
    "EdgeDefaultSettingsPanel",
    "EdgeErrorsMenuPanel",
    "EdgePropagationMenuPanel",
    "EdgeStyleBodyPanel",
    "EdgeStyleMenuPanel",
    "EdgeStyleToolbarPanel",
    "EdgeWarningsMenuPanel",
    "EditEdgeMenuPanel",
    "EditInstanceMenuPanel",
    "EditMacroMenuPanel",
    "EditSelectionMenuPanel",
    "EditingSettingsPanel",
    "EditorZoomPanSettingsPanel",
    "EnterMenuPanel",
    "ExecutionSettingsPanel",
    "FocusGraphPanel",
    "GraphContextPanel",
    "GraphMorePanel",
    "GraphRunSettingsPanel",
    "GroupMenuPanel",
    "InsertRerouteMenuPanel",
    "LockToolbarPanel",
    "MacroSelectionMenuPanel",
    "MinimapSettingsPanel",
    "ModifiedInstanceMenuPanel",
    "NodeAppearancePanel",
    "NodeErrorsSelectionMenuPanel",
    "NodeSkinDefaultPanel",
    "NodeSkinMenuPanel",
    "NodeSkinSettingsPanel",
    "NodeSourceMenuPanel",
    "NodeThemeMenuPanel",
    "OpenInCodeEditorMenuPanel",
    "OpenInHaystackMenuPanel",
    "PastePanel",
    "PinEditMenuPanel",
    "PinShowWidgetMenuPanel",
    "PortShowWidgetStrategyPanel",
    "SaveNewMacroMenuPanel",
    "PortTypeMenuPanel",
    "PortWidgetMenuPanel",
    "RebuildSelectionMenuPanel",
    "ReconnectEdgeMenuPanel",
    "RedrawSelectionMenuPanel",
    "RemoveFromStageMenuPanel",
    "ResetNodeCardsMenuPanel",
    "ResetSelectionMenuPanel",
    "ResetSettingMenuPanel",
    "RevalidateSelectionMenuPanel",
    "SelectionOverflowPanel",
    "SendBackwardMenuPanel",
    "SendToBackMenuPanel",
    "TestCopyNodeMenuPanel",
    "TestCopySelectionMenuPanel",
    "TestCreateNodeMenuPanel",
    "TestDeleteEdgeMenuPanel",
    "TestDeleteNodeMenuPanel",
    "TestEdgeErrorsMenuPanel",
    "TestEdgePathMenuPanel",
    "TestEdgeWarningsMenuPanel",
    "TestInspectEdgeMenuPanel",
    "TestPasteSelectionMenuPanel",
    "TestRedrawNodeMenuPanel",
    "TestResetNodeMenuPanel",
    "TestRevalidateNodeMenuPanel",
    "TestSessionStateMenuPanel",
    "ThemeSettingsPanel",
    "UpdateMacroMenuPanel",
}


def _expected(name: str, view: set[str], edit: set[str], admin: set[str]) -> AccessTier | None:
    """The tier ``name`` is listed under, or ``None`` if it is in no table."""
    for table, tier in ((view, AccessTier.VIEW), (edit, AccessTier.EDIT), (admin, AccessTier.ADMIN)):
        if name in table:
            return tier
    return None


def _classes(library_system, registry_cls) -> dict[str, type]:
    registry = library_system.injector.get(registry_cls)
    classes = (registry.get(key) for key in registry.list_names())
    return {cls.__name__: cls for cls in classes if cls is not None}


@pytest.fixture
def editors(library_system) -> dict[str, type]:
    from haywire.ui.editor.registry import EditorTypeRegistry

    return _classes(library_system, EditorTypeRegistry)


@pytest.fixture
def panels(library_system) -> dict[str, type]:
    from haywire.ui.panel.registry import PanelRegistry

    return _classes(library_system, PanelRegistry)


@pytest.mark.integration
def test_every_editor_and_panel_is_classified(editors, panels) -> None:
    """Each registered editor and panel is listed once, at the tier it declares."""
    problems = []
    for found, view, edit, admin in (
        (editors, VIEW_EDITORS, EDIT_EDITORS, ADMIN_EDITORS),
        (panels, VIEW_PANELS, EDIT_PANELS, ADMIN_PANELS),
    ):
        for name, cls in sorted(found.items()):
            expected = _expected(name, view, edit, admin)
            if expected is None:
                problems.append(f"{name}: not classified in this test (declares {required_tier(cls).value})")
            elif required_tier(cls) is not expected:
                problems.append(f"{name}: {required_tier(cls).value}, expected {expected.value}")
    assert not problems, "\n".join(problems)


@pytest.mark.integration
def test_the_tables_name_only_registered_components(editors, panels) -> None:
    assert (VIEW_EDITORS | EDIT_EDITORS | ADMIN_EDITORS) - set(editors) == set()
    assert (VIEW_PANELS | EDIT_PANELS | ADMIN_PANELS) - set(panels) == set()


@pytest.mark.integration
def test_the_file_menu_offers_only_the_viewer_below_edit(panels) -> None:
    assert required_tier(panels["OpenInFileViewerMenuPanel"]) is AccessTier.VIEW
    assert required_tier(panels["OpenInCodeEditorMenuPanel"]) is AccessTier.EDIT
    assert required_tier(panels["OpenInHaystackMenuPanel"]) is AccessTier.EDIT


@pytest.fixture
def restore_resolver() -> Iterator[None]:
    previous = access_resolver()
    yield
    set_access_resolver(previous)


@pytest.mark.integration
@pytest.mark.parametrize(("tier", "sees_share"), [(AccessTier.VIEW, False), (AccessTier.EDIT, True)])
def test_a_view_principal_is_not_shown_an_edit_editor(
    editors, restore_resolver, tier: AccessTier, sees_share: bool
) -> None:
    """The expression ``Slot._editor_accessible`` evaluates for each binding."""
    set_access_resolver(lambda _name: tier)
    context = SessionContext(session_id="s1", app=MagicMock())
    context.principal = "someone"

    assert context.can_access(required_tier(editors["ShareEditor"])) is sees_share
    assert context.can_access(required_tier(editors["PropertiesEditor"])) is True
    assert context.can_access(required_tier(editors["GraphEditor"])) is True


@pytest.mark.integration
def test_a_view_principal_sees_the_inspector_tabs_but_not_the_app_settings(
    library_system, restore_resolver
) -> None:
    """Every Properties tab's panel reaches a viewer only if it is an inspector panel."""
    from haywire.ui.panel.registry import PanelRegistry

    set_access_resolver(lambda _name: AccessTier.VIEW)
    context = SessionContext(session_id="s1", app=MagicMock())
    context.principal = "someone"
    registry = library_system.injector.get(PanelRegistry)
    tabs = [s for s in registry.get_root_surfaces() if s.presentation is not None]

    shown: set[str] = set()
    hidden: set[str] = set()
    for surface in tabs:
        for cls in registry.get_panels(surface):
            (shown if context.can_access(required_tier(cls)) else hidden).add(cls.__name__)

    assert shown == INSPECTOR_PANELS
    # The app-settings tabs hold unstamped global settings: none of their panels reach a viewer.
    assert {"ExecutionSettingsPanel", "CanvasSettingsPanel", "DebugSettingsPanel"} <= hidden


def _properties_editor(library_system, tier: AccessTier):
    """A PropertiesEditor and a context whose principal holds ``tier``, over the real panels."""
    from typing import cast

    from haybale_studio.editors.properties_editor import PropertiesEditor
    from haywire.ui.editor.wrapper import EditorWrapper
    from haywire.ui.panel.registry import PanelRegistry

    set_access_resolver(lambda _name: tier)
    app = MagicMock()
    app.library_service.get_panel_registry.return_value = library_system.injector.get(PanelRegistry)
    context = SessionContext(session_id="s1", app=app)
    context.principal = "someone"
    return PropertiesEditor(cast(EditorWrapper, object())), context


APP_SETTINGS_TABS = {"app", "execution", "canvas", "debug"}

#: The graph editor's inspector surfaces (Properties tabs), taken from the classes so ids cannot drift.
INSPECTOR_SURFACE_IDS = {
    cls.id for cls in (GraphInspector, NodeInspector, SettingsInspector, PortInspector, EdgeInspector)
}


@pytest.mark.integration
def test_a_view_principal_is_not_offered_the_app_settings_tabs(library_system, restore_resolver) -> None:
    """A tab none of whose panels reach the principal is neither listed nor the default."""
    editor, context = _properties_editor(library_system, AccessTier.VIEW)

    offered = {surface.id for surface in editor._offered_surfaces(context)}
    assert offered
    assert offered.isdisjoint(APP_SETTINGS_TABS)

    editor._resolve_active_surface(context)
    assert editor._active_surface_id in offered
    # The default is an inspector tab, never an app-settings one.
    assert editor._active_surface_id in INSPECTOR_SURFACE_IDS


@pytest.mark.integration
def test_an_edit_principal_is_offered_the_app_settings_tabs(library_system, restore_resolver) -> None:
    editor, context = _properties_editor(library_system, AccessTier.EDIT)

    assert APP_SETTINGS_TABS <= {surface.id for surface in editor._offered_surfaces(context)}
    editor._resolve_active_surface(context)
    assert editor._active_surface_id == "app"


@pytest.mark.integration
def test_an_active_tab_that_stops_being_offered_falls_back_to_one_that_is(
    library_system, restore_resolver
) -> None:
    editor, context = _properties_editor(library_system, AccessTier.EDIT)
    editor._resolve_active_surface(context)
    assert editor._active_surface_id == "app"

    set_access_resolver(lambda _name: AccessTier.VIEW)
    editor._resolve_active_surface(context)
    assert editor._active_surface_id not in APP_SETTINGS_TABS
    assert editor._active_surface_id in {surface.id for surface in editor._offered_surfaces(context)}
