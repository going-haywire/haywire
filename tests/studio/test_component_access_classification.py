"""Every shipped editor and panel declares its access deliberately: the default is edit."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from haywire.core.access import AccessTier, access_resolver, required_access, set_access_resolver
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
    "ShortcutsEditor",
}
ADMIN_EDITORS = {"RosterEditor"}

#: Panels a principal below edit reaches: the account menu and the file browser's viewer entry.
VIEW_PANELS = {"DeveloperModePanel", "LogoutPanel", "OpenActivityPanel", "OpenInFileViewerMenuPanel"}
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
    "PropertiesEditor",
    "ShareEditor",
}
EDIT_PANELS = {
    "ActivitySettingsPanel",
    "AddToStageMenuPanel",
    "AppearanceToolbarPanel",
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
    "DissolveRerouteMenuPanel",
    "EdgeAdapterChainPanel",
    "EdgeAdapterEditMenuPanel",
    "EdgeDefaultSettingsPanel",
    "EdgeErrorsMenuPanel",
    "EdgeErrorsPanel",
    "EdgePathPanel",
    "EdgePropagationMenuPanel",
    "EdgePropagationPanel",
    "EdgeStatsPanel",
    "EdgeStyleBodyPanel",
    "EdgeStyleMenuPanel",
    "EdgeStylePanel",
    "EdgeStyleToolbarPanel",
    "EdgeWarningsMenuPanel",
    "EdgeWarningsPanel",
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
    "GraphInfoPanel",
    "GraphMetadataPanel",
    "GraphMorePanel",
    "GraphRunSettingsPanel",
    "GraphSettingsPanel",
    "GroupMenuPanel",
    "InsertRerouteMenuPanel",
    "LockToolbarPanel",
    "MinimapSettingsPanel",
    "ModifiedInstanceMenuPanel",
    "NodeAppearancePanel",
    "NodeErrorsPanel",
    "NodeErrorsSelectionMenuPanel",
    "NodeInfoPanel",
    "NodePortsPanel",
    "NodePropertiesPanel",
    "NodeSettingsPanel",
    "NodeSkinDefaultPanel",
    "NodeSkinMenuPanel",
    "NodeSkinSettingsPanel",
    "NodeSourceMenuPanel",
    "NodeStatusPanel",
    "NodeThemeMenuPanel",
    "OpenInCodeEditorMenuPanel",
    "OpenInHaystackMenuPanel",
    "PastePanel",
    "PinEditMenuPanel",
    "PinShowWidgetMenuPanel",
    "PortShowWidgetStrategyPanel",
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
                problems.append(
                    f"{name}: not classified in this test (declares {required_access(cls).value})"
                )
            elif required_access(cls) is not expected:
                problems.append(f"{name}: {required_access(cls).value}, expected {expected.value}")
    assert not problems, "\n".join(problems)


@pytest.mark.integration
def test_the_tables_name_only_registered_components(editors, panels) -> None:
    assert (VIEW_EDITORS | EDIT_EDITORS | ADMIN_EDITORS) - set(editors) == set()
    assert (VIEW_PANELS | EDIT_PANELS | ADMIN_PANELS) - set(panels) == set()


@pytest.mark.integration
def test_the_file_menu_offers_only_the_viewer_below_edit(panels) -> None:
    assert required_access(panels["OpenInFileViewerMenuPanel"]) is AccessTier.VIEW
    assert required_access(panels["OpenInCodeEditorMenuPanel"]) is AccessTier.EDIT
    assert required_access(panels["OpenInHaystackMenuPanel"]) is AccessTier.EDIT


@pytest.fixture
def restore_resolver() -> Iterator[None]:
    previous = access_resolver()
    yield
    set_access_resolver(previous)


@pytest.mark.integration
@pytest.mark.parametrize(("tier", "sees_properties"), [(AccessTier.VIEW, False), (AccessTier.EDIT, True)])
def test_a_view_principal_is_not_shown_an_edit_editor(
    editors, restore_resolver, tier: AccessTier, sees_properties: bool
) -> None:
    """The expression ``Slot._editor_accessible`` evaluates for each binding."""
    set_access_resolver(lambda _name: tier)
    context = SessionContext(session_id="s1", app=MagicMock())
    context.principal = "someone"

    assert context.can_access(required_access(editors["PropertiesEditor"])) is sees_properties
    assert context.can_access(required_access(editors["GraphEditor"])) is True
